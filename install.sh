#!/bin/bash
# LinkJumper installer.
# Installs the package via pip, then runs `linkjumper setup` for system configuration.
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

# ── 2. Install package ──────────────────────────────────────────────────────
echo "Installing linkjumper ..."
pip3 install -e "${SCRIPT_DIR}"
echo ""

# ── 3. Run setup ─────────────────────────────────────────────────────────────
exec sudo linkjumper setup
