#!/usr/bin/env python3
"""
tools/figma_export.py
~~~~~~~~~~~~~~~~~~~~~
Export named frames from a Figma file as PNGs using the Figma REST API.

Dependencies: requests

Usage:
    export FIGMA_TOKEN=figd_...
    python tools/figma_export.py --file-key <KEY> [--page Export] [--out assets/raw]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("requests is required: pip install requests")

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        sys.exit("tomllib not available (Python <3.11) and tomli not installed.")

_REPO_ROOT = Path(__file__).parent.parent
_FIGMA_API = "https://api.figma.com/v1"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_CHUNK_SIZE = 40


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_key_from_url(url: str) -> str:
    """Extract the Figma file key from a figma.com URL."""
    m = re.search(r"/(?:design|file)/([^/?#]+)", url)
    if not m:
        raise ValueError(f"Cannot parse Figma file key from URL: {url!r}")
    return m.group(1)


def _figma_get(session: "requests.Session", url: str, *, timeout: int = 20, retries: int = 3) -> dict:
    """GET *url* with retry logic for 429 rate-limit responses."""
    for attempt in range(retries):
        resp = session.get(url, timeout=timeout)
        if resp.status_code == 403:
            sys.exit("Error 403: Check your FIGMA_TOKEN — it may be expired or lack read access.")
        if resp.status_code == 404:
            sys.exit("Error 404: File not found — check the --file-key / --url argument.")
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 10))
            print(f"  Rate-limited. Sleeping {wait}s (attempt {attempt + 1}/{retries}) …")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]
    sys.exit(f"Failed after {retries} retries due to rate-limiting.")


def _download_image(session: "requests.Session", url: str, dest: Path, *, timeout: int = 20, retries: int = 3) -> str:
    """Download a rendered PNG from *url* to *dest*. Returns 'ok' or 'skip' or 'error'."""
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=timeout)
        except Exception as exc:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return f"error ({exc})"
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 5))
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            return f"error (HTTP {resp.status_code})"
        data = resp.content
        if not data.startswith(_PNG_MAGIC):
            return "error (not a PNG)"
        dest.write_bytes(data)
        return "ok"
    return "error (max retries)"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _collect_frames(session: "requests.Session", key: str, page_name: str) -> dict[str, str]:
    """Return {frame_name: node_id} for all top-level frames on *page_name*."""
    data = _figma_get(session, f"{_FIGMA_API}/files/{key}?depth=2")
    pages = data["document"]["children"]
    target = next((p for p in pages if p["name"] == page_name), None)
    if target is None:
        available = [p["name"] for p in pages]
        sys.exit(
            f"Page {page_name!r} not found. Available pages: {available}"
        )
    frames: dict[str, str] = {}
    for child in target.get("children", []):
        frames[child["name"]] = child["id"]
    return frames


def _render_images(
    session: "requests.Session",
    key: str,
    node_ids: list[str],
    scale: int,
) -> dict[str, str]:
    """Call the Figma images endpoint; return {node_id: image_url}."""
    ids_param = ",".join(node_ids)
    url = (
        f"{_FIGMA_API}/images/{key}"
        f"?ids={ids_param}&format=png&scale={scale}&use_absolute_bounding_box=true"
    )
    data = _figma_get(session, url)
    return data.get("images", {})


def _chunk(lst: list, size: int):
    """Yield successive *size*-sized slices of *lst*."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the Figma export tool."""
    parser = argparse.ArgumentParser(description="Export Figma frames as PNGs.")
    key_group = parser.add_mutually_exclusive_group()
    key_group.add_argument("--file-key", help="Figma file key")
    key_group.add_argument("--url", help="figma.com URL (key extracted automatically)")
    parser.add_argument("--page", default="Export", help="Figma page name (default: Export)")
    parser.add_argument(
        "--manifest",
        default=str(_REPO_ROOT / "assets" / "manifest.toml"),
        help="Path to assets/manifest.toml",
    )
    parser.add_argument(
        "--out",
        default=str(_REPO_ROOT / "assets" / "raw"),
        help="Output directory for downloaded PNGs",
    )
    parser.add_argument("--only", default=None, help="Comma-separated asset names to export")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--list", action="store_true", help="List frames on the page and exit")
    args = parser.parse_args()

    # Resolve Figma file key
    token = os.environ.get("FIGMA_TOKEN", "")
    if not token:
        sys.exit("FIGMA_TOKEN environment variable is not set.")

    file_key = args.file_key or os.environ.get("FIGMA_FILE_KEY")
    if not file_key and args.url:
        file_key = _parse_key_from_url(args.url)
    if not file_key:
        sys.exit("Provide --file-key, FIGMA_FILE_KEY env var, or --url.")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"X-Figma-Token": token})

    # 1. Fetch page frames
    frames = _collect_frames(session, file_key, args.page)

    if args.list:
        print(f"Frames on page {args.page!r}:")
        for name in sorted(frames):
            print(f"  {name}  ({frames[name]})")
        return

    # 2. Read manifest
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"Warning: manifest not found at {manifest_path}; exporting all frames.")
        assets: list[dict] = [
            {"name": n, "scale": 1, "kind": "unknown"} for n in frames
        ]
    else:
        with manifest_path.open("rb") as fh:
            manifest_data = tomllib.load(fh)
        assets = manifest_data.get("asset", [])

    # Filter by --only
    if args.only:
        only_set = {n.strip() for n in args.only.split(",")}
        assets = [a for a in assets if a["name"] in only_set]

    # Report missing frames
    for asset in assets:
        name = asset["name"]
        if name not in frames:
            print(f"  warning: frame {name!r} not found on Figma page {args.page!r}")

    # 3. Group by scale, chunk node_ids
    by_scale: dict[int, list[dict]] = {}
    for asset in assets:
        scale = int(asset.get("scale", 1))
        by_scale.setdefault(scale, []).append(asset)

    image_urls: dict[str, str] = {}
    for scale, scale_assets in by_scale.items():
        node_ids = [frames[a["name"]] for a in scale_assets if a["name"] in frames]
        for id_chunk in _chunk(node_ids, _CHUNK_SIZE):
            chunk_urls = _render_images(session, file_key, id_chunk, scale)
            image_urls.update(chunk_urls)

    # 4. Download each PNG
    results: list[dict] = []
    log_entries: list[dict] = []
    for asset in assets:
        name = asset["name"]
        scale = int(asset.get("scale", 1))
        node_id = frames.get(name)
        if node_id is None:
            results.append({"name": name, "scale": scale, "status": "missing frame"})
            continue
        url = image_urls.get(node_id)
        if url is None:
            results.append({"name": name, "scale": scale, "status": "no render url"})
            continue
        dest = out_dir / f"{name}.png"
        if dest.exists() and not args.force:
            status = "skip"
        else:
            status = _download_image(session, url, dest)
        results.append({"name": name, "scale": scale, "status": status})
        log_entries.append({"name": name, "scale": scale, "url": url, "status": status})

    # 5. Print table
    print(f"\n{'Name':<30} {'Scale':>5}  Status")
    print("-" * 50)
    any_failed = False
    for r in results:
        print(f"  {r['name']:<28} {r['scale']:>5}  {r['status']}")
        if "error" in r["status"] or "missing" in r["status"]:
            any_failed = True

    # 6. Write log
    log_path = out_dir / "_export_log.json"
    log_path.write_text(json.dumps(log_entries, indent=2), encoding="utf-8")
    print(f"\nLog written to {log_path}")

    if any_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
