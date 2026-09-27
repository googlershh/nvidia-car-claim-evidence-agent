"""First trial: can hosted video models read our dashcam clips?

Sends three downscaled eval videos (720p, 4 fps, no audio) to Nemotron 3 Nano
Omni and Cosmos Reason 2, asks for a fixed JSON description of the accident,
and prints it next to the code-table ground truth. One Omni call uses a
Korean prompt to probe Korean understanding. Hard cap: 6 chat calls; cached
responses are reused on re-runs.

Usage:
    python scripts/try_video_models.py
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
KOREAN_PROMPT_FOR = "bb_1_141105_vehicle_29_166"
OMNI = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
COSMOS = "nvidia/cosmos-reason2-8b"
MAX_CALLS = 6
OUT = ROOT / "data" / "interim" / "trials" / "first_trial.json"

SCHEMA = """{
  "road_type": "straight_road | signalized_4way_intersection | unsignalized_4way_intersection | t_junction | other",
  "ego_signal": "green | yellow | red | green_left_arrow | no_signal | not_visible",
  "ego_movement": "straight | left_turn | right_turn | u_turn | lane_change | stopped | reversing",
  "other_vehicle_position_before_collision": "ahead_same_direction | behind_same_direction | oncoming | from_left | from_right | adjacent_lane",
  "other_vehicle_movement": "straight | left_turn | right_turn | u_turn | lane_change | stopped | reversing",
  "collision": true,
  "collision_time_sec": 0.0,
  "ego_impact_area": "front | rear | left | right | none_visible",
  "other_impact_area": "front | rear | left | right | none_visible",
  "description": "2-3 sentences"
}"""

PROMPT_EN = f"""This is a dashcam video recorded from the ego vehicle (the camera car) in South Korea (right-hand traffic).
A traffic accident between the ego vehicle and one other vehicle happens in the clip.
Describe it by filling this JSON. Pick one value from each list; use "not_visible" only if it truly cannot be seen.
Return only the JSON.
{SCHEMA}"""

PROMPT_KO = f"""이 영상은 한국(우측통행)에서 자기 차량(카메라가 달린 차)의 블랙박스로 찍은 영상입니다.
영상 속에서 자기 차량과 다른 차량 1대 사이에 교통사고가 납니다.
아래 JSON을 채워 사고를 설명하세요. 각 항목은 목록 중 하나를 고르고, 정말 보이지 않을 때만 "not_visible"을 쓰세요.
"description"은 한국어 2~3문장으로 쓰고, JSON만 출력하세요.
{SCHEMA}"""


def ground_truth() -> dict[str, dict]:
    codes = {r["code"]: r for r in csv.DictReader((ROOT / "data/interim/accident_codes.csv").open(encoding="utf-8-sig"))}
    out = {}
    for r in csv.DictReader((ROOT / "data/interim/eval_fault.csv").open(encoding="utf-8-sig")):
        if r["video_name"] in VIDEOS:
            c = codes[r["accident_type"]]
            out[r["video_name"]] = {"eval_id": r["eval_id"], "type": r["accident_type"], "place": c["place_key"],
                                    "feature": c["place_feature"], "A(other)": c["a_progress"],
                                    "B(ego)": c["b_progress"], "fault A:B": f"{c['fault_a']}:{c['fault_b']}"}
    return out


def payload(model: str, video: Path, prompt: str) -> dict:
    b64 = base64.b64encode(video.read_bytes()).decode("ascii")
    body = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64}"}},
            {"type": "text", "text": prompt},
        ]}],
        "max_tokens": 4096,
        "temperature": 0.2,
    }
    if model == OMNI:
        body["chat_template_kwargs"] = {"enable_thinking": True}
    return body


def parse_json(text: str) -> dict | None:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def main() -> None:
    client = NimClient(max_calls=MAX_CALLS)
    truth = ground_truth()
    results = []
    for name in VIDEOS:
        video = ROOT / "data/interim/media/videos_small" / f"{name}.mp4"
        for model in (OMNI, COSMOS):
            prompt = PROMPT_KO if (model == OMNI and name == KOREAN_PROMPT_FOR) else PROMPT_EN
            rec = {"video": name, "model": model, "prompt_lang": "ko" if prompt is PROMPT_KO else "en",
                   "truth": truth[name]}
            try:
                resp = client.chat(payload(model, video, prompt), tag=f"first_trial:{name}")
                msg = resp["choices"][0]["message"]
                rec.update(content=msg.get("content"), reasoning=(msg.get("reasoning_content") or "")[:1500],
                           parsed=parse_json(msg.get("content")), usage=resp.get("usage"))
            except Exception as e:
                rec["error"] = str(e)[:500]
            results.append(rec)
            print(f"\n== {truth[name]['eval_id']} {name} | {model.split('/')[1]} ({rec['prompt_lang']})")
            print("   truth :", json.dumps(truth[name], ensure_ascii=False))
            print("   model :", json.dumps(rec.get("parsed") or rec.get("error") or rec.get("content"), ensure_ascii=False)[:900])
            print("   usage :", rec.get("usage"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nchat calls made this run: {client.calls} (cap {MAX_CALLS}); saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
