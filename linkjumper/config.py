"""Shared constants, paths, and configuration helpers."""

import json
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.environ.get("LINKJUMPER_DATA_DIR", "/usr/local/etc/linkjumper"))
REDIRECTS_PATH = DATA_DIR / "redirects.json"
SETTINGS_PATH = DATA_DIR / "config.json"
CERT_DIR = DATA_DIR / "certs"
WEBLOC_DIR = Path.home() / "Documents" / "LinkJumper"

PLIST_LABEL = "com.linkjumper.redirect"
PLIST_PATH = f"/Library/LaunchDaemons/{PLIST_LABEL}.plist"

BIND_ADDR = "127.0.0.2"
LOG_PATH = "/var/log/link-jumper.log"
ERR_PATH = "/var/log/link-jumper.err"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def load_settings():
    try:
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"prefix": "go"}


def save_settings(settings):
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")


def get_prefix():
    return load_settings().get("prefix", "go")


def ensure_data_dir():
    """Create the data directory if it doesn't exist.

    When run under sudo, chown the directory and all files inside it
    to the real user so non-root commands (add, remove, list) can
    read/write config files.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    uid = int(os.environ.get("SUDO_UID", -1))
    gid = int(os.environ.get("SUDO_GID", -1))
    if uid >= 0:
        os.chown(DATA_DIR, uid, gid)
        for f in DATA_DIR.iterdir():
            if f.is_file():
                os.chown(f, uid, gid)


# ---------------------------------------------------------------------------
# Redirects
# ---------------------------------------------------------------------------

DEFAULT_REDIRECTS = {
    "gh": "https://github.com",
    "mail": "https://mail.google.com",
    "cal": "https://calendar.google.com",
    "docs": "https://docs.google.com",
    "drive": "https://drive.google.com",
    "yt": "https://youtube.com",
}


def load_redirects():
    try:
        with open(REDIRECTS_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_redirects(redirects):
    with open(REDIRECTS_PATH, "w") as f:
        json.dump(redirects, f, indent=2)
        f.write("\n")
