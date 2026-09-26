"""Extract only the media the evaluation sets use from the large AI Hub zips.

    videos: data/manifests/eval_fault.csv  -> 597 VS_차대차_영상_*.zip
    images: data/interim/synth_cases.jsonl -> 581 VS_damage.zip

Members are matched by file name stem (video_name / image file_name), so the
folder layout inside the zips does not matter. Output goes to
data/interim/media/{videos,images}; a report lists anything not found.

Usage:
    python scripts/extract_media.py [videos] [images]
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MEDIA = ROOT / "data" / "interim" / "media"


def extract(zips: list[Path], wanted: set[str], out_dir: Path, by_stem: bool) -> set[str]:
    """Copy members whose stem (or full name) is in `wanted`; return what was found."""
    out_dir.mkdir(parents=True, exist_ok=True)
    found: set[str] = set()
    for path in zips:
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = PurePosixPath(info.filename)
                key = name.stem if by_stem else name.name
                if key in wanted and key not in found:
                    target = out_dir / name.name
                    if not (target.exists() and target.stat().st_size == info.file_size):
                        with z.open(info) as src, target.open("wb") as dst:
                            shutil.copyfileobj(src, dst, 1 << 20)
                    found.add(key)
        print(f"  {path.name}: {len(found)}/{len(wanted)} found so far")
    return found


def main(targets: list[str]) -> None:
    targets = targets or ["videos", "images"]
    missing_all = {}
    if "videos" in targets:
        with (ROOT / "data" / "manifests" / "eval_fault.csv").open(encoding="utf-8") as f:
            wanted = {r["video_name"] for r in csv.DictReader(f)}
        zips = sorted((RAW / "597").rglob("VS_차대차_영상_*.zip"))
        print(f"[videos] {len(wanted)} wanted from {[z.name for z in zips]}")
        missing_all["videos"] = sorted(wanted - extract(zips, wanted, MEDIA / "videos", by_stem=True))
    if "images" in targets:
        with (ROOT / "data" / "interim" / "synth_cases.jsonl").open(encoding="utf-8") as f:
            wanted = {img for line in f for img in json.loads(line)["images"]}
        zips = sorted((RAW / "581").rglob("VS_damage.zip"))
        print(f"[images] {len(wanted)} wanted from {[z.name for z in zips]}")
        missing_all["images"] = sorted(wanted - extract(zips, wanted, MEDIA / "images", by_stem=False))
    for kind, missing in missing_all.items():
        print(f"[{kind}] missing {len(missing)}: {missing[:10]}")
    sys.exit(1 if any(missing_all.values()) else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
