package bridge

import (
	"context"
	"strconv"
	"time"

	"go.mau.fi/mautrix-meta/pkg/messagix"
	"go.mau.fi/whatsmeow/store"
	waTypes "go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/util/keys"
)

// Implement all the store interfaces for DeviceStore

func (ds *DeviceStore) PutIdentity(ctx context.Context, address string, key [32]byte) error {
	ds.mu.Lock()
	defer ds.mu.Unlock()
	ds.identities[address] = key
	go ds.Save()
	return nil
}

func (ds *DeviceStore) DeleteAllIdentities(ctx context.Context, phone string) error {
	return nil
}

func (ds *DeviceStore) DeleteIdentity(ctx context.Context, address string) error {
	ds.mu.Lock()
	defer ds.mu.Unlock()
	delete(ds.identities, address)
	go ds.Save()
	return nil
}

func (ds *DeviceStore) IsTrustedIdentity(ctx context.Context, address string, key [32]byte) (bool, error) {
	ds.mu.RLock()
	defer ds.mu.RUnlock()
	existing, ok := ds.identities[address]
	if !ok {
		return true, nil
	}
	return existing == key, nil
}

func (ds *DeviceStore) GetSession(ctx context.Context, address string) ([]byte, error) {
	ds.mu.RLock()
	defer ds.mu.RUnlock()
	return ds.sessions[address], nil
}

func (ds *DeviceStore) HasSession(ctx context.Context, address string) (bool, error) {
	ds.mu.RLock()
	defer ds.mu.RUnlock()
	_, ok := ds.sessions[address]
	return ok, nil
}

func (ds *DeviceStore) GetManySessions(ctx context.Context, addresses []string) (map[string][]byte, error) {
	ds.mu.RLock()
	defer ds.mu.RUnlock()
	result := make(map[string][]byte, len(addresses))
	for _, addr := range addresses {
		result[addr] = ds.sessions[addr]
	}
	return result, nil
}

func (ds *DeviceStore) PutSession(ctx context.Context, address string, session []byte) error {
	ds.mu.Lock()
	defer ds.mu.Unlock()
	ds.sessions[address] = session
	go ds.Save()
	return nil
}

func (ds *DeviceStore) PutManySessions(ctx context.Context, sessions map[string][]byte) error {
	ds.mu.Lock()
	defer ds.mu.Unlock()
	for addr, sess := range sessions {
		ds.sessions[addr] = sess
	}
	go ds.Save()
	return nil
}

func (ds *DeviceStore) DeleteAllSessions(ctx context.Context, phone string) error {
	return nil
}

func (ds *DeviceStore) DeleteSession(ctx context.Context, address string) error {
	ds.mu.Lock()
	defer ds.mu.Unlock()
	delete(ds.sessions, address)
	go ds.Save()
	return nil
}

func (ds *DeviceStore) MigratePNToLID(ctx context.Context, pn, lid waTypes.JID) error {
	return nil
}

func (ds *DeviceStore) GetOrGenPreKeys(ctx context.Context, count uint32) ([]*keys.PreKey, error) {
	ds.mu.Lock()
	defer ds.mu.Unlock()
	result := make([]*keys.PreKey, 0, count)
	for i := uint32(0); i < count; i++ {
		pk := keys.NewPreKey(ds.nextPreKeyID)
		ds.preKeys[ds.nextPreKeyID] = pk
		result = append(result, pk)
		ds.nextPreKeyID++
	}
	go ds.Save()
	return result, nil
}

func (ds *DeviceStore) GenOnePreKey(ctx context.Context) (*keys.PreKey, error) {
	ds.mu.Lock()
	defer ds.mu.Unlock()
	pk := keys.NewPreKey(ds.nextPreKeyID)
	ds.preKeys[ds.nextPreKeyID] = pk
	ds.nextPreKeyID++
	go ds.Save()
	return pk, nil
}

func (ds *DeviceStore) GetPreKey(ctx context.Context, id uint32) (*keys.PreKey, error) {
	ds.mu.RLock()
	defer ds.mu.RUnlock()
	return ds.preKeys[id], nil
}

func (ds *DeviceStore) RemovePreKey(ctx context.Context, id uint32) error {
	ds.mu.Lock()
	defer ds.mu.Unlock()
	delete(ds.preKeys, id)
	go ds.Save()
	return nil
}

func (ds *DeviceStore) MarkPreKeysAsUploaded(ctx context.Context, upToID uint32) error {
	return nil
}

func (ds *DeviceStore) UploadedPreKeyCount(ctx context.Context) (int, error) {
	ds.mu.RLock()
	defer ds.mu.RUnlock()
	return len(ds.preKeys), nil
}

func (ds *DeviceStore) PutSenderKey(ctx context.Context, group, user string, session []byte) error {
	ds.mu.Lock()
	defer ds.mu.Unlock()
	ds.senderKeys[group+":"+user] = session
	go ds.Save()
	return nil
}

func (ds *DeviceStore) GetSenderKey(ctx context.Context, group, user string) ([]byte, error) {
	ds.mu.RLock()
	defer ds.mu.RUnlock()
	return ds.senderKeys[group+":"+user], nil
}

func (ds *DeviceStore) PutDevice(ctx context.Context, device *store.Device) error {
	return ds.Save()
}

func (ds *DeviceStore) DeleteDevice(ctx context.Context, device *store.Device) error {
	return nil
}

// Stub implementations for other interfaces
func (ds *DeviceStore) PutAppStateSyncKey(ctx context.Context, id []byte, key store.AppStateSyncKey) error {
	return nil
}

func (ds *DeviceStore) GetAppStateSyncKey(ctx context.Context, id []byte) (*store.AppStateSyncKey, error) {
	return nil, nil
}

func (ds *DeviceStore) GetLatestAppStateSyncKeyID(ctx context.Context) ([]byte, error) {
	return nil, nil
}

func (ds *DeviceStore) GetAllAppStateSyncKeys(ctx context.Context) ([]*store.AppStateSyncKey, error) {
	return nil, nil
}

func (ds *DeviceStore) PutAppStateVersion(ctx context.Context, name string, version uint64, hash [128]byte) error {
	return nil
}

func (ds *DeviceStore) GetAppStateVersion(ctx context.Context, name string) (uint64, [128]byte, error) {
	return 0, [128]byte{}, nil
}

func (ds *DeviceStore) DeleteAppStateVersion(ctx context.Context, name string) error {
	return nil
}

func (ds *DeviceStore) PutAppStateMutationMACs(ctx context.Context, name string, version uint64, mutations []store.AppStateMutationMAC) error {
	return nil
}

func (ds *DeviceStore) DeleteAppStateMutationMACs(ctx context.Context, name string, indexMACs [][]byte) error {
	return nil
}

func (ds *DeviceStore) GetAppStateMutationMAC(ctx context.Context, name string, indexMAC []byte) (valueMAC []byte, err error) {
	return nil, nil
}

func (ds *DeviceStore) PutPushName(ctx context.Context, user waTypes.JID, pushName string) (bool, string, error) {
	return false, "", nil
}

func (ds *DeviceStore) PutBusinessName(ctx context.Context, user waTypes.JID, businessName string) (bool, string, error) {
	return false, "", nil
}

func (ds *DeviceStore) PutContactName(ctx context.Context, user waTypes.JID, firstName, fullName string) error {
	return nil
}

func (ds *DeviceStore) PutAllContactNames(ctx context.Context, contacts []store.ContactEntry) error {
	return nil
}

func (ds *DeviceStore) PutManyRedactedPhones(ctx context.Context, entries []store.RedactedPhoneEntry) error {
	return nil
}

func (ds *DeviceStore) GetContact(ctx context.Context, user waTypes.JID) (waTypes.ContactInfo, error) {
	return waTypes.ContactInfo{}, nil
}

func (ds *DeviceStore) GetAllContacts(ctx context.Context) (map[waTypes.JID]waTypes.ContactInfo, error) {
	return nil, nil
}

func (ds *DeviceStore) PutMutedUntil(ctx context.Context, chat waTypes.JID, mutedUntil time.Time) error {
	return nil
}

func (ds *DeviceStore) PutPinned(ctx context.Context, chat waTypes.JID, pinned bool) error {
	return nil
}

func (ds *DeviceStore) PutArchived(ctx context.Context, chat waTypes.JID, archived bool) error {
	return nil
}

func (ds *DeviceStore) GetChatSettings(ctx context.Context, chat waTypes.JID) (waTypes.LocalChatSettings, error) {
	return waTypes.LocalChatSettings{}, nil
}

func (ds *DeviceStore) PutMessageSecrets(ctx context.Context, inserts []store.MessageSecretInsert) error {
	return nil
}

func (ds *DeviceStore) PutMessageSecret(ctx context.Context, chat, sender waTypes.JID, id waTypes.MessageID, secret []byte) error {
	return nil
}

func (ds *DeviceStore) GetMessageSecret(ctx context.Context, chat, sender waTypes.JID, id waTypes.MessageID) ([]byte, waTypes.JID, error) {
	return nil, waTypes.JID{}, nil
}

func (ds *DeviceStore) PutPrivacyTokens(ctx context.Context, tokens ...store.PrivacyToken) error {
	return nil
}

func (ds *DeviceStore) GetPrivacyToken(ctx context.Context, user waTypes.JID) (*store.PrivacyToken, error) {
	return nil, nil
}

func (ds *DeviceStore) PutLIDMapping(ctx context.Context, lid, pn waTypes.JID) error {
	return nil
}

func (ds *DeviceStore) PutManyLIDMappings(ctx context.Context, mappings []store.LIDMapping) error {
	return nil
}

func (ds *DeviceStore) GetPNForLID(ctx context.Context, lid waTypes.JID) (waTypes.JID, error) {
	return waTypes.JID{}, nil
}

func (ds *DeviceStore) GetLIDForPN(ctx context.Context, pn waTypes.JID) (waTypes.JID, error) {
	return waTypes.JID{}, nil
}

func (ds *DeviceStore) GetManyLIDsForPNs(ctx context.Context, pns []waTypes.JID) (map[waTypes.JID]waTypes.JID, error) {
	return nil, nil
}

func (ds *DeviceStore) GetBufferedEvent(ctx context.Context, ciphertextHash [32]byte) (*store.BufferedEvent, error) {
	return nil, nil
}

func (ds *DeviceStore) PutBufferedEvent(ctx context.Context, ciphertextHash [32]byte, plaintext []byte, serverTimestamp time.Time) error {
	return nil
}

func (ds *DeviceStore) DoDecryptionTxn(ctx context.Context, fn func(context.Context) error) error {
	return fn(ctx)
}

func (ds *DeviceStore) ClearBufferedEventPlaintext(ctx context.Context, ciphertextHash [32]byte) error {
	return nil
}

func (ds *DeviceStore) DeleteOldBufferedHashes(ctx context.Context) error {
	return nil
}

// EventBuffer outgoing-event methods (added in newer whatsmeow). We don't
// persist outgoing events — the bridge is stateless w.r.t. retries.

func (ds *DeviceStore) GetOutgoingEvent(ctx context.Context, chatJID, altChatJID waTypes.JID, id waTypes.MessageID) (string, []byte, error) {
	return "", nil, nil
}

func (ds *DeviceStore) AddOutgoingEvent(ctx context.Context, chatJID waTypes.JID, id waTypes.MessageID, format string, plaintext []byte) error {
	return nil
}

func (ds *DeviceStore) DeleteOldOutgoingEvents(ctx context.Context) error {
	return nil
}

// Unused imports fix
var _ = messagix.ErrTokenInvalidated
var _ = strconv.Atoi
