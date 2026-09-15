package main

import (
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
	for _, required := range []string{"newClient", "connect", "connectE2EE", "isConnected", "events"} {
		if !slices.Contains(capabilities, required) {
			t.Errorf("capabilities does not contain %q", required)
		}
	}
}

func TestServeRequestsRejectsOversizedLine(t *testing.T) {
	input := strings.NewReader(strings.Repeat("x", 65) + "\n")

	err := serveRequests(input, 64)

	if err == nil {
		t.Fatal("serveRequests() accepted a request larger than its hard limit")
	}
}
