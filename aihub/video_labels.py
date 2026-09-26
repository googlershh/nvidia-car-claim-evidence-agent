"""597 traffic accident video labels (TL/VL zips).

Three schema variants are mixed in the files (docs/HANDOFF.md 7.3):
- fault ratio as `accident_negligence_rateA/B`, or a single
  `accident_negligence_rate` which is vehicle A's fault (checked against the
  code table: 70/70 decidable files match A)
- accident type as `traffic_accident_type` or `accident_type`
The manual spells the fields `accidental_negligence_rate*`; those are accepted too.
For first-person (blackbox) video the filming vehicle is object B.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .common import find_files, iter_zip_json

_ZIP_RE = re.compile(r"^(?P<split>[TV])L_(?P<object>[^_]+)_영상_(?P<place>.+)\.zip$")


@dataclass
class VideoLabel:
    video_name: str
    split: str                 # "train" | "val"
    zip_object: str            # e.g. 차대차 (from zip name)
    zip_place: str             # e.g. 직선도로 (from zip name)
    video_date: str
    filming_way: str           # bb (blackbox) | cc (cctv)
    point_of_view: int         # 1 first person | 3 third person
    accident_type: int
    fault_a: int
    fault_b: int
    accident_object: int
    accident_place: int
    accident_place_feature: int
    a_progress: int
    b_progress: int
    schema: str                # which field names the file used


def _first(v: dict, *keys: str):
    for k in keys:
        if k in v and v[k] is not None:
            return k, v[k]
    return None, None


def parse_record(video: dict, split: str, zip_object: str, zip_place: str) -> VideoLabel:
    type_key, accident_type = _first(video, "traffic_accident_type", "accident_type")
    _, rate_a = _first(video, "accident_negligence_rateA", "accidental_negligence_rateA")
    _, rate_b = _first(video, "accident_negligence_rateB", "accidental_negligence_rateB")
    if rate_a is None:
        _, rate_a = _first(video, "accident_negligence_rate", "accidental_negligence_rate")
        rate_b = None if rate_a is None else 100 - rate_a
        schema = f"rate_single/{type_key}"
    else:
        schema = f"rate_ab/{type_key}"
    if accident_type is None or rate_a is None:
        raise ValueError(f"{video.get('video_name')}: missing accident type or fault ratio")
    return VideoLabel(
        video_name=video["video_name"],
        split=split,
        zip_object=zip_object,
        zip_place=zip_place,
        video_date=video.get("video_date", ""),
        filming_way=video["filming_way"],
        point_of_view=int(video["video_point_of_view"]),
        accident_type=int(accident_type),
        fault_a=int(rate_a),
        fault_b=int(rate_b),
        accident_object=int(video["accident_object"]),
        accident_place=int(video["accident_place"]),
        accident_place_feature=int(video["accident_place_feature"]),
        a_progress=int(video["vehicle_a_progress_info"]),
        b_progress=int(video["vehicle_b_progress_info"]),
        schema=schema,
    )


def iter_labels(zip_paths: list[Path] | None = None) -> Iterator[VideoLabel]:
    for path in zip_paths or find_files("597", "[TV]L_*_영상_*.zip"):
        m = _ZIP_RE.match(path.name)
        if not m:
            continue
        split = "train" if m["split"] == "T" else "val"
        for _, doc in iter_zip_json(path):
            yield parse_record(doc["video"], split, m["object"], m["place"])
