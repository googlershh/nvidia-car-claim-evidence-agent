"""Tool commands for an agent harness (OpenClaw skill `claim-evidence`). JSON in, JSON/Markdown out.

The fixed pipeline (agent/pipeline.py) runs every stage in order. These commands expose the same
tools one by one so a planning agent can call them in whatever order a case needs, bring its own
video findings (from VSS), and re-check modifiers on video before drafting.

    python3 -m agent.cli cases
    python3 -m agent.cli case C006
    python3 -m agent.cli candidates --place 직선도로
    python3 -m agent.cli fault 11
    python3 -m agent.cli compare C006 --code 11 --role B
    python3 -m agent.cli estimate C006
    python3 -m agent.cli anomaly C006 --code 11 --role B
    python3 -m agent.cli letter C006 --code 11 --role B --evidence "..." --modifier-check '{"name":"진로변경 신호불이행·지연","verdict":"not_seen","evidence":"4~6초 방향지시등 안 보임"}'

Photo findings come from the damage labels (a stand-in for a photo model); the agent supplies the
accident type, the claimant's role and the video evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.cases import iter_cases  # noqa: E402
from agent.schemas import ClaimResult, DamageFinding, ModifierCheck, VideoFinding  # noqa: E402
from agent.tools.anomaly import check_consistency  # noqa: E402
from agent.tools.damage import check_estimate, photo_directions  # noqa: E402
from agent.tools.fault import (chart_label, chart_map, charts, code_modifiers, codes_en, codes_ko,  # noqa: E402
                               in_scope_codes, search_fault_table)
from agent.tools.negotiation import dispute_likelihood, draft_negotiation  # noqa: E402
from agent.tools.report import template_report  # noqa: E402
from agent.tools.routing import route  # noqa: E402
from agent.tools.statements import compare_statements  # noqa: E402

OUT = ROOT / "outputs"


def _cases() -> dict:
    return {b.case_id: (b, t) for b, t in iter_cases()}


def _case(case_id: str):
    found = _cases()
    if case_id not in found:
        raise SystemExit(f"unknown case {case_id}; run `cases`")
    return found[case_id]


def _damage(truth) -> DamageFinding:
    return DamageFinding(parts=list(truth.photo_parts), directions=photo_directions(truth.photo_parts),
                         source="damage labels (photo model stand-in)")


def _fault(code: int, role: str, evidence: str = ""):
    return search_fault_table(VideoFinding(top3=[code], scene={"evidence": evidence}, source="agent", ego_role=role))


def _print(obj) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=sorted))


def cmd_cases(_a) -> None:
    rows = []
    for cid, (b, t) in _cases().items():
        rows.append({"case_id": cid, "car": b.car_name, "photos": len(b.photos), "estimate_lines": len(b.estimate),
                     "statements": len(b.statements)})
    _print(rows)


def cmd_case(a) -> None:
    b, t = _case(a.case_id)
    d = _damage(t)
    _print({
        "case_id": b.case_id, "car": b.car_name,
        "video": {"vst_sensor": b.video.stem, "note": "filming car = claimant; ask VSS about this sensor"},
        "photos": {"count": len(b.photos), "damaged_parts": d.parts, "directions": sorted(d.directions),
                   "source": d.source},
        "estimate": [{"no": l.no, "item": l.name, "work": l.work, "claimed": l.claimed} for l in b.estimate],
        "statements": [{"source": s.source, "text": s.text, "claimed_chart": s.claimed_chart,
                        "claimed_insured_fault": s.claimed_insured_fault,
                        "modifiers": [vars(m) for m in s.modifiers]} for s in b.statements],
    })


def cmd_candidates(a) -> None:
    ko, en = codes_ko(), codes_en()
    rows = [{"code": c, "place": ko[c]["place_key"], "situation_en": en[c]["situation"],
             "vehicle_a_en": en[c]["vehicle_a"], "vehicle_b_en": en[c]["vehicle_b"], "chart": chart_label(c)}
            for c in in_scope_codes() if not a.place or ko[c]["place_key"] == a.place]
    _print(rows)


def cmd_fault(a) -> None:
    ch = chart_map()[a.code]
    detail = charts()[ch["chart"]]
    _print({"code": a.code, "chart": chart_label(a.code), "title": detail["title"], "parties": detail["parties"],
            "base_fault_a_b": [int(ch["chart_fault_a"]), int(ch["chart_fault_b"])], "mapping": ch["mapping"],
            "modifiers": [{"role": r, "name": n, "value": v} for r, n, v in code_modifiers(a.code)],
            "standard": "과실비율 인정기준 제10차 개정"})


def cmd_compare(a) -> None:
    b, _t = _case(a.case_id)
    f = _fault(a.code, a.role)
    _print({"video_chart": f.chart, "insured_fault": f.other_fault, "claimant_fault": f.claimant_fault,
            "checks": [{"source": c.source, "verdict": c.verdict, "detail": c.detail,
                        "modifiers_to_verify": [vars(m) for m in c.modifiers_to_verify]}
                       for c in compare_statements(f, b.statements)]})


def cmd_estimate(a) -> None:
    b, t = _case(a.case_id)
    lines = check_estimate(b.estimate, _damage(t))
    claimed = sum(c.line.claimed for c in lines)
    flagged = [c for c in lines if c.flagged]
    _print({"claimed_total": claimed, "approved_total": claimed - sum(c.line.claimed for c in flagged),
            "flagged": [{"no": c.line.no, "item": c.line.name, "work": c.line.work, "claimed": c.line.claimed,
                         "reason": c.reason} for c in flagged]})


def cmd_anomaly(a) -> None:
    _b, t = _case(a.case_id)
    _print([vars(x) for x in check_consistency(_fault(a.code, a.role), _damage(t))])


def _result(a) -> ClaimResult:
    b, t = _case(a.case_id)
    f = _fault(a.code, a.role, a.evidence)
    d = _damage(t)
    lines = check_estimate(b.estimate, d)
    anomalies = check_consistency(f, d)
    video = VideoFinding(top3=[a.code], scene={"evidence": a.evidence}, source="agent (VSS)", ego_role=a.role)
    res = ClaimResult(case_id=b.case_id, backend="agent", video=video, fault=f, damage=d, lines=lines,
                      anomalies=anomalies, decision=route(f, lines, anomalies), report_md="",
                      statement_checks=compare_statements(f, b.statements),
                      modifier_checks=[ModifierCheck(**json.loads(m)) for m in a.modifier_check])
    res.report_md = template_report(res)
    res.negotiation_md = draft_negotiation(res)
    return res


def cmd_letter(a) -> None:
    res = _result(a)
    out = OUT / res.case_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "negotiation.md").write_text(res.negotiation_md, encoding="utf-8")
    (out / "report.md").write_text(res.report_md, encoding="utf-8")
    level, reasons = dispute_likelihood(res)
    _print({"route": res.decision.route, "dispute_likelihood": level, "reasons": reasons,
            "payout_estimate": res.decision.payout_estimate,
            "files": [str(out / "negotiation.md"), str(out / "report.md")],
            "status": "draft — needs the handler's approval before anything is sent"})


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="claim", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cases").set_defaults(fn=cmd_cases)
    p = sub.add_parser("case"); p.add_argument("case_id"); p.set_defaults(fn=cmd_case)
    p = sub.add_parser("candidates"); p.add_argument("--place", default=""); p.set_defaults(fn=cmd_candidates)
    p = sub.add_parser("fault"); p.add_argument("code", type=int); p.set_defaults(fn=cmd_fault)
    p = sub.add_parser("estimate"); p.add_argument("case_id"); p.set_defaults(fn=cmd_estimate)
    for name, fn in (("compare", cmd_compare), ("anomaly", cmd_anomaly), ("letter", cmd_letter)):
        p = sub.add_parser(name)
        p.add_argument("case_id")
        p.add_argument("--code", type=int, required=True, help="accident type code judged from the video")
        p.add_argument("--role", choices=["A", "B"], required=True, help="table vehicle of the filming car")
        if name == "letter":
            p.add_argument("--evidence", default="", help="video evidence with timestamps")
            p.add_argument("--modifier-check", action="append", default=[],
                           help='JSON {"name","verdict":"confirmed|not_seen|unclear","evidence"}; repeatable')
        p.set_defaults(fn=fn)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
