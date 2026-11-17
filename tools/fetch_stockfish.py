#!/usr/bin/env python3
"""
tools/fetch_stockfish.py
~~~~~~~~~~~~~~~~~~~~~~~~
Download, verify, and install a Stockfish binary from an archive URL.
Stdlib only — no third-party dependencies.

Usage example:
    python tools/fetch_stockfish.py \\
        --os linux \\
        --url https://github.com/official-stockfish/Stockfish/releases/download/sf_16/stockfish-ubuntu-x86-64-avx2.tar \\
        --sha256 <hex> \\
        --variant avx2
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
BIN_BASE = _REPO_ROOT / "bin" / "stockfish"


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def _download(url: str, dest: Path, *, timeout: int = 60) -> None:
    """Download *url* to *dest*, showing a simple progress indicator."""
    print(f"Downloading {url} …")
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        received = 0
        chunk_size = 65536
        with dest.open("wb") as fh:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                fh.write(chunk)
                received += len(chunk)
                if total:
                    pct = received * 100 // total
                    print(f"\r  {pct}% ({received}/{total} bytes)", end="", flush=True)
    print()
    print(f"  → saved to {dest}")


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def _verify_sha256(path: Path, expected: str) -> None:
    """Raise ValueError if the file's SHA-256 does not match *expected*."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if actual.lower() != expected.lower():
        raise ValueError(
            f"SHA-256 mismatch:\n  expected: {expected}\n  actual:   {actual}"
        )
    print(f"  SHA-256 OK ({actual[:16]}…)")


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def _find_stockfish_in_members(names: list[str]) -> str | None:
    """Return the archive member name whose basename starts with 'stockfish'."""
    # Prefer exact name 'stockfish' or 'stockfish.exe', then longest match
    scored = [
        n for n in names
        if Path(n).name.startswith("stockfish") and not Path(n).name.endswith(".md")
        and not Path(n).name.startswith("stockfish_")  # skip docs
    ]
    if not scored:
        return None
    # Prefer executables (no extension or .exe), then shortest path depth
    scored.sort(key=lambda n: (Path(n).suffix not in ("", ".exe"), len(Path(n).parts), n))
    return scored[0]


def _extract_archive(archive_path: Path, extract_dir: Path) -> Path:
    """Extract *archive_path* to *extract_dir*; return the stockfish binary path."""
    extract_dir.mkdir(parents=True, exist_ok=True)
    suffix = archive_path.suffix.lower()

    if suffix == ".zip" or zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as zf:
            names = zf.namelist()
            sf_name = _find_stockfish_in_members(names)
            if sf_name is None:
                raise FileNotFoundError("No file starting with 'stockfish' found in archive")
            zf.extract(sf_name, extract_dir)
            return extract_dir / sf_name

    # Try tar (including .tar.gz, .tar.bz2, .tar.xz, bare .tar)
    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path) as tf:
            names = tf.getnames()
            sf_name = _find_stockfish_in_members(names)
            if sf_name is None:
                raise FileNotFoundError("No file starting with 'stockfish' found in archive")
            member = tf.getmember(sf_name)
            tf.extract(member, extract_dir, filter="data")
            return extract_dir / sf_name

    raise ValueError(f"Unrecognised archive format: {archive_path.suffix}")


def _find_license(extract_dir: Path) -> Path | None:
    """Return the first LICENSE or COPYING file found, or None."""
    for name in ("COPYING", "LICENSE", "LICENSE.txt", "COPYING.txt"):
        for candidate in extract_dir.rglob(name):
            return candidate
    return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_binary(binary: Path) -> str:
    """Run the binary, send 'uci', expect 'uciok' within 5 s.  Return engine name."""
    print(f"Validating binary: {binary}")
    proc = subprocess.Popen(
        [str(binary)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    name_line = ""
    deadline = time.time() + 5.0
    try:
        assert proc.stdin is not None
        proc.stdin.write("uci\n")
        proc.stdin.flush()
        while time.time() < deadline:
            line = proc.stdout.readline()  # type: ignore[union-attr]
            if not line:
                break
            line = line.strip()
            if line.startswith("id name"):
                name_line = line[len("id name"):].strip()
            if line == "uciok":
                print(f"  uciok received — engine: {name_line or '(unknown)'}")
                return name_line
        raise TimeoutError("Did not receive 'uciok' within 5 seconds")
    finally:
        try:
            proc.stdin.write("quit\n")  # type: ignore[union-attr]
            proc.stdin.flush()
        except Exception:
            pass
        proc.wait(timeout=3)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point for the fetch-stockfish tool."""
    parser = argparse.ArgumentParser(
        description="Download and install a Stockfish binary from an archive URL."
    )
    parser.add_argument("--os", required=True, choices=["win", "linux", "mac"],
                        help="Target OS subfolder under bin/stockfish/")
    parser.add_argument("--url", required=True, help="Direct download URL for the archive")
    parser.add_argument("--sha256", default=None, help="Expected SHA-256 hex digest (optional)")
    parser.add_argument("--variant", default=None,
                        help="Variant label; binary saved as stockfish-<variant> instead of stockfish")
    args = parser.parse_args()

    os_folder: str = args.os
    dest_dir: Path = BIN_BASE / os_folder
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Determine destination binary name
    is_win = os_folder == "win"
    if args.variant:
        bin_name = f"stockfish-{args.variant}" + (".exe" if is_win else "")
    else:
        bin_name = "stockfish" + (".exe" if is_win else "")
    dest_binary = dest_dir / bin_name

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        archive_path = tmp / "archive"

        # 1. Download
        _download(args.url, archive_path)

        # 2. Verify SHA-256
        if args.sha256:
            _verify_sha256(archive_path, args.sha256)

        # 3. Extract
        extract_dir = tmp / "extracted"
        sf_extracted = _extract_archive(archive_path, extract_dir)
        print(f"  extracted: {sf_extracted.name}")

        # 4. Copy binary
        shutil.copy2(sf_extracted, dest_binary)
        if not is_win:
            dest_binary.chmod(dest_binary.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        print(f"  installed: {dest_binary}")

        # 5. Copy license
        lic = _find_license(extract_dir)
        if lic:
            shutil.copy2(lic, dest_dir / "LICENSE.txt")
            print(f"  license:   {dest_dir / 'LICENSE.txt'}")
        else:
            print("  warning: no LICENSE/COPYING file found in archive")

        # 6. Validate
        engine_name = _validate_binary(dest_binary)

        # 7. Write VERSION.txt
        version_file = dest_dir / "VERSION.txt"
        version_file.write_text(f"{engine_name}\n", encoding="utf-8")
        print(f"  version:   {version_file} → {engine_name!r}")

    print("\nDone.")


if __name__ == "__main__":
    main()
