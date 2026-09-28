"""Print the files a remote run needs, relative to the repo root (input for rsync --files-from).

Code and small reference data come from git; from data/interim only what the agent reads
at run time, and only the videos and photos of the synthetic cases. AI Hub raw zips and
the fault standard PDF stay on this machine.

Usage (inside WSL or Linux):
    python3 scripts/brev_files.py > /tmp/files.txt
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
RUNTIME = ["accident_codes.csv", "eval_fault_reviewed.csv", "synth_cases.jsonl", "statements.jsonl",
           "knia/charts.json"]


def main() -> None:
    tracked = subprocess.run(["git", "-c", "safe.directory=*", "ls-files"], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout.splitlines()
    files = [f for f in tracked if not f.startswith("proposals/")]
    files += [f"data/interim/{name}" for name in RUNTIME]
    for line in (INTERIM / "synth_cases.jsonl").open(encoding="utf-8"):
        case = json.loads(line)
        files.append(f"data/interim/media/videos/{case['video']['video_name']}.mp4")
        files += [f"data/interim/media/images/{name}" for name in case["images"]]
    missing = [f for f in files if not (ROOT / f).exists()]
    if missing:
        raise SystemExit(f"missing locally: {missing[:5]} (run the regeneration steps in CLAUDE.md)")
    print("\n".join(sorted(set(files))))


if __name__ == "__main__":
    main()
