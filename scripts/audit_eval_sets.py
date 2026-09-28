"""Audit the evaluation sets against the raw AI Hub files, bypassing aihub/*.

Re-reads the original zips (and the manual via `pdftotext -layout`, not the
`-table` + DP parser) and checks that data/manifests/eval_fault.csv and
data/interim/synth_cases.jsonl match them. Prints a report and exits 1 if a
hard check fails.

Usage:
    python scripts/audit_eval_sets.py
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PLACES = ("직선도로", "사거리교차로(신호등있음)", "T자형교차로")

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(("  OK   " if ok else "  FAIL ") + msg)
    if not ok:
        failures.append(msg)


def raw_video_labels() -> dict[str, dict]:
    """video_name -> raw label + zip info, straight from the VL zips."""
    out: dict[str, dict] = {}
    dupes = []
    for path in sorted((RAW / "597").rglob("VL_*_영상_*.zip")):
        place = path.stem.split("_영상_")[1]
        obj = path.stem.split("_")[1]
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if not name.endswith(".json"):
                    continue
                v = json.loads(z.read(name).decode("utf-8-sig"))["video"]
                if v["video_name"] in out:
                    dupes.append(v["video_name"])
                out[v["video_name"]] = {**v, "_zip_place": place, "_zip_object": obj, "_member": name}
    check(not dupes, f"video names unique across VL zips ({len(out)} labels, dupes {dupes[:3]})")
    return out


def layout_code_faults() -> dict[int, tuple[int, int]]:
    """Code -> (fault A, fault B) from `pdftotext -layout`, one-line regex only."""
    pdf = next((RAW / "597").rglob("*manual*.pdf"))
    txt = subprocess.run([shutil.which("pdftotext"), "-layout", "-enc", "UTF-8", str(pdf), "-"],
                         capture_output=True, check=True).stdout.decode("utf-8")
    faults = {}
    for line in txt.splitlines():
        m = re.search(r"\s(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s*$", line)
        if m and int(m[1]) + int(m[2]) == 100:
            faults.setdefault(int(m[3]), (int(m[1]), int(m[2])))
    return faults


def audit_fault_set(raw: dict[str, dict]) -> None:
    print("\n[1] fault eval set vs raw VL labels")
    manifest = list(csv.DictReader((ROOT / "data" / "manifests" / "eval_fault.csv").open(encoding="utf-8")))
    names = [r["video_name"] for r in manifest]
    check(len(manifest) == 150, f"150 rows (got {len(manifest)})")
    check(len(set(names)) == len(names), "no duplicate videos")
    check(Counter(r["zip_place"] for r in manifest) == Counter({p: 50 for p in PLACES}),
          f"50 per place {dict(Counter(r['zip_place'] for r in manifest))}")
    check([r["eval_id"] for r in manifest] == [f"F{i:03d}" for i in range(1, 151)], "eval ids F001..F150 in order")

    missing = [n for n in names if n not in raw]
    check(not missing, f"every video has a raw VL label (missing {missing[:3]})")
    wrong_place = [n for r in manifest if (n := r["video_name"]) in raw and raw[n]["_zip_place"] != r["zip_place"]]
    check(not wrong_place, f"manifest place == raw zip place (wrong {wrong_place[:3]})")
    check(all(raw[n]["_zip_object"] == "차대차" for n in names if n in raw), "all from 차대차 zips")
    check(all(raw[n]["filming_way"] == "bb" and raw[n]["video_point_of_view"] == 1 for n in names if n in raw),
          "all blackbox (bb) first person (pov 1)")
    check(all(n.startswith("bb_1_") for n in names), "file names start with bb_1_")

    interim = {r["video_name"]: r for r in csv.DictReader((INTERIM / "eval_fault.csv").open(encoding="utf-8-sig"))}
    faults = layout_code_faults()
    mism_type, mism_fault, mism_code, not_found = [], [], [], []
    for n in names:
        v, r = raw[n], interim[n]
        typ = v.get("traffic_accident_type", v.get("accident_type"))
        fa = v.get("accident_negligence_rateA", v.get("accident_negligence_rate"))
        if str(typ) != r["accident_type"]:
            mism_type.append(n)
        if str(fa) != r["fault_a"]:
            mism_fault.append(n)
        if typ not in faults:
            not_found.append((n, typ))
        elif faults[typ][0] != fa:
            mism_code.append((n, typ, fa, faults[typ]))
    check(not mism_type, f"accident type == raw ({mism_type[:3]})")
    check(not mism_fault, f"fault A == raw ({mism_fault[:3]})")
    check(not mism_code, f"raw fault A == manual base fault via -layout regex ({mism_code[:3]})")
    print(f"       codes not in -layout one-line regex (checked by DP parser only): {not_found[:5]}")

    codes = {r["code"]: r for r in csv.DictReader((INTERIM / "accident_codes.csv").open(encoding="utf-8-sig"))}
    check(all(codes[r["accident_type"]]["accident_object"] == "차대차" for r in interim.values()),
          "all accident types are car-to-car codes")
    check(all(codes[r["accident_type"]]["place_key"] == r["zip_place"] for r in interim.values()),
          "code place == zip place for every row")

    print("\n[2] distribution: pool vs sample (fault A)")
    pool = [v for v in raw.values() if v["_zip_object"] == "차대차" and v["_zip_place"] in PLACES
            and v["filming_way"] == "bb" and v["video_point_of_view"] == 1]
    for place in PLACES:
        p = Counter(v.get("accident_negligence_rateA", v.get("accident_negligence_rate"))
                    for v in pool if v["_zip_place"] == place)
        s = Counter(int(interim[n]["fault_a"]) for n in names if interim[n]["zip_place"] == place)
        types_pool = len({v.get("traffic_accident_type", v.get("accident_type")) for v in pool if v["_zip_place"] == place})
        types_s = len({interim[n]["accident_type"] for n in names if interim[n]["zip_place"] == place})
        print(f"  {place}: pool {sum(p.values())} ({types_pool} types) -> sample 50 ({types_s} types)")
        print(f"      pool   {dict(sorted(p.items()))}")
        print(f"      sample {dict(sorted(s.items()))}")
        short = [f for f in p if s[f] < min(p[f], max(s.values()))]
        print(f"      fault values sampled below the max although the pool had more: {short}")


def audit_synth(raw_videos: dict[str, dict]) -> None:
    print("\n[3] synthetic cases (reviewed clips only) vs raw damage labels and estimates")
    cases = [json.loads(l) for l in (INTERIM / "synth_cases.jsonl").open(encoding="utf-8")]
    manifest = {r["case_id"]: r for r in csv.DictReader((ROOT / "data" / "manifests" / "synth_cases.csv").open(encoding="utf-8"))}
    review = {r["video_name"]: r for r in csv.DictReader((ROOT / "data" / "manifests" / "label_review.csv").open(encoding="utf-8"))}
    usable = {n for n, r in review.items() if r["use"] == "1"}
    n_cases = len(cases)
    check(n_cases == len(usable) and set(manifest) == {c["case_id"] for c in cases},
          f"{n_cases} cases = reviewed clips ({len(usable)}), manifest ids match")
    check(Counter(c["case_type"] for c in cases) == Counter(normal=56, inflated=18, contradiction=18), "type mix 56/18/18")
    check(len({c["accident_id"] for c in cases}) == n_cases, "each damage accident used once")
    check({c["video"]["video_name"] for c in cases} == usable, "each reviewed clip used once, no excluded clip")
    check(all(c["claimant"] == review[c["video"]["video_name"]]["ego_role"] for c in cases),
          "claimant role == label review ego_role")
    areas = {r["code"]: r for r in csv.DictReader((ROOT / "data" / "reference" / "collision_areas.csv").open(encoding="utf-8-sig"))}
    check(all(c["claimant_impact_directions"] == sorted(areas[c["video"]["accident_type"]][
        "a_areas" if c["claimant"] == "A" else "b_areas"].split(";")) for c in cases),
          "claimant impact directions follow the claimant's role in collision_areas.csv")
    check(all(int(c["video"]["ego_fault"]) == int(c["video"]["fault_b" if c["claimant"] == "B" else "fault_a"])
              and int(c["video"]["ego_fault"]) + int(c["video"]["other_fault"]) == 100 for c in cases),
          "claimant fault = fault of the claimant's role, shares sum to 100")
    charts = {int(r["code"]): r for r in csv.DictReader((ROOT / "data" / "reference" / "code_to_chart.csv").open(encoding="utf-8"))}
    ch = [charts[int(c["video"]["accident_type"])] for c in cases]
    check(all((int(c["video"]["fault_a"]), int(c["video"]["fault_b"])) == (int(x["chart_fault_a"]), int(x["chart_fault_b"]))
              and (int(c["video"]["aihub_fault_a"]), int(c["video"]["aihub_fault_b"])) == (int(x["aihub_fault_a"]), int(x["aihub_fault_b"]))
              for c, x in zip(cases, ch)), "fault = current standard chart (code_to_chart.csv), AI Hub fault kept alongside")
    check(all(int(c["video"]["fault_scored"]) == int(x["mapping"] != "uncertain") for c, x in zip(cases, ch)),
          f"fault not scored only for uncertain charts ({sum(x['mapping'] == 'uncertain' for x in ch)} cases)")
    check(all(c["accident_id"].startswith("sc-") for c in cases), "all SOCAR (sc-) accidents")

    ids = {c["accident_id"] for c in cases}
    imgs: dict[str, set] = {i: set() for i in ids}
    parts: dict[str, set] = {i: set() for i in ids}
    with zipfile.ZipFile(next((RAW / "581").rglob("VL_damage.zip"))) as z:
        for name in z.namelist():
            if name.endswith(".json"):
                d = json.loads(z.read(name).decode("utf-8-sig"))
                aid = d["categories"]["id"]
                if aid in ids:
                    imgs[aid].add(d["images"]["file_name"])
                    for a in d["annotations"]:
                        for item in ([a["repair"]] if isinstance(a["repair"], str) else a["repair"] or []):
                            if ":" in item:
                                parts[aid].add(item.split(":")[0].strip())
    check(all(set(c["images"]) == imgs[c["accident_id"]] for c in cases), "image lists == raw VL_damage images")
    check(all(set(c["photo_parts"]) == parts[c["accident_id"]] for c in cases), "photo parts == raw repair parts")

    def n(x):
        s = re.sub(r"[^\d]", "", str(x or ""))
        return int(s) if s else 0

    bad_amount, bad_items, bad_video = [], [], []
    with zipfile.ZipFile(next((RAW / "581").rglob("TS_99*.zip"))) as z:
        for c in cases:
            e = json.loads(z.read(c["accident_id"] + ".json").decode("utf-8-sig"))
            rows = e["수리내역"]
            claimed = sum(n(r["손해사정전"]["부품가격"]) + n(r["손해사정전"]["공임"]) for r in rows)
            approved = sum(n(r["손해사정후"]["부품가격"]) + n(r["손해사정후"]["공임"]) for r in rows)
            injected = sum(n(i["claimed_part"]) + n(i["claimed_labor"]) for i in c["injected_items"])
            if (claimed + injected, approved) != (c["claimed_total"], c["approved_total"]):
                bad_amount.append((c["case_id"], claimed + injected, c["claimed_total"], approved, c["approved_total"]))
            if [r["작업항목 및 부품명"].strip() for r in rows] != [i["name"] for i in c["estimate_items"]]:
                bad_items.append(c["case_id"])
            v = raw_videos[c["video"]["video_name"]]
            if str(v.get("traffic_accident_type", v.get("accident_type"))) != c["video"]["accident_type"]:
                bad_video.append(c["case_id"])
            for i in c["injected_items"]:
                donor = json.loads(z.read(i["donor_estimate"] + ".json").decode("utf-8-sig"))["수리내역"]
                if not any(r["작업항목 및 부품명"].strip() == i["name"] and r["작업"].strip() == i["work"] for r in donor):
                    bad_items.append(c["case_id"] + ":donor")
                if i["name"] in {r["작업항목 및 부품명"].strip() for r in rows}:
                    bad_items.append(c["case_id"] + ":dup")
    check(not bad_amount, f"claimed/approved totals == raw estimate (+ injected) {bad_amount[:3]}")
    check(not bad_items, f"estimate items and donor items match raw {bad_items[:3]}")
    check(not bad_video, f"case video labels == raw {bad_video[:3]}")
    route_ok = all(
        c["expected_route"] == ("siu" if c["case_type"] == "contradiction"
                                else "adjust" if c["injected_items"] or c["approved_total"] < c["claimed_total"] - sum(
                                    n(i["claimed_part"]) + n(i["claimed_labor"]) for i in c["injected_items"])
                                else "approve")
        for c in cases)
    check(route_ok, "expected route follows the stated rule from raw amounts")


def audit_leakage() -> None:
    print("\n[4] train/eval leakage (TL labels)")
    tl_zips = sorted((RAW / "597").rglob("TL_*_영상_*.zip"))
    if not tl_zips:
        print("  SKIP no TL label zips (download_aihub.py --stage 1)")
        return
    tl: dict[str, str] = {}
    for path in tl_zips:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.endswith(".json"):
                    v = json.loads(z.read(name).decode("utf-8-sig"))["video"]
                    tl[v["video_name"]] = path.stem.split("_영상_")[1]
    names = [r["video_name"] for r in csv.DictReader((ROOT / "data" / "manifests" / "eval_fault.csv").open(encoding="utf-8"))]
    check(not set(names) & set(tl), f"no eval video name in TL ({len(tl)} TL labels)")
    # names are bb_<pov>_<date>_vehicle_<source>_<seq>; same date+source can hold unrelated accidents
    stem = lambda n: n.rsplit("_", 1)[0]  # noqa: E731
    shared = [n for n in names if stem(n) in {stem(t) for t in tl}]
    print(f"       eval videos sharing date+source prefix with a TL clip: {len(shared)} {shared[:5]}")


def audit_media() -> None:
    print("\n[5] extracted media")
    media = ROOT / "data" / "interim" / "media"
    if not media.exists():
        print("  SKIP no data/interim/media (scripts/extract_media.py)")
        return
    names = [r["video_name"] for r in csv.DictReader((ROOT / "data" / "manifests" / "eval_fault.csv").open(encoding="utf-8"))]
    videos = {p.stem: p for p in (media / "videos").glob("*")}
    check(all(n in videos and videos[n].stat().st_size > 0 for n in names), f"all {len(names)} eval videos extracted")
    images = {img for line in (INTERIM / "synth_cases.jsonl").open(encoding="utf-8") for img in json.loads(line)["images"]}
    have = {p.name for p in (media / "images").glob("*") if p.stat().st_size > 0}
    check(images <= have, f"all {len(images)} synthetic-case images extracted (missing {sorted(images - have)[:3]})")


def main() -> None:
    raw = raw_video_labels()
    audit_fault_set(raw)
    audit_synth(raw)
    audit_leakage()
    audit_media()
    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} FAILED'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
