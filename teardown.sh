#!/bin/bash
# Standalone LinkJumper teardown script.
# Reverses all system-level changes WITHOUT depending on the linkjumper binary.
#
# Usage:
#   sudo bash teardown.sh                  # auto-detects prefix
#   sudo bash teardown.sh --prefix go      # explicit prefix
#
# Use this if you ran `brew uninstall linkjumper` before running teardown,
# or if the linkjumper binary is otherwise unavailable.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_LABEL="com.linkjumper.redirect"
PLIST_PATH="/Library/LaunchDaemons/${PLIST_LABEL}.plist"
BIND_ADDR="127.0.0.2"
PREFIX=""

# ── Parse arguments ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --prefix) PREFIX="$2"; shift 2 ;;
        --prefix=*) PREFIX="${1#*=}"; shift ;;
        -h|--help)
            echo "Usage: sudo bash teardown.sh [--prefix <prefix>]"
            echo ""
            echo "Reverses all LinkJumper system changes (hosts, launchd, loopback)."
            echo "Auto-detects the prefix from config.json if not specified."
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Detect prefix if not provided ────────────────────────────────────────────
if [ -z "$PREFIX" ]; then
    for cfg in \
        "${SCRIPT_DIR}/config.json" \
        "/usr/local/etc/linkjumper/config.json"; do
        if [ -f "$cfg" ]; then
            PREFIX=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('prefix','go'))" "$cfg" 2>/dev/null || true)
            [ -n "$PREFIX" ] && break
        fi
    done
    PREFIX="${PREFIX:-go}"
fi

echo "=== LinkJumper — Standalone Teardown ==="
echo "  Prefix: ${PREFIX}"
echo ""

# ── 0. Clean up *.go experiment artifacts ────────────────────────────────────
if [ -f /etc/resolver/go ]; then
    echo "Cleaning up /etc/resolver/go ..."
    rm -f /etc/resolver/go
fi
for ca_path in \
    "${SCRIPT_DIR}/certs/ca.pem" \
    "/usr/local/etc/linkjumper/certs/ca.pem"; do
    if [ -f "$ca_path" ]; then
        echo "Removing old CA certificate from keychain ..."
        security remove-trusted-cert -d "$ca_path" 2>/dev/null || true
        break
    fi
done

# ── 1. Stop and remove launchd service ───────────────────────────────────────
if [ -f "${PLIST_PATH}" ]; then
    echo "[1/3] Stopping and removing service ..."
    launchctl bootout "system/${PLIST_LABEL}" 2>/dev/null || true
    rm -f "${PLIST_PATH}"
    echo "      Done."
else
    echo "[1/3] No launchd service found — skipping."
fi

# ── 2. Remove /etc/hosts entry ───────────────────────────────────────────────
if grep -q "^${BIND_ADDR}[[:space:]].*${PREFIX}$" /etc/hosts 2>/dev/null; then
    echo "[2/3] Removing '${PREFIX}' from /etc/hosts ..."
    sed -i '' "/^${BIND_ADDR}[[:space:]].*${PREFIX}$/d" /etc/hosts
    dscacheutil -flushcache
    killall -HUP mDNSResponder 2>/dev/null || true
    echo "      Done. DNS cache flushed."
else
    echo "[2/3] No '${PREFIX}' entry in /etc/hosts — skipping."
fi

# ── 3. Remove loopback alias ─────────────────────────────────────────────────
if ifconfig lo0 | grep -q "${BIND_ADDR}"; then
    echo "[3/3] Removing loopback alias ${BIND_ADDR} ..."
    ifconfig lo0 -alias "${BIND_ADDR}"
    echo "      Done."
else
    echo "[3/3] No loopback alias found — skipping."
fi

echo ""
echo "=== Teardown complete ==="
