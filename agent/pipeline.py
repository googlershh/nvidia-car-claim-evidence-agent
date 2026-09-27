"""Run one claim through all stages and record a per-stage trace."""

from __future__ import annotations

import time

from .backends.base import Backend
from .schemas import ClaimBundle, ClaimResult, StageTrace
from .tools.anomaly import check_consistency
from .tools.damage import check_estimate
from .tools.fault import search_fault_table
from .tools.routing import route


def run(bundle: ClaimBundle, backend: Backend) -> ClaimResult:
    trace: list[StageTrace] = []

    def stage(name: str, fn):
        calls0, tokens0 = backend.usage()
        t0 = time.perf_counter()
        out = fn()
        calls1, tokens1 = backend.usage()
        trace.append(StageTrace(name, round(time.perf_counter() - t0, 3), calls1 - calls0, tokens1 - tokens0))
        return out

    stage("intake", lambda: _intake(bundle))
    video = stage("A.analyze_video", lambda: backend.video.analyze(bundle))
    fault = stage("A.search_fault_table", lambda: search_fault_table(video))
    damage = stage("B.assess_damage", lambda: backend.damage.analyze(bundle))
    lines = stage("B.check_estimate", lambda: check_estimate(bundle.estimate, damage))
    anomalies = stage("C.check_consistency", lambda: check_consistency(fault, damage))
    decision = stage("route", lambda: route(fault, lines, anomalies))
    result = ClaimResult(case_id=bundle.case_id, backend=backend.name, video=video, fault=fault, damage=damage,
                         lines=lines, anomalies=anomalies, decision=decision, report_md="", trace=trace)
    result.report_md = stage("draft", lambda: backend.writer.write(result))
    return result


def _intake(bundle: ClaimBundle) -> None:
    missing = [str(p) for p in [bundle.video, *bundle.photos] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"{bundle.case_id}: missing media {missing[:3]} (run scripts/extract_media.py)")
    if not bundle.estimate:
        raise ValueError(f"{bundle.case_id}: empty estimate")
