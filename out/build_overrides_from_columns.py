#!/usr/bin/env python3
# build_overrides_from_columns.py
# Minimal generator: reads columns.json and emits nonlinear_overrides.json
import json
from pathlib import Path
from collections import defaultdict

# --- Default (simple) hinge parameters — adjust later as you calibrate
DEFAULT_STEEL = {
    "My": 1.0e6,      # N·m (placeholder)
    "theta": 0.005,   # rad
    "Lp": 0.10,       # m
    "b": 0.01,
    "R0": 20.0, "cR1": 0.925, "cR2": 0.15,
    "a1": 0.01, "a2": 1.0, "a3": 0.01, "a4": 1.0,
}

def _gen_tag_blocks():
    """Yield unique tags for each hinge set: (sec_i, sec_j, beamInt, elastic, matMy, matMz)."""
    base = 30
    while True:
        base += 10
        yield (base, base+1, base+3, 4000 + base, 5000 + base, 6000 + base)

def _validate(hinge_sets, elements):
    """Light validation mirroring generate_explicit_model.HingeSet.valid()."""
    problems = []
    used = set()
    def need(d, keys): return all(k in d for k in keys)

    for hs in hinge_sets:
        if not (hs.get("sec_i_tag") and hs.get("sec_j_tag") and hs.get("beamInt_tag") and hs.get("hingeLength",0)>0):
            problems.append(f"[{hs.get('name')}] core tags/hingeLength missing")
        el = hs.get("elastic", {})
        my = hs.get("matMy", {})
        mz = hs.get("matMz", {})
        if not (need(el,("tag","E","A","Iy","Iz","G","J")) and
                need(my,("tag","My","theta","Lp","b","R0","cR1","cR2","a1","a2","a3","a4")) and
                need(mz,("tag","My","theta","Lp","b","R0","cR1","cR2","a1","a2","a3","a4"))):
            problems.append(f"[{hs.get('name')}] incomplete emit payload")
        for t in (el.get("tag"), my.get("tag"), mz.get("tag"),
                  hs.get("sec_i_tag"), hs.get("sec_j_tag"), hs.get("beamInt_tag")):
            if t in used: problems.append(f"[{hs.get('name')}] duplicate tag {t}")
            used.add(t)
        if my.get("My",0)<=0 or mz.get("My",0)<=0: problems.append(f"[{hs.get('name')}] My must be > 0")
        if not (0 < my.get("b",0.01) <= 0.2 and 0 < mz.get("b",0.01) <= 0.2):
            problems.append(f"[{hs.get('name')}] b out of expected range (0,0.2]")

    names = {hs["name"] for hs in hinge_sets}
    for t in elements:
        if t.get("use_set") not in names: problems.append(f"[target] unknown hinge set {t.get('use_set')}")
        if t.get("kind","") != "COLUMN": problems.append("[target] kind must be 'COLUMN'")

    return problems

def build_from_columns(columns_path: str, output_path: str, hinge_len: float = 0.20):
    # Load columns.json (supports either {"columns":[...]} or a top-level array)
    records = json.load(open(columns_path, "r", encoding="utf-8"))
    records = records.get("columns", records)

    # 1) With simplified model, all columns are deformable (no more segment splitting)
    deformable = [r for r in records if r.get("line")]  # All records with "line" field are valid elements

    # 2) Group by section and collect nominal elastic props from the deformable piece
    by_sec = defaultdict(list)
    props = {}
    for r in deformable:
        sec = str(r.get("section","")).strip()
        if not sec: continue
        by_sec[sec].append(int(r["tag"]))
        if sec not in props:
            props[sec] = {
                "E": float(r.get("E",0.0)), "A": float(r.get("A",0.0)),
                "Iy": float(r.get("Iy",0.0)), "Iz": float(r.get("Iz",0.0)),
                "G": float(r.get("G",0.0)), "J": float(r.get("J",0.0)),
            }

    # 3) Emit hinge_sets + element targets (by.tags) per section
    hinge_sets, elements = [], []
    tag_blocks = _gen_tag_blocks()

    for sec, tags in sorted(by_sec.items()):
        sec_i, sec_j, beamInt, elastic_tag, my_tag, mz_tag = next(tag_blocks)
        hs = {
            "name": f"ColHinge_{sec}",
            "mode": "emit",
            "elastic": {"tag": elastic_tag, **props[sec]},
            "matMy": {"tag": my_tag, **DEFAULT_STEEL},
            "matMz": {"tag": mz_tag, **DEFAULT_STEEL},
            "sec_i_tag": sec_i,
            "sec_j_tag": sec_j,
            "beamInt_tag": beamInt,
            "hingeLength": hinge_len,
        }
        hinge_sets.append(hs)
        elements.append({
            "kind": "COLUMN",
            "by": {"tags": tags},
            "use_set": hs["name"],
            "eleType": "forceBeamColumn",
        })

    problems = _validate(hinge_sets, elements)
    data = {"hinge_sets": hinge_sets, "elements": elements}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return {"sections": {k: len(v) for k, v in by_sec.items()},
            "tags_total": sum(len(v) for v in by_sec.values()),
            "problems": problems}

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("columns_json")
    ap.add_argument("output_json")
    ap.add_argument("--hinge-length", type=float, default=0.20)
    args = ap.parse_args()
    summary = build_from_columns(args.columns_json, args.output_json, hinge_len=args.hinge_length)
    print(json.dumps(summary, indent=2))
