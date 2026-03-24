#!/bin/bash
# LinkJumper uninstaller.
# Runs teardown for system cleanup, then removes CLI wrappers.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 1. System teardown ───────────────────────────────────────────────────────
PYTHONPATH="${SCRIPT_DIR}" /usr/bin/python3 -m linkjumper teardown

# ── 2. Remove CLI wrappers ───────────────────────────────────────────────────
echo "Removing CLI wrappers ..."
sudo rm -f /usr/local/bin/linkjumper /usr/local/bin/linkj
echo "  Done."

echo ""
echo "Files in ${SCRIPT_DIR} were preserved."
echo "Delete the directory to fully remove: rm -rf ${SCRIPT_DIR}"
