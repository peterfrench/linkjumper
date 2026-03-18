#!/bin/bash
# Wrapper script called by launchd.
# 1. Ensures the 127.0.0.2 loopback alias exists (needed after reboot).
# 2. Starts the LinkJumper Python server.

set -euo pipefail

# Add loopback alias if not already present
if ! ifconfig lo0 | grep -q '127\.0\.0\.2'; then
    ifconfig lo0 alias 127.0.0.2 up
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec /usr/bin/python3 "${SCRIPT_DIR}/server.py"
