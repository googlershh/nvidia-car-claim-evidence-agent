"""Run one synthetic claim through the pipeline and print the draft report.

    python scripts/run_case.py C003                  # offline oracle backend
    python scripts/run_case.py C003 --backend nim --yes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.backends import load_backend  # noqa: E402
from agent.cases import iter_cases  # noqa: E402
from agent.pipeline import run  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_id")
    ap.add_argument("--backend", default="oracle", choices=["oracle", "nim"])
    ap.add_argument("--yes", action="store_true", help="actually call the nim backend (3 calls)")
    args = ap.parse_args()

    found = {b.case_id: (b, t) for b, t in iter_cases()}
    if args.case_id not in found:
        raise SystemExit(f"unknown case {args.case_id}")
    bundle, truth = found[args.case_id]
    if args.backend == "nim":
        if not args.yes:
            raise SystemExit("nim backend makes 3 calls (~10k tokens); re-run with --yes after confirming the cost")
        backend = load_backend("nim", max_calls=9)
    else:
        backend = load_backend("oracle", truths={truth.case_id: truth})
    res = run(bundle, backend)
    sys.stdout.reconfigure(encoding="utf-8")
    print(res.report_md)
    print("\n---\ntrace:", [(t.stage, t.seconds, t.calls, t.tokens) for t in res.trace])
    print(f"truth: type {truth.case_type}, route {truth.expected_route}, code {truth.accident_type}, "
          f"approved {truth.approved_total:,}, injected {truth.injected}")


if __name__ == "__main__":
    main()
