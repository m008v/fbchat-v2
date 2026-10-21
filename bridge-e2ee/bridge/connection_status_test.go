package bridge

import (
	"context"
	"crypto/x509"
	"encoding/json"
	"errors"
	"net"
	"net/url"
	"testing"

	"go.mau.fi/mautrix-meta/pkg/messagix/dgw"
	"go.mau.fi/mautrix-meta/pkg/messagix/httpclient"
	"go.mau.fi/whatsmeow/store"
	"go.mau.fi/whatsmeow/types/events"
)

func TestClassifyConnectionErrorUsesTypedSentinels(t *testing.T) {
	tests := []struct {
		name      string
		err       error
		code      FailureCode
		retryable bool
		permanent bool
	}{
		{
			name:      "authentication",
			err:       fmtWrap(httpclient.ErrTokenInvalidated),
			code:      FailureAuthFailed,
			permanent: true,
		},
		{
			name:      "checkpoint",
			err:       fmtWrap(httpclient.ErrCheckpointRequired),
			code:      FailureCheckpointRequired,
			permanent: true,
		},
		{
			name:      "dgw unauthorized",
			err:       fmtWrap(dgw.ErrUnauthorized),
			code:      FailureAuthFailed,
			permanent: true,
		},
		{
			name:      "device deleted",
			err:       fmtWrap(store.ErrDeviceDeleted),
			code:      FailureDeviceStateInvalid,
			permanent: true,
		},
		{
			name:      "malformed device state",
			err:       fmtWrap(ErrDeviceStateInvalid),
			code:      FailureDeviceStateInvalid,
			permanent: true,
		},
		{
			name:      "network",
			err:       &net.DNSError{IsTimeout: true},
			code:      FailureNetworkDisconnected,
			retryable: true,
		},
		{
			name: "certificate verification",
			err: &url.Error{
				Op:  "Get",
				URL: "https://invalid.example",
				Err: x509.CertificateInvalidError{
					Cert:   &x509.Certificate{},
					Reason: x509.Expired,
				},
			},
			code:      FailureConfigInvalid,
			permanent: true,
		},
		{
			name:      "invalid json",
			err:       &json.SyntaxError{},
			code:      FailureProtocolError,
			permanent: true,
		},
		{
			name: "cancelled",
			err:  context.Canceled,
			code: FailureCancelled,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			classification := ClassifyConnectionError(test.err)
			if !classification.Classified || classification.Code != test.code ||
				classification.Retryable != test.retryable ||
				classification.Permanent != test.permanent {
				t.Fatalf("classification = %#v", classification)
			}
		})
	}

	if classification := ClassifyConnectionError(errors.New("opaque")); classification.Classified {
		t.Fatalf("opaque string error was guessed from text: %#v", classification)
	}
}

func TestInvalidDeviceDataUsesDeviceStateClassification(t *testing.T) {
	for _, data := range []string{"{", "{}"} {
		_, err := NewDeviceStoreFromData(data)
		if err == nil {
			t.Fatalf("NewDeviceStoreFromData(%q) unexpectedly succeeded", data)
		}
		classification := ClassifyConnectionError(err)
		if !classification.Classified || classification.Code != FailureDeviceStateInvalid ||
			classification.Retryable || !classification.Permanent {
			t.Fatalf("device state classification = %#v for %v", classification, err)
		}
	}
}

func fmtWrap(err error) error {
	return errors.Join(errors.New("outer"), err)
}

func TestConnectionStatusPrefersPermanentFailureAndAggregatesReconnect(t *testing.T) {
	client := &Client{}
	client.setTransportFailure(false, transientConnectionFailure(nil))
	client.setTransportFailure(true, e2eeConnectFailure(events.ConnectFailureLoggedOut))

	status := client.ConnectionStatus()
	if !status.HasFailure || status.FailureCode != FailureAuthFailed ||
		status.FailureTransport != connectionTransportE2EE || !status.Permanent ||
		status.Retryable || !status.NativeReconnecting {
		t.Fatalf("status = %#v", status)
	}

	client.clearTransportFailure(true)
	status = client.ConnectionStatus()
	if status.FailureCode != FailureNetworkDisconnected ||
		status.FailureTransport != connectionTransportRegular || !status.Retryable ||
		status.Permanent || !status.NativeReconnecting {
		t.Fatalf("regular reconnect status = %#v", status)
	}
}

func TestTransportPermanentFailureIsStickyUntilExplicitReset(t *testing.T) {
	client := &Client{}
	terminal := e2eeConnectFailure(events.ConnectFailureLoggedOut)
	client.setTransportFailure(true, terminal)

	effective := client.setTransportFailure(true, transientConnectionFailure(nil))
	if effective.code != FailureAuthFailed || !effective.permanent ||
		effective.retryable || effective.nativeReconnecting {
		t.Fatalf("transient failure overwrote terminal state: %#v", effective)
	}
	effective = client.setTransportFailure(true, transportFailureState{
		code:      FailureConfigInvalid,
		permanent: true,
		active:    true,
	})
	if effective.code != FailureAuthFailed {
		t.Fatalf("later permanent failure overwrote sticky auth state: %#v", effective)
	}

	client.markTransportConnecting(true)
	status := client.ConnectionStatus()
	if status.FailureCode != FailureNetworkDisconnected || !status.Retryable ||
		status.Permanent || !status.NativeReconnecting {
		t.Fatalf("explicit reconnect did not reset terminal state: %#v", status)
	}

	client.clearTransportFailure(true)
	if status := client.ConnectionStatus(); status.HasFailure || status.NativeReconnecting {
		t.Fatalf("successful connection did not clear failure: %#v", status)
	}
}

func TestStructuredFailureEventContainsOnlySafeBoundedFields(t *testing.T) {
	data := connectionFailureEventData(false, transportFailureState{
		code:               FailureNetworkDisconnected,
		retryable:          true,
		nativeReconnecting: true,
		active:             true,
	})
	if len(data) != 5 {
		t.Fatalf("structured failure field count = %d, want 5", len(data))
	}
	for _, forbidden := range []string{"error", "detail", "raw", "key", "credential"} {
		if _, exists := data[forbidden]; exists {
			t.Fatalf("structured failure leaked forbidden field %q", forbidden)
		}
	}
}

func TestNativeStoppedNetworkFailureRemainsExternallyRetryable(t *testing.T) {
	failure := permanentConnectionFailure(&net.DNSError{IsTimeout: true})
	if failure.code != FailureNetworkDisconnected || !failure.retryable ||
		failure.permanent || failure.nativeReconnecting {
		t.Fatalf("native-stopped network failure = %#v", failure)
	}
}

func TestE2EEConnectFailureClassificationMatchesNativeRetryPolicy(t *testing.T) {
	retrying := e2eeConnectFailure(events.ConnectFailureServiceUnavailable)
	if !retrying.retryable || !retrying.nativeReconnecting || retrying.permanent {
		t.Fatalf("service unavailable = %#v", retrying)
	}

	terminal := e2eeConnectFailure(events.ConnectFailureClientOutdated)
	if terminal.code != FailureProtocolError || terminal.retryable ||
		terminal.nativeReconnecting || !terminal.permanent {
		t.Fatalf("client outdated = %#v", terminal)
	}

	unknownPermanent := e2eeConnectFailure(events.ConnectFailureExperimental)
	if unknownPermanent.code != FailureConnectionFailed || unknownPermanent.retryable ||
		unknownPermanent.nativeReconnecting || !unknownPermanent.permanent {
		t.Fatalf("experimental failure = %#v", unknownPermanent)
	}
}
