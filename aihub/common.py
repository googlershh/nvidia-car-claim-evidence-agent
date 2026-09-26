"""Paths and small helpers shared by the parsers."""

from __future__ import annotations

import json
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
INTERIM_DIR = ROOT / "data" / "interim"

_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def find_files(dataset_key: str, pattern: str) -> list[Path]:
    """Files under data/raw/<dataset_key> matching a glob pattern, sorted."""
    return sorted((RAW_DIR / dataset_key).rglob(pattern))


def find_file(dataset_key: str, pattern: str) -> Path:
    files = find_files(dataset_key, pattern)
    if not files:
        raise FileNotFoundError(f"no {pattern} under {RAW_DIR / dataset_key}; run scripts/download_aihub.py")
    return files[0]


def iter_zip_json(path: Path) -> Iterator[tuple[str, dict]]:
    """Yield (member name, parsed JSON) for every .json member of a zip."""
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith(".json"):
                yield name, json.loads(z.read(name).decode("utf-8-sig"))


def to_number(text: object) -> float | int | None:
    """Parse '1,441,370', '33,000원', '67,219Km', 1.24 -> number; '' / None -> None."""
    if text is None or isinstance(text, (int, float)):
        return text
    m = _NUM_RE.search(str(text))
    if not m:
        return None
    s = m.group().replace(",", "")
    return float(s) if "." in s else int(s)


def rate_and_amount(text: str | None) -> tuple[float | int | None, float | int | None]:
    """Parse '10%(144,137)' or '10(82,597)' -> (10, 144137)."""
    if not text:
        return None, None
    m = re.match(r"\s*([\d.]+)\s*%?\s*\(([\d,.\-]*)\)", text)
    if not m:
        return None, to_number(text)
    return to_number(m.group(1)), to_number(m.group(2))
