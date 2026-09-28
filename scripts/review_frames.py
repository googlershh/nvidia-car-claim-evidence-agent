"""Frame sheets for a human-style label review of the fault eval set.

For each eval clip writes two JPEG grids under data/interim/label_review/frames/:
  <eval_id>_a.jpg  overview, 1 fps, t = 0..9 s (5x2)
  <eval_id>_b.jpg  collision window, 4 fps, t = 4.00..6.75 s (4x3)
Black letterbox bars are cropped (ffmpeg cropdetect). Also writes labels.csv with
the label in words (ego = object B for first-person clips, per the dataset manual).

Usage:
    python scripts/review_frames.py            # all 150
    python scripts/review_frames.py F001 F002  # selected ids
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEOS = ROOT / "data/interim/media/videos"
OUT = ROOT / "data/interim/label_review"
FRAMES = OUT / "frames"


def crop_filter(video: Path) -> str:
    """Most frequent cropdetect result over the first 3 s, or '' if no bars."""
    res = subprocess.run(["ffmpeg", "-hide_banner", "-t", "3", "-i", str(video), "-vf", "cropdetect=24:16:0",
                          "-f", "null", "-"], capture_output=True, text=True)
    found = re.findall(r"crop=(\d+:\d+:\d+:\d+)", res.stderr)
    if not found:
        return ""
    best = max(set(found), key=found.count)
    w, h, _, _ = map(int, best.split(":"))
    return f"crop={best}," if w > 0 and h > 0 else ""


def sheets(eval_id: str, video: Path) -> None:
    crop = crop_filter(video)
    a = FRAMES / f"{eval_id}_a.jpg"
    b = FRAMES / f"{eval_id}_b.jpg"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(video), "-vf",
                    f"{crop}fps=1,scale=400:-2,tile=5x2", "-frames:v", "1", str(a)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "4", "-i", str(video), "-vf",
                    f"{crop}fps=4,scale=400:-2,tile=4x3", "-frames:v", "1", str(b)], check=True)


def main() -> None:
    FRAMES.mkdir(parents=True, exist_ok=True)
    codes = {r["code"]: r for r in csv.DictReader((ROOT / "data/interim/accident_codes.csv").open(encoding="utf-8-sig"))}
    rows = list(csv.DictReader((ROOT / "data/interim/eval_fault.csv").open(encoding="utf-8-sig")))
    wanted = set(sys.argv[1:])
    labels = []
    for r in rows:
        c = codes[r["accident_type"]]
        labels.append({"eval_id": r["eval_id"], "video_name": r["video_name"], "zip_place": r["zip_place"],
                       "code": r["accident_type"], "place_feature": c["place_feature"],
                       "a_other": c["a_progress"], "b_ego": c["b_progress"],
                       "fault_a_other": r["fault_a"], "fault_b_ego": r["fault_b"]})
        if wanted and r["eval_id"] not in wanted:
            continue
        if not (FRAMES / f"{r['eval_id']}_b.jpg").exists() or wanted:
            sheets(r["eval_id"], VIDEOS / f"{r['video_name']}.mp4")
    with (OUT / "labels.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(labels[0]))
        w.writeheader()
        w.writerows(labels)
    print(f"sheets in {FRAMES.relative_to(ROOT)}, labels in {(OUT / 'labels.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
