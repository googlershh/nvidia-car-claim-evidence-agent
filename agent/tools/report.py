"""draft_report: Korean loss adjustment draft (template; the nim backend can rewrite prose with Ultra)."""

from __future__ import annotations

from ..schemas import ClaimResult

ROUTE_KO = {"approve": "정상 처리(승인 권고)", "adjust": "정비공장 조정 요청", "siu": "SIU(보험사기 조사) 이관"}
KO_DIR = {"front": "전면", "rear": "후면", "left": "좌측", "right": "우측"}


def _dirs(d: set[str]) -> str:
    return ", ".join(KO_DIR.get(x, x) for x in sorted(d)) or "-"


def _won(n: int) -> str:
    return f"{n:,}원"


def template_report(r: ClaimResult) -> str:
    f, d, dec = r.fault, r.damage, r.decision
    flagged = [c for c in r.lines if c.flagged]
    out = [
        f"# 대물 손해사정서 초안 — {r.case_id}",
        "",
        f"> 상태: **담당자 승인 대기**. 이 문서는 에이전트가 만든 초안이며 최종 판단은 담당자가 한다.  ",
        f"> 모델 백엔드: `{r.backend}`" + (" (정답 주입 테스트용, 실제 인식 결과 아님)" if r.backend == "oracle" else ""),
        "",
        "## 1. 처리 권고",
        f"- **{ROUTE_KO[dec.route]}**",
        *[f"- 사유: {reason}" for reason in dec.reasons],
        "",
        "## 2. 과실 판단",
        f"- 사고유형: **{f.code}** — {f.place} / {f.situation}",
        f"- 상대 차량({'A' if f.claimant_role == 'B' else 'B'}, 당사 피보험자): {f.other_progress}",
        f"- 청구 차량({f.claimant_role}, 블랙박스 촬영 차량): {f.claimant_progress}",
        f"- 기본 과실비율 상대:청구 = **{f.other_fault}:{f.claimant_fault}** "
        f"(과실비율 인정기준 기본과실, 수정요소 미반영. 도표 A:B = {f.fault_a}:{f.fault_b})",
        f"- 다른 후보 유형: {', '.join(map(str, f.alternatives)) or '없음'}",
        f"- 영상 근거: {r.video.scene.get('evidence', '-')}",
        "- 수정요소(가감 요소): 담당자 확인 필요",
        "",
        "## 3. 손해액",
        f"- 사진상 손상 부위: {', '.join(d.parts) or '-'} (방향: {_dirs(d.directions)})",
        f"- 청구 수리비(부가세 별도): {_won(dec.claimed_total)}",
        f"- 인정 예상 수리비(부가세 별도): **{_won(dec.approved_total)}**"
        + (f" (불인정 제안 {len(flagged)}건, {_won(dec.claimed_total - dec.approved_total)})" if flagged else ""),
        f"- 지급 예상액: 인정액 × 1.1(부가세) × 상대 과실 {f.other_fault}% = **{_won(dec.payout_estimate)}**",
        "",
    ]
    if flagged:
        out += ["### 불인정 제안 항목", "| No | 항목 | 작업 | 청구액 | 사유 |", "|---|---|---|---|---|"]
        out += [f"| {c.line.no} | {c.line.name} | {c.line.work} | {_won(c.line.claimed)} | 사진에 없는 방향({_dirs(c.directions)}) |"
                for c in flagged]
        out.append("")
    out += ["## 4. 이상 징후"]
    out += [f"- [{a.severity}] {a.detail}" for a in r.anomalies] or ["- 없음"]
    out.append("")
    if dec.route == "adjust":
        out += ["## 5. 정비공장 조정 요청서(초안)",
                f"귀 공장에서 제출한 견적 중 아래 사유로 조정을 요청합니다. 차량: {r.case_id}",
                *[f"- {reason}" for reason in dec.reasons], ""]
    if dec.route == "siu":
        out += ["## 5. SIU 이관 메모(초안)",
                "- 이관 사유: 사고 형태와 청구 손상 부위의 불일치",
                *[f"- {a.detail}" for a in r.anomalies if a.severity == "siu"],
                "- 요청: 현장·차량 실물 확인, 사고 이력 조회", ""]
    return "\n".join(out)
