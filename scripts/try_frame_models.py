"""Small frame-based accident-type trial for an image-capable hosted model.

Sends the nim backend's video prompt (8 frames + English candidate table + ego
role question, agent/backends/nim.py) for a few clips of the reviewed fault set
and scores the answer against the reviewed label (code, ego role, ego fault).
Hard call cap including retries on HTTP 503; responses are cached.

Usage:
    python scripts/try_frame_models.py --model deepseek-ai/deepseek-v4.1-flash --ids F016 F049 F053
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.backends.nim import _Video  # noqa: E402
from agent.nim_client import NimClient  # noqa: E402
from agent.schemas import ClaimBundle  # noqa: E402
from agent.tools.fault import codes_ko  # noqa: E402

VIDEOS = ROOT / "data" / "interim" / "media" / "videos"
OUT = ROOT / "data" / "interim" / "trials"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--ids", nargs="+", required=True)
    ap.add_argument("--max-calls", type=int, default=6)
    ap.add_argument("--max-tokens", type=int, default=4096)
    args = ap.parse_args()

    truth = {r["eval_id"]: r for r in csv.DictReader(
        (ROOT / "data" / "interim" / "eval_fault_reviewed.csv").open(encoding="utf-8-sig"))}
    missing = [i for i in args.ids if i not in truth]
    if missing:
        raise SystemExit(f"not in the reviewed set: {missing}")
    client = NimClient(max_calls=args.max_calls, timeout=900, retries_on_busy=1, busy_wait=30)
    usage = {"prompt": 0, "completion": 0}

    def tally(resp: dict) -> None:
        u = resp.get("usage") or {}
        usage["prompt"] += u.get("prompt_tokens", 0)
        usage["completion"] += u.get("completion_tokens", 0)

    video = _Video(client, tally, model=args.model, max_tokens=args.max_tokens)
    codes = codes_ko()
    rows = []
    for eid in args.ids:
        t = truth[eid]
        bundle = ClaimBundle(case_id=eid, video=VIDEOS / f"{t['video_name']}.mp4", photos=[], estimate=[])
        started = time.time()
        try:
            f = video.analyze(bundle)
            pred = f.top3[0] if f.top3 else None
            role = f.ego_role
            pred_fault = None
            if pred in codes:
                c = codes[pred]
                pred_fault = int(c["fault_b"] if role == "B" else c["fault_a"])
            row = {"eval_id": eid, "true_code": int(t["accident_type"]), "true_role": t["ego_role"],
                   "true_ego_fault": int(t["ego_fault"]), "pred_top3": f.top3, "pred_role": role,
                   "pred_ego_fault": pred_fault, "scene": f.scene}
        except Exception as e:  # keep going on API errors
            row = {"eval_id": eid, "error": str(e)[:300]}
        row["seconds"] = round(time.time() - started, 1)
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))

    ok = [r for r in rows if "error" not in r]
    if ok:
        print(f"\n{args.model}: {len(ok)}/{len(rows)} answered | "
              f"top1 {sum(r['pred_top3'][:1] == [r['true_code']] for r in ok)} | "
              f"top3 {sum(r['true_code'] in r['pred_top3'] for r in ok)} | "
              f"ego role {sum(r['pred_role'] == r['true_role'] for r in ok)} | "
              f"ego fault exact {sum(r['pred_ego_fault'] == r['true_ego_fault'] for r in ok)}")
    print(f"calls {client.calls}/{args.max_calls}, tokens prompt {usage['prompt']:,} completion {usage['completion']:,}")
    OUT.mkdir(parents=True, exist_ok=True)
    name = args.model.replace("/", "_")
    (OUT / f"frames_{name}.json").write_text(json.dumps({"model": args.model, "rows": rows, "usage": usage},
                                                        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
