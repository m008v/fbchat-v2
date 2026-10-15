package bridge

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"
)

func TestRedactingLogWriterHidesProviderIdentifiersAndCredentials(t *testing.T) {
	var output bytes.Buffer
	writer := newRedactingLogWriter(&output)
	input := `{"level":"warn","database_id":1,"readerId":"opaque-reader","threadName":"private group","thread_id":123456789012345,"message_id":"mid.123456789012345","cookie":"c_user=123456789; xs=secret","new_cursor":"opaque-sync-cursor","data":["private row"],"val":"private value","payload":{"text":"private message"},"error":"request https://example.test/path?access_token=secret for 123456789@msgr failed; <iq id=\"short-id\" from=\"12345@msgr\"><enc>ciphertext</enc></iq>"}` + "\n"
	if _, err := writer.Write([]byte(input)); err != nil {
		t.Fatalf("Write() error = %v", err)
	}

	var payload map[string]any
	if err := json.Unmarshal(output.Bytes(), &payload); err != nil {
		t.Fatalf("decode redacted log: %v", err)
	}
	if payload["database_id"] != float64(1) {
		t.Fatalf("database_id = %v, want 1", payload["database_id"])
	}
	for _, field := range []string{"readerId", "threadName", "thread_id", "message_id", "cookie", "new_cursor", "data", "val", "payload"} {
		if payload[field] != redactedLogValue {
			t.Errorf("%s = %v, want redacted", field, payload[field])
		}
	}
	serialized := output.String()
	for _, secret := range []string{"opaque-reader", "private group", "123456789012345", "123456789@msgr", "access_token=secret", "xs=secret", "private message", "opaque-sync-cursor", "private row", "private value", "short-id", "ciphertext"} {
		if strings.Contains(serialized, secret) {
			t.Errorf("redacted log still contains %q", secret)
		}
	}
}

func TestRedactingLogWriterHidesCompleteProtocolStanzas(t *testing.T) {
	var output bytes.Buffer
	writer := newRedactingLogWriter(&output)
	input := `{"level":"debug","message":"<iq id=\"short-id\"><identity>private-key-material</identity><list><key><value>prekey-material</value></key></list></iq>","component":"whatsmeow"}` + "\n"
	if _, err := writer.Write([]byte(input)); err != nil {
		t.Fatalf("Write() error = %v", err)
	}

	serialized := output.String()
	for _, secret := range []string{"short-id", "private-key-material", "prekey-material"} {
		if strings.Contains(serialized, secret) {
			t.Errorf("redacted stanza still contains %q", secret)
		}
	}
	if !strings.Contains(serialized, redactedLogValue) {
		t.Fatal("redacted stanza does not contain the redaction marker")
	}
}

func TestRedactingLogWriterBuffersPartialLines(t *testing.T) {
	var output bytes.Buffer
	writer := newRedactingLogWriter(&output)
	if _, err := writer.Write([]byte(`{"message":"user 123456789`)); err != nil {
		t.Fatalf("first Write() error = %v", err)
	}
	if output.Len() != 0 {
		t.Fatal("partial JSON line was emitted before newline")
	}
	if _, err := writer.Write([]byte(` connected"}` + "\n")); err != nil {
		t.Fatalf("second Write() error = %v", err)
	}
	if strings.Contains(output.String(), "123456789") {
		t.Fatal("partial log line identifier was not redacted")
	}
}
