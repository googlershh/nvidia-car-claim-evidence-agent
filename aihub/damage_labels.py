"""581 vehicle damage labels (COCO-like JSON, one file per image).

Two label sets share the format:
- `damage`: damage-type polygons; `part` and `level` are always null
- `damage_part`: adds part polygons with `part` and `level` (severity 1~4,
  4 = most severe, inferred from exchange rates; the manual does not say)

`categories.id` is the accident ID (manual: "사고 ID") and equals the repair
estimate file name (e.g. `as-0000043`). `repair` entries look like
"Front bumper:coating,exchange"; they are merged over an image's annotations
(a list in `damage`, sometimes a bare string in `damage_part`).
Segmentation polygons are dropped to keep the parsed records small.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .common import find_file, iter_zip_json


@dataclass
class Annotation:
    damage: str | None         # Scratched | Separated | Crushed | Breakage
    part: str | None
    level: int | None
    bbox: list[float]
    area: float


@dataclass
class DamageImage:
    image_file: str
    label_set: str             # damage | damage_part
    accident_id: str           # categories.id == estimate file stem
    source: str                # socar | external
    car_size: str              # CityCar | Compact car | Mid-size car | Full-size car
    year: int | None
    color: str | None
    width: int
    height: int
    repair: dict[str, list[str]]   # part -> methods (coating, exchange, sheet_metal, repair)
    annotations: list[Annotation] = field(default_factory=list)


def parse_repair(items: list[str] | str | None, out: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    """Merge "Part:method,method" entries into `out`. Some damage_part files store one string, not a list."""
    out = {} if out is None else out
    if isinstance(items, str):
        items = [items]
    for item in items or []:
        if ":" not in item:
            continue
        part, _, methods = item.partition(":")
        out.setdefault(part.strip(), [])
        for m in methods.split(","):
            if m and m not in out[part.strip()]:
                out[part.strip()].append(m.strip())
    return out


def parse_record(doc: dict, label_set: str) -> DamageImage:
    anns = doc.get("annotations", [])
    first = anns[0] if anns else {}
    image = doc["images"]
    repair: dict[str, list[str]] = {}
    for a in anns:
        parse_repair(a.get("repair"), repair)
    return DamageImage(
        image_file=image["file_name"],
        label_set=label_set,
        accident_id=doc["categories"]["id"],
        source=doc["info"].get("name", ""),
        car_size=doc["categories"].get("supercategory_name", ""),
        year=first.get("year"),
        color=first.get("color"),
        width=image.get("width"),
        height=image.get("height"),
        repair=repair,
        annotations=[
            Annotation(a.get("damage"), a.get("part"), a.get("level"), a.get("bbox", []), a.get("area", 0.0))
            for a in anns
        ],
    )


def iter_images(label_set: str = "damage", zip_path: Path | None = None) -> Iterator[DamageImage]:
    """label_set: 'damage' or 'damage_part'. Defaults to the VL zip."""
    path = zip_path or find_file("581", f"VL_{label_set}.zip")
    for _, doc in iter_zip_json(path):
        yield parse_record(doc, label_set)
