"""Certificate generation and macOS keychain trust management."""

import re
import subprocess
import tempfile
from pathlib import Path

from linkjumper.config import BIND_ADDR, CERT_DIR


def generate_certs(prefix):
    """Generate CA (if missing) and server certificate for the prefix hostname."""
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    ca_key = CERT_DIR / "ca-key.pem"
    ca_cert = CERT_DIR / "ca.pem"
    srv_key = CERT_DIR / "server-key.pem"

    # CA
    if not ca_key.exists() or not ca_cert.exists():
        _run_openssl(
            ["openssl", "genrsa", "-out", str(ca_key), "2048"],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            ca_cnf = Path(tmpdir) / "ca.cnf"
            ca_cnf.write_text(
                "[req]\n"
                "distinguished_name = dn\n"
                "prompt = no\n"
                "x509_extensions = v3_ca\n"
                "[dn]\n"
                "CN = LinkJumper Local CA\n"
                "[v3_ca]\n"
                "basicConstraints = critical, CA:TRUE\n"
                "keyUsage = critical, keyCertSign, cRLSign\n"
                "subjectKeyIdentifier = hash\n"
            )
            _run_openssl(
                ["openssl", "req", "-new", "-x509",
                 "-config", str(ca_cnf),
                 "-key", str(ca_key), "-out", str(ca_cert),
                 "-days", "3650"],
            )

    # Server key
    if not srv_key.exists():
        _run_openssl(
            ["openssl", "genrsa", "-out", str(srv_key), "2048"],
        )

    # Server cert signed by CA
    srv_cert = CERT_DIR / "server.pem"
    if not srv_cert.exists():
        sign_server_cert(prefix)


def _run_openssl(cmd):
    """Run an openssl command, showing stderr on failure."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        detail = (r.stderr or r.stdout or "").strip()
        raise RuntimeError(
            f"openssl failed (exit {r.returncode}): {' '.join(cmd)}\n  {detail}"
        )


def sign_server_cert(prefix):
    """Issue a server certificate for the given prefix hostname."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        csr = tmp / "server.csr"
        san_cnf = tmp / "san.cnf"
        req_cnf = tmp / "req.cnf"

        # Minimal config so LibreSSL doesn't depend on a system openssl.cnf
        req_cnf.write_text(
            "[req]\n"
            "distinguished_name = dn\n"
            "prompt = no\n"
            "[dn]\n"
            f"CN = {prefix}\n"
        )

        _run_openssl(
            ["openssl", "req", "-new",
             "-config", str(req_cnf),
             "-key", str(CERT_DIR / "server-key.pem"),
             "-out", str(csr)],
        )
        san_cnf.write_text(
            "[v3_req]\n"
            f"subjectAltName = DNS:{prefix}, IP:{BIND_ADDR}\n"
            "basicConstraints = critical, CA:FALSE\n"
            "extendedKeyUsage = serverAuth\n"
            "keyUsage = critical, digitalSignature, keyEncipherment\n"
        )
        _run_openssl(
            ["openssl", "x509", "-req",
             "-in", str(csr),
             "-CA", str(CERT_DIR / "ca.pem"),
             "-CAkey", str(CERT_DIR / "ca-key.pem"),
             "-CAcreateserial",
             "-out", str(CERT_DIR / "server.pem"),
             "-days", "398",
             "-extfile", str(san_cnf),
             "-extensions", "v3_req"],
        )
    (CERT_DIR / "ca.srl").unlink(missing_ok=True)


def has_ca_trust():
    """Check if a LinkJumper CA certificate is already in the System keychain."""
    r = subprocess.run(
        ["security", "find-certificate", "-a", "-c", "LinkJumper Local CA",
         "-Z", "/Library/Keychains/System.keychain"],
        capture_output=True, text=True,
    )
    return r.returncode == 0 and "SHA-1 hash:" in r.stdout


def trust_ca():
    """Add the CA certificate to the macOS System keychain as a trusted root."""
    subprocess.run(
        ["sudo", "security", "add-trusted-cert", "-d", "-r", "trustRoot",
         "-p", "ssl", "-k", "/Library/Keychains/System.keychain",
         str(CERT_DIR / "ca.pem")],
        check=True,
    )


def remove_ca_trust():
    """Remove all LinkJumper CA certificates from the System keychain."""
    r = subprocess.run(
        ["security", "find-certificate", "-a", "-c", "LinkJumper Local CA",
         "-Z", "/Library/Keychains/System.keychain"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return False

    hashes = re.findall(r"SHA-1 hash:\s+([0-9A-F]+)", r.stdout)
    if not hashes:
        return False

    for h in hashes:
        d = subprocess.run(
            ["sudo", "security", "delete-certificate",
             "-Z", h, "/Library/Keychains/System.keychain"],
            capture_output=True,
        )
        if d.returncode != 0:
            # Deletion blocked — mark as deny instead
            export = subprocess.run(
                ["security", "find-certificate", "-Z", h,
                 "-p", "/Library/Keychains/System.keychain"],
                capture_output=True, text=True,
            )
            if export.returncode == 0 and export.stdout.strip():
                tmp = CERT_DIR / f"_deny_{h}.pem"
                tmp.write_text(export.stdout)
                subprocess.run(
                    ["sudo", "security", "add-trusted-cert", "-d",
                     "-r", "deny", "-k", "/Library/Keychains/System.keychain",
                     str(tmp)],
                )
                tmp.unlink(missing_ok=True)
    return True
