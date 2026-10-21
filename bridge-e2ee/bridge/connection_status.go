package bridge

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"errors"
	"net"

	"go.mau.fi/mautrix-meta/pkg/messagix"
	"go.mau.fi/mautrix-meta/pkg/messagix/bloks"
	"go.mau.fi/mautrix-meta/pkg/messagix/dgw"
	"go.mau.fi/mautrix-meta/pkg/messagix/httpclient"
	"go.mau.fi/whatsmeow/store"
	"go.mau.fi/whatsmeow/types/events"
)

// FailureCode is a stable, non-sensitive machine-readable connection failure.
// It deliberately does not contain provider payloads, credentials, IDs or raw
// error text.
type FailureCode string

// ErrDeviceStateInvalid marks persisted or supplied E2EE identity state that
// cannot be decoded safely. Wrapping the original error preserves diagnostics
// while keeping the public failure classification stable and non-sensitive.
var ErrDeviceStateInvalid = errors.New("device state invalid")

const (
	FailureNetworkDisconnected FailureCode = "network_disconnected"
	FailureAuthFailed          FailureCode = "auth_failed"
	FailureCheckpointRequired  FailureCode = "checkpoint_required"
	FailureConfigInvalid       FailureCode = "config_invalid"
	FailureProtocolError       FailureCode = "protocol_error"
	FailureDeviceStateInvalid  FailureCode = "device_state_invalid"
	FailureConnectionFailed    FailureCode = "connection_failed"
	FailureCancelled           FailureCode = "cancelled"
)

const (
	connectionTransportRegular = "regular"
	connectionTransportE2EE    = "e2ee"
)

// ErrorClassification is safe to expose in the JSON-RPC envelope. Classified
// is false when an error has no reliable typed/sentinel classification; callers
// must not infer a category by matching error strings.
type ErrorClassification struct {
	Code       FailureCode
	Retryable  bool
	Permanent  bool
	Classified bool
}

// ConnectionStatus is the aggregate transport status returned by isConnected.
// Failure fields describe the highest-priority active failure. The two normal
// readiness booleans remain separate in the RPC payload for compatibility.
type ConnectionStatus struct {
	NativeReconnecting bool
	FailureCode        FailureCode
	Retryable          bool
	Permanent          bool
	FailureTransport   string
	HasFailure         bool
}

type transportFailureState struct {
	code               FailureCode
	retryable          bool
	permanent          bool
	nativeReconnecting bool
	active             bool
}

func classifiedFailure(code FailureCode, retryable, permanent bool) ErrorClassification {
	return ErrorClassification{
		Code:       code,
		Retryable:  retryable,
		Permanent:  permanent,
		Classified: true,
	}
}

// ClassifyConnectionError uses typed errors and exported sentinels only. Raw
// provider text is intentionally ignored so a credential, checkpoint URL or
// account identifier can never become part of structured status.
func ClassifyConnectionError(err error) ErrorClassification {
	if err == nil {
		return ErrorClassification{}
	}
	if errors.Is(err, context.Canceled) {
		return classifiedFailure(FailureCancelled, false, false)
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return classifiedFailure(FailureNetworkDisconnected, true, false)
	}
	if errors.Is(err, httpclient.ErrChallengeRequired) ||
		errors.Is(err, httpclient.ErrCheckpointRequired) {
		return classifiedFailure(FailureCheckpointRequired, false, true)
	}
	var checkpointError bloks.CheckpointError
	if errors.As(err, &checkpointError) {
		return classifiedFailure(FailureCheckpointRequired, false, true)
	}
	if errors.Is(err, httpclient.ErrTokenInvalidated) ||
		errors.Is(err, httpclient.ErrConsentRequired) ||
		errors.Is(err, httpclient.ErrAccountSuspended) ||
		dgw.IsUnauthorized(err) {
		return classifiedFailure(FailureAuthFailed, false, true)
	}
	if errors.Is(err, ErrDeviceStateInvalid) || errors.Is(err, store.ErrDeviceDeleted) {
		return classifiedFailure(FailureDeviceStateInvalid, false, true)
	}
	if errors.Is(err, messagix.ErrClientIsNil) {
		return classifiedFailure(FailureConfigInvalid, false, true)
	}
	if errors.Is(err, httpclient.ErrTooManyRedirects) ||
		errors.Is(err, httpclient.ErrVersionIDNotFound) {
		return classifiedFailure(FailureProtocolError, false, true)
	}
	var certificateVerificationError *tls.CertificateVerificationError
	var unknownAuthorityError x509.UnknownAuthorityError
	var hostnameError x509.HostnameError
	var certificateInvalidError x509.CertificateInvalidError
	if errors.As(err, &certificateVerificationError) ||
		errors.As(err, &unknownAuthorityError) ||
		errors.As(err, &hostnameError) ||
		errors.As(err, &certificateInvalidError) {
		return classifiedFailure(FailureConfigInvalid, false, true)
	}
	var syntaxError *json.SyntaxError
	var typeError *json.UnmarshalTypeError
	if errors.As(err, &syntaxError) || errors.As(err, &typeError) {
		return classifiedFailure(FailureProtocolError, false, true)
	}
	if errors.Is(err, dgw.ErrDial) ||
		errors.Is(err, dgw.ErrPongTimeout) ||
		errors.Is(err, dgw.ErrAckTimeout) ||
		errors.Is(err, dgw.ErrReceiveTimeout) ||
		errors.Is(err, httpclient.ErrRequestFailed) ||
		errors.Is(err, httpclient.ErrResponseReadFailed) ||
		errors.Is(err, httpclient.ErrMaxRetriesReached) ||
		errors.Is(err, messagix.ErrFatalSocketSyncError) {
		return classifiedFailure(FailureNetworkDisconnected, true, false)
	}
	var networkError net.Error
	if errors.As(err, &networkError) {
		return classifiedFailure(FailureNetworkDisconnected, true, false)
	}
	return ErrorClassification{}
}

func transientConnectionFailure(err error) transportFailureState {
	classified := ClassifyConnectionError(err)
	if classified.Classified && (classified.Permanent || !classified.Retryable) {
		return transportFailureState{
			code:      classified.Code,
			retryable: classified.Retryable,
			permanent: true,
			active:    true,
		}
	}
	code := FailureNetworkDisconnected
	if classified.Classified {
		code = classified.Code
	}
	return transportFailureState{
		code:               code,
		retryable:          true,
		nativeReconnecting: true,
		active:             true,
	}
}

// permanentConnectionFailure is used when the native transport has stopped
// its own retry loop. A reliably classified network error remains externally
// retryable, but nativeReconnecting stays false so the parent may replace the
// process; auth/config/protocol and unknown failures remain terminal.
func permanentConnectionFailure(err error) transportFailureState {
	classified := ClassifyConnectionError(err)
	if !classified.Classified {
		classified = classifiedFailure(FailureConnectionFailed, false, true)
	}
	return transportFailureState{
		code:      classified.Code,
		retryable: classified.Retryable,
		permanent: classified.Permanent || !classified.Retryable,
		active:    true,
	}
}

func synchronousConnectionFailure(err error) transportFailureState {
	classified := ClassifyConnectionError(err)
	if !classified.Classified {
		classified = classifiedFailure(FailureConnectionFailed, false, true)
	}
	return transportFailureState{
		code:      classified.Code,
		retryable: classified.Retryable,
		permanent: classified.Permanent || !classified.Retryable,
		active:    true,
	}
}

func e2eeConnectFailure(reason events.ConnectFailureReason) transportFailureState {
	switch reason {
	case events.ConnectFailureLoggedOut,
		events.ConnectFailureTempBanned,
		events.ConnectFailureMainDeviceGone,
		events.ConnectFailureUnknownLogout,
		events.ConnectFailureCATExpired,
		events.ConnectFailureCATInvalid:
		return transportFailureState{code: FailureAuthFailed, permanent: true, active: true}
	case events.ConnectFailureClientOutdated,
		events.ConnectFailureBadUserAgent,
		events.ConnectFailureClientUnknown:
		return transportFailureState{code: FailureProtocolError, permanent: true, active: true}
	case events.ConnectFailureNotFound:
		return transportFailureState{code: FailureConfigInvalid, permanent: true, active: true}
	case events.ConnectFailureInternalServerError,
		events.ConnectFailureServiceUnavailable:
		return transportFailureState{
			code:               FailureNetworkDisconnected,
			retryable:          true,
			nativeReconnecting: true,
			active:             true,
		}
	default:
		return transportFailureState{code: FailureConnectionFailed, permanent: true, active: true}
	}
}

func (c *Client) markTransportConnecting(isE2EE bool) {
	c.replaceTransportFailure(isE2EE, transportFailureState{
		code:               FailureNetworkDisconnected,
		retryable:          true,
		nativeReconnecting: true,
		active:             true,
	})
}

// setTransportFailure keeps a terminal failure sticky for each transport. Some
// native clients emit a generic Disconnected event immediately after a
// LoggedOut/permanent event; allowing that transient event to overwrite state
// would incorrectly tell the parent to keep retrying authentication.
func (c *Client) setTransportFailure(isE2EE bool, failure transportFailureState) transportFailureState {
	c.connectionStatusMu.Lock()
	defer c.connectionStatusMu.Unlock()
	target := &c.regularFailure
	if isE2EE {
		target = &c.e2eeFailure
	}
	if target.active && target.permanent {
		return *target
	}
	*target = failure
	return failure
}

func (c *Client) replaceTransportFailure(isE2EE bool, failure transportFailureState) {
	c.connectionStatusMu.Lock()
	if isE2EE {
		c.e2eeFailure = failure
	} else {
		c.regularFailure = failure
	}
	c.connectionStatusMu.Unlock()
}

func (c *Client) clearTransportFailure(isE2EE bool) {
	c.connectionStatusMu.Lock()
	if isE2EE {
		c.e2eeFailure = transportFailureState{}
	} else {
		c.regularFailure = transportFailureState{}
	}
	c.connectionStatusMu.Unlock()
}

func (c *Client) clearConnectionFailures() {
	c.connectionStatusMu.Lock()
	c.regularFailure = transportFailureState{}
	c.e2eeFailure = transportFailureState{}
	c.connectionStatusMu.Unlock()
}

// ConnectionStatus returns only bounded machine-readable state. It never
// includes raw upstream errors or event bodies.
func (c *Client) ConnectionStatus() ConnectionStatus {
	if c == nil {
		return ConnectionStatus{}
	}
	c.connectionStatusMu.RLock()
	regular := c.regularFailure
	e2ee := c.e2eeFailure
	c.connectionStatusMu.RUnlock()

	status := ConnectionStatus{
		NativeReconnecting: regular.nativeReconnecting || e2ee.nativeReconnecting,
	}
	chosen := regular
	transport := connectionTransportRegular
	if !chosen.active || (e2ee.active && e2ee.permanent && !chosen.permanent) {
		chosen = e2ee
		transport = connectionTransportE2EE
	}
	if !chosen.active {
		return status
	}
	status.HasFailure = true
	status.FailureCode = chosen.code
	status.Retryable = chosen.retryable
	status.Permanent = chosen.permanent
	status.FailureTransport = transport
	return status
}

func connectionFailureEventData(isE2EE bool, failure transportFailureState) map[string]any {
	return map[string]any{
		"isE2EE":             isE2EE,
		"nativeReconnecting": failure.nativeReconnecting,
		"failureCode":        failure.code,
		"retryable":          failure.retryable,
		"permanent":          failure.permanent,
	}
}

func safeConnectionFailureMessage(isE2EE bool, failure transportFailureState) string {
	transport := "Messenger"
	if isE2EE {
		transport = "E2EE"
	}
	switch failure.code {
	case FailureAuthFailed:
		return transport + " authentication failed"
	case FailureCheckpointRequired:
		return transport + " account verification is required"
	case FailureProtocolError:
		return transport + " protocol is incompatible"
	case FailureConfigInvalid:
		return transport + " configuration is invalid"
	case FailureDeviceStateInvalid:
		return transport + " device state is invalid"
	case FailureCancelled:
		return transport + " connection was cancelled"
	default:
		return transport + " connection is unavailable"
	}
}

func (c *Client) emitConnectionFailure(isE2EE bool, failure transportFailureState) {
	failure = c.setTransportFailure(isE2EE, failure)
	c.emitEvent(EventTypeDisconnected, connectionFailureEventData(isE2EE, failure))
	code := 0
	if failure.permanent {
		code = 1
	}
	c.emitEvent(EventTypeError, &ErrorEvent{
		Message: safeConnectionFailureMessage(isE2EE, failure),
		Code:    code,
	})
}
