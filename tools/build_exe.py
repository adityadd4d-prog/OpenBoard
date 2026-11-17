"""
tools/build_exe.py
~~~~~~~~~~~~~~~~~~
Build a standalone desktop distribution of OpenBoard using PyInstaller
in --onedir mode, run post-build smoke tests, and package into a zip archive.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

_REPO_ROOT = Path(__file__).resolve().parent.parent


def get_platform_info() -> tuple[str, str, str]:
    """Return (os_folder, executable_name, stockfish_name)."""
    p = sys.platform
    if p == "win32":
        return "win", "OpenBoard.exe", "stockfish.exe"
    elif p == "darwin":
        return "mac", "OpenBoard", "stockfish"
    else:
        return "linux", "OpenBoard", "stockfish"


def find_icon(repo_root: Path, os_name: str) -> Path | None:
    """Find appropriate application icon."""
    candidates = [
        repo_root / "assets" / "build" / "icons" / ("icon.ico" if os_name == "win" else "icon.png"),
        repo_root / "assets" / "build" / "app.ico",
        repo_root / "assets" / "build" / "app" / "app_icon.png",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def run_stockfish_smoke_test(sf_binary: Path) -> bool:
    """Send 'uci' to Stockfish binary and require 'uciok' within 5 seconds."""
    print(f"Smoke test 1: Testing Stockfish at {sf_binary}...")
    try:
        proc = subprocess.Popen(
            [str(sf_binary)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, _ = proc.communicate(input="uci\nquit\n", timeout=5.0)
        if "uciok" in stdout:
            print("  Stockfish answered 'uciok' successfully.")
            return True
        else:
            print(f"  Error: Stockfish did not answer 'uciok'. Output:\n{stdout}")
            return False
    except Exception as exc:
        print(f"  Error running Stockfish: {exc}")
        return False


def run_app_selftest(app_binary: Path) -> bool:
    """Run built application with --selftest flag and verify JSON output."""
    print(f"Smoke test 2: Testing built app at {app_binary} --selftest...")
    try:
        proc = subprocess.run(
            [str(app_binary), "--selftest"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15.0,
        )
        if proc.returncode != 0:
            print(f"  Error: App returned exit code {proc.returncode}.")
            print(f"  stdout:\n{proc.stdout}")
            print(f"  stderr:\n{proc.stderr}")
            return False

        # Parse JSON from stdout
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        # Find json block
        json_str = proc.stdout.strip()
        data = json.loads(json_str)
        print(f"  Self-test output: {json.dumps(data, indent=2)}")

        if not data.get("python_engine_ok"):
            print("  Error: python_engine_ok is False!")
            return False
        if not data.get("stockfish_ok"):
            print("  Error: stockfish_ok is False!")
            return False

        print("  App self-test passed: both engines answered properly.")
        return True
    except Exception as exc:
        print(f"  Error during app self-test: {exc}")
        return False


def build(skip_tests: bool = False, skip_zip: bool = False) -> None:
    os_name, exe_name, sf_name = get_platform_info()
    print(f"Building OpenBoard for platform '{os_name}'...")

    # Load version
    sys.path.insert(0, str(_REPO_ROOT))
    from openboard import config
    version = config.APP_VERSION

    # Verify input files
    assets_build = _REPO_ROOT / "assets" / "build"
    if not assets_build.exists():
        raise RuntimeError(f"Missing assets build directory: {assets_build}. Run build_assets.py first.")

    sf_dir = _REPO_ROOT / "bin" / "stockfish" / os_name
    if not sf_dir.exists():
        print(f"Warning: Stockfish dir {sf_dir} does not exist.")

    licenses_file = _REPO_ROOT / "THIRD_PARTY_LICENSES.md"
    if not licenses_file.exists():
        raise RuntimeError(f"Missing THIRD_PARTY_LICENSES.md at {licenses_file}")

    sep = ";" if sys.platform == "win32" else ":"

    # Data arguments
    datas = [
        f"{assets_build}{sep}assets/build",
        f"{licenses_file}{sep}.",
    ]
    if sf_dir.exists():
        datas.append(f"{sf_dir}{sep}bin/stockfish/{os_name}")

    # Build PyInstaller command
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name",
        "OpenBoard",
        "--distpath",
        str(_REPO_ROOT / "dist"),
        "--workpath",
        str(_REPO_ROOT / "build"),
        "--specpath",
        str(_REPO_ROOT),
        "--hidden-import",
        "chess",
        "--hidden-import",
        "chess.engine",
        "--hidden-import",
        "chess.polyglot",
        "--hidden-import",
        "platformdirs",
    ]

    for d in datas:
        cmd.extend(["--add-data", d])

    icon = find_icon(_REPO_ROOT, os_name)
    if icon:
        cmd.extend(["--icon", str(icon)])

    entry_point = _REPO_ROOT / "main.py"
    cmd.append(str(entry_point))

    print("Running PyInstaller...")
    print(" ".join(cmd))
    res = subprocess.run(cmd, cwd=str(_REPO_ROOT))
    if res.returncode != 0:
        raise RuntimeError(f"PyInstaller failed with return code {res.returncode}")

    dist_dir = _REPO_ROOT / "dist" / "OpenBoard"
    app_binary = dist_dir / exe_name

    # Ensure THIRD_PARTY_LICENSES.md is also at dist root
    top_license = dist_dir / "THIRD_PARTY_LICENSES.md"
    if not top_license.exists():
        shutil.copy2(licenses_file, top_license)

    # Ensure executable permissions on POSIX
    if sys.platform != "win32" and app_binary.exists():
        app_binary.chmod(0o755)

    # Locate Stockfish in dist
    sf_candidates = [p for p in dist_dir.rglob(sf_name) if p.is_file()]
    for sf in sf_candidates:
        if sys.platform != "win32":
            sf.chmod(0o755)

    # Smoke tests
    if not skip_tests:
        print("\n--- Running Post-Build Smoke Tests ---")
        if sf_candidates:
            if not run_stockfish_smoke_test(sf_candidates[0]):
                raise RuntimeError("Stockfish smoke test failed!")
        else:
            print("Notice: No bundled Stockfish found in dist to test.")

        if not run_app_selftest(app_binary):
            raise RuntimeError("App --selftest smoke test failed!")
        print("All post-build smoke tests passed!\n")

    # Packaging into zip
    if not skip_zip:
        zip_name = f"OpenBoard-{version}-{os_name}.zip"
        zip_path = _REPO_ROOT / "dist" / zip_name
        print(f"Creating release archive: {zip_path}...")

        if zip_path.exists():
            zip_path.unlink()

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(dist_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(_REPO_ROOT / "dist")
                    # Preserve executable bit in zip info on posix
                    zinfo = zipfile.ZipInfo.from_file(file_path, str(arcname))
                    if sys.platform != "win32" and os.access(file_path, os.X_OK):
                        zinfo.external_attr = 0o755 << 16
                    zf.writestr(zinfo, file_path.read_bytes())

        print(f"Successfully packaged {zip_path} ({zip_path.stat().st_size / (1024 * 1024):.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build OpenBoard standalone distribution")
    parser.add_argument("--skip-tests", action="store_true", help="Skip post-build smoke tests")
    parser.add_argument("--skip-zip", action="store_true", help="Skip creating release zip")
    args = parser.parse_args()

    build(skip_tests=args.skip_tests, skip_zip=args.skip_zip)


if __name__ == "__main__":
    main()
