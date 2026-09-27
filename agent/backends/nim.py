"""Hosted NIM backend (build.nvidia.com). NOT RUN YET: needs billing / free-tier capacity.

Settings follow docs/HANDOFF.md 5.3 (third trial, the one that got F003 right):
- video: 8 evenly spaced frames (640px) + English candidate table, reasoning off
- damage: photos + a fixed English part vocabulary, reasoning off
- writer: Nemotron 3 Ultra writes only the Korean narrative paragraph; every
  number in the report stays in the deterministic template
For DGX Spark self-hosting, pass base_url of the local OpenAI-compatible server.
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
from pathlib import Path

from aihub.parts import _EN_BASE

from ..nim_client import NimClient
from ..schemas import ClaimBundle, ClaimResult, DamageFinding, VideoFinding
from ..tools.damage import photo_directions
from ..tools.fault import candidate_table_en
from ..tools.report import template_report

OMNI = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
ULTRA = "nvidia/nemotron-3-ultra-550b-a55b"
ROOT = Path(__file__).resolve().parents[2]
FRAME_DIR = ROOT / "data" / "interim" / "media" / "frames"
N_FRAMES = 8
MAX_PHOTOS = 6
SIDED = {"Front door", "Rear door", "Front fender", "Rear fender", "A pillar", "B pillar", "C pillar",
         "Front Wheel", "Rear Wheel", "Rocker panel", "Side mirror", "Head lights", "Rear lamp"}
PART_VOCAB = sorted({b for b in _EN_BASE} | {f"{b}(L)" for b in SIDED} | {f"{b}(R)" for b in SIDED})


def _data_url(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _parse_json(text: str | None) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group()) if m else {}
    except json.JSONDecodeError:
        return {}


def extract_frames(video: Path, n: int = N_FRAMES, duration: float = 10.0) -> list[tuple[float, Path]]:
    out = FRAME_DIR / video.stem
    out.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(n):
        t = round(duration * (i + 0.5) / n, 3)
        f = out / f"f{i}_t{t}.jpg"
        if not f.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(video), "-frames:v", "1",
                            "-vf", "scale=640:-2", "-q:v", "4", str(f)], check=True)
        frames.append((t, f))
    return frames


class _Video:
    def __init__(self, client: NimClient, tally):
        self.client, self.tally = client, tally

    def analyze(self, bundle: ClaimBundle) -> VideoFinding:
        frames = extract_frames(bundle.video)
        text = f"""These {len(frames)} images are frames from one dashcam clip, in chronological order, taken at t = {', '.join(f'{t:.2f}' for t, _ in frames)} seconds.
The camera is mounted in the ego vehicle. Traffic in South Korea drives on the right.
A collision between the ego vehicle and one other vehicle happens in the clip.

In the candidate table below, the ego vehicle is always "vehicle B" and the other vehicle is "vehicle A".
Choose the accident type codes that best match what happens. Consider the road layout, traffic signals,
the direction each vehicle travels (straight, left turn, right turn, lane change, stopped...) and where they collide.

{candidate_table_en()}

Return only this JSON:
{{"top3": [code, code, code], "ego_movement": "...", "other_movement": "...", "road_type": "...", "evidence": "1-2 sentences in English citing frame times"}}"""
        content = [{"type": "image_url", "image_url": {"url": _data_url(f, "image/jpeg")}} for _, f in frames]
        content.append({"type": "text", "text": text})
        resp = self.client.chat({"model": OMNI, "messages": [{"role": "user", "content": content}], "max_tokens": 1024,
                                 "temperature": 0.2, "chat_template_kwargs": {"enable_thinking": False}},
                                tag=f"video:{bundle.case_id}")
        self.tally(resp)
        p = _parse_json(resp["choices"][0]["message"].get("content"))
        top3 = [int(c) for c in p.get("top3", []) if str(c).isdigit()]
        return VideoFinding(top3=top3, scene={k: v for k, v in p.items() if k != "top3"}, source=OMNI)


class _Damage:
    def __init__(self, client: NimClient, tally):
        self.client, self.tally = client, tally

    def analyze(self, bundle: ClaimBundle) -> DamageFinding:
        photos = bundle.photos[:MAX_PHOTOS]
        text = ("These are photos of one damaged car. List the damaged exterior parts you can see, using only names "
                "from this vocabulary ((L) = left side, (R) = right side of the car):\n" + ", ".join(PART_VOCAB)
                + '\nReturn only this JSON: {"parts": ["..."], "notes": "one sentence"}')
        content = [{"type": "image_url", "image_url": {"url": _data_url(p, "image/jpeg")}} for p in photos]
        content.append({"type": "text", "text": text})
        resp = self.client.chat({"model": OMNI, "messages": [{"role": "user", "content": content}], "max_tokens": 512,
                                 "temperature": 0.2, "chat_template_kwargs": {"enable_thinking": False}},
                                tag=f"damage:{bundle.case_id}")
        self.tally(resp)
        parts = [p for p in _parse_json(resp["choices"][0]["message"].get("content")).get("parts", []) if p in PART_VOCAB]
        return DamageFinding(parts=parts, directions=photo_directions(parts), source=OMNI)


class _Writer:
    def __init__(self, client: NimClient, tally):
        self.client, self.tally = client, tally

    def write(self, result: ClaimResult) -> str:
        body = template_report(result)
        facts = {"사고유형": f"{result.fault.code} {result.fault.place} {result.fault.situation}",
                 "상대차량": result.fault.a_progress, "청구차량": result.fault.b_progress,
                 "영상근거": result.video.scene.get("evidence", ""), "손상부위": result.damage.parts,
                 "권고": result.decision.route}
        resp = self.client.chat({"model": ULTRA, "max_tokens": 400, "temperature": 0.3, "messages": [
            {"role": "system", "content": "당신은 손해보험사 대물보상 담당자의 보조자다. 주어진 사실만 사용하고 숫자는 쓰지 않는다."},
            {"role": "user", "content": "다음 사실로 사고 경위를 한국어 3~4문장으로 요약하라.\n" + json.dumps(facts, ensure_ascii=False)}]},
            tag=f"writer:{result.case_id}")
        self.tally(resp)
        summary = (resp["choices"][0]["message"].get("content") or "").strip()
        head, _, rest = body.partition("## 1. 처리 권고")
        return f"{head}## 0. 사고 경위 요약\n{summary}\n\n## 1. 처리 권고{rest}"


class NimBackend:
    name = "nim"

    CALLS_PER_CASE = 3   # video, damage, writer

    def __init__(self, max_calls: int, retries_on_busy: int = 2, base_url: str | None = None):
        kwargs = {"base_url": base_url} if base_url else {}
        self.client = NimClient(max_calls=max_calls, retries_on_busy=retries_on_busy, **kwargs)
        self.tokens = 0
        self.video = _Video(self.client, self._tally)
        self.damage = _Damage(self.client, self._tally)
        self.writer = _Writer(self.client, self._tally)

    def _tally(self, resp: dict) -> None:
        self.tokens += (resp.get("usage") or {}).get("total_tokens", 0)

    def usage(self) -> tuple[int, int]:
        return self.client.calls, self.tokens
