#!/bin/bash
# A unified local development startup script that runs the threat filter and the military intel app together

# Cleanup any previous background jobs on exit
trap 'kill $(jobs -p) 2>/dev/null' SIGINT SIGTERM EXIT

echo "Starting DNS Threat Filter backend & dashboard..."
export PORT=8502
(cd dns-threat-filter && source venv/bin/activate && ./start.sh) &

echo "Starting CoreDNS Threat Filter on port 1053..."
(cd dns-threat-filter/coredns-plugin && ./coredns -conf Corefile.dev) &

echo "Waiting for DNS Threat Filter API to become healthy..."
until curl -s http://localhost:8000/health | grep -q '"status":"ok"'; do
    sleep 1
done
echo "DNS Threat Filter is UP!"

echo "Starting Military Intel Platform with DNS Interceptor Enabled..."
export USE_THREAT_FILTER_DNS=1
cd military-intel-platform
source venv/bin/activate
# Install dnspython if missing
pip install -r requirements.txt > /dev/null
streamlit run app.py
