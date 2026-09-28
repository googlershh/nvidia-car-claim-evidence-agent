"""Find near-duplicate clips in the fault eval set (same accident under different names).

Takes 20 frames per clip (2 fps, t = 0.25..9.75 s), shrinks each to 32x18 grayscale,
normalizes every frame to zero mean and unit variance (so brightness and colour
grading of re-uploads do not matter), and drops near-uniform frames (dark night
shots) that would otherwise match everything. Clips are compared by the mean
absolute difference of normalized frames at the best time offset (-3..+3 s,
since re-uploads are often trimmed differently). Stdlib + ffmpeg only.

Limitation (checked on the 150 eval clips, 2026-09-28): a plain re-encode is found
clearly (F102/F114: 0.02), but re-uploads that were cropped, colour-graded or
overlaid with text score like unrelated clips of similar scenes (F034/F041: 0.43
among many false pairs; F077/F097 and F128/F132 above 0.6). Use this only as a
first pass; the label review (`data/interim/label_review/review.csv`) is the
reference for duplicates.

Usage:
    python scripts/find_duplicate_clips.py [threshold] [--known F034,F041 ...]
"""

from __future__ import annotations

import csv
import statistics
import subprocess
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEOS = ROOT / "data/interim/media/videos"
W, H, FPS, N = 32, 18, 2, 20
MIN_STD = 12.0  # grey levels; below this a frame carries no structure


def signature(video: Path) -> list[list[float] | None]:
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", "0.25", "-i", str(video), "-vf",
                          f"fps={FPS},scale={W}:{H},format=gray", "-frames:v", str(N), "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    frames = []
    for i in range(0, len(raw) - W * H + 1, W * H):
        px = list(raw[i:i + W * H])
        mean, std = statistics.fmean(px), statistics.pstdev(px)
        frames.append(None if std < MIN_STD else [(p - mean) / std for p in px])
    return frames


def distance(a: list, b: list) -> tuple[float, int]:
    best, used = 9.0, 0
    for shift in range(-3 * FPS, 3 * FPS + 1):
        pairs = [(a[i], b[i + shift]) for i in range(len(a))
                 if 0 <= i + shift < len(b) and a[i] is not None and b[i + shift] is not None]
        if len(pairs) < 6:
            continue
        d = sum(abs(x - y) for fa, fb in pairs for x, y in zip(fa, fb)) / (len(pairs) * W * H)
        if d < best:
            best, used = d, len(pairs)
    return best, used


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    threshold = float(args[0]) if args else 0.5
    rows = list(csv.DictReader((ROOT / "data/interim/eval_fault.csv").open(encoding="utf-8-sig")))
    by_id = {r["eval_id"]: r for r in rows}
    sigs = {r["eval_id"]: signature(VIDEOS / f"{r['video_name']}.mp4") for r in rows}
    found = []
    for a, b in combinations(sigs, 2):
        d, used = distance(sigs[a], sigs[b])
        if d < threshold:
            found.append((d, used, a, b))
    for d, used, a, b in sorted(found):
        ra, rb = by_id[a], by_id[b]
        print(f"{d:5.2f} ({used:2d} frames)  {a} {ra['video_name']} code {ra['accident_type']} "
              f"{ra['fault_a']}:{ra['fault_b']}  |  {b} {rb['video_name']} code {rb['accident_type']} "
              f"{rb['fault_a']}:{rb['fault_b']}")
    print(f"{len(found)} pairs below {threshold}")


if __name__ == "__main__":
    main()
