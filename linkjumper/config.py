"""Shared constants, paths, and configuration helpers."""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
REDIRECTS_PATH = PROJECT_DIR / "redirects.json"
SETTINGS_PATH = PROJECT_DIR / "config.json"
CERT_DIR = PROJECT_DIR / "certs"
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
