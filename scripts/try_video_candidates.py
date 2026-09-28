"""Probe which hosted models can actually read our dashcam video.

Sends one eval clip (F003, straight-road rear-end) to each video-capable
candidate on build.nvidia.com and records whether the call works, the latency,
the token usage and the answer next to the code-table ground truth.
Hard cap: 10 calls in total (8 chat + 2 VILA) including retries on HTTP 503; responses are cached.

Candidates come from docs/HANDOFF.md 5.4. `nvidia/cosmos3-nano-reasoner` is not in
/v1/models; the call checks whether the hosted API accepts it anyway.

Usage:
    python scripts/try_video_candidates.py
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.nim_client import CallCapExceeded, NimClient  # noqa: E402
from scripts.try_video_models import PROMPT_EN, ground_truth, parse_json  # noqa: E402

VIDEO = "bb_1_100727_vehicle_21_024"  # F003
SMALL = ROOT / "data/interim/media/videos_small" / f"{VIDEO}.mp4"  # 720p 4fps, 181KB
TINY = ROOT / "data/interim/media/videos_tiny" / f"{VIDEO}.mp4"    # 640px 2fps, for VILA's inline limit
MAX_CALLS = 8  # + 2 for VILA = 10 total
OUT = ROOT / "data" / "interim" / "trials" / "video_candidates.json"

CHAT_MODELS = [
    ("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", {"chat_template_kwargs": {"enable_thinking": False}}, 1024),
    ("nvidia/cosmos3-nano-reasoner", {}, 1024),
    ("nvidia/cosmos-reason2-8b", {}, 1024),
    ("google/gemma-4-31b-it", {}, 1024),
    ("moonshotai/kimi-k2.6", {}, 2048),
]
VILA_PATH = "/vlm/nvidia/vila"


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def chat_payload(model: str, extra: dict, max_tokens: int) -> dict:
    return {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64(SMALL)}"}},
            {"type": "text", "text": PROMPT_EN},
        ]}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
        **extra,
    }


def vila_payload() -> dict:
    return {
        "messages": [{"role": "user",
                      "content": f'{PROMPT_EN} <video src="data:video/mp4;base64,{b64(TINY)}" />'}],
        "max_tokens": 1024,
        "temperature": 0.2,
        "num_frames_per_inference": 16,
    }


def run(label: str, fn) -> dict:
    rec = {"model": label}
    started = time.time()
    try:
        resp = fn()
        msg = resp["choices"][0]["message"]
        content = msg.get("content") or ""
        rec.update(ok=True, content=content, parsed=parse_json(content), usage=resp.get("usage"),
                   reasoning=(msg.get("reasoning_content") or "")[:800])
    except CallCapExceeded as e:
        rec.update(ok=False, error=f"skipped: {e}")
    except Exception as e:
        rec.update(ok=False, error=str(e)[:400])
    rec["seconds"] = round(time.time() - started, 1)
    return rec


def main() -> None:
    truth = ground_truth()[VIDEO]
    client = NimClient(max_calls=MAX_CALLS, retries_on_busy=1, busy_wait=30)
    vila = NimClient(max_calls=2, retries_on_busy=1, busy_wait=30, base_url="https://ai.api.nvidia.com/v1")
    print("truth:", json.dumps(truth, ensure_ascii=False))
    results = []
    for model, extra, max_tokens in CHAT_MODELS:
        rec = run(model, lambda: client.chat(chat_payload(model, extra, max_tokens), tag=f"video_candidates:{model}"))
        results.append(rec)
        print(f"\n== {model} | ok={rec['ok']} | {rec['seconds']}s | usage={rec.get('usage')}")
        print("  ", json.dumps(rec.get("parsed") or rec.get("error") or rec.get("content"), ensure_ascii=False)[:700])
    rec = run("nvidia/vila", lambda: vila._post(VILA_PATH, vila_payload(), tag="video_candidates:nvidia/vila"))
    results.append(rec)
    print(f"\n== nvidia/vila | ok={rec['ok']} | {rec['seconds']}s | usage={rec.get('usage')}")
    print("  ", json.dumps(rec.get("parsed") or rec.get("error") or rec.get("content"), ensure_ascii=False)[:700])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"truth": truth, "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ncalls: chat {client.calls}/{MAX_CALLS}, vila {vila.calls}/2; saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
