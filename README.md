# LinkJumper

Local URL shortener for macOS. Create go-links that work in every browser and Spotlight.

```
go/gh       ->  https://github.com
go/mail     ->  https://mail.google.com
go/docs     ->  https://docs.google.com
```

Type `go/gh` in your browser instead of the full URL. Add a subpath like `go/gh/user/repo` and it passes through. Works with query strings too.

Shortcuts are searchable in Spotlight — press Cmd+Space, type "go gh", and hit Enter.

## Install

### Homebrew

```bash
brew tap peterfrench/linkjumper
brew install linkjumper
sudo linkjumper setup
```

### Manual

```bash
git clone https://github.com/peterfrench/linkjumper.git
cd linkjumper
sudo bash install.sh
```

Setup configures `/etc/hosts`, generates SSL certificates, trusts the CA in your keychain, and starts a background service via launchd. You'll be prompted for your password.

## Usage

### Managing shortcuts

```bash
linkjumper add gh https://github.com       # Add a shortcut
linkjumper add gh github.com               # https:// is added automatically
linkjumper add gh https://gitlab.com        # Update an existing one
linkjumper remove gh                        # Remove it
linkjumper list                             # List all shortcuts
linkjumper go gh                            # Open in default browser
```

The `linkj` alias works anywhere `linkjumper` does.

Changes take effect automatically — no restart needed.

### How redirects work

| You type | You get |
|---|---|
| `go/gh` | `https://github.com` |
| `go/gh/user/repo` | `https://github.com/user/repo` |
| `go/gh?tab=repos` | `https://github.com?tab=repos` |
| `go/gh/user/repo?tab=repos` | `https://github.com/user/repo?tab=repos` |

The root page (`http://go/`) shows a web UI where you can view, add, and remove shortcuts.

### Spotlight

Every shortcut gets a `.webloc` file in `~/Documents/LinkJumper/`. Press Cmd+Space, type the prefix and key (e.g. "go gh"), and hit Enter to open the link directly.

### Browser setup

Most browsers need a one-time configuration to recognize `go/` as a URL rather than a search query. Run:

```bash
linkjumper browser
```

This prints setup instructions for every browser it detects on your system (Chrome, Firefox, Safari, Arc, Edge, Brave, Vivaldi, Opera).

**Safari tip:** Add a trailing slash — `go/gh/` — and Safari navigates directly without any configuration.

## Configuration

### Change the prefix

The default prefix is `go`. Change it to anything you like:

```bash
sudo linkjumper config --prefix links
```

This updates `/etc/hosts`, regenerates the SSL certificate, renames your Spotlight files, and restarts the service. All your shortcuts now live under `links/` instead of `go/`.

### Auto-open

Automatically open shortcuts in your browser when you add them:

```bash
linkjumper config --auto-open true
```

### View config

```bash
linkjumper config
```

Prefix must start with a lowercase letter and contain only lowercase letters, numbers, and hyphens.

### Data directory

Shortcuts, settings, and certificates are stored in `/usr/local/etc/linkjumper/`. Override with the `LINKJUMPER_DATA_DIR` environment variable.

### Service control

```bash
sudo linkjumper start    # Start the service
sudo linkjumper stop     # Stop the service
```

The service runs as a launchd daemon and starts automatically at boot. Logs are at `/var/log/link-jumper.log`.

## Uninstall

```bash
# Homebrew
brew uninstall linkjumper

# Manual
sudo bash uninstall.sh
```

Teardown reverses all system changes (hosts entry, CA trust, launchd service, loopback alias, Spotlight files). Your `redirects.json` and `config.json` are preserved.

If the `linkjumper` command is unavailable (e.g. you already ran `brew uninstall`), use the standalone teardown script:

```bash
sudo bash teardown.sh
```

## Development

### Setup

```bash
git clone https://github.com/peterfrench/linkjumper.git
cd linkjumper
pip3 install -e .
```

Set `LINKJUMPER_DATA_DIR` to a local path during development to avoid touching `/usr/local/etc/linkjumper`:

```bash
export LINKJUMPER_DATA_DIR=./data
```

### Running tests

```bash
pip3 install pytest
pytest tests/ -v
```

All tests use temporary directories and mocked subprocesses — nothing touches your system.

### Project structure

```
linkjumper/
  __init__.py       # Package version
  __main__.py       # python -m linkjumper entry point
  cli.py            # All CLI commands and argument parsing
  config.py         # Paths, settings/redirects I/O, defaults
  server.py         # HTTP/HTTPS server with auto-reload
  certs.py          # SSL certificate generation and keychain trust
  system.py         # /etc/hosts, loopback alias, DNS, launchd
  webloc.py         # Spotlight .webloc file management
  browsers.py       # Browser detection and setup instructions
tests/
  conftest.py       # Shared fixtures (temp dirs, test HTTP server)
  test_config.py    # JSON I/O, defaults, roundtrips
  test_server.py    # HTTP handler routing, config reload
  test_webloc.py    # File creation, deletion, sync
  test_cli.py       # Command handlers
  test_system.py    # Hosts file regex, plist generation
  test_certs.py     # OpenSSL subprocess mocking
  test_browsers.py  # Browser detection
```

### How it works

LinkJumper binds a lightweight Python HTTP server to `127.0.0.2` on ports 80 and 443. An `/etc/hosts` entry maps your prefix (e.g. `go`) to that address. When you visit `go/gh`, the server looks up "gh" in `redirects.json` and returns a 302 redirect.

The server runs as a launchd daemon (`com.linkjumper.redirect`) that starts at boot and auto-restarts if it crashes. A file-watching thread reloads config every 2 seconds, so `linkjumper add/remove` works without restarting the service.

HTTPS uses a local CA certificate trusted in the macOS System keychain. The server certificate includes both the DNS name and the `127.0.0.2` IP as Subject Alternative Names.
