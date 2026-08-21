import os
import socket
import logging

logger = logging.getLogger(__name__)
# Keep a reference to the original, un-patched function
_original_getaddrinfo = socket.getaddrinfo
_patched = False

def init_dns_interceptor():
    global _patched
    if _patched:
        return
        
    if os.environ.get("USE_THREAT_FILTER_DNS") != "1":
        # Do absolutely nothing if the env var isn't set (e.g., in production)
        return
        
    try:
        import dns.resolver
        import dns.exception
    except ImportError:
        logger.warning("[DNS Fallback] dnspython not installed. Cannot intercept DNS. Using default resolver.")
        return

    # Configure a custom resolver that explicitly targets our local CoreDNS threat filter
    custom_resolver = dns.resolver.Resolver(configure=False)
    custom_resolver.nameservers = ["127.0.0.1"]
    custom_resolver.port = 1053
    # Short timeouts so we fail fast if the filter isn't running
    custom_resolver.timeout = 1.0
    custom_resolver.lifetime = 1.0

    def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        # We only want to intercept IPv4 (A) or IPv6 (AAAA) lookups for actual hostnames
        # If it's already an IP address, the original getaddrinfo handles it instantly.
        # This simple check avoids parsing IPs:
        is_ip = False
        try:
            socket.inet_aton(host)
            is_ip = True
        except (socket.error, TypeError):
            pass
            
        try:
            socket.inet_pton(socket.AF_INET6, host)
            is_ip = True
        except (socket.error, TypeError, ValueError):
            pass

        if not is_ip and host and host != "localhost":
            try:
                # Query our custom CoreDNS resolver
                answer = custom_resolver.resolve(host, 'A')
                ip_address = answer[0].to_text()
                
                # Now that we have the IP from our filter, pass THAT back into the original 
                # getaddrinfo to return the exact tuple format expected by standard library sockets.
                # This ensures compatibility with httpx, requests, asyncio, etc.
                return _original_getaddrinfo(ip_address, port, family, type, proto, flags)
            except dns.resolver.NXDOMAIN:
                # Domain is blocked by the threat filter — do NOT fall back to system DNS
                logger.warning(f"🚨 [DNS Threat Filter] Blocked connection to: {host}")
                try:
                    from streamlit.runtime.scriptrunner import get_script_run_ctx
                    import streamlit as st
                    ctx = get_script_run_ctx()
                    if ctx:
                        if "dns_blocks" not in st.session_state:
                            st.session_state["dns_blocks"] = []
                        if host not in st.session_state["dns_blocks"]:
                            st.session_state["dns_blocks"].append(host)
                except Exception as ctx_e:
                    logger.warning(f"Failed to notify UI of block: {ctx_e}")
                raise socket.gaierror(socket.EAI_NONAME, f"Name or service not known (Blocked by Threat Filter): {host}")
                
            except (dns.exception.Timeout, dns.resolver.NoNameservers, ConnectionRefusedError, Exception) as e:
                # Fail-safe: filter is unreachable — fall back to system DNS gracefully
                logger.warning(f"⚠️ [DNS Fallback] CoreDNS filter unreachable for '{host}' ({e.__class__.__name__}). Falling back to system DNS.")
                return _original_getaddrinfo(host, port, family, type, proto, flags)
                
        # For localhost or direct IPs, just use the original resolver
        return _original_getaddrinfo(host, port, family, type, proto, flags)

    # Apply the monkey patch
    socket.getaddrinfo = _patched_getaddrinfo
    _patched = True
    print("🛡️  [DNS Interceptor] Active: Routing outbound queries to localhost:1053")

