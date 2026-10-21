package main

import (
	"context"
	"errors"
	"slices"
	"strings"
	"testing"
)

func TestHelloPayloadDeclaresCompatibleContract(t *testing.T) {
	payload := helloPayload()

	if got := payload["protocolVersion"]; got != bridgeProtocolVersion {
		t.Fatalf("protocolVersion = %v, want %d", got, bridgeProtocolVersion)
	}
	if got := payload["bridgeVersion"]; got != bridgeVersion {
		t.Fatalf("bridgeVersion = %v, want %q", got, bridgeVersion)
	}

	capabilities, ok := payload["capabilities"].([]string)
	if !ok {
		t.Fatalf("capabilities has type %T, want []string", payload["capabilities"])
	}
	for _, required := range []string{
		"newClient",
		"connect",
		"connectE2EE",
		"isConnected",
		"events",
		"structuredConnectionStatus",
	} {
		if !slices.Contains(capabilities, required) {
			t.Errorf("capabilities does not contain %q", required)
		}
	}
}

func TestConnectionPayloadWithoutClientIsExplicitlyHealthyProcessOnly(t *testing.T) {
	payload := connectionPayload(nil)
	if payload["connected"] != false || payload["e2eeConnected"] != false ||
		payload["nativeReconnecting"] != false {
		t.Fatalf("nil client connection payload = %#v", payload)
	}
	for _, absent := range []string{"failureCode", "retryable", "permanent", "failureTransport"} {
		if _, exists := payload[absent]; exists {
			t.Fatalf("nil client payload unexpectedly contains %q", absent)
		}
	}
}

func TestFailureResponseAddsOnlyTypedStructuredClassification(t *testing.T) {
	network := failureResponse(7, context.DeadlineExceeded)
	if network.ErrorCode != "network_disconnected" || network.Retryable == nil ||
		!*network.Retryable {
		t.Fatalf("network failure response = %#v", network)
	}

	opaque := failureResponse(8, errors.New("opaque provider detail"))
	if opaque.ErrorCode != "" || opaque.Retryable != nil {
		t.Fatalf("opaque failure was guessed from text: %#v", opaque)
	}
}

func TestServeRequestsRejectsOversizedLine(t *testing.T) {
	input := strings.NewReader(strings.Repeat("x", 65) + "\n")

	err := serveRequests(input, 64)

	if err == nil {
		t.Fatal("serveRequests() accepted a request larger than its hard limit")
	}
}
