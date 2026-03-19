"""Tests for linkjumper.certs — openssl subprocess and CA trust."""

from unittest.mock import MagicMock

import pytest

from linkjumper.certs import _run_openssl, generate_certs, remove_ca_trust


# ---------------------------------------------------------------------------
# _run_openssl
# ---------------------------------------------------------------------------


def test_run_openssl_success(monkeypatch):
    mock = MagicMock(return_value=MagicMock(returncode=0, stderr="", stdout=""))
    monkeypatch.setattr("subprocess.run", mock)

    _run_openssl(["openssl", "version"])

    mock.assert_called_once()


def test_run_openssl_failure_raises(monkeypatch):
    mock = MagicMock(
        return_value=MagicMock(returncode=1, stderr="some error", stdout="")
    )
    monkeypatch.setattr("subprocess.run", mock)

    with pytest.raises(RuntimeError, match="openssl failed"):
        _run_openssl(["openssl", "version"])


# ---------------------------------------------------------------------------
# generate_certs
# ---------------------------------------------------------------------------


def test_generate_certs_creates_ca_when_missing(tmp_project_dir, monkeypatch):
    calls = []
    monkeypatch.setattr("linkjumper.certs._run_openssl", lambda cmd: calls.append(cmd))
    monkeypatch.setattr("linkjumper.certs.sign_server_cert", lambda p: None)

    generate_certs("go")

    # CA key + CA cert + server key = 3 openssl calls
    assert len(calls) == 3
    assert "genrsa" in calls[0]  # CA key
    assert "req" in calls[1]      # CA cert
    assert "genrsa" in calls[2]  # server key


def test_generate_certs_skips_ca_when_present(tmp_project_dir, monkeypatch):
    cert_dir = tmp_project_dir / "certs"
    (cert_dir / "ca-key.pem").write_text("fake-key")
    (cert_dir / "ca.pem").write_text("fake-cert")

    calls = []
    monkeypatch.setattr("linkjumper.certs._run_openssl", lambda cmd: calls.append(cmd))
    monkeypatch.setattr("linkjumper.certs.sign_server_cert", lambda p: None)

    generate_certs("go")

    # Only server key generated (CA skipped)
    assert len(calls) == 1
    assert "genrsa" in calls[0]


# ---------------------------------------------------------------------------
# remove_ca_trust
# ---------------------------------------------------------------------------


def test_remove_ca_trust_parses_hashes(monkeypatch):
    """SHA-1 hashes are extracted and used in delete-certificate calls."""
    fake_find_output = (
        "SHA-1 hash: AABBCCDD1122334455667788990011AABBCCDDEE\n"
        "SHA-1 hash: 112233445566778899AABBCCDDEEFF0011223344\n"
    )
    delete_calls = []

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        if isinstance(cmd, list) and "find-certificate" in cmd:
            result.returncode = 0
            result.stdout = fake_find_output
        elif isinstance(cmd, list) and "delete-certificate" in cmd:
            result.returncode = 0
            delete_calls.append(cmd)
        else:
            result.returncode = 0
        return result

    monkeypatch.setattr("subprocess.run", mock_run)

    assert remove_ca_trust() is True
    assert len(delete_calls) == 2
    # Each delete call should contain the corresponding hash
    assert "AABBCCDD1122334455667788990011AABBCCDDEE" in delete_calls[0]
    assert "112233445566778899AABBCCDDEEFF0011223344" in delete_calls[1]
