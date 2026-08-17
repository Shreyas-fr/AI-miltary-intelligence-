#!/usr/bin/env bash
# build_coredns.sh — Build a CoreDNS binary with the threatfilter plugin.
#
# Usage: ./build_coredns.sh
# Output: coredns-plugin/coredns (executable)
#
# Requirements: Go 1.21+, internet access (clones CoreDNS once)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$SCRIPT_DIR/coredns-plugin"
COREDNS_CLONE="$PLUGIN_DIR/.coredns-src"
COREDNS_VERSION="v1.11.3"

echo "==> Checking Go..."
export PATH=$PATH:/opt/homebrew/bin
go version

# 1. Clone CoreDNS source if not already present
if [ ! -d "$COREDNS_CLONE" ]; then
  echo "==> Cloning CoreDNS $COREDNS_VERSION..."
  git clone --depth=1 --branch "$COREDNS_VERSION" \
    https://github.com/coredns/coredns.git "$COREDNS_CLONE"
else
  echo "==> CoreDNS source already present at $COREDNS_CLONE"
fi

# 2. Copy plugin files into CoreDNS source tree
PLUGIN_TARGET="$COREDNS_CLONE/plugin/threatfilter"
mkdir -p "$PLUGIN_TARGET"
cp "$PLUGIN_DIR/threatfilter.go" "$PLUGIN_TARGET/"
cp "$PLUGIN_DIR/setup.go"        "$PLUGIN_TARGET/"
echo "==> Plugin files copied to $PLUGIN_TARGET"

# 3. Register plugin in plugin.cfg (idempotent — only adds if not already there)
PLUGIN_CFG="$COREDNS_CLONE/plugin.cfg"
if ! grep -q "threatfilter:" "$PLUGIN_CFG"; then
  # Insert before the 'forward' line so it runs first in the chain
  sed -i.bak '/^forward:/i threatfilter:github.com/coredns/coredns/plugin/threatfilter' "$PLUGIN_CFG"
  echo "==> Registered threatfilter in plugin.cfg"
else
  echo "==> threatfilter already in plugin.cfg"
fi

# 4. Rebuild generated code and compile
cd "$COREDNS_CLONE"
echo "==> Running go generate..."
go generate ./...
echo "==> Building CoreDNS with threatfilter plugin..."
go build -o "$PLUGIN_DIR/coredns" .
echo ""
echo "✅  Build complete: $PLUGIN_DIR/coredns"
echo ""
echo "To run (dev, port 1053):"
echo "  cd dns-threat-filter/coredns-plugin"
echo "  ./coredns -conf Corefile.dev"
