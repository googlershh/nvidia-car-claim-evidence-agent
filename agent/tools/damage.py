"""parse_estimate / check_estimate: compare estimate lines with what the photos show."""

from __future__ import annotations

from aihub.parts import en_part_directions, ko_item_directions

from ..schemas import DamageFinding, EstimateLine, LineCheck

REPAIR_WORK = {"교환", "판금", "수리"}      # removal/refit and paint rows follow the repaired part
KO_DIR = {"front": "전면", "rear": "후면", "left": "좌측", "right": "우측"}


def ko_dirs(dirs: set[str]) -> str:
    return ", ".join(KO_DIR.get(d, d) for d in sorted(dirs)) or "없음"


def photo_directions(parts: list[str]) -> set[str]:
    dirs: set[str] = set()
    for p in parts:
        dirs |= en_part_directions(p)
    return dirs


def check_estimate(lines: list[EstimateLine], damage: DamageFinding) -> list[LineCheck]:
    """Flag repair lines whose part faces no photographed direction."""
    checks = []
    for line in lines:
        dirs = ko_item_directions(line.name)
        flagged = line.work in REPAIR_WORK and bool(dirs) and not dirs <= damage.directions
        reason = (f"'{line.name}' {line.work}: 부위 방향({ko_dirs(dirs)})이 사진의 손상 방향({ko_dirs(damage.directions)})과 겹치지 않거나 벗어남"
                  if flagged else "")
        checks.append(LineCheck(line=line, directions=dirs, flagged=flagged, reason=reason))
    return checks
