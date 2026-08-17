// setup.go — Corefile parser and plugin registration for threatfilter.
//
// To include this plugin in CoreDNS:
//   1. Clone CoreDNS: git clone https://github.com/coredns/coredns.git
//   2. Copy this plugin dir into: coredns/plugin/threatfilter/
//   3. Add to coredns/plugin.cfg (before the forward line):
//        threatfilter:github.com/coredns/coredns/plugin/threatfilter
//   4. Run: make gen && make
//   5. The resulting ./coredns binary includes this plugin.
//
// Corefile usage:
//   .:1053 {
//       threatfilter http://localhost:8000
//       forward . 8.8.8.8
//       errors
//       log
//   }

package threatfilter

import (
	"time"

	"github.com/coredns/caddy"
	"github.com/coredns/coredns/core/dnsserver"
	"github.com/coredns/coredns/plugin"
	"net/http"
)

func init() {
	plugin.Register("threatfilter", setup)
}

func setup(c *caddy.Controller) error {
	tf, err := parseThreatFilter(c)
	if err != nil {
		return plugin.Error("threatfilter", err)
	}

	dnsserver.GetConfig(c).AddPlugin(func(next plugin.Handler) plugin.Handler {
		tf.Next = next
		return tf
	})
	return nil
}

func parseThreatFilter(c *caddy.Controller) (*ThreatFilter, error) {
	tf := &ThreatFilter{
		APIEndpoint: "http://localhost:8000",
		Client: &http.Client{
			Timeout: 2 * time.Second, // DNS clients time out fast; keep this tight
		},
	}

	for c.Next() {
		if c.NextArg() {
			tf.APIEndpoint = c.Val()
		}
	}
	return tf, nil
}
