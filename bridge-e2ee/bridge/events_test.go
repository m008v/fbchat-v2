package bridge

import (
	"context"
	"fmt"
	"testing"
	"time"

	"go.mau.fi/mautrix-meta/pkg/messagix"
	"go.mau.fi/mautrix-meta/pkg/messagix/table"
	"go.mau.fi/whatsmeow/types/events"
)

func newEventPipelineTestClient(t *testing.T, liveCutoffMs int64) *Client {
	t.Helper()
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	return &Client{
		eventChan:           make(chan *Event, 16),
		ctx:                 ctx,
		cancel:              cancel,
		threadCache:         make(map[int64]*Thread),
		recentMessages:      make(map[string]recentMessageEvent),
		liveMessageCutoffMs: liveCutoffMs,
	}
}

func TestHandleSocketErrorsWithoutUnderlyingError(t *testing.T) {
	tests := []struct {
		name      string
		event     any
		code      int
		retryable bool
		permanent bool
	}{
		{
			name:      "socket disconnected",
			event:     &messagix.TransientDisconnectEvent{},
			retryable: true,
		},
		{
			name:      "permanent failure",
			event:     &messagix.PermanentErrorEvent{},
			code:      1,
			permanent: true,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			client := newEventPipelineTestClient(t, 0)
			client.regularConnected.Store(true)
			client.handleMessagixEvent(context.Background(), test.event)
			if client.IsConnected() {
				t.Fatal("client remained connected after a socket failure")
			}

			raw := <-client.eventChan
			if raw.Type != EventTypeRaw {
				t.Fatalf("first event type = %q, want %q", raw.Type, EventTypeRaw)
			}
			disconnected := <-client.eventChan
			if disconnected.Type != EventTypeDisconnected {
				t.Fatalf("connection state event type = %q, want %q", disconnected.Type, EventTypeDisconnected)
			}
			state, ok := disconnected.Data.(map[string]any)
			if !ok || state["isE2EE"] != false ||
				state["retryable"] != test.retryable ||
				state["permanent"] != test.permanent ||
				state["nativeReconnecting"] != test.retryable {
				t.Fatalf("connection state data = %#v", disconnected.Data)
			}
			if state["failureCode"] == "" {
				t.Fatal("connection state omitted safe failure code")
			}

			diagnostic := <-client.eventChan
			if diagnostic.Type != EventTypeError {
				t.Fatalf("diagnostic event type = %q, want %q", diagnostic.Type, EventTypeError)
			}
			errorEvent, ok := diagnostic.Data.(*ErrorEvent)
			if !ok || errorEvent.Message == "" || errorEvent.Code != test.code {
				t.Fatalf("diagnostic event data = %#v, want fallback message and code %d", diagnostic.Data, test.code)
			}
		})
	}
}

func TestHandleE2EEUndecryptableMessageEmitsDiagnostic(t *testing.T) {
	client := newEventPipelineTestClient(t, timeNowMs()-1_000)
	client.handleE2EEEvent(&events.UndecryptableMessage{})

	raw := <-client.eventChan
	if raw.Type != EventTypeRaw {
		t.Fatalf("first event type = %q, want %q", raw.Type, EventTypeRaw)
	}
	diagnostic := <-client.eventChan
	if diagnostic.Type != EventTypeError {
		t.Fatalf("diagnostic event type = %q, want %q", diagnostic.Type, EventTypeError)
	}
	errorEvent, ok := diagnostic.Data.(*ErrorEvent)
	if !ok || errorEvent.Code != 2 {
		t.Fatalf("diagnostic event data = %#v, want decrypt error", diagnostic.Data)
	}
}

func TestHandleE2EELoggedOutEmitsPermanentStructuredDisconnect(t *testing.T) {
	client := newEventPipelineTestClient(t, timeNowMs()-1_000)
	client.handleE2EEEvent(&events.LoggedOut{
		OnConnect: true,
		Reason:    events.ConnectFailureLoggedOut,
	})

	raw := <-client.eventChan
	if raw.Type != EventTypeRaw {
		t.Fatalf("first event type = %q, want %q", raw.Type, EventTypeRaw)
	}
	disconnected := <-client.eventChan
	if disconnected.Type != EventTypeDisconnected {
		t.Fatalf("state event type = %q, want %q", disconnected.Type, EventTypeDisconnected)
	}
	state, ok := disconnected.Data.(map[string]any)
	if !ok || state["isE2EE"] != true || state["failureCode"] != FailureAuthFailed ||
		state["retryable"] != false || state["permanent"] != true ||
		state["nativeReconnecting"] != false {
		t.Fatalf("logged-out state = %#v", disconnected.Data)
	}
	diagnostic := <-client.eventChan
	if diagnostic.Type != EventTypeError {
		t.Fatalf("diagnostic event type = %q, want %q", diagnostic.Type, EventTypeError)
	}
	status := client.ConnectionStatus()
	if !status.HasFailure || status.FailureCode != FailureAuthFailed ||
		status.FailureTransport != connectionTransportE2EE || !status.Permanent ||
		status.Retryable || status.NativeReconnecting {
		t.Fatalf("connection status = %#v", status)
	}

	// whatsmeow may report the underlying websocket close after LoggedOut. That
	// generic event must not downgrade a terminal auth failure to native retry.
	client.handleE2EEEvent(&events.Disconnected{})
	<-client.eventChan // raw
	disconnected = <-client.eventChan
	state, ok = disconnected.Data.(map[string]any)
	if !ok || state["failureCode"] != FailureAuthFailed ||
		state["retryable"] != false || state["permanent"] != true ||
		state["nativeReconnecting"] != false {
		t.Fatalf("post-logout disconnect downgraded state = %#v", disconnected.Data)
	}
	<-client.eventChan // diagnostic
	status = client.ConnectionStatus()
	if status.FailureCode != FailureAuthFailed || !status.Permanent ||
		status.Retryable || status.NativeReconnecting {
		t.Fatalf("post-logout status = %#v", status)
	}
}

func TestHandleE2EEConnectedClearsReconnectStatus(t *testing.T) {
	client := newEventPipelineTestClient(t, timeNowMs()-1_000)
	client.handleE2EEEvent(&events.Disconnected{})
	for range 3 {
		<-client.eventChan
	}
	if status := client.ConnectionStatus(); !status.NativeReconnecting {
		t.Fatalf("disconnected status = %#v, want native reconnect", status)
	}

	client.handleE2EEEvent(&events.Connected{})
	if status := client.ConnectionStatus(); status.HasFailure || status.NativeReconnecting {
		t.Fatalf("connected status retained failure = %#v", status)
	}
}

func TestClaimE2EEMessageIDDeduplicatesWithinProcess(t *testing.T) {
	client := newEventPipelineTestClient(t, timeNowMs()-1_000)
	if !client.claimE2EEMessageID("e2ee-mid") {
		t.Fatal("first E2EE message ID was rejected")
	}
	if client.claimE2EEMessageID("e2ee-mid") {
		t.Fatal("duplicate E2EE message ID was accepted")
	}
	if !client.claimE2EEMessageID("") || !client.claimE2EEMessageID("") {
		t.Fatal("empty E2EE message IDs must remain deliverable")
	}
}

func TestClaimE2EEMessageIDHasHardMemoryBound(t *testing.T) {
	client := newEventPipelineTestClient(t, timeNowMs()-1_000)
	client.recentE2EEMessages = make(map[string]int64, recentE2EEMessageLimit)
	client.recentE2EESweep = timeNowMs() + recentMessageSweepIntervalMs
	for index := range recentE2EEMessageLimit {
		client.recentE2EEMessages[fmt.Sprintf("mid-%d", index)] = int64(index + 1)
	}

	if !client.claimE2EEMessageID("mid-new") {
		t.Fatal("new E2EE message ID was rejected at the dedupe limit")
	}
	if got := len(client.recentE2EEMessages); got != recentE2EEMessageLimit {
		t.Fatalf("dedupe size = %d, want hard limit %d", got, recentE2EEMessageLimit)
	}
	if _, exists := client.recentE2EEMessages["mid-0"]; exists {
		t.Fatal("oldest E2EE message ID was not evicted")
	}
}

func TestHandleTableEmitsRecentStandaloneUpsert(t *testing.T) {
	now := timeNowMs()
	client := newEventPipelineTestClient(t, now-1_000)
	client.handleTable(&table.LSTable{LSUpsertMessage: []*table.LSUpsertMessage{{
		MessageId:   "mid.live",
		ThreadKey:   100,
		SenderId:    200,
		Text:        "/ping",
		TimestampMs: now,
	}}})

	select {
	case event := <-client.eventChan:
		if event.Type != EventTypeMessage {
			t.Fatalf("event type = %q, want %q", event.Type, EventTypeMessage)
		}
		message, ok := event.Data.(*Message)
		if !ok || message.ID != "mid.live" || message.Text != "/ping" {
			t.Fatalf("event data = %#v, want converted live message", event.Data)
		}
	default:
		t.Fatal("recent standalone upsert did not emit a message event")
	}
}

func TestHandleTableDoesNotEmitRangeBackedOrStaleUpserts(t *testing.T) {
	now := timeNowMs()
	client := newEventPipelineTestClient(t, now-1_000)
	client.handleTable(&table.LSTable{
		LSInsertNewMessageRange: []*table.LSInsertNewMessageRange{{ThreadKey: 100}},
		LSUpsertMessage: []*table.LSUpsertMessage{
			{
				MessageId:   "mid.backfill",
				ThreadKey:   100,
				SenderId:    200,
				Text:        "/old-command",
				TimestampMs: now,
			},
			{
				MessageId:   "mid.stale",
				ThreadKey:   101,
				SenderId:    200,
				Text:        "/old-command",
				TimestampMs: now - 2_000,
			},
		},
	})

	if got := len(client.eventChan); got != 0 {
		t.Fatalf("emitted %d message events for backfill/stale upserts, want 0", got)
	}
}

func TestHandleTableRejectsOldUpsertOnLongLivedConnection(t *testing.T) {
	now := timeNowMs()
	client := newEventPipelineTestClient(t, now-int64(time.Hour/time.Millisecond))
	client.handleTable(&table.LSTable{LSUpsertMessage: []*table.LSUpsertMessage{{
		MessageId:   "mid.old-live",
		ThreadKey:   100,
		SenderId:    200,
		Text:        "/old-command",
		TimestampMs: now - int64(10*time.Minute/time.Millisecond),
	}}})

	if got := len(client.eventChan); got != 0 {
		t.Fatalf("emitted %d events for old standalone upsert, want 0", got)
	}
}

func TestHandleTableRejectsStandaloneUpsertBeforeRealtimeWindow(t *testing.T) {
	now := timeNowMs()
	client := newEventPipelineTestClient(t, 0)
	client.handleTable(&table.LSTable{LSUpsertMessage: []*table.LSUpsertMessage{{
		MessageId:   "mid.before-connect",
		ThreadKey:   100,
		SenderId:    200,
		Text:        "/ping",
		TimestampMs: now,
	}}})

	if got := len(client.eventChan); got != 0 {
		t.Fatalf("emitted %d events before realtime window opened, want 0", got)
	}
}

func TestInitialRealtimeWindowDoesNotReplayPreConnectUpsert(t *testing.T) {
	now := timeNowMs()
	client := newEventPipelineTestClient(t, 0)
	client.openRealtimeMessageWindow(0)
	client.handleTable(&table.LSTable{LSUpsertMessage: []*table.LSUpsertMessage{{
		MessageId:   "mid.before-start",
		ThreadKey:   100,
		SenderId:    200,
		Text:        "/old-command",
		TimestampMs: now - 1_000,
	}}})

	if got := len(client.eventChan); got != 0 {
		t.Fatalf("emitted %d events for pre-connect upsert, want 0", got)
	}
}

func TestHandleTableEmitsEmptyIDInsertOnlyOnce(t *testing.T) {
	now := timeNowMs()
	client := newEventPipelineTestClient(t, now-1_000)
	client.handleTable(&table.LSTable{LSInsertMessage: []*table.LSInsertMessage{{
		ThreadKey:   100,
		SenderId:    200,
		Text:        "no id",
		TimestampMs: now,
	}}})

	if got := len(client.eventChan); got != 1 {
		t.Fatalf("emitted %d events for one empty-ID insert, want 1", got)
	}
}

func TestConvertThumbsUpDoesNotMutateWrappedMessage(t *testing.T) {
	client := newEventPipelineTestClient(t, timeNowMs()-1_000)
	wrapped := &table.WrappedMessage{
		LSInsertMessage: &table.LSInsertMessage{MessageId: "mid.thumb"},
		Stickers: []*table.LSInsertStickerAttachment{{
			TargetId: facebookThumbsUpSmallStickerID,
		}},
	}

	converted := client.convertWrappedMessage(wrapped)

	if converted.Text != "👍" || len(converted.Attachments) != 0 {
		t.Fatalf("converted thumbs-up = %#v, want emoji without sticker", converted)
	}
	if wrapped.Text != "" || len(wrapped.Stickers) != 1 {
		t.Fatalf("converter mutated wrapped input: %#v", wrapped)
	}
}

func TestHandleTableRejectsInvalidStandaloneUpserts(t *testing.T) {
	now := timeNowMs()
	client := newEventPipelineTestClient(t, now-1_000)
	client.handleTable(&table.LSTable{LSUpsertMessage: []*table.LSUpsertMessage{
		{ThreadKey: 100, SenderId: 200, TimestampMs: now},
		{MessageId: "mid.no-thread", SenderId: 200, TimestampMs: now},
		{MessageId: "mid.no-sender", ThreadKey: 100, TimestampMs: now},
		{
			MessageId:   "mid.unsent",
			ThreadKey:   100,
			SenderId:    200,
			TimestampMs: now,
			IsUnsent:    true,
		},
	}})

	if got := len(client.eventChan); got != 0 {
		t.Fatalf("emitted %d message events for invalid upserts, want 0", got)
	}
}

func TestHandleTableDeduplicatesUpsertAndInsertMessageID(t *testing.T) {
	now := timeNowMs()
	client := newEventPipelineTestClient(t, now-1_000)
	client.handleTable(&table.LSTable{
		LSUpsertMessage: []*table.LSUpsertMessage{{
			MessageId:   "mid.same",
			ThreadKey:   100,
			SenderId:    200,
			Text:        "upsert",
			TimestampMs: now,
		}},
		LSInsertMessage: []*table.LSInsertMessage{{
			MessageId:   "mid.same",
			ThreadKey:   100,
			SenderId:    200,
			Text:        "insert",
			TimestampMs: now,
		}},
	})

	if got := len(client.eventChan); got != 1 {
		t.Fatalf("emitted %d events for duplicate message ID, want 1", got)
	}
	event := <-client.eventChan
	message := event.Data.(*Message)
	if message.Text != "insert" {
		t.Fatalf("deduplicated message text = %q, want insert payload", message.Text)
	}

	client.handleTable(&table.LSTable{LSInsertMessage: []*table.LSInsertMessage{{
		MessageId:   "mid.same",
		ThreadKey:   100,
		SenderId:    200,
		Text:        "replayed",
		TimestampMs: now,
	}}})
	if got := len(client.eventChan); got != 0 {
		t.Fatalf("emitted %d events for cross-table duplicate, want 0", got)
	}
}

func TestAuthoritativeInsertSupersedesEarlierStandaloneUpsert(t *testing.T) {
	now := timeNowMs()
	client := newEventPipelineTestClient(t, now-1_000)
	client.handleTable(&table.LSTable{LSUpsertMessage: []*table.LSUpsertMessage{{
		MessageId:   "mid.upgraded",
		ThreadKey:   100,
		SenderId:    200,
		Text:        "Encrypted placeholder",
		TimestampMs: now,
	}}})

	first := <-client.eventChan
	if message := first.Data.(*Message); message.Text != "Encrypted placeholder" {
		t.Fatalf("standalone payload text = %q", message.Text)
	}

	client.handleTable(&table.LSTable{LSInsertMessage: []*table.LSInsertMessage{{
		MessageId:   "mid.upgraded",
		ThreadKey:   100,
		SenderId:    200,
		Text:        "/ping",
		TimestampMs: now,
	}}})

	if got := len(client.eventChan); got != 1 {
		t.Fatalf("authoritative insert emitted %d events, want 1", got)
	}
	upgraded := (<-client.eventChan).Data.(*Message)
	if upgraded.Text != "/ping" {
		t.Fatalf("authoritative payload text = %q, want /ping", upgraded.Text)
	}
}
