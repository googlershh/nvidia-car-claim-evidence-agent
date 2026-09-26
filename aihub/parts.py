"""Map vehicle parts to impact directions (front / rear / left / right).

Used to pair accident videos with damage photos (the video labels'
`damage_location` is always empty) and to judge whether claimed repair items
fit the collision. Corner parts belong to two directions (a front fender is
both front and its side) so a rear-end victim with a rear-quarter dent still
counts as consistent. Parts whose side is unknown ("Bumper", "Front door"
without L/R) or that face no direction (roof, undercarriage) map to an empty
set and are ignored by the consistency checks.
"""

from __future__ import annotations

import re

DIRECTIONS = ("front", "rear", "left", "right")

_EN_BASE = {
    "Front bumper": {"front"}, "Bonnet": {"front"}, "Head lights": {"front"}, "Windshield": {"front"},
    "Rear bumper": {"rear"}, "Trunk lid": {"rear"}, "Rear lamp": {"rear"}, "Rear windshield": {"rear"},
    "Front fender": {"front"}, "Rear fender": {"rear"}, "Front Wheel": {"front"}, "Rear Wheel": {"rear"},
    "A pillar": set(), "B pillar": set(), "C pillar": {"rear"},
    "Front door": set(), "Rear door": set(), "Rocker panel": set(), "Side mirror": set(),
}
_EN_RE = re.compile(r"^(?P<base>.+?)\s*(?:\((?P<side>[LR])\))?$")


def en_part_directions(part: str) -> set[str]:
    """Directions of a damage-label part name such as 'Front fender(L)'."""
    m = _EN_RE.match(part.strip())
    if not m or m["base"] not in _EN_BASE:
        return set()
    dirs = set(_EN_BASE[m["base"]])
    if m["side"]:
        dirs.add("left" if m["side"] == "L" else "right")
    elif m["base"] in ("Head lights", "Rear lamp"):
        pass  # side-less lamps still face front/rear
    elif not dirs:
        return set()
    return dirs


# Korean estimate item names, checked in this order. Shops spell "front" as
# 후론트/프론트/프런트, so 후론트 must win over the rear keyword 후방.
_KO_SIDE_ONLY = re.compile(r"(?<!백)도어|사이드\s*미러|아웃\s*사이드\s*미러|사이드\s*실|사이드\s*스텝|필러|락커|로커")
_KO_BACKDOOR = re.compile(r"백\s*도어|테일\s*게이트")
_KO_FRONT = re.compile(r"후론트|프론트|프런트|(?<![가-힣])앞|전방|후드|보닛|본넷|본네트|헤드\s*램프|헤드\s*라이트|전조등|"
                       r"라디에|그릴|인터쿨러|콘덴|윈드\s*실드|윈드\s*쉴드|안개등|포그|에이프런")
_KO_REAR = re.compile(r"리어|(?<![가-힣])뒤|뒷|후방|트렁크|테일|후미등|쿼터|백\s*패널|백\s*워닝")
# 좌/우 only as a standalone token: "(좌)", "(뒤,우)", "좌측" -- not the 우 in "아우(outer)".
_KO_LEFT = re.compile(r"(?:^|[(,\s])좌(?=[),\s]|$)|좌측|\bLH\b|\(L\)")
_KO_RIGHT = re.compile(r"(?:^|[(,\s])우(?=[),\s]|$)|우측|\bRH\b|\(R\)")


def ko_item_directions(name: str) -> set[str]:
    """Directions of a Korean estimate item such as '앞휀다(좌)', '후론트 범퍼 커버', '휠(앞,우)'."""
    if _KO_BACKDOOR.search(name):
        dirs = {"rear"}
    elif _KO_SIDE_ONLY.search(name):
        dirs = set()          # doors, mirrors, sills: side only ("(뒤,우)" = rear door, right)
    elif _KO_FRONT.search(name):
        dirs = {"front"}
    elif _KO_REAR.search(name):
        dirs = {"rear"}
    elif "(앞" in name:
        dirs = {"front"}      # wheels, tyres: "휠(앞,우)"
    elif "(뒤" in name:
        dirs = {"rear"}
    else:
        dirs = set()
    if _KO_LEFT.search(name):
        dirs.add("left")
    elif _KO_RIGHT.search(name):
        dirs.add("right")
    return dirs


def fits(part_dirs: list[set[str]], allowed: set[str]) -> str:
    """Compare parts' directions with the directions a collision allows.

    'consistent': every directional part touches an allowed direction
    'contradiction': no directional part touches an allowed direction
    'partial': some do, some do not; 'unknown': no directional parts
    """
    known = [d for d in part_dirs if d]
    if not known:
        return "unknown"
    hits = [bool(d & allowed) for d in known]
    if all(hits):
        return "consistent"
    if not any(hits):
        return "contradiction"
    return "partial"
