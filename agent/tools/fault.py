"""search_fault_table: accident type code -> fault standard chart, current base fault, impact directions.

The base fault comes from the KNIA fault standard (10th edition, 2023) via
data/reference/code_to_chart.csv (scripts/build_chart_map.py). The AI Hub code table
follows the 9th edition; 4 in-scope codes changed value and 1 has no clear chart.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from ..schemas import FaultAssessment, VideoFinding

ROOT = Path(__file__).resolve().parents[2]
CODES_KO = ROOT / "data" / "interim" / "accident_codes.csv"
CODES_EN = ROOT / "data" / "reference" / "accident_codes_en.csv"
COLLISION = ROOT / "data" / "reference" / "collision_areas.csv"
CHART_MAP = ROOT / "data" / "reference" / "code_to_chart.csv"
IN_SCOPE_PLACES = ("직선도로", "사거리교차로(신호등있음)", "T자형교차로")


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=1)
def codes_ko() -> dict[int, dict]:
    if not CODES_KO.exists():
        raise FileNotFoundError(f"{CODES_KO} missing; run scripts/build_interim.py codes")
    return {int(r["code"]): r for r in _read(CODES_KO)}


@lru_cache(maxsize=1)
def codes_en() -> dict[int, dict]:
    return {int(r["code"]): r for r in _read(CODES_EN)}


@lru_cache(maxsize=1)
def collision_areas() -> dict[int, dict]:
    return {int(r["code"]): {"a": set(r["a_areas"].split(";")), "b": set(r["b_areas"].split(";")),
                             "confidence": r["confidence"], "note": r["note"]} for r in _read(COLLISION)}


@lru_cache(maxsize=1)
def chart_map() -> dict[int, dict]:
    """Code -> chart number, variant, current base fault (A/B in the code's orientation), mapping status."""
    return {int(r["code"]): r for r in _read(CHART_MAP)}


def in_scope_codes() -> list[int]:
    return sorted(c for c, r in codes_ko().items() if r["accident_object"] == "차대차" and r["place_key"] in IN_SCOPE_PLACES)


def candidate_table_en() -> str:
    """English candidate list for video models (Omni is English-only)."""
    en = codes_en()
    lines = ["code | place | situation | vehicle A | vehicle B"]
    lines += [f"{c} | {en[c]['place']} | {en[c]['situation']} | {en[c]['vehicle_a']} | {en[c]['vehicle_b']}"
              for c in in_scope_codes()]
    return "\n".join(lines)


def search_fault_table(finding: VideoFinding) -> FaultAssessment:
    """Take the best in-scope code from the video finding and look up its base fault."""
    ko, areas, charts = codes_ko(), collision_areas(), chart_map()
    scope = set(in_scope_codes())
    ranked = [c for c in finding.top3 if c in scope] or [c for c in finding.top3 if c in ko]
    if not ranked:
        raise ValueError(f"no known accident type in {finding.top3}")
    code = ranked[0]
    r = ko[code]
    area = areas.get(code, {"a": set(), "b": set(), "confidence": "low"})
    ch = charts.get(code)
    fault_a, fault_b = (int(ch["chart_fault_a"]), int(ch["chart_fault_b"])) if ch else (int(r["fault_a"]), int(r["fault_b"]))
    return FaultAssessment(
        code=code, place=r["place_key"], situation=r["place_feature"], a_progress=r["a_progress"],
        b_progress=r["b_progress"], fault_a=fault_a, fault_b=fault_b,
        alternatives=[c for c in finding.top3 if c != code],
        impact_a=set(area["a"]), impact_b=set(area["b"]), confidence=area["confidence"],
        claimant_role=finding.ego_role if finding.ego_role in ("A", "B") else "B",
        chart=(ch["chart"] + (f"({ch['variant']})" if ch["variant"] else "")) if ch else "",
        chart_mapping=ch["mapping"] if ch else "none",
    )
