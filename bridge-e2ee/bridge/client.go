package bridge

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"math/rand"
	"os"
	"sync"

	"github.com/google/uuid"
	"github.com/rs/zerolog"
	"go.mau.fi/util/exhttp"
	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/proto/waAdv"
	"go.mau.fi/whatsmeow/store"
	waTypes "go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/util/keys"

	"go.mau.fi/mautrix-meta/pkg/messagix"
	"go.mau.fi/mautrix-meta/pkg/messagix/cookies"
	"go.mau.fi/mautrix-meta/pkg/messagix/table"
	"go.mau.fi/mautrix-meta/pkg/messagix/types"
)

// Client wraps the messagix client and e2ee client
type Client struct {
	ID          uint64
	Messagix    *messagix.Client
	E2EE        *whatsmeow.Client
	DeviceStore *DeviceStore
	Logger      zerolog.Logger
	FBID        int64
	Platform    types.Platform

	eventChan           chan *Event
	ctx                 context.Context
	cancel              context.CancelFunc
	mu                  sync.RWMutex
	recentUnreactions   map[string]int64 // key: messageId+actorId, value: timestamp
	recentUnreactionsMu sync.RWMutex
}

// ClientConfig for creating a new client
type ClientConfig struct {
	Cookies        map[string]string `json:"cookies"`
	Platform       string            `json:"platform"` // "facebook", "messenger", "instagram"
	DevicePath     string            `json:"devicePath"`
	DeviceData     string            `json:"deviceData,omitempty"`     // JSON string of device data (optional, takes priority over DevicePath)
	E2EEMemoryOnly bool              `json:"e2eeMemoryOnly,omitempty"` // If true, E2EE state is stored in memory only (no file, no events)
	LogLevel       string            `json:"logLevel"`
}

// NewClient creates a new messagix client
func NewClient(cfg *ClientConfig) (*Client, error) {
	// Parse platform
	var platform types.Platform
	switch cfg.Platform {
	case "facebook":
		platform = types.Facebook
	case "messenger":
		platform = types.Messenger
	case "instagram":
		platform = types.Instagram
	default:
		platform = types.Facebook
	}

	// Create cookies
	cks := &cookies.Cookies{Platform: platform}
	valMap := make(map[cookies.MetaCookieName]string)
	for k, v := range cfg.Cookies {
		valMap[cookies.MetaCookieName(k)] = v
	}
	cks.UpdateValues(valMap)

	// Setup logger
	logLevel := zerolog.InfoLevel
	switch cfg.LogLevel {
	case "debug":
		logLevel = zerolog.DebugLevel
	case "trace":
		logLevel = zerolog.TraceLevel
	case "warn":
		logLevel = zerolog.WarnLevel
	case "error":
		logLevel = zerolog.ErrorLevel
	case "none":
		logLevel = zerolog.Disabled
	}
	zerolog.SetGlobalLevel(logLevel)
	logger := zerolog.New(zerolog.ConsoleWriter{Out: os.Stderr}).With().Timestamp().Logger()

	// Create messagix client
	msgClient := messagix.NewClient(cks, logger, &messagix.Config{
		ClientSettings: exhttp.ClientSettings{},
	})

	// Create device store
	var deviceStore *DeviceStore
	var err error
	if cfg.E2EEMemoryOnly {
		// Memory only mode - no persistence
		deviceStore, err = NewDeviceStoreMemoryOnly()
	} else if cfg.DeviceData != "" {
		// Use provided device data (no file I/O)
		deviceStore, err = NewDeviceStoreFromData(cfg.DeviceData)
	} else {
		// Use file path
		devicePath := cfg.DevicePath
		if devicePath == "" {
			devicePath = "e2ee_device.json"
		}
		deviceStore, err = NewDeviceStore(devicePath)
	}
	if err != nil {
		return nil, err
	}

	// Set device on client
	msgClient.SetDevice(deviceStore.Device)

	ctx, cancel := context.WithCancel(context.Background())

	client := &Client{
		Messagix:          msgClient,
		DeviceStore:       deviceStore,
		Logger:            logger,
		Platform:          platform,
		eventChan:         make(chan *Event, 100),
		ctx:               ctx,
		cancel:            cancel,
		recentUnreactions: make(map[string]int64),
	}

	// Set callback for device data changes (only when using deviceData mode)
	if cfg.DeviceData != "" {
		deviceStore.onDataChanged = func(data string) {
			client.emitEvent(EventDeviceDataChanged, map[string]interface{}{
				"deviceData": data,
			})
		}
	}

	// Set event handler
	msgClient.SetEventHandler(client.handleEvent)

	return client, nil
}

// Connect connects to Messenger
func (c *Client) Connect() (*UserInfo, *InitialData, error) {
	// Load messages page
	currentUser, initialTable, err := c.Messagix.LoadMessagesPage(c.ctx)
	if err != nil {
		return nil, nil, err
	}

	// Extract user info
	userInfo := &UserInfo{
		Name:     currentUser.GetName(),
		Username: currentUser.GetUsername(),
		ID:       currentUser.GetFBID(),
	}
	c.FBID = userInfo.ID

	// Connect socket
	if err := c.Messagix.Connect(c.ctx); err != nil {
		return nil, nil, err
	}

	// Extract initial data
	initialData := &InitialData{}
	if initialTable != nil {
		for _, t := range initialTable.LSDeleteThenInsertThread {
			initialData.Threads = append(initialData.Threads, convertThread(t))
		}
		for _, m := range initialTable.LSUpsertMessage {
			initialData.Messages = append(initialData.Messages, convertMessage(m))
		}
	}

	return userInfo, initialData, nil
}

// ConnectE2EE sets up and connects the E2EE client
func (c *Client) ConnectE2EE() error {
	if c.E2EE != nil && c.E2EE.IsConnected() {
		return nil
	}

	// Prepare E2EE client
	e2eeClient, err := c.Messagix.PrepareE2EEClient()
	if err != nil {
		return err
	}
	c.E2EE = e2eeClient

	// Register E2EE
	if err := c.Messagix.RegisterE2EE(c.ctx, c.FBID); err != nil {
		return err
	}
	c.DeviceStore.Save()

	// Connect E2EE
	if err := c.E2EE.Connect(); err != nil {
		return err
	}

	// Add E2EE event handler
	c.E2EE.AddEventHandler(c.handleE2EEEvent)

	return nil
}

// Disconnect disconnects from Messenger
func (c *Client) Disconnect() {
	c.cancel()
	if c.E2EE != nil && c.E2EE.IsConnected() {
		c.E2EE.Disconnect()
	}
	c.Messagix.Disconnect()
	close(c.eventChan)
}

// IsConnected returns true if connected
func (c *Client) IsConnected() bool {
	return c.Messagix != nil
}

// IsE2EEConnected returns true if E2EE is connected
func (c *Client) IsE2EEConnected() bool {
	return c.E2EE != nil && c.E2EE.IsConnected()
}

// Events returns the event channel
func (c *Client) Events() <-chan *Event {
	return c.eventChan
}

// DeviceStore manages the E2EE device persistently
type DeviceStore struct {
	Device        *store.Device
	path          string
	mu            sync.RWMutex
	identities    map[string][32]byte
	sessions      map[string][]byte
	preKeys       map[uint32]*keys.PreKey
	senderKeys    map[string][]byte
	nextPreKeyID  uint32
	onDataChanged func(string) // callback when data changes (for deviceData mode)
}

// DeviceJSON for JSON serialization
type DeviceJSON struct {
	NoiseKeyPriv     string            `json:"noise_key_priv"`
	IdentityKeyPriv  string            `json:"identity_key_priv"`
	SignedPreKeyPriv string            `json:"signed_pre_key_priv"`
	SignedPreKeyID   uint32            `json:"signed_pre_key_id"`
	SignedPreKeySig  string            `json:"signed_pre_key_sig"`
	RegistrationID   uint32            `json:"registration_id"`
	AdvSecretKey     string            `json:"adv_secret_key"`
	FacebookUUID     string            `json:"facebook_uuid"`
	JIDUser          string            `json:"jid_user,omitempty"`
	JIDDevice        uint16            `json:"jid_device,omitempty"`
	Identities       map[string]string `json:"identities,omitempty"`
	Sessions         map[string]string `json:"sessions,omitempty"`
	PreKeys          map[string]string `json:"pre_keys,omitempty"`
	SenderKeys       map[string]string `json:"sender_keys,omitempty"`
	NextPreKeyID     uint32            `json:"next_pre_key_id"`
}

// NewDeviceStore creates or loads a device store
func NewDeviceStore(path string) (*DeviceStore, error) {
	ds := &DeviceStore{
		path:         path,
		identities:   make(map[string][32]byte),
		sessions:     make(map[string][]byte),
		preKeys:      make(map[uint32]*keys.PreKey),
		senderKeys:   make(map[string][]byte),
		nextPreKeyID: 1,
	}

	if data, err := os.ReadFile(path); err == nil {
		var deviceJSON DeviceJSON
		if err := json.Unmarshal(data, &deviceJSON); err != nil {
			return nil, err
		}

		noisePriv, _ := base64.StdEncoding.DecodeString(deviceJSON.NoiseKeyPriv)
		identityPriv, _ := base64.StdEncoding.DecodeString(deviceJSON.IdentityKeyPriv)
		signedPreKeyPriv, _ := base64.StdEncoding.DecodeString(deviceJSON.SignedPreKeyPriv)
		signedPreKeySig, _ := base64.StdEncoding.DecodeString(deviceJSON.SignedPreKeySig)
		advSecretKey, _ := base64.StdEncoding.DecodeString(deviceJSON.AdvSecretKey)

		if len(noisePriv) != 32 || len(identityPriv) != 32 || len(signedPreKeyPriv) != 32 || len(signedPreKeySig) != 64 {
			return nil, errors.New("invalid key lengths in stored device")
		}

		ds.Device = &store.Device{
			NoiseKey:    keys.NewKeyPairFromPrivateKey(*(*[32]byte)(noisePriv)),
			IdentityKey: keys.NewKeyPairFromPrivateKey(*(*[32]byte)(identityPriv)),
			SignedPreKey: &keys.PreKey{
				KeyPair:   *keys.NewKeyPairFromPrivateKey(*(*[32]byte)(signedPreKeyPriv)),
				KeyID:     deviceJSON.SignedPreKeyID,
				Signature: (*[64]byte)(signedPreKeySig),
			},
			RegistrationID: deviceJSON.RegistrationID,
			AdvSecretKey:   advSecretKey,
		}

		if deviceJSON.FacebookUUID != "" {
			ds.Device.FacebookUUID, _ = uuid.Parse(deviceJSON.FacebookUUID)
		}
		if deviceJSON.JIDUser != "" {
			ds.Device.ID = &waTypes.JID{User: deviceJSON.JIDUser, Device: deviceJSON.JIDDevice, Server: waTypes.MessengerServer}
		}

		ds.nextPreKeyID = deviceJSON.NextPreKeyID

		// Load identities
		for k, v := range deviceJSON.Identities {
			decoded, _ := base64.StdEncoding.DecodeString(v)
			if len(decoded) == 32 {
				ds.identities[k] = *(*[32]byte)(decoded)
			}
		}

		// Load sessions
		for k, v := range deviceJSON.Sessions {
			decoded, _ := base64.StdEncoding.DecodeString(v)
			ds.sessions[k] = decoded
		}

		// Load pre-keys
		for idStr, v := range deviceJSON.PreKeys {
			var id uint32
			fmt.Sscanf(idStr, "%d", &id)
			decoded, _ := base64.StdEncoding.DecodeString(v)
			if len(decoded) == 32 {
				ds.preKeys[id] = &keys.PreKey{
					KeyPair: *keys.NewKeyPairFromPrivateKey(*(*[32]byte)(decoded)),
					KeyID:   id,
				}
			}
		}

		// Load sender keys
		for k, v := range deviceJSON.SenderKeys {
			decoded, _ := base64.StdEncoding.DecodeString(v)
			ds.senderKeys[k] = decoded
		}
	} else {
		// Create new device
		ds.Device = &store.Device{
			NoiseKey:       keys.NewKeyPair(),
			IdentityKey:    keys.NewKeyPair(),
			RegistrationID: rand.Uint32()%16380 + 1,
			AdvSecretKey:   make([]byte, 32),
		}
		rand.Read(ds.Device.AdvSecretKey)
		ds.Device.SignedPreKey = ds.Device.IdentityKey.CreateSignedPreKey(1)
		ds.Device.FacebookUUID = uuid.New()
		if err := ds.Save(); err != nil {
			return nil, err
		}
	}

	// Set store interfaces
	ds.Device.Identities = ds
	ds.Device.Sessions = ds
	ds.Device.PreKeys = ds
	ds.Device.SenderKeys = ds
	ds.Device.Container = ds
	ds.Device.AppStateKeys = ds
	ds.Device.AppState = ds
	ds.Device.Contacts = ds
	ds.Device.ChatSettings = ds
	ds.Device.MsgSecrets = ds
	ds.Device.PrivacyTokens = ds
	ds.Device.LIDs = ds
	ds.Device.EventBuffer = ds
	ds.Device.Initialized = true

	if ds.Device.Account == nil {
		ds.Device.Account = &waAdv.ADVSignedDeviceIdentity{
			Details: make([]byte, 0), AccountSignatureKey: make([]byte, 32),
			AccountSignature: make([]byte, 64), DeviceSignature: make([]byte, 64),
		}
	}

	return ds, nil
}

// GetDeviceData returns the device data as a JSON string
func (ds *DeviceStore) GetDeviceData() (string, error) {
	ds.mu.RLock()
	defer ds.mu.RUnlock()

	deviceJSON := DeviceJSON{
		NoiseKeyPriv:     base64.StdEncoding.EncodeToString(ds.Device.NoiseKey.Priv[:]),
		IdentityKeyPriv:  base64.StdEncoding.EncodeToString(ds.Device.IdentityKey.Priv[:]),
		SignedPreKeyPriv: base64.StdEncoding.EncodeToString(ds.Device.SignedPreKey.Priv[:]),
		SignedPreKeyID:   ds.Device.SignedPreKey.KeyID,
		SignedPreKeySig:  base64.StdEncoding.EncodeToString(ds.Device.SignedPreKey.Signature[:]),
		RegistrationID:   ds.Device.RegistrationID,
		AdvSecretKey:     base64.StdEncoding.EncodeToString(ds.Device.AdvSecretKey),
		FacebookUUID:     ds.Device.FacebookUUID.String(),
		NextPreKeyID:     ds.nextPreKeyID,
		Identities:       make(map[string]string),
		Sessions:         make(map[string]string),
		PreKeys:          make(map[string]string),
		SenderKeys:       make(map[string]string),
	}

	if ds.Device.ID != nil {
		deviceJSON.JIDUser = ds.Device.ID.User
		deviceJSON.JIDDevice = ds.Device.ID.Device
	}

	// Save identities
	for k, v := range ds.identities {
		deviceJSON.Identities[k] = base64.StdEncoding.EncodeToString(v[:])
	}

	// Save sessions
	for k, v := range ds.sessions {
		deviceJSON.Sessions[k] = base64.StdEncoding.EncodeToString(v)
	}

	// Save pre-keys
	for id, pk := range ds.preKeys {
		deviceJSON.PreKeys[fmt.Sprintf("%d", id)] = base64.StdEncoding.EncodeToString(pk.Priv[:])
	}

	// Save sender keys
	for k, v := range ds.senderKeys {
		deviceJSON.SenderKeys[k] = base64.StdEncoding.EncodeToString(v)
	}

	data, err := json.MarshalIndent(deviceJSON, "", "  ")
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// Save saves the device store to disk (only if path is set)
func (ds *DeviceStore) Save() error {
	data, err := ds.GetDeviceData()
	if err != nil {
		return err
	}

	if ds.path == "" {
		// No path set, emit callback instead of saving to file
		if ds.onDataChanged != nil {
			ds.onDataChanged(data)
		}
		return nil
	}

	return os.WriteFile(ds.path, []byte(data), 0600)
}

// NewDeviceStoreFromData creates a device store from JSON data string (no file I/O)
func NewDeviceStoreFromData(dataStr string) (*DeviceStore, error) {
	ds := &DeviceStore{
		path:         "", // Empty path means no file saving
		identities:   make(map[string][32]byte),
		sessions:     make(map[string][]byte),
		preKeys:      make(map[uint32]*keys.PreKey),
		senderKeys:   make(map[string][]byte),
		nextPreKeyID: 1,
	}

	var deviceJSON DeviceJSON
	if err := json.Unmarshal([]byte(dataStr), &deviceJSON); err != nil {
		return nil, err
	}

	noisePriv, _ := base64.StdEncoding.DecodeString(deviceJSON.NoiseKeyPriv)
	identityPriv, _ := base64.StdEncoding.DecodeString(deviceJSON.IdentityKeyPriv)
	signedPreKeyPriv, _ := base64.StdEncoding.DecodeString(deviceJSON.SignedPreKeyPriv)
	signedPreKeySig, _ := base64.StdEncoding.DecodeString(deviceJSON.SignedPreKeySig)
	advSecretKey, _ := base64.StdEncoding.DecodeString(deviceJSON.AdvSecretKey)

	if len(noisePriv) != 32 || len(identityPriv) != 32 || len(signedPreKeyPriv) != 32 || len(signedPreKeySig) != 64 {
		return nil, errors.New("invalid key lengths in device data")
	}

	ds.Device = &store.Device{
		NoiseKey:    keys.NewKeyPairFromPrivateKey(*(*[32]byte)(noisePriv)),
		IdentityKey: keys.NewKeyPairFromPrivateKey(*(*[32]byte)(identityPriv)),
		SignedPreKey: &keys.PreKey{
			KeyPair:   *keys.NewKeyPairFromPrivateKey(*(*[32]byte)(signedPreKeyPriv)),
			KeyID:     deviceJSON.SignedPreKeyID,
			Signature: (*[64]byte)(signedPreKeySig),
		},
		RegistrationID: deviceJSON.RegistrationID,
		AdvSecretKey:   advSecretKey,
	}

	if deviceJSON.FacebookUUID != "" {
		ds.Device.FacebookUUID, _ = uuid.Parse(deviceJSON.FacebookUUID)
	}
	if deviceJSON.JIDUser != "" {
		ds.Device.ID = &waTypes.JID{User: deviceJSON.JIDUser, Device: deviceJSON.JIDDevice, Server: waTypes.MessengerServer}
	}

	ds.nextPreKeyID = deviceJSON.NextPreKeyID

	// Load identities
	for k, v := range deviceJSON.Identities {
		decoded, _ := base64.StdEncoding.DecodeString(v)
		if len(decoded) == 32 {
			ds.identities[k] = *(*[32]byte)(decoded)
		}
	}

	// Load sessions
	for k, v := range deviceJSON.Sessions {
		decoded, _ := base64.StdEncoding.DecodeString(v)
		ds.sessions[k] = decoded
	}

	// Load pre-keys
	for idStr, v := range deviceJSON.PreKeys {
		var id uint32
		fmt.Sscanf(idStr, "%d", &id)
		decoded, _ := base64.StdEncoding.DecodeString(v)
		if len(decoded) == 32 {
			ds.preKeys[id] = &keys.PreKey{
				KeyPair: *keys.NewKeyPairFromPrivateKey(*(*[32]byte)(decoded)),
				KeyID:   id,
			}
		}
	}

	// Load sender keys
	for k, v := range deviceJSON.SenderKeys {
		decoded, _ := base64.StdEncoding.DecodeString(v)
		ds.senderKeys[k] = decoded
	}

	// Set store interfaces
	ds.Device.Identities = ds
	ds.Device.Sessions = ds
	ds.Device.PreKeys = ds
	ds.Device.SenderKeys = ds
	ds.Device.Container = ds
	ds.Device.AppStateKeys = ds
	ds.Device.AppState = ds
	ds.Device.Contacts = ds
	ds.Device.ChatSettings = ds
	ds.Device.MsgSecrets = ds
	ds.Device.PrivacyTokens = ds
	ds.Device.LIDs = ds
	ds.Device.EventBuffer = ds
	ds.Device.Initialized = true

	if ds.Device.Account == nil {
		ds.Device.Account = &waAdv.ADVSignedDeviceIdentity{
			Details: make([]byte, 0), AccountSignatureKey: make([]byte, 32),
			AccountSignature: make([]byte, 64), DeviceSignature: make([]byte, 64),
		}
	}

	return ds, nil
}

// NewDeviceStoreMemoryOnly creates a new device store that only lives in memory
// No file saving, no events emitted - state is lost when client disconnects
func NewDeviceStoreMemoryOnly() (*DeviceStore, error) {
	ds := &DeviceStore{
		path:         "", // Empty path means no file saving
		identities:   make(map[string][32]byte),
		sessions:     make(map[string][]byte),
		preKeys:      make(map[uint32]*keys.PreKey),
		senderKeys:   make(map[string][]byte),
		nextPreKeyID: 1,
		// onDataChanged is nil - no callback
	}

	// Create new device
	ds.Device = &store.Device{
		NoiseKey:       keys.NewKeyPair(),
		IdentityKey:    keys.NewKeyPair(),
		RegistrationID: rand.Uint32()%16380 + 1,
		AdvSecretKey:   make([]byte, 32),
	}
	rand.Read(ds.Device.AdvSecretKey)
	ds.Device.SignedPreKey = ds.Device.IdentityKey.CreateSignedPreKey(1)
	ds.Device.FacebookUUID = uuid.New()

	// Set store interfaces
	ds.Device.Identities = ds
	ds.Device.Sessions = ds
	ds.Device.PreKeys = ds
	ds.Device.SenderKeys = ds
	ds.Device.Container = ds
	ds.Device.AppStateKeys = ds
	ds.Device.AppState = ds
	ds.Device.Contacts = ds
	ds.Device.ChatSettings = ds
	ds.Device.MsgSecrets = ds
	ds.Device.PrivacyTokens = ds
	ds.Device.LIDs = ds
	ds.Device.EventBuffer = ds
	ds.Device.Initialized = true

	if ds.Device.Account == nil {
		ds.Device.Account = &waAdv.ADVSignedDeviceIdentity{
			Details: make([]byte, 0), AccountSignatureKey: make([]byte, 32),
			AccountSignature: make([]byte, 64), DeviceSignature: make([]byte, 64),
		}
	}

	return ds, nil
}

// GetCookies returns the current cookies from the messagix client
func (c *Client) GetCookies() map[string]string {
	if c.Messagix == nil {
		return nil
	}
	cks := c.Messagix.GetCookies()
	if cks == nil {
		return nil
	}
	result := make(map[string]string)
	for k, v := range cks.GetAll() {
		result[string(k)] = v
	}
	return result
}

// PushKeys holds the web push notification keys
type PushKeys struct {
	P256DH []byte `json:"p256dh"`
	Auth   []byte `json:"auth"`
}

// RegisterPushNotificationsOptions holds options for push notification registration
type RegisterPushNotificationsOptions struct {
	Endpoint string `json:"endpoint"`
	P256DH   string `json:"p256dh"` // base64 encoded
	Auth     string `json:"auth"`   // base64 encoded
}

// RegisterPushNotifications registers web push notification endpoint
func (c *Client) RegisterPushNotifications(ctx context.Context, opts *RegisterPushNotificationsOptions) error {
	if c.Messagix == nil {
		return fmt.Errorf("client not connected")
	}

	// Decode base64 keys
	p256dh, err := base64.RawURLEncoding.DecodeString(opts.P256DH)
	if err != nil {
		return fmt.Errorf("invalid p256dh key: %w", err)
	}
	auth, err := base64.RawURLEncoding.DecodeString(opts.Auth)
	if err != nil {
		return fmt.Errorf("invalid auth key: %w", err)
	}

	return c.Messagix.Facebook.RegisterPushNotifications(ctx, opts.Endpoint, messagix.PushKeys{
		P256DH: p256dh,
		Auth:   auth,
	})
}

// Helper to convert thread
func convertThread(t *table.LSDeleteThenInsertThread) *Thread {
	return &Thread{
		ID:                      t.ThreadKey,
		Type:                    int(t.ThreadType),
		Name:                    t.ThreadName,
		LastActivityTimestampMs: t.LastActivityTimestampMs,
		Snippet:                 t.Snippet,
	}
}

// Helper to convert message from LSUpsertMessage
func convertMessage(m *table.LSUpsertMessage) *Message {
	return &Message{
		ID:          m.MessageId,
		ThreadID:    m.ThreadKey,
		SenderID:    m.SenderId,
		Text:        m.Text,
		TimestampMs: m.TimestampMs,
	}
}

// Helper to convert message from LSInsertMessage
func convertInsertMessage(m *table.LSInsertMessage) *Message {
	return &Message{
		ID:          m.MessageId,
		ThreadID:    m.ThreadKey,
		SenderID:    m.SenderId,
		Text:        m.Text,
		TimestampMs: m.TimestampMs,
	}
}

// Helper to convert message from LSDeleteThenInsertMessage
func convertDeleteThenInsertMessage(m *table.LSDeleteThenInsertMessage) *Message {
	return &Message{
		ID:          m.MessageId,
		ThreadID:    m.ThreadKey,
		SenderID:    m.SenderId,
		Text:        m.Text,
		TimestampMs: m.TimestampMs,
	}
}
