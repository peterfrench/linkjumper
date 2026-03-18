#!/bin/bash
# LinkJumper uninstaller.
# Runs teardown for system cleanup, then removes CLI symlinks.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 1. System teardown ───────────────────────────────────────────────────────
python3 "${SCRIPT_DIR}/cli.py" teardown

# ── 2. Remove CLI symlinks ───────────────────────────────────────────────────
if [ -L /usr/local/bin/linkjumper ] || [ -L /usr/local/bin/linkj ]; then
    echo "Removing CLI symlinks ..."
    sudo rm -f /usr/local/bin/linkjumper /usr/local/bin/linkj
    echo "  Done."
fi

echo ""
echo "Files in ${SCRIPT_DIR} were preserved."
echo "Delete the directory to fully remove: rm -rf ${SCRIPT_DIR}"
