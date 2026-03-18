#!/bin/bash
# LinkJumper installer.
# Installs CLI symlinks, then runs `linkjumper setup` for system configuration.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== LinkJumper — Install ==="
echo ""

# ── 1. Check Python 3 ────────────────────────────────────────────────────────
if ! /usr/bin/python3 --version &>/dev/null; then
    echo "Error: python3 not found. Install Xcode CLI tools: xcode-select --install"
    exit 1
fi
echo "Python 3 found: $(/usr/bin/python3 --version)"

# ── 2. Install CLI symlinks ──────────────────────────────────────────────────
echo "Installing CLI symlinks ..."
chmod +x "${SCRIPT_DIR}/cli.py" "${SCRIPT_DIR}/start.sh"
sudo mkdir -p /usr/local/bin
sudo ln -sf "${SCRIPT_DIR}/cli.py" /usr/local/bin/linkjumper
sudo ln -sf /usr/local/bin/linkjumper /usr/local/bin/linkj
echo "  Installed: linkjumper, linkj"
echo ""

# ── 3. Run setup ─────────────────────────────────────────────────────────────
exec python3 "${SCRIPT_DIR}/cli.py" setup
