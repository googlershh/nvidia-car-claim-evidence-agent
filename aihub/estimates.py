"""581 repair estimates (`TS_99. 붙임_견적서.zip`, one JSON per accident).

The file stem is the accident ID shared with damage labels' `categories.id`.
Two sources with one schema each:
- `as-` (repair shops, 57,004): item `부품가격`/`공임` only
- `sc-` (SOCAR, 68,002): item `손해사정전`/`손해사정후` {부품가격, 공임}, i.e.
  claimed vs approved amounts after a human loss adjuster, plus 청구액/지급액.
  Items with `작업 == 불인정` are disallowed (approved amounts are blank).
For `as-` items the claimed amounts are stored and approved ones stay None.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .common import find_file, iter_zip_json, rate_and_amount, to_number


@dataclass
class EstimateItem:
    no: int | None
    no_flag: str               # suffix after the number, e.g. "U"
    name: str                  # 작업항목 및 부품명
    work: str                  # 교환 | 탈착 | 판금 | 도장 | 수리 | 불인정 | 1/2OH ...
    hq_pct: float | None
    part_code: str
    claimed_part: int | None
    claimed_labor: int | None
    approved_part: int | None = None   # sc- only
    approved_labor: int | None = None  # sc- only
    note: str = ""


@dataclass
class Estimate:
    estimate_id: str           # == damage label accident_id
    source: str                # as | sc
    maker: str
    vehicle_class: str         # 승용 | RV | "" (from "현대 / 승용")
    car_name: str
    model: str
    first_registered: str
    parts_applied: str
    mileage_km: int | None
    entered: str
    released: str
    rate_detach: int | None    # 탈부착 M/H 단가 (원)
    rate_sheet_metal: int | None
    rate_paint: int | None
    labor_subtotal: int | None
    parts_subtotal: int | None
    vat: int | None
    fault_offset_pct: float | None
    fault_offset: int | None
    deductible: int | None
    total: int | None          # as: 총계, sc: 지급액 (paid)
    claimed_total: int | None  # sc: 청구액, as: None
    items: list[EstimateItem] = field(default_factory=list)

    @property
    def has_adjustment(self) -> bool:
        return any(
            it.approved_labor != it.claimed_labor or it.approved_part != it.claimed_part
            for it in self.items if self.source == "sc"
        )


def _int(v) -> int | None:
    n = to_number(v)
    return None if n is None else int(n)


def _parse_item(r: dict, source: str) -> EstimateItem:
    m = re.match(r"\s*(\d+)\s*(\S*)", str(r.get("No", "")))
    base = dict(
        no=int(m.group(1)) if m else None,
        no_flag=m.group(2) if m else "",
        name=str(r.get("작업항목 및 부품명", "")).strip(),
        work=str(r.get("작업", "")).strip(),
        hq_pct=to_number(r.get("HQ%")),
        part_code=str(r.get("부품코드", "")).strip(),
        note=str(r.get("비고", "")).strip(),
    )
    if source == "sc":
        pre, post = r.get("손해사정전", {}), r.get("손해사정후", {})
        return EstimateItem(**base, claimed_part=_int(pre.get("부품가격")), claimed_labor=_int(pre.get("공임")),
                            approved_part=_int(post.get("부품가격")), approved_labor=_int(post.get("공임")))
    return EstimateItem(**base, claimed_part=_int(r.get("부품가격")), claimed_labor=_int(r.get("공임")))


def parse_record(estimate_id: str, doc: dict) -> Estimate:
    source = estimate_id.split("-")[0]
    car = doc["차량정보"]
    settle = doc["수리비 정산정보"]
    total = settle["합계"]
    maker, _, vclass = str(car.get("제작사/차종", "")).partition("/")
    _, vat = rate_and_amount(total.get("부가세"))
    offset_pct, offset = rate_and_amount(total.get("과실상계"))
    return Estimate(
        estimate_id=estimate_id,
        source=source,
        maker=maker.strip(),
        vehicle_class=vclass.strip(),
        car_name=car.get("차량명칭", ""),
        model=car.get("모델", ""),
        first_registered=car.get("최초등록일", ""),
        parts_applied=car.get("부품적용일", ""),
        mileage_km=_int(car.get("주행거리")),
        entered=car.get("입고일자", ""),
        released=car.get("출고일자", ""),
        rate_detach=_int(car.get("탈부착M/H")),
        rate_sheet_metal=_int(car.get("판금M/H")),
        rate_paint=_int(car.get("도장M/H")),
        labor_subtotal=_int(settle["공임"].get("공임소계")),
        parts_subtotal=_int(settle["부품"].get("부품소계")),
        vat=vat,
        fault_offset_pct=offset_pct,
        fault_offset=offset,
        deductible=_int(total.get("면책금") if source == "as" else total.get("자기부담금")),
        total=_int(total.get("총계") if source == "as" else total.get("지급액")),
        claimed_total=_int(total.get("청구액")) if source == "sc" else None,
        items=[_parse_item(r, source) for r in doc.get("수리내역", [])],
    )


def iter_estimates(zip_path: Path | None = None) -> Iterator[Estimate]:
    path = zip_path or find_file("581", "TS_99*견적서.zip")
    for name, doc in iter_zip_json(path):
        yield parse_record(Path(name).stem, doc)
