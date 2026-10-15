package bridge

import (
	"bytes"
	"encoding/json"
	"io"
	"regexp"
	"strings"
	"sync"
)

const redactedLogValue = "[redacted]"

var (
	logCookiePattern = regexp.MustCompile(`(?i)\b(c_user|xs|fr|datr|sb|presence|access_token)=([^;\s]+)`)
	logJIDPattern    = regexp.MustCompile(`\b[0-9]{5,}:[0-9]+@[A-Za-z0-9._-]+\b|\b[0-9]{5,}@[A-Za-z0-9._-]+\b`)
	logIDPattern     = regexp.MustCompile(`\b[0-9]{7,}\b`)
	logUUIDPattern   = regexp.MustCompile(`(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b`)
	logURLQuery      = regexp.MustCompile(`(https?://[^\s?"']+)\?[^\s"']+`)
	logXMLTagPattern = regexp.MustCompile(`(?i)</?[a-z][^>]*>`)
)

type redactingLogWriter struct {
	mu      sync.Mutex
	out     io.Writer
	pending []byte
}

func newRedactingLogWriter(out io.Writer) io.Writer {
	return &redactingLogWriter{out: out}
}

func normalizeLogKey(key string) string {
	return strings.NewReplacer("_", "", "-", "").Replace(strings.ToLower(key))
}

func isSensitiveLogKey(key string) bool {
	normalized := normalizeLogKey(key)
	if strings.HasSuffix(normalized, "id") && normalized != "databaseid" && normalized != "streamid" {
		return true
	}
	if strings.Contains(normalized, "cookie") ||
		strings.Contains(normalized, "token") ||
		strings.Contains(normalized, "secret") ||
		strings.Contains(normalized, "password") ||
		strings.Contains(normalized, "authorization") ||
		strings.Contains(normalized, "cursor") ||
		strings.Contains(normalized, "prekey") {
		return true
	}
	switch normalized {
	case "id", "fbid", "facebookid", "userid", "senderid", "threadid", "messageid", "chatjid", "senderjid", "jid", "deviceid", "registrationid", "epochid", "sessionid", "name", "threadname", "sendername", "username", "displayname", "url", "imageurl", "profileurl", "attachments", "payload", "body", "text", "content", "raw", "request", "response", "data", "val", "value", "config", "configs", "database", "syncparams", "blockresponse", "fullblock", "ptks", "key", "identity", "identitykey", "signature", "registration", "routinginfo":
		return true
	default:
		return false
	}
}

func redactLogString(value string) string {
	if logXMLTagPattern.MatchString(value) {
		return redactedLogValue
	}
	value = logCookiePattern.ReplaceAllString(value, `$1=`+redactedLogValue)
	value = logURLQuery.ReplaceAllString(value, `$1?`+redactedLogValue)
	value = logJIDPattern.ReplaceAllString(value, redactedLogValue)
	value = logUUIDPattern.ReplaceAllString(value, redactedLogValue)
	return logIDPattern.ReplaceAllString(value, redactedLogValue)
}

func redactLogObject(value any) any {
	switch typed := value.(type) {
	case map[string]any:
		for key, nested := range typed {
			if isSensitiveLogKey(key) {
				typed[key] = redactedLogValue
			} else {
				typed[key] = redactLogObject(nested)
			}
		}
		return typed
	case []any:
		for index, nested := range typed {
			typed[index] = redactLogObject(nested)
		}
		return typed
	case string:
		return redactLogString(typed)
	default:
		return value
	}
}

func redactLogLine(line []byte) []byte {
	trimmed := bytes.TrimSpace(line)
	if len(trimmed) == 0 {
		return []byte("\n")
	}
	var payload map[string]any
	if err := json.Unmarshal(trimmed, &payload); err != nil {
		return append([]byte(redactLogString(string(trimmed))), '\n')
	}
	redacted, err := json.Marshal(redactLogObject(payload))
	if err != nil {
		return []byte("{\"level\":\"error\",\"message\":\"log redaction failed\"}\n")
	}
	return append(redacted, '\n')
}

func (writer *redactingLogWriter) Write(input []byte) (int, error) {
	writer.mu.Lock()
	defer writer.mu.Unlock()

	writtenInput := len(input)
	writer.pending = append(writer.pending, input...)
	for {
		newline := bytes.IndexByte(writer.pending, '\n')
		if newline < 0 {
			break
		}
		line := writer.pending[:newline]
		writer.pending = writer.pending[newline+1:]
		if _, err := writer.out.Write(redactLogLine(line)); err != nil {
			return 0, err
		}
	}
	return writtenInput, nil
}
