"""Offline backend: perception results are the dataset labels (ground truth).

Use only to test plumbing and the deterministic rules. Scores from this
backend are an upper bound for "perfect perception", not model performance.
"""

from __future__ import annotations

from ..cases import GroundTruth
from ..schemas import ClaimBundle, ClaimResult, DamageFinding, VideoFinding
from ..tools.damage import photo_directions
from ..tools.report import template_report


class _Video:
    def __init__(self, truths: dict[str, GroundTruth]):
        self.truths = truths

    def analyze(self, bundle: ClaimBundle) -> VideoFinding:
        t = self.truths[bundle.case_id]
        return VideoFinding(top3=[t.accident_type], scene={"evidence": "(oracle) 검수된 라벨의 사고유형"}, source="oracle",
                            ego_role=t.claimant_role)


class _Damage:
    def __init__(self, truths: dict[str, GroundTruth]):
        self.truths = truths

    def analyze(self, bundle: ClaimBundle) -> DamageFinding:
        parts = self.truths[bundle.case_id].photo_parts
        return DamageFinding(parts=parts, directions=photo_directions(parts), source="oracle")


class _Writer:
    def write(self, result: ClaimResult) -> str:
        return template_report(result)


class OracleBackend:
    name = "oracle"

    def __init__(self, truths: dict[str, GroundTruth]):
        self.video = _Video(truths)
        self.damage = _Damage(truths)
        self.writer = _Writer()

    def usage(self) -> tuple[int, int]:
        return 0, 0
