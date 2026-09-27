"""Minimal client for NVIDIA hosted NIM endpoints (OpenAI-compatible), stdlib only.

Guards against surprise usage:
- calls https://integrate.api.nvidia.com by default (or a self-hosted `base_url`),
  never partner endpoints
- a per-process call cap (`max_calls`); exceeding it raises instead of calling
- responses are cached by request hash under data/interim/api_cache, so re-runs
  of the same request cost nothing
- every real call is appended to data/interim/api_usage.jsonl with token usage

The API key comes from NVIDIA_API_KEY in the environment or the project .env
and is never printed or written anywhere else.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://integrate.api.nvidia.com/v1"
CACHE_DIR = ROOT / "data" / "interim" / "api_cache"
USAGE_LOG = ROOT / "data" / "interim" / "api_usage.jsonl"


class CallCapExceeded(RuntimeError):
    pass


def api_key() -> str:
    key = os.environ.get("NVIDIA_API_KEY")
    if not key and (ROOT / ".env").exists():
        m = re.search(r"^\s*NVIDIA_API_KEY\s*=\s*(\S+)", (ROOT / ".env").read_text(encoding="utf-8-sig"), re.M)
        key = m.group(1).strip("'\"") if m else None
    if not key:
        raise RuntimeError("NVIDIA_API_KEY is not set (put it in .env)")
    return key


class NimClient:
    def __init__(self, max_calls: int, timeout: float = 300.0, retries_on_busy: int = 0, busy_wait: float = 30.0,
                 base_url: str = BASE_URL):
        """retries_on_busy: extra attempts after HTTP 503 (shared free workers full); each counts as a call.
        base_url: another OpenAI-compatible server, e.g. vLLM/NIM on DGX Spark."""
        self.base_url = base_url.rstrip("/")
        self.max_calls = max_calls
        self.calls = 0
        self.timeout = timeout
        self.retries_on_busy = retries_on_busy
        self.busy_wait = busy_wait
        self._key = api_key()

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, method=method, headers={
            "Authorization": f"Bearer {self._key}",
            "Accept": "application/json",
            **({"Content-Type": "application/json"} if data else {}),
        })
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:800]
            raise RuntimeError(f"HTTP {e.code} from {path}: {detail}") from None

    def list_models(self) -> list[str]:
        """GET /models: no inference, no tokens."""
        return sorted(m["id"] for m in self._request("GET", "/models").get("data", []))

    def chat(self, payload: dict, tag: str = "") -> dict:
        """POST /chat/completions with cache, call cap and usage logging."""
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]
        cache = CACHE_DIR / f"{digest}.json"
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        for attempt in range(self.retries_on_busy + 1):
            try:
                return self._call(payload, tag, digest, cache)
            except RuntimeError as e:
                if "HTTP 503" not in str(e) or attempt == self.retries_on_busy:
                    raise
                time.sleep(self.busy_wait * (attempt + 1))
        raise AssertionError("unreachable")

    def _call(self, payload: dict, tag: str, digest: str, cache: Path) -> dict:
        if self.calls >= self.max_calls:
            raise CallCapExceeded(f"call cap {self.max_calls} reached; not calling {payload.get('model')}")
        self.calls += 1
        started = time.time()
        error = None
        try:
            result = self._request("POST", "/chat/completions", payload)
        except Exception as e:  # log failed attempts too
            error, result = str(e), None
        elapsed = round(time.time() - started, 2)
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with USAGE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "tag": tag, "model": payload.get("model"),
                                "request": digest, "seconds": elapsed, "usage": (result or {}).get("usage"),
                                "error": error}, ensure_ascii=False) + "\n")
        if error:
            raise RuntimeError(error)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result
