import subprocess
import urllib.parse
import json
import urllib.request
import sys

def get_chrome_urls():
    applescript = """
    tell application "Google Chrome"
        set urlList to ""
        repeat with w in windows
            repeat with t in tabs of w
                set urlList to urlList & URL of t & "\\n"
            end repeat
        end repeat
        return urlList
    end tell
    """
    try:
        result = subprocess.run(['osascript', '-e', applescript], capture_output=True, text=True, check=True)
        # Split by newline and remove empty strings
        urls = [url.strip() for url in result.stdout.split('\\n') if url.strip()]
        return urls
    except subprocess.CalledProcessError as e:
        print(f"Error running AppleScript. Is Google Chrome running? {e}")
        return []

def scan_domain(domain):
    url = "http://localhost:8000/check"
    data = json.dumps({"domain": domain}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result
    except Exception as e:
        print(f"Error scanning domain {domain}: {e}")
        return None

def main():
    print("Fetching active tabs from Google Chrome...")
    urls = get_chrome_urls()
    
    if not urls:
        print("No open tabs found in Google Chrome or Chrome is not running.")
        sys.exit(0)
        
    print(f"Found {len(urls)} open tab(s). Extracting domains...")
    
    # Extract unique domains
    domains = set()
    for url in urls:
        # Some internal chrome URLs (like chrome://extensions) don't have a normal hostname
        parsed = urllib.parse.urlparse(url)
        if parsed.hostname:
            domains.add(parsed.hostname)
            
    if not domains:
        print("No scannable domains found in your tabs.")
        sys.exit(0)
        
    print(f"Scanning {len(domains)} unique domain(s) against the DNS Threat Filter...\\n")
    
    blocked_count = 0
    
    for domain in domains:
        result = scan_domain(domain)
        if not result:
            continue
            
        verdict = result.get("verdict")
        source = result.get("source")
        
        if verdict == "BLOCKED":
            blocked_count += 1
            print(f"🚨 BLOCKED : {domain} (Source: {source})")
        else:
            print(f"✅ ALLOWED : {domain}")
            
    print("\\n--- Scan Complete ---")
    if blocked_count > 0:
        print(f"⚠️  WARNING: Found {blocked_count} potentially malicious domain(s) open in your tabs!")
    else:
        print("🎉 All your open tabs look safe!")

if __name__ == "__main__":
    main()
