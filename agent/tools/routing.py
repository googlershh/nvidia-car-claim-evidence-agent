"""route: approve / adjust / siu, with amounts. Rules: docs/ARCHITECTURE.md section 4."""

from __future__ import annotations

from ..schemas import Anomaly, Decision, FaultAssessment, LineCheck

VAT = 0.10


def route(fault: FaultAssessment, lines: list[LineCheck], anomalies: list[Anomaly]) -> Decision:
    claimed = sum(c.line.claimed for c in lines)
    flagged = [c for c in lines if c.flagged]
    approved = claimed - sum(c.line.claimed for c in flagged)
    reasons: list[str] = []
    siu = [a for a in anomalies if a.severity == "siu"]
    review = [a for a in anomalies if a.severity == "review"]
    if siu:
        decision = "siu"
        reasons += [a.detail for a in siu]
    elif review or flagged:
        decision = "adjust"
        reasons += [a.detail for a in review] + [c.reason for c in flagged]
    else:
        decision = "approve"
        reasons.append("사고유형과 손상 부위가 맞고, 사진에 없는 부위의 수리 청구가 없음")
    payout = round(approved * (1 + VAT) * fault.fault_a / 100)
    return Decision(route=decision, reasons=reasons, claimed_total=claimed, approved_total=approved,
                    payout_estimate=payout)
