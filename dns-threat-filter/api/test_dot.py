import dns.query
import dns.message
import ssl
import sys

def test_dot(domain):
    print(f"\n--- Testing DoT resolution for: {domain} ---")
    try:
        # Create a DNS query for the A record
        q = dns.message.make_query(domain, dns.rdatatype.A)
        
        # We are using a self-signed certificate, so we must disable cert verification
        # (This is standard practice for local demonstration DoT testing)
        tls_context = ssl.create_default_context()
        tls_context.check_hostname = False
        tls_context.verify_mode = ssl.CERT_NONE

        # Send the query over TLS (DoT) to localhost:8530
        response = dns.query.tls(q, '127.0.0.1', port=8530, ssl_context=tls_context, timeout=5)
        
        print(f"Status: {dns.rcode.to_text(response.rcode())}")
        if response.answer:
            print("Answer section:")
            for answer in response.answer:
                print(f"  {answer}")
        else:
            print("Answer section: Empty (Blocked or NXDOMAIN)")
    except Exception as e:
        print(f"Error querying {domain}: {e}")

if __name__ == "__main__":
    test_dot("microsoft.com")
    test_dot("cvyh1po636avyrsxebwbkn7.ddns.net")
