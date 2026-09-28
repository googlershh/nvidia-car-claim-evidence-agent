"""Frame-based accident-type judgment through OpenRouter (same prompt as the nim backend).

Sends 8 frames + the English candidate table + the ego-role question (agent/backends/nim.py
`video_prompt`) for reviewed clips and scores code, ego role and ego fault. Reads
OPENROUTER_API_KEY from the environment; prints usage and cost from OpenRouter's response.

    OPENROUTER_API_KEY=... python3 scripts/try_openrouter_frames.py --model deepseek/deepseek-v4.1-flash --ids F007

Defaults: reasoning effort high, 48k output tokens. On F007 (2026-09-28) DeepSeek V4.1 Flash with
no effort set spent all 16k tokens thinking and gave no answer ($0.02); "low" answered but called it a
rear-end; "high" stopped by itself after ~5.8k reasoning tokens and picked the right type (~$0.008).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.backends.nim import _data_url, _parse_json, extract_frames, video_prompt  # noqa: E402
from agent.tools.fault import chart_map  # noqa: E402

URL = "https://openrouter.ai/api/v1/chat/completions"
OUT = ROOT / "data" / "interim" / "trials"


def call(model: str, content: list, max_tokens: int, timeout: int, effort: str) -> dict:
    payload = {"model": model, "messages": [{"role": "user", "content": content}],
               "max_tokens": max_tokens, "temperature": 0.2, "usage": {"include": True}}
    if effort:
        # reasoning models otherwise spend the whole budget thinking and never emit the JSON
        payload["reasoning"] = {"effort": effort}
    body = json.dumps(payload).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--ids", nargs="+", required=True)
    ap.add_argument("--max-tokens", type=int, default=48000)
    ap.add_argument("--timeout", type=int, default=1500)
    ap.add_argument("--reasoning-effort", default="high", help="low | medium | high | '' (provider default)")
    args = ap.parse_args()
    truth = {r["eval_id"]: r for r in csv.DictReader(
        (ROOT / "data" / "interim" / "eval_fault_reviewed.csv").open(encoding="utf-8-sig"))}
    cm = chart_map()
    rows, cost = [], 0.0
    for eid in args.ids:
        t = truth[eid]
        frames = extract_frames(ROOT / "data" / "interim" / "media" / "videos" / f"{t['video_name']}.mp4")
        content = [{"type": "image_url", "image_url": {"url": _data_url(f, "image/jpeg")}} for _, f in frames]
        content.append({"type": "text", "text": video_prompt([s for s, _ in frames])})
        started = time.time()
        resp = call(args.model, content, args.max_tokens, args.timeout, args.reasoning_effort)
        msg = resp["choices"][0]["message"]
        p = _parse_json(msg.get("content"))
        top3 = [int(c) for c in p.get("top3", []) if str(c).isdigit()]
        role = str(p.get("ego_role", "")).strip().upper()[:1]
        pred_fault = None
        if top3 and top3[0] in cm and role in ("A", "B"):
            pred_fault = int(cm[top3[0]]["chart_fault_a" if role == "A" else "chart_fault_b"])
        usage = resp.get("usage", {})
        cost += float(usage.get("cost") or 0)
        rows.append({"eval_id": eid, "true_code": int(t["accident_type"]), "true_role": t["ego_role"],
                     "true_ego_fault": int(t["ego_fault"]), "review_confidence": t["review_confidence"],
                     "pred_top3": top3, "pred_role": role, "pred_ego_fault": pred_fault,
                     "scene": {k: v for k, v in p.items() if k not in ("top3", "ego_role")},
                     "finish_reason": resp["choices"][0].get("finish_reason"), "usage": usage,
                     "seconds": round(time.time() - started, 1)})
        print(json.dumps(rows[-1], ensure_ascii=False, indent=1))
    print(f"\n{args.model}: cost ${cost:.4f}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"openrouter_{args.model.replace('/', '_')}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
