"""Spotlight .webloc file management."""

from linkjumper.config import WEBLOC_DIR


def _webloc_path(prefix, key):
    return WEBLOC_DIR / f"{prefix} {key}.webloc"


def _webloc_xml(url):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"\n'
        '  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        '<dict>\n'
        '    <key>URL</key>\n'
        f'    <string>{url}</string>\n'
        '</dict>\n'
        '</plist>\n'
    )


def create_webloc(prefix, key, url):
    WEBLOC_DIR.mkdir(parents=True, exist_ok=True)
    _webloc_path(prefix, key).write_text(_webloc_xml(url))


def delete_webloc(prefix, key):
    _webloc_path(prefix, key).unlink(missing_ok=True)


def sync_weblocs(prefix, redirects):
    """Sync webloc files with current redirects: create missing, remove orphaned."""
    WEBLOC_DIR.mkdir(parents=True, exist_ok=True)

    for key, url in redirects.items():
        create_webloc(prefix, key, url)

    for f in WEBLOC_DIR.glob(f"{prefix} *.webloc"):
        stem = f.stem
        parts = stem.split(" ", 1)
        if len(parts) == 2 and parts[0] == prefix and parts[1] not in redirects:
            f.unlink()


def remove_all_weblocs(prefix):
    """Remove all webloc files for the given prefix."""
    if not WEBLOC_DIR.exists():
        return
    for f in WEBLOC_DIR.glob(f"{prefix} *.webloc"):
        f.unlink()
    try:
        WEBLOC_DIR.rmdir()
    except OSError:
        pass
