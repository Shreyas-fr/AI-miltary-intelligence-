// threatfilter.go — ServeDNS handler for the threatfilter CoreDNS plugin.
//
// For every A/AAAA query:
//   1. POST the domain to the FastAPI /check endpoint.
//   2. If verdict == "BLOCKED" → return NXDOMAIN immediately.
//   3. Otherwise → forward to the next plugin in the chain (typically `forward`).
//
// If the FastAPI service is unreachable (timeout / connection refused), the plugin
// fails OPEN — it forwards the query rather than blocking everything. This is a
// deliberate Milestone 1 choice: the plugin is a filter, not a firewall. Milestone 2
// will add a configurable fail-closed option.

package threatfilter

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	"github.com/coredns/coredns/plugin"
	"github.com/miekg/dns"
)

// ThreatFilter holds the plugin configuration and next handler.
type ThreatFilter struct {
	Next        plugin.Handler
	APIEndpoint string
	Client      *http.Client
}

// Name returns the plugin name (must match plugin.cfg registration).
func (tf ThreatFilter) Name() string { return "threatfilter" }

type checkRequest struct {
	Domain string `json:"domain"`
}

type checkResponse struct {
	Domain        string   `json:"domain"`
	Verdict       string   `json:"verdict"`
	Source        *string  `json:"source"`
	DGAScore      *float64 `json:"dga_score"`
	URLhausStatus string   `json:"urlhaus_status"`
}

// ServeDNS intercepts every DNS query.
func (tf ThreatFilter) ServeDNS(ctx context.Context, w dns.ResponseWriter, r *dns.Msg) (int, error) {
	// Only inspect A and AAAA queries; pass everything else through.
	if len(r.Question) == 0 {
		return plugin.NextOrFailure(tf.Name(), tf.Next, ctx, w, r)
	}
	q := r.Question[0]
	if q.Qtype != dns.TypeA && q.Qtype != dns.TypeAAAA {
		return plugin.NextOrFailure(tf.Name(), tf.Next, ctx, w, r)
	}

	domain := strings.TrimSuffix(q.Name, ".")

	verdict, err := tf.checkDomain(domain)
	if err != nil {
		// FastAPI unreachable — fail open, log and forward.
		fmt.Printf("[threatfilter] WARNING: API unreachable for %s: %v — failing open\n", domain, err)
		return plugin.NextOrFailure(tf.Name(), tf.Next, ctx, w, r)
	}

	if verdict == "BLOCKED" {
		fmt.Printf("[threatfilter] BLOCKED: %s\n", domain)
		m := new(dns.Msg)
		m.SetReply(r)
		m.SetRcode(r, dns.RcodeNameError) // NXDOMAIN
		m.Authoritative = true
		w.WriteMsg(m)
		return dns.RcodeNameError, nil
	}

	fmt.Printf("[threatfilter] ALLOW:   %s\n", domain)
	return plugin.NextOrFailure(tf.Name(), tf.Next, ctx, w, r)
}

func (tf ThreatFilter) checkDomain(domain string) (string, error) {
	payload, _ := json.Marshal(checkRequest{Domain: domain})
	resp, err := tf.Client.Post(
		tf.APIEndpoint+"/check",
		"application/json",
		bytes.NewReader(payload),
	)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}

	var cr checkResponse
	if err := json.Unmarshal(body, &cr); err != nil {
		return "", fmt.Errorf("invalid JSON from API: %w", err)
	}
	return cr.Verdict, nil
}
