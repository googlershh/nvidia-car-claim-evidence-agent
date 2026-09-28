"""Data structures passed between pipeline stages.

`ClaimBundle` is everything a claims handler would receive; it never carries
ground truth. Evaluation labels live in `cases.GroundTruth` and only the
oracle backend may read them (explicitly, for upper-bound testing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EstimateLine:
    no: int | None
    name: str
    work: str
    claimed_part: int
    claimed_labor: int

    @property
    def claimed(self) -> int:
        return self.claimed_part + self.claimed_labor


@dataclass
class ClaimBundle:
    case_id: str
    video: Path                      # dashcam clip; claimant = filming vehicle = vehicle B
    photos: list[Path]               # damage photos of the claimant's car
    estimate: list[EstimateLine]     # repair shop estimate as submitted
    car_name: str = ""
    statement: str = ""              # claimant statement (not in the AI Hub data yet)


@dataclass
class VideoFinding:
    top3: list[int]                  # accident type codes, best first
    scene: dict = field(default_factory=dict)   # ego/other movement, road type, evidence ...
    source: str = ""                 # backend name
    ego_role: str = "B"              # which table vehicle (A/B) the filming car is in the chosen code


@dataclass
class FaultAssessment:
    code: int
    place: str
    situation: str
    a_progress: str
    b_progress: str
    fault_a: int                     # table vehicle A, current (10th edition) base fault
    fault_b: int                     # table vehicle B
    alternatives: list[int]
    impact_a: set[str]
    impact_b: set[str]
    confidence: str                  # collision-area confidence: high | medium | low
    # The claimant is the filming car. The dataset manual says it is vehicle B, but the
    # label review found 19 of 92 usable clips where it is vehicle A (docs/LABEL_REVIEW.md).
    claimant_role: str = "B"
    chart: str = ""                  # fault standard chart, e.g. 차43-2 or 차1-2(가)
    chart_mapping: str = ""          # same | revised (10th edition value differs from AI Hub) | uncertain | none

    @property
    def claimant_fault(self) -> int:
        return self.fault_b if self.claimant_role == "B" else self.fault_a

    @property
    def other_fault(self) -> int:
        """Fault share of the other party (our insured): the payout ratio."""
        return self.fault_a if self.claimant_role == "B" else self.fault_b

    @property
    def claimant_progress(self) -> str:
        return self.b_progress if self.claimant_role == "B" else self.a_progress

    @property
    def other_progress(self) -> str:
        return self.a_progress if self.claimant_role == "B" else self.b_progress

    @property
    def claimant_impact(self) -> set[str]:
        return self.impact_b if self.claimant_role == "B" else self.impact_a


@dataclass
class DamageFinding:
    parts: list[str]                 # damaged parts seen in photos
    directions: set[str]
    source: str = ""


@dataclass
class LineCheck:
    line: EstimateLine
    directions: set[str]
    flagged: bool
    reason: str = ""


@dataclass
class Anomaly:
    kind: str                        # e.g. impact_mismatch
    severity: str                    # siu | review
    detail: str


@dataclass
class Decision:
    route: str                       # approve | adjust | siu
    reasons: list[str]
    claimed_total: int               # parts + labour, before VAT
    approved_total: int              # after removing flagged lines, before VAT
    payout_estimate: int             # approved x VAT x other party's fault share


@dataclass
class StageTrace:
    stage: str
    seconds: float
    calls: int = 0
    tokens: int = 0
    note: str = ""


@dataclass
class ClaimResult:
    case_id: str
    backend: str
    video: VideoFinding
    fault: FaultAssessment
    damage: DamageFinding
    lines: list[LineCheck]
    anomalies: list[Anomaly]
    decision: Decision
    report_md: str
    status: str = "pending_approval"
    trace: list[StageTrace] = field(default_factory=list)
