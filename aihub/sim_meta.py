"""71958 accident simulation metadata (XML, 800 files).

The XML files live in `Other.zip` under `/메타데이터/` next to ~2GB of 3D
assets we do not use, so `extract()` copies just the XML to
data/interim/71958_meta and the zip can then be deleted. Fields are
attributes of `Accident_Info`, `Participant_Info`, `Occupant_Info`.

`Collision_Type` does not follow the manual's code list (rear-end crashes are
all coded 4 = "횡단중"), so use `Accident_col_Type` for collision type.
"""

from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from .common import INTERIM_DIR, find_file

META_DIR = INTERIM_DIR / "71958_meta"

COL_TYPE = {1: "차대사람_횡단중", 2: "차대사람_기타", 3: "정면충돌", 4: "측면충돌", 5: "측면접촉",
            6: "추돌", 7: "차대이륜", 8: "이륜대이륜", 9: "차량단독_충돌", 10: "차량단독_기타", 100: "불명"}
AREA = {1: "전면", 2: "우측", 3: "좌측", 4: "후면", 5: "위쪽", 6: "하부", 7: "사람", 8: "해당없음", 100: "불명"}
ACCIDENT_TYPE_CAR_TO_CAR = 2


def extract(zip_path: Path | None = None, out_dir: Path = META_DIR) -> int:
    """Copy the metadata XML files out of Other.zip. Returns the file count."""
    path = zip_path or find_file("71958", "Other.zip")
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith(".xml") and "메타데이터" in name:
                (out_dir / PurePosixPath(name).name).write_bytes(z.read(name))
                n += 1
    return n


def _num(v: str | None):
    if v in (None, ""):
        return None
    try:
        f = float(v)
    except ValueError:
        return v
    return int(f) if f.is_integer() else f


def parse_file(path: Path) -> dict:
    root = ET.parse(path).getroot()
    rec: dict = {"file": path.name, "kind": "real" if "_R_" in path.name else "edge"}
    for tag in ("Accident_Info", "Participant_Info", "Occupant_Info"):
        el = root.find(tag)
        if el is not None:
            rec.update({k: (v if k in ("ID", "story", "Date") else _num(v)) for k, v in el.attrib.items()})
    return rec


def iter_meta(meta_dir: Path = META_DIR) -> Iterator[dict]:
    files = sorted(meta_dir.glob("*.xml"))
    if not files:
        raise FileNotFoundError(f"no XML in {meta_dir}; download Other.zip (manifest stage 'meta') and run extract()")
    for p in files:
        yield parse_file(p)


def collision_area_table(records: list[dict] | None = None) -> Counter:
    """Counter of (collision type, area A, area B) over car-to-car records."""
    records = records if records is not None else list(iter_meta())
    return Counter(
        (COL_TYPE.get(r.get("Accident_col_Type"), str(r.get("Accident_col_Type"))),
         AREA.get(r.get("Area_of_Deformation_A"), str(r.get("Area_of_Deformation_A"))),
         AREA.get(r.get("Area_of_Deformation_B"), str(r.get("Area_of_Deformation_B"))))
        for r in records if r.get("Accident_Type") == ACCIDENT_TYPE_CAR_TO_CAR
    )
