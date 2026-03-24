"""macOS system-level operations: /etc/hosts, loopback, DNS, launchd."""

import re
import subprocess
import sys
import textwrap
from pathlib import Path

from linkjumper.config import (
    BIND_ADDR, ERR_PATH, LOG_PATH, PLIST_LABEL, PLIST_PATH,
)

# ---------------------------------------------------------------------------
# /etc/hosts
# ---------------------------------------------------------------------------


def has_hosts_entry(prefix):
    hosts = Path("/etc/hosts").read_text()
    return bool(re.search(rf"^{re.escape(BIND_ADDR)}\s+{re.escape(prefix)}$",
                           hosts, re.MULTILINE))


def add_hosts_entry(prefix):
    if has_hosts_entry(prefix):
        return False
    subprocess.run(
        f'echo "{BIND_ADDR}\t{prefix}" | sudo tee -a /etc/hosts >/dev/null',
        shell=True, check=True,
    )
    return True


def remove_hosts_entry(prefix):
    if not has_hosts_entry(prefix):
        return False
    subprocess.run(
        ["sudo", "sed", "-i", "",
         f"/^{re.escape(BIND_ADDR)}[[:space:]].*{re.escape(prefix)}$/d",
         "/etc/hosts"],
        check=True,
    )
    return True


# ---------------------------------------------------------------------------
# DNS
# ---------------------------------------------------------------------------

def flush_dns():
    subprocess.run(["sudo", "dscacheutil", "-flushcache"], check=True)
    subprocess.run(["sudo", "killall", "-HUP", "mDNSResponder"],
                   capture_output=True)


# ---------------------------------------------------------------------------
# Loopback alias
# ---------------------------------------------------------------------------

def has_loopback_alias():
    r = subprocess.run(["ifconfig", "lo0"], capture_output=True, text=True)
    return BIND_ADDR in r.stdout


def add_loopback_alias():
    if has_loopback_alias():
        return False
    subprocess.run(["sudo", "ifconfig", "lo0", "alias", BIND_ADDR, "up"],
                   check=True)
    return True


def remove_loopback_alias():
    if not has_loopback_alias():
        return False
    subprocess.run(["sudo", "ifconfig", "lo0", "-alias", BIND_ADDR], check=True)
    return True


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup_dotgo_artifacts():
    """Remove artifacts from the *.go DNS/HTTPS experiment if present."""
    resolver = Path("/etc/resolver/go")
    changed = False

    if resolver.exists():
        subprocess.run(["sudo", "rm", "-f", str(resolver)], check=True)
        print("      Cleaned up /etc/resolver/go")
        changed = True

    if changed:
        flush_dns()


# ---------------------------------------------------------------------------
# launchd
# ---------------------------------------------------------------------------

def build_plist():
    python = sys.executable
    # The parent of the linkjumper package directory
    package_root = str(Path(__file__).resolve().parent.parent)
    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
          "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{PLIST_LABEL}</string>

            <key>EnvironmentVariables</key>
            <dict>
                <key>PYTHONPATH</key>
                <string>{package_root}</string>
            </dict>

            <key>ProgramArguments</key>
            <array>
                <string>{python}</string>
                <string>-m</string>
                <string>linkjumper.server</string>
            </array>

            <key>RunAtLoad</key>
            <true/>

            <key>KeepAlive</key>
            <true/>

            <key>StandardOutPath</key>
            <string>{LOG_PATH}</string>

            <key>StandardErrorPath</key>
            <string>{ERR_PATH}</string>
        </dict>
        </plist>
    """)


def install_launchd():
    subprocess.run(
        ["sudo", "tee", PLIST_PATH],
        input=build_plist(), text=True,
        stdout=subprocess.DEVNULL, check=True,
    )
    subprocess.run(
        ["sudo", "launchctl", "bootout", f"system/{PLIST_LABEL}"],
        capture_output=True,
    )
    subprocess.run(
        ["sudo", "launchctl", "bootstrap", "system", PLIST_PATH],
        check=True,
    )


def remove_launchd():
    subprocess.run(
        ["sudo", "launchctl", "bootout", f"system/{PLIST_LABEL}"],
        capture_output=True,
    )
    subprocess.run(["sudo", "rm", "-f", PLIST_PATH], check=True)
