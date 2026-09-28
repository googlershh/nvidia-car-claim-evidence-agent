"""compare_statements: check each side's statement against the fault judged from the video."""

from __future__ import annotations

from ..schemas import FaultAssessment, Statement, StatementCheck
from .fault import charts

SOURCE_KO = {"insured": "당사 피보험자", "counterparty": "상대 보험사"}


def chart_title(label: str) -> str:
    """'차6-1(가)' -> the chart title from the fault standard ('' if unknown)."""
    return charts().get(label.split("(")[0], {}).get("title", "")


def compare_statements(fault: FaultAssessment, statements: list[Statement]) -> list[StatementCheck]:
    ours, ours_fault = fault.chart, fault.other_fault
    checks = []
    for s in statements:
        who = SOURCE_KO.get(s.source, s.source)
        total = s.claimed_total_insured_fault
        if s.claimed_chart == ours and s.claimed_insured_fault == ours_fault:
            if s.modifiers:
                mods = ", ".join(f"{m.name}({m.value:+d})" for m in s.modifiers)
                checks.append(StatementCheck(
                    s.source, "needs_video", s.claimed_chart, total,
                    f"{who}: 사고유형은 영상 판단({ours})과 같다. 수정요소 {mods} 주장은 영상에서 확인해야 한다 "
                    f"(인정 시 당사 피보험자 과실 {ours_fault} → {total}).", list(s.modifiers)))
            else:
                checks.append(StatementCheck(s.source, "consistent", s.claimed_chart, total,
                                             f"{who}: 영상 판단과 같은 도표({ours}), 같은 기본과실"))
            continue
        if s.claimed_chart == ours:
            why = "같은 도표에서 두 차의 역할(누가 어떤 진행이었는지)을 반대로 주장"
        else:
            why = f"다른 사고유형 주장: {s.claimed_chart} 「{chart_title(s.claimed_chart)}」"
        checks.append(StatementCheck(
            s.source, "contradicts", s.claimed_chart, total,
            f"{who}: {why}. 주장대로면 당사 피보험자 과실 {s.claimed_insured_fault}, "
            f"영상 판단은 {ours} 「{chart_title(ours)}」 기준 {ours_fault}.", list(s.modifiers)))
    return checks
