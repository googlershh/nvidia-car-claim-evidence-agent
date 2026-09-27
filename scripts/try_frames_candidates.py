"""Second trial: frames we choose + a candidate list of accident types.

For each of the three first-trial videos, send 8 evenly spaced frames
(640px, chronological) to Nemotron 3 Nano Omni together with the 84 in-scope
car-to-car accident type codes and ask for the top-3 codes. The candidate
table is English (data/reference/accident_codes_en.csv) by default, or the
Korean manual text with `ko`. Each video is asked twice: reasoning on and off.

Guards: at most MAX_CALLS chat calls (default 6, retries after HTTP 503
included), and stop once cumulative tokens exceed 60,000. Successful
responses are cached, so a re-run only calls for the ones that failed.

Usage:
    python scripts/try_frames_candidates.py [max_calls] [en|ko]
"""

from __future__ import annotations

import base64
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.nim_client import NimClient  # noqa: E402

VIDEOS = ["bb_1_100727_vehicle_21_024", "bb_1_161120_vehicle_255_34198", "bb_1_141105_vehicle_29_166"]
PLACES = ("직선도로", "사거리교차로(신호등있음)", "T자형교차로")
OMNI = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
MAX_CALLS = int(sys.argv[1]) if len(sys.argv) > 1 else 6
LANG = sys.argv[2] if len(sys.argv) > 2 else "en"   # candidate table: en (data/reference) or ko (manual)
TOKEN_BUDGET = 60_000
OUT = ROOT / "data" / "interim" / "trials" / f"second_trial_{LANG}.json"


def load_codes() -> list[dict]:
    rows = csv.DictReader((ROOT / "data/interim/accident_codes.csv").open(encoding="utf-8-sig"))
    return [r for r in rows if r["accident_object"] == "차대차" and r["place_key"] in PLACES]


def candidate_block(codes: list[dict]) -> str:
    lines = ["code | place | situation | vehicle A | vehicle B"]
    if LANG == "en":
        en = {r["code"]: r for r in csv.DictReader((ROOT / "data/reference/accident_codes_en.csv").open(encoding="utf-8"))}
        lines += [f"{c['code']} | {en[c['code']]['place']} | {en[c['code']]['situation']} | "
                  f"{en[c['code']]['vehicle_a']} | {en[c['code']]['vehicle_b']}" for c in codes]
    else:
        lines += [f"{c['code']} | {c['place_key']} | {c['place_feature']} | {c['a_progress']} | {c['b_progress']}" for c in codes]
    return "\n".join(lines)


def prompt(codes: list[dict], times: list[float]) -> str:
    return f"""These {len(times)} images are frames from one dashcam clip, in chronological order, taken at t = {', '.join(f'{t:.2f}' for t in times)} seconds.
The camera is mounted in the ego vehicle. Traffic in South Korea drives on the right.
A collision between the ego vehicle and one other vehicle happens in the clip.

In the candidate table below, the ego vehicle is always "vehicle B" and the other vehicle is "vehicle A".
Choose the accident type codes that best match what happens. Consider the road layout, traffic signals,
the direction each vehicle travels (straight, left turn, right turn, lane change, stopped...) and where they collide.

{candidate_block(codes)}

Return only this JSON:
{{"top3": [code, code, code], "ego_movement": "...", "other_movement": "...", "road_type": "...", "evidence": "1-2 sentences in English citing frame times"}}"""


def payload(frames: list[Path], text: str, thinking: bool) -> dict:
    content = [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(f.read_bytes()).decode("ascii")}}
               for f in frames]
    content.append({"type": "text", "text": text})
    return {"model": OMNI, "messages": [{"role": "user", "content": content}], "max_tokens": 4096,
            "temperature": 0.2, "chat_template_kwargs": {"enable_thinking": thinking}}


def parse_json(text: str | None) -> dict | None:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group()) if m else None
    except json.JSONDecodeError:
        return None


def main() -> None:
    codes = load_codes()
    by_code = {c["code"]: c for c in codes}
    truth = {r["video_name"]: r for r in csv.DictReader((ROOT / "data/interim/eval_fault.csv").open(encoding="utf-8-sig"))
             if r["video_name"] in VIDEOS}
    client = NimClient(max_calls=MAX_CALLS, retries_on_busy=2, busy_wait=30)
    used_tokens, results = 0, []
    for name in VIDEOS:
        frames = sorted((ROOT / "data/interim/media/frames" / name).glob("f*_t*.jpg"))
        times = [float(re.search(r"_t([\d.]+)\.jpg", f.name).group(1)) for f in frames]
        for thinking in (True, False):
            if used_tokens > TOKEN_BUDGET:
                print(f"token budget {TOKEN_BUDGET} exceeded ({used_tokens}); stopping")
                break
            t = truth[name]
            rec = {"video": name, "eval_id": t["eval_id"], "thinking": thinking, "truth_code": t["accident_type"]}
            try:
                resp = client.chat(payload(frames, prompt(codes, times), thinking), tag=f"second_trial:{name}:{thinking}")
                msg = resp["choices"][0]["message"]
                rec.update(content=msg.get("content"), parsed=parse_json(msg.get("content")), usage=resp.get("usage"))
                used_tokens += (resp.get("usage") or {}).get("total_tokens", 0)
            except Exception as e:
                rec["error"] = str(e)[:500]
            results.append(rec)
            top3 = [str(c) for c in ((rec.get("parsed") or {}).get("top3") or [])]
            tc = by_code[t["accident_type"]]
            print(f"\n== {t['eval_id']} thinking={thinking} | truth {t['accident_type']}: {tc['place_key']} / A {tc['a_progress']} / B {tc['b_progress']}")
            for rank, c in enumerate(top3, 1):
                d = by_code.get(c)
                mark = "  <== truth" if c == t["accident_type"] else ""
                print(f"   #{rank} {c}: " + (f"{d['place_key']} / A {d['a_progress']} / B {d['b_progress']}" if d else "(not a candidate)") + mark)
            p = rec.get("parsed") or {}
            print("   ego:", p.get("ego_movement"), "| other:", p.get("other_movement"), "| road:", p.get("road_type"))
            print("   evidence:", (p.get("evidence") or rec.get("error") or (rec.get("content") or "")[:300]))
            print("   usage:", rec.get("usage"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    hits1 = sum(1 for r in results if (r.get("parsed") or {}).get("top3") and str(r["parsed"]["top3"][0]) == r["truth_code"])
    hits3 = sum(1 for r in results if r["truth_code"] in [str(c) for c in ((r.get("parsed") or {}).get("top3") or [])])
    print(f"\ntop-1 {hits1}/{len(results)}, top-3 {hits3}/{len(results)}; calls {client.calls}/{MAX_CALLS}; tokens {used_tokens}")


if __name__ == "__main__":
    main()
