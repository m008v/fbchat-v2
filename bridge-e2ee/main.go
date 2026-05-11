// Standalone E2EE bridge for fbchat-v2.
//
// Communicates with the Python parent process over stdin/stdout using
// line-delimited JSON. Single-client per process (Python spawns one).
//
// Protocol
// --------
// Request  (Python -> bridge): one JSON object per line:
//     {"id": <int>, "method": "<name>", "params": {...}}
//
// Response (bridge -> Python): one JSON object per line:
//     {"id": <int>, "ok": true,  "data": {...}}
//     {"id": <int>, "ok": false, "error": "..."}
//
// Async event (bridge -> Python): one JSON object per line, no id:
//     {"event": {"type": "<name>", "data": {...}, "timestamp": <ms>}}
//
// Methods: newClient, connect, connectE2EE, isConnected, disconnect,
// sendMessage, sendE2EEMessage.
//
// Build:
//     go mod tidy
//     go build -ldflags="-s -w" -o ../build/fbchat-bridge-e2ee.exe .
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sync"

	"fbchat-bridge-e2ee/bridge"
)

type request struct {
	ID     uint64          `json:"id"`
	Method string          `json:"method"`
	Params json.RawMessage `json:"params"`
}

type response struct {
	ID    uint64      `json:"id"`
	OK    bool        `json:"ok"`
	Data  interface{} `json:"data,omitempty"`
	Error string      `json:"error,omitempty"`
}

type eventEnvelope struct {
	Event *bridge.Event `json:"event"`
}

var (
	client *bridge.Client
	stdoutMu sync.Mutex
)

func writeJSON(v interface{}) {
	stdoutMu.Lock()
	defer stdoutMu.Unlock()
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
}

func ok(id uint64, data interface{}) {
	writeJSON(response{ID: id, OK: true, Data: data})
}

func fail(id uint64, err error) {
	writeJSON(response{ID: id, OK: false, Error: err.Error()})
}

// pumpEvents copies events from the client to stdout asynchronously.
func pumpEvents(c *bridge.Client) {
	for evt := range c.Events() {
		if evt == nil {
			continue
		}
		writeJSON(eventEnvelope{Event: evt})
	}
}

func handle(req *request) {
	switch req.Method {
	case "newClient":
		if client != nil {
			fail(req.ID, fmt.Errorf("client already created"))
			return
		}
		var cfg bridge.ClientConfig
		if err := json.Unmarshal(req.Params, &cfg); err != nil {
			fail(req.ID, err)
			return
		}
		c, err := bridge.NewClient(&cfg)
		if err != nil {
			fail(req.ID, err)
			return
		}
		client = c
		go pumpEvents(client)
		ok(req.ID, map[string]interface{}{"ready": true})

	case "connect":
		if client == nil {
			fail(req.ID, fmt.Errorf("client not initialised"))
			return
		}
		user, initial, err := client.Connect()
		if err != nil {
			fail(req.ID, err)
			return
		}
		ok(req.ID, map[string]interface{}{
			"user":        user,
			"initialData": initial,
		})

	case "connectE2EE":
		if client == nil {
			fail(req.ID, fmt.Errorf("client not initialised"))
			return
		}
		if err := client.ConnectE2EE(); err != nil {
			fail(req.ID, err)
			return
		}
		ok(req.ID, map[string]interface{}{})

	case "isConnected":
		if client == nil {
			ok(req.ID, map[string]interface{}{"connected": false, "e2eeConnected": false})
			return
		}
		ok(req.ID, map[string]interface{}{
			"connected":     client.IsConnected(),
			"e2eeConnected": client.IsE2EEConnected(),
		})

	case "sendMessage":
		if client == nil {
			fail(req.ID, fmt.Errorf("client not initialised"))
			return
		}
		var opts bridge.SendMessageOptions
		if err := json.Unmarshal(req.Params, &opts); err != nil {
			fail(req.ID, err)
			return
		}
		res, err := client.SendMessage(&opts)
		if err != nil {
			fail(req.ID, err)
			return
		}
		ok(req.ID, res)

	case "sendE2EEMessage":
		if client == nil {
			fail(req.ID, fmt.Errorf("client not initialised"))
			return
		}
		var p struct {
			ChatJID          string `json:"chatJid"`
			Text             string `json:"text"`
			ReplyToID        string `json:"replyToId,omitempty"`
			ReplyToSenderJID string `json:"replyToSenderJid,omitempty"`
		}
		if err := json.Unmarshal(req.Params, &p); err != nil {
			fail(req.ID, err)
			return
		}
		res, err := client.SendMessage(&bridge.SendMessageOptions{
			Text:                 p.Text,
			IsE2EE:               true,
			E2EEChatJID:          p.ChatJID,
			E2EEReplyToID:        p.ReplyToID,
			E2EEReplyToSenderJID: p.ReplyToSenderJID,
		})
		if err != nil {
			fail(req.ID, err)
			return
		}
		ok(req.ID, res)

	case "disconnect":
		if client != nil {
			client.Disconnect()
			client = nil
		}
		ok(req.ID, map[string]interface{}{})

	default:
		fail(req.ID, fmt.Errorf("unknown method: %s", req.Method))
	}
}

func main() {
	// Use a large buffer because initial sync data can be substantial.
	reader := bufio.NewReaderSize(os.Stdin, 1<<20)
	for {
		line, err := reader.ReadBytes('\n')
		if len(line) > 0 {
			var req request
			if jerr := json.Unmarshal(line, &req); jerr != nil {
				fail(0, fmt.Errorf("invalid json: %w", jerr))
			} else {
				handle(&req)
			}
		}
		if err != nil {
			if err == io.EOF {
				if client != nil {
					client.Disconnect()
				}
				return
			}
			fmt.Fprintln(os.Stderr, "stdin error:", err)
			return
		}
	}
}
