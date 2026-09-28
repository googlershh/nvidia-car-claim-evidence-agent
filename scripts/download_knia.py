"""Download the fault ratio standard (과실비율 인정기준) PDF from the KNIA portal.

Source: 손해보험협회 과실비율정보포털 자료실 > 기준정보,
"(2023.6.) 자동차사고 과실비율 인정기준(제10차 개정) 전문" (posted 2023-06-29).
The PDF stays in data/raw/knia/ (gitignored); only derived tables go into git.

Usage:
    python scripts/download_knia.py
"""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "knia" / "knia_fault_standard_10th_2023.pdf"
URL = "https://www.knia.or.kr/file-manager/105814"
SIZE = 16_982_418


def main() -> None:
    if OUT.exists() and OUT.stat().st_size == SIZE:
        print(f"already present: {OUT.relative_to(ROOT)}")
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://accident.knia.or.kr/"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = resp.read()
        if len(data) != SIZE or not data.startswith(b"%PDF"):
            raise SystemExit(f"unexpected download: {len(data)} bytes, starts with {data[:8]!r}")
        OUT.write_bytes(data)
        print(f"wrote {OUT.relative_to(ROOT)} ({len(data):,} bytes)")
    print("sha256", hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
