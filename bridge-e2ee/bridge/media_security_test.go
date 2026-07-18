package bridge

import "testing"

func TestValidateMediaURL(t *testing.T) {
	tests := []struct {
		name    string
		url     string
		wantErr bool
	}{
		{name: "facebook CDN", url: "https://scontent.fsgn5-1.fna.fbcdn.net/file.jpg"},
		{name: "lookaside", url: "https://lookaside.fbsbx.com/file"},
		{name: "reject HTTP", url: "http://scontent.fbcdn.net/file", wantErr: true},
		{name: "reject private host", url: "https://127.0.0.1/admin", wantErr: true},
		{name: "reject suffix trick", url: "https://evilfbcdn.net/file", wantErr: true},
		{name: "reject user info", url: "https://user@facebook.com/file", wantErr: true},
		{name: "reject custom port", url: "https://facebook.com:8443/file", wantErr: true},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			_, err := validateMediaURL(test.url)
			if (err != nil) != test.wantErr {
				t.Fatalf("validateMediaURL(%q) error = %v, wantErr = %v", test.url, err, test.wantErr)
			}
		})
	}
}
