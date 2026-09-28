"""draft_negotiation: fault evidence letter to the counterparty insurer, plus internal notes.

The letter carries our chart citation, the video evidence, a review of the counterparty's
claim, the modifiers still to be checked on video, and how likely the case is to go to the
fault ratio dispute committee. Our own insured's statement is checked in an internal
section that is not sent.
"""

from __future__ import annotations

from ..schemas import ClaimResult, StatementCheck
from .fault import code_modifiers
from .statements import chart_title

GENERIC = {"현저한과실", "중대한과실"}
LEVEL_KO = {"low": "낮음", "medium": "중간", "high": "높음"}
VERDICT_KO = {"consistent": "일치", "contradicts": "영상과 다름", "needs_video": "수정요소 영상 확인 필요"}


def dispute_likelihood(r: ClaimResult) -> tuple[str, list[str]]:
    """low | medium | high, with reasons. Rule of thumb, not a model."""
    ours = r.fault.other_fault
    cp = next((c for c in r.statement_checks if c.source == "counterparty"), None)
    level, reasons = "low", []
    if cp is None:
        level, reasons = "medium", ["상대 보험사 주장이 아직 없음"]
    elif cp.verdict == "consistent":
        reasons.append("상대 보험사 주장이 영상 판단과 같은 도표·기본과실")
    elif cp.verdict == "needs_video":
        checked = {c.name: c.verdict for c in r.modifier_checks}
        open_ = [m.name for m in cp.modifiers_to_verify if checked.get(m.name) not in ("confirmed", "not_seen")]
        if open_:
            level = "medium"
            reasons.append(f"수정요소 주장({', '.join(open_)})이 영상으로 확인되지 않은 채 남아 있음")
        else:
            reasons.append("상대 보험사의 수정요소 주장을 영상으로 모두 확인함(확인/미확인 결과를 근거로 제시)")
    else:
        gap = abs(cp.claimed_insured_fault - ours)
        level = "high" if gap >= 20 else "medium"
        reasons.append(f"상대 보험사가 영상과 다른 사고 형태를 주장(당사 피보험자 과실 차이 {gap}%p). "
                       "영상 제시로 해소되지 않으면 심의 청구 가능성이 크다")
    if r.fault.chart_mapping in ("uncertain", "none"):
        level = "high" if level == "high" else "medium"
        reasons.append("적용 도표 자체가 불확실(담당자 확인 필요)")
    return level, reasons


CHECK_KO = {"confirmed": "영상에서 확인", "not_seen": "영상에서 확인되지 않음", "unclear": "영상으로 판단 불가"}


def _modifier_rows(r: ClaimResult, cp: StatementCheck | None) -> list[str]:
    claimed = {m.name for m in cp.modifiers_to_verify} if cp else set()
    checked = {c.name: c for c in r.modifier_checks}
    rows = []
    insured_role = "A" if r.fault.claimant_role == "B" else "B"
    for role, name, value in code_modifiers(r.fault.code):
        if name in GENERIC and name not in claimed and name not in checked:
            continue
        who = "당사 피보험자" if role == insured_role else "귀사 고객"
        c = checked.get(name)
        status = CHECK_KO.get(c.verdict, c.verdict) if c else "영상 확인 전"
        if name in claimed:
            status = f"귀사 주장, {status}"
        rows.append(f"| {who} | {name} | {value:+d} | {status} | {c.evidence if c and c.evidence else '-'} |")
    return rows


def draft_negotiation(r: ClaimResult) -> str:
    f = r.fault
    cp = next((c for c in r.statement_checks if c.source == "counterparty"), None)
    ins = next((c for c in r.statement_checks if c.source == "insured"), None)
    level, reasons = dispute_likelihood(r)
    out = [
        f"# 과실 협의 근거 — {r.case_id}",
        "",
        "> 수신: 귀사(청구 차량 보험사) 대물 담당자 / 발신: 당사 대물보상 담당  ",
        "> 상태: **담당자 승인 전 초안**. 발송은 담당자가 승인한 뒤에만 한다.",
        "",
        "## 1. 사고 개요",
        f"- 장소·유형: {f.place} / {f.situation}",
        f"- 귀사 고객(청구 차량, 블랙박스 촬영 차량): {f.claimant_progress}",
        f"- 당사 피보험자: {f.other_progress}",
        "",
        "## 2. 당사 판단",
        f"- 적용 기준: 자동차사고 과실비율 인정기준(제10차 개정) **{f.chart or '-'}** 「{chart_title(f.chart) if f.chart else '-'}」",
        f"- 기본과실 당사:귀사 = **{f.other_fault}:{f.claimant_fault}**",
        f"- 영상 근거: {r.video.scene.get('evidence', '-')}",
        *(["- **적용 도표가 불확실함: 담당자가 도표를 확정한 뒤 발송**"] if f.chart_mapping in ("uncertain", "none") else []),
        "",
        "## 3. 귀사 주장 검토",
    ]
    if cp is None:
        out.append("- 귀사 주장 미접수")
    else:
        out += [f"- 귀사 주장: {cp.claimed_chart} 「{chart_title(cp.claimed_chart)}」, "
                f"당사:귀사 = {cp.claimed_insured_fault}:{100 - cp.claimed_insured_fault}",
                f"- 검토 결과: **{VERDICT_KO[cp.verdict]}** — {cp.detail}"]
        if cp.verdict == "contradicts":
            out.append("- 요청: 영상의 해당 구간을 함께 확인하고 당사 판단 도표로 재검토를 요청합니다. 영상 사본 제공 가능.")
    out += ["", "## 4. 수정요소 검토 (영상 확인 대상)",
            "| 해당 차량 | 수정요소 | 가감(%p) | 상태 | 근거 시각 |", "|---|---|---|---|---|",
            *(_modifier_rows(r, cp) or ["| - | 해당 도표의 개별 수정요소 없음 | - | - | - |"]),
            "", "## 5. 제안",
            f"- 기본과실 당사:귀사 = **{f.other_fault}:{f.claimant_fault}**. 수정요소는 영상 확인 결과를 반영해 조정한다.",
            "", f"## 6. 분쟁심의 가능성: **{LEVEL_KO[level]}**",
            *[f"- {x}" for x in reasons],
            "- 참고: 합의가 안 되면 보험사가 과실비율분쟁심의위원회에 심의를 청구한다(2024년 약 15.7만 건, "
            "평균 소요 대표자 회의 41일·소심의 61일·재심의 113일).",
            "", "---", "", "## [내부용, 발송 제외] 당사 피보험자 진술 대조"]
    if ins is None:
        out.append("- 피보험자 진술 미접수")
    else:
        out.append(f"- 결과: **{VERDICT_KO[ins.verdict]}** — {ins.detail}")
        if ins.verdict == "contradicts":
            out.append("- 조치: 피보험자에게 영상 판단을 안내하고, 협의 문서에 피보험자 진술을 인용하지 않는다.")
    return "\n".join(out) + "\n"
