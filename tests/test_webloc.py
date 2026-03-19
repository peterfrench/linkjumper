"""Tests for linkjumper.webloc — .webloc file creation, deletion, and sync."""

from linkjumper.webloc import (
    create_webloc,
    delete_webloc,
    remove_all_weblocs,
    sync_weblocs,
)


def test_create_webloc_creates_file(tmp_webloc_dir):
    create_webloc("go", "gh", "https://github.com")
    path = tmp_webloc_dir / "go gh.webloc"
    assert path.exists()
    content = path.read_text()
    assert "https://github.com" in content
    assert "<plist" in content


def test_create_webloc_creates_dir(tmp_webloc_dir):
    """WEBLOC_DIR is created on demand if it doesn't exist."""
    assert not tmp_webloc_dir.exists()
    create_webloc("go", "gh", "https://github.com")
    assert tmp_webloc_dir.is_dir()


def test_delete_webloc_removes_file(tmp_webloc_dir):
    create_webloc("go", "gh", "https://github.com")
    path = tmp_webloc_dir / "go gh.webloc"
    assert path.exists()
    delete_webloc("go", "gh")
    assert not path.exists()


def test_delete_webloc_missing_is_noop(tmp_webloc_dir):
    """No error when the file doesn't exist."""
    delete_webloc("go", "nonexistent")


def test_sync_weblocs_creates_missing(tmp_webloc_dir):
    redirects = {"gh": "https://github.com", "mail": "https://mail.google.com"}
    sync_weblocs("go", redirects)
    assert (tmp_webloc_dir / "go gh.webloc").exists()
    assert (tmp_webloc_dir / "go mail.webloc").exists()


def test_sync_weblocs_removes_orphaned(tmp_webloc_dir):
    """Stale webloc files deleted, current ones kept."""
    tmp_webloc_dir.mkdir(parents=True)
    (tmp_webloc_dir / "go old.webloc").write_text("stale")
    (tmp_webloc_dir / "go gh.webloc").write_text("existing")

    sync_weblocs("go", {"gh": "https://github.com"})

    assert (tmp_webloc_dir / "go gh.webloc").exists()
    assert not (tmp_webloc_dir / "go old.webloc").exists()


def test_sync_weblocs_ignores_unrelated_files(tmp_webloc_dir):
    """Files that don't match the prefix pattern are left alone."""
    tmp_webloc_dir.mkdir(parents=True)
    notes = tmp_webloc_dir / "notes.txt"
    notes.write_text("keep me")
    other_prefix = tmp_webloc_dir / "other gh.webloc"
    other_prefix.write_text("different prefix")

    sync_weblocs("go", {"gh": "https://github.com"})

    assert notes.exists()
    assert other_prefix.exists()


def test_remove_all_weblocs(tmp_webloc_dir):
    tmp_webloc_dir.mkdir(parents=True)
    (tmp_webloc_dir / "go gh.webloc").write_text("x")
    (tmp_webloc_dir / "go mail.webloc").write_text("x")

    remove_all_weblocs("go")

    assert not (tmp_webloc_dir / "go gh.webloc").exists()
    assert not (tmp_webloc_dir / "go mail.webloc").exists()


def test_remove_all_weblocs_removes_empty_dir(tmp_webloc_dir):
    """Directory is removed if empty after cleanup."""
    tmp_webloc_dir.mkdir(parents=True)
    (tmp_webloc_dir / "go gh.webloc").write_text("x")

    remove_all_weblocs("go")

    assert not tmp_webloc_dir.exists()
