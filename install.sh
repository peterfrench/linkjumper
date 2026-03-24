#!/bin/bash
# LinkJumper installer.
# Creates CLI wrappers in /usr/local/bin, then runs setup for system configuration.
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

# ── 2. Install CLI wrappers ──────────────────────────────────────────────────
echo "Installing linkjumper to /usr/local/bin ..."
sudo mkdir -p /usr/local/bin

sudo tee /usr/local/bin/linkjumper >/dev/null <<EOF
#!/bin/bash
PYTHONPATH="${SCRIPT_DIR}" exec /usr/bin/python3 -m linkjumper "\$@"
EOF
sudo chmod +x /usr/local/bin/linkjumper
sudo ln -sf /usr/local/bin/linkjumper /usr/local/bin/linkj

echo "  Installed: linkjumper, linkj"
echo ""

# ── 3. Run setup ─────────────────────────────────────────────────────────────
exec sudo linkjumper setup
