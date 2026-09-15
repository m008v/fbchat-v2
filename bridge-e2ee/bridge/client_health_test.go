package bridge

import (
	"context"
	"errors"
	"testing"

	"go.mau.fi/mautrix-meta/pkg/messagix"
	"go.mau.fi/whatsmeow"
)

type fakeE2EEConnectionState struct {
	connected bool
	loggedIn  bool
}

func (state *fakeE2EEConnectionState) IsConnected() bool { return state.connected }
func (state *fakeE2EEConnectionState) IsLoggedIn() bool  { return state.loggedIn }

func TestClientConnectionHealthTracksSocketEvents(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	client := &Client{
		Messagix:  &messagix.Client{},
		eventChan: make(chan *Event, 8),
		ctx:       ctx,
		cancel:    cancel,
	}

	if client.IsConnected() {
		t.Fatal("new client reported connected before a socket ready event")
	}

	client.handleMessagixEvent(ctx, &messagix.Event_Ready{})
	if !client.IsConnected() {
		t.Fatal("client did not report connected after a socket ready event")
	}

	client.handleMessagixEvent(ctx, &messagix.Event_SocketError{Err: errors.New("socket closed")})
	if client.IsConnected() {
		t.Fatal("client remained connected after a socket error")
	}

	client.handleMessagixEvent(ctx, &messagix.Event_Reconnected{})
	if !client.IsConnected() {
		t.Fatal("client did not report connected after a socket reconnect event")
	}
}

func TestConnectClearsStaleSocketReadinessBeforeBootstrap(t *testing.T) {
	client := &Client{disconnected: true}
	client.regularConnected.Store(true)

	if _, _, err := client.Connect(); err == nil {
		t.Fatal("Connect() unexpectedly succeeded for a disconnected client")
	}
	if client.regularConnected.Load() {
		t.Fatal("Connect() retained stale socket readiness")
	}
}

func TestE2EEReadinessRequiresTransportAndAuthentication(t *testing.T) {
	tests := []struct {
		name      string
		state     e2eeConnectionState
		wantReady bool
	}{
		{name: "nil", state: nil, wantReady: false},
		{
			name:      "transport only",
			state:     &fakeE2EEConnectionState{connected: true},
			wantReady: false,
		},
		{
			name:      "authentication only",
			state:     &fakeE2EEConnectionState{loggedIn: true},
			wantReady: false,
		},
		{
			name: "transport and authentication",
			state: &fakeE2EEConnectionState{
				connected: true,
				loggedIn:  true,
			},
			wantReady: true,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := isE2EEReady(test.state); got != test.wantReady {
				t.Fatalf("isE2EEReady() = %v, want %v", got, test.wantReady)
			}
		})
	}
}

func TestConnectE2EERollsBackPartialClientOnFailure(t *testing.T) {
	tests := []struct {
		name        string
		failureStep string
	}{
		{name: "prepare", failureStep: "prepare"},
		{name: "register", failureStep: "register"},
		{name: "save", failureStep: "save"},
		{name: "connect", failureStep: "connect"},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			ctx, cancel := context.WithCancel(context.Background())
			t.Cleanup(cancel)
			candidate := &whatsmeow.Client{}
			expectedError := errors.New(test.failureStep + " failed")
			client := &Client{ctx: ctx, cancel: cancel}
			disconnectCalls := 0

			operations := e2eeConnectOperations{
				prepare: func() (*whatsmeow.Client, error) {
					if test.failureStep == "prepare" {
						return nil, expectedError
					}
					return candidate, nil
				},
				register: func() error {
					if test.failureStep == "register" {
						return expectedError
					}
					return nil
				},
				save: func() error {
					if test.failureStep == "save" {
						return expectedError
					}
					return nil
				},
				connect: func(*whatsmeow.Client) error {
					if test.failureStep == "connect" {
						return expectedError
					}
					return nil
				},
				disconnect: func(*whatsmeow.Client) {
					disconnectCalls++
				},
			}

			err := client.connectE2EE(operations)

			if !errors.Is(err, expectedError) {
				t.Fatalf("connectE2EE() error = %v, want %v", err, expectedError)
			}
			if client.E2EE != nil {
				t.Fatal("connectE2EE() retained a partially initialized client")
			}
			wantDisconnectCalls := 1
			if test.failureStep == "prepare" {
				wantDisconnectCalls = 0
			}
			if disconnectCalls != wantDisconnectCalls {
				t.Fatalf("disconnect calls = %d, want %d", disconnectCalls, wantDisconnectCalls)
			}
		})
	}
}
