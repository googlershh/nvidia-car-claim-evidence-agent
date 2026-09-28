"""check_consistency: does the damage fit how the accident happened?"""

from __future__ import annotations

from aihub.parts import en_part_directions, fits

from ..schemas import Anomaly, DamageFinding, FaultAssessment

KO_DIR = {"front": "전면", "rear": "후면", "left": "좌측", "right": "우측"}


def _ko(dirs: set[str]) -> str:
    return ", ".join(KO_DIR.get(d, d) for d in sorted(dirs)) or "없음"


def check_consistency(fault: FaultAssessment, damage: DamageFinding) -> list[Anomaly]:
    impact = fault.claimant_impact
    fit = fits([en_part_directions(p) for p in damage.parts], impact)
    if fit == "contradiction":
        severity = "siu" if fault.confidence in ("high", "medium") else "review"
        return [Anomaly("impact_mismatch", severity,
                        f"사고유형 {fault.code}({fault.situation})에서 청구 차량({fault.claimant_role})의 충돌 가능 부위는 "
                        f"{_ko(impact)}인데, 사진의 손상은 {_ko(damage.directions)}에만 있음 "
                        f"(사고유형-부위 대응 신뢰도 {fault.confidence})")]
    if fit == "partial":
        return [Anomaly("impact_partial", "info",
                        f"사진 손상 일부({_ko(damage.directions - impact)})가 사고유형의 충돌 가능 부위 밖에 있음")]
    return []
