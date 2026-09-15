package bridge

import (
	"testing"
	"time"
)

func TestUnknownE2EESendResultDoesNotClaimDelivery(t *testing.T) {
	timestamp := time.UnixMilli(1_700_000_000_123)

	result := newUnknownE2EESendResult("mid-timeout", timestamp)

	if result.MessageID != "mid-timeout" {
		t.Fatalf("MessageID = %q, want mid-timeout", result.MessageID)
	}
	if result.TimestampMs != timestamp.UnixMilli() {
		t.Fatalf("TimestampMs = %d, want %d", result.TimestampMs, timestamp.UnixMilli())
	}
	if result.DeliveryStatus != DeliveryStatusUnknown {
		t.Fatalf("DeliveryStatus = %q, want %q", result.DeliveryStatus, DeliveryStatusUnknown)
	}
}
