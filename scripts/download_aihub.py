"""Download AI Hub files listed in data/manifests/aihub_files.csv.

Python port of the download path of the official `aihubshell` (v0.6):
GET https://api.aihub.or.kr/down/0.6/{dataset_key}.do?fileSn={file_key}
with header `apikey: <key>`. The response is a tar that may contain split
`*.zip.partN` files, which are merged here (no Linux/WSL needed).

The API key is read from the AIHUB_APIKEY environment variable, falling back
to the project's .env file. It is never printed or written to disk.

Usage:
    python scripts/download_aihub.py --stage 1 --dry-run
    python scripts/download_aihub.py --stage 1
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "manifests" / "aihub_files.csv"
RAW_DIR = ROOT / "data" / "raw"
ENV_FILE = ROOT / ".env"
DOWNLOAD_URL = "https://api.aihub.or.kr/down/0.6/{dataset_key}.do?fileSn={file_key}"
PART_RE = re.compile(r"^(?P<prefix>.+)\.part(?P<num>\d+)$")
CHUNK = 1 << 20


def read_env_file(key: str) -> str | None:
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        name, sep, value = line.partition("=")
        if sep and name.strip() == key:
            return value.strip().strip("'\"") or None
    return None


def load_manifest(stages: set[str]) -> list[dict[str, str]]:
    with MANIFEST.open(encoding="utf-8", newline="") as f:
        return [row for row in csv.DictReader(f) if row["stage"] in stages]


def find_existing(dataset_dir: Path, filename: str) -> Path | None:
    # The server replaces spaces with underscores in paths ("TS_99. 붙임" -> "TS_99._붙임").
    if not dataset_dir.exists():
        return None
    wanted = filename.replace(" ", "_")
    return next((p for p in dataset_dir.rglob("*.zip") if p.name.replace(" ", "_") == wanted), None)


def fetch_tar(url: str, api_key: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"apikey": api_key})
    try:
        with urllib.request.urlopen(req) as resp, dest.open("wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while chunk := resp.read(CHUNK):
                out.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {done / 2**20:,.1f} / {total / 2**20:,.1f} MB", end="", flush=True)
            print()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"HTTP {e.code}: {body.strip()[:500]}") from None


def merge_parts(root: Path) -> None:
    groups: dict[Path, list[tuple[int, Path]]] = {}
    for p in root.rglob("*.part*"):
        m = PART_RE.match(p.name)
        if m:
            groups.setdefault(p.with_name(m["prefix"]), []).append((int(m["num"]), p))
    for target, parts in groups.items():
        parts.sort()
        print(f"  merging {len(parts)} parts -> {target.relative_to(ROOT)}")
        with target.open("wb") as out:
            for _, part in parts:
                with part.open("rb") as src:
                    shutil.copyfileobj(src, out, CHUNK)
        for _, part in parts:
            part.unlink()


def download(row: dict[str, str], api_key: str) -> None:
    dataset_dir = RAW_DIR / row["dataset_key"]
    existing = find_existing(dataset_dir, row["filename"])
    if existing:
        print(f"[skip] {row['filename']} (exists: {existing.relative_to(ROOT)})")
        return

    dataset_dir.mkdir(parents=True, exist_ok=True)
    tar_path = dataset_dir / f"download_{row['file_key']}.tar"
    url = DOWNLOAD_URL.format(dataset_key=row["dataset_key"], file_key=row["file_key"])
    print(f"[get ] {row['filename']} ({row['size']})")
    fetch_tar(url, api_key, tar_path)

    with tarfile.open(tar_path) as tf:
        tf.extractall(dataset_dir, filter="data")
    tar_path.unlink()
    merge_parts(dataset_dir)

    if not find_existing(dataset_dir, row["filename"]):
        raise RuntimeError(f"{row['filename']} not found after extraction")
    print(f"[ok  ] {row['filename']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", nargs="+", default=["1"], help="manifest stages to download")
    parser.add_argument("--dry-run", action="store_true", help="list files without downloading")
    args = parser.parse_args()

    rows = load_manifest(set(args.stage))
    if not rows:
        print(f"no manifest rows for stage(s) {args.stage}")
        return 1

    for row in rows:
        print(f"stage {row['stage']}  {row['dataset_key']:>5}/{row['file_key']:<6}  {row['size']:>7}  {row['filename']}")
    if args.dry_run:
        return 0

    api_key = os.environ.get("AIHUB_APIKEY") or read_env_file("AIHUB_APIKEY")
    if not api_key:
        print("AIHUB_APIKEY is not set. Put `AIHUB_APIKEY=<key>` in .env (see .env.example).")
        return 1

    failed = []
    for row in rows:
        try:
            download(row, api_key)
        except Exception as e:  # keep going; report at the end
            print(f"[fail] {row['filename']}: {e}")
            failed.append(row["filename"])
    if failed:
        print(f"\n{len(failed)} failed: {failed}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
