"""Run the pipeline over the synthetic claims and compute docs/HANDOFF.md section 8 metrics.

    python eval/run_eval.py --backend oracle             # offline, free (perfect-perception upper bound)
    python eval/run_eval.py --backend nim --limit 5      # prints the call/token estimate, does not call
    python eval/run_eval.py --backend nim --limit 5 --yes

Outputs data/interim/eval/<backend>/{results.jsonl, summary.md, reports/<case>.md}.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.backends import load_backend  # noqa: E402
from agent.cases import iter_cases  # noqa: E402
from agent.pipeline import run  # noqa: E402

# per-case token guesses for the nim backend (docs/HANDOFF.md 5.3: ~5.2k for 8 frames + candidates)
EST_TOKENS = {"video": 5_500, "damage": 4_000, "writer": 1_000}


def metrics(rows: list[dict]) -> dict:
    n = len(rows)
    top1 = sum(r["pred_code"] == r["true_code"] for r in rows)
    top3 = sum(r["true_code"] in r["pred_top3"] for r in rows)
    role_ok = sum(r["pred_claimant_role"] == r["true_claimant_role"] for r in rows)
    scored = [r for r in rows if r["fault_scored"]]   # chart mapping uncertain -> fault not scored
    fault_exact = sum(r["pred_claimant_fault"] == r["true_claimant_fault"] for r in scored)
    fault_10 = sum(abs(r["pred_claimant_fault"] - r["true_claimant_fault"]) <= 10 for r in scored)
    route_ok = sum(r["pred_route"] == r["true_route"] for r in rows)
    siu_true = [r for r in rows if r["true_route"] == "siu"]
    siu_pred = [r for r in rows if r["pred_route"] == "siu"]
    siu_tp = sum(r["pred_route"] == "siu" for r in siu_true)
    inj_true = sum(len(r["injected"]) for r in rows)
    inj_flagged = sum(len(r["flagged"]) for r in rows)
    inj_tp = sum(len(set(r["flagged"]) & set(r["injected"])) for r in rows)
    ape = [abs(r["pred_approved"] - r["true_approved"]) / r["true_approved"] for r in rows if r["true_approved"]]
    by_type = Counter((r["case_type"], r["pred_route"]) for r in rows)
    return {
        "cases": n,
        "accident_type_top1": top1 / n, "accident_type_top3": top3 / n,
        "claimant_role_accuracy": role_ok / n,
        "fault_scored_cases": len(scored),
        "claimant_fault_exact": fault_exact / len(scored) if scored else None,
        "claimant_fault_within_10pt": fault_10 / len(scored) if scored else None,
        "route_accuracy": route_ok / n,
        "siu_recall": siu_tp / len(siu_true) if siu_true else None,
        "siu_precision": siu_tp / len(siu_pred) if siu_pred else None,
        "injected_recall": inj_tp / inj_true if inj_true else None,
        "injected_precision": inj_tp / inj_flagged if inj_flagged else None,
        "approved_mape": sum(ape) / len(ape) if ape else None,
        "route_by_case_type": {f"{k[0]}->{k[1]}": v for k, v in sorted(by_type.items())},
        "calls": sum(r["calls"] for r in rows), "tokens": sum(r["tokens"] for r in rows),
        "seconds": round(sum(r["seconds"] for r in rows), 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="oracle", choices=["oracle", "nim"])
    ap.add_argument("--limit", type=int, default=0, help="first N cases only")
    ap.add_argument("--yes", action="store_true", help="actually call the nim backend")
    ap.add_argument("--base-url", default=None, help="self-hosted OpenAI-compatible server for nim")
    args = ap.parse_args()

    cases = list(iter_cases())
    if args.limit:
        cases = cases[:args.limit]
    if args.backend == "nim":
        calls = len(cases) * 3
        tokens = len(cases) * sum(EST_TOKENS.values())
        print(f"nim estimate: {len(cases)} cases -> {calls} calls (up to {calls * 3} with busy retries), ~{tokens:,} tokens")
        if not args.yes:
            print("not calling; re-run with --yes after confirming the cost")
            return
        backend = load_backend("nim", max_calls=calls * 3, base_url=args.base_url)
    else:
        backend = load_backend("oracle", truths={b.case_id: t for b, t in cases})

    out = ROOT / "data" / "interim" / "eval" / args.backend
    (out / "reports").mkdir(parents=True, exist_ok=True)
    rows = []
    with (out / "results.jsonl").open("w", encoding="utf-8") as f:
        for bundle, truth in cases:
            res = run(bundle, backend)
            (out / "reports" / f"{bundle.case_id}.md").write_text(res.report_md, encoding="utf-8")
            row = {
                "case_id": bundle.case_id, "case_type": truth.case_type,
                "true_code": truth.accident_type, "pred_code": res.fault.code, "pred_top3": res.video.top3,
                "true_claimant_role": truth.claimant_role, "pred_claimant_role": res.fault.claimant_role,
                "true_claimant_fault": truth.claimant_fault, "pred_claimant_fault": res.fault.claimant_fault,
                "fault_scored": truth.fault_scored, "pred_chart": res.fault.chart,
                "true_route": truth.expected_route, "pred_route": res.decision.route,
                "injected": truth.injected, "flagged": [c.line.name for c in res.lines if c.flagged],
                "true_approved": truth.approved_total, "pred_approved": res.decision.approved_total,
                "payout": res.decision.payout_estimate,
                "calls": sum(t.calls for t in res.trace), "tokens": sum(t.tokens for t in res.trace),
                "seconds": sum(t.seconds for t in res.trace),
            }
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    m = metrics(rows)
    note = " (정답 주입: 인식이 완벽할 때의 상한, 실제 모델 성능 아님)" if args.backend == "oracle" else ""
    lines = [f"# 평가 결과 — backend `{args.backend}`{note}", "", "| 지표 | 값 |", "|---|---|"]
    for k, v in m.items():
        lines.append(f"| {k} | {v:.3f} |" if isinstance(v, float) else f"| {k} | {v} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
