"""
Create BEAM elements as OpenSeesPy elasticBeamColumn members. Writes Phase-2
artifact `beams.json`.

Rules
-----
- Auto-initialize OpenSees model if ndm/ndf are zero (no wipe).
- One element per ETABS line, connecting directly between grid nodes.
- Deterministic node tags: node_tag = point_int * 1000 + story_index
- Story index 0 = Roof (top), increasing downward.
- Orientation vector: local z-axis = (0, 0, 1) for beams.
"""
from __future__ import annotations

from typing import Dict, Any, List, Set, Tuple, Optional
import json
import os
import hashlib

import openseespy.opensees as ops  # unified ops namespace

# Optional config hooks
try:
    from config import OUT_DIR  # type: ignore
except Exception:
    OUT_DIR = "out"

# Prefer project tagging helpers if available
try:
    from tagging import node_tag_grid, element_tag  # type: ignore
except Exception:
    node_tag_grid = None  # type: ignore

    def element_tag(kind: str, name: str, story_index: int) -> int:  # type: ignore
        s = f"{kind}|{name}|{story_index}".encode("utf-8")
        return int.from_bytes(hashlib.md5(s).digest()[:4], "big") & 0x7FFFFF

# Rigid end scale (A, Iy, Iz, J are multiplied by this for rigid segments)
try:
    from config import RIGID_END_SCALE  # type: ignore
except Exception:
    RIGID_END_SCALE = 1.0e6

# Removed rigid end splitting - rigid_end_utils no longer used


def _ensure_ops_model(ndm: int = 3, ndf: int = 6) -> None:
    """
    Ensure the OpenSees domain is initialized. If ndm/ndf are zero, set a basic 3D, 6-DOF model.
    This is idempotent and does not wipe an existing model.
    """
    try:
        cur_ndm = ops.getNDM()
        cur_ndf = ops.getNDF()
    except Exception:
        cur_ndm, cur_ndf = 0, 0
    if int(cur_ndm) == 0 or int(cur_ndf) == 0:
        ops.model("basic", "-ndm", ndm, "-ndf", ndf)
        print(f"[beams] Initialized OpenSees model: ndm={ndm}, ndf={ndf}")


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _point_pid(p: Dict[str, Any]) -> Optional[str]:
    for key in ("id", "tag", "point", "pid"):
        if key in p and p[key] is not None:
            return str(p[key])
    return None


def _active_points_map(story: Dict[str, Any]) -> Dict[Tuple[str, str], Tuple[float, float, float]]:
    out: Dict[Tuple[str, str], Tuple[float, float, float]] = {}
    aps = story.get("active_points") or {}
    for sname, pts in aps.items():
        for p in pts:
            pid = _point_pid(p)
            if not pid:
                print(f"[beams] WARN: active_point in '{sname}' missing 'id'/'tag'; skipped.")
                continue
            out[(pid, sname)] = (float(p["x"]), float(p["y"]), float(p["z"]))
    return out


def _ensure_node_for(
    pid: str, sname: str, sidx: int, act_pt_map: Dict[Tuple[str, str], Tuple[float, float, float]],
    existing_nodes: Set[int],
) -> Optional[int]:
    """
    Ensure a node for (pid, sname) exists; create it if missing using active_points coords.
    Returns the node tag, or None if the point is absent from active_points.
    """
    key = (str(pid), sname)
    if key not in act_pt_map:
        return None
    tag = int(pid) * 1000 + int(sidx)
    if tag not in existing_nodes:
        x, y, z = act_pt_map[key]
        ops.node(tag, x, y, z)
        existing_nodes.add(tag)
    return tag


def _dedupe_last_section_wins(lines_for_story: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    last: Dict[str, Dict[str, Any]] = {}
    for ln in lines_for_story:
        last[str(ln["name"])] = ln
    return list(last.values())


def define_beams(
    story_path: str = os.path.join(OUT_DIR, "story_graph.json"),
    raw_path: str = os.path.join(OUT_DIR, "parsed_raw.json"),
    *,
    # --- Placeholder properties (override as needed; units consistent with your model) ---
    b_sec: float = 0.40,   # width  [m]
    h_sec: float = 0.50,   # depth  [m]
    E_beam: float = 2.50e10,  # [Pa]
    nu_beam: float = 0.20
) -> List[int]:
    """
    Builds BEAM elements per-story with "last section wins" within each story.
    Returns the list of created element tags. Also writes OUT_DIR/beams.json.
    """
    # Ensure OpenSees domain exists
    _ensure_ops_model(3, 6)

    story = _load_json(story_path)
    _raw = _load_json(raw_path)  # parity/debugging

    # --- Section / Material ---
    G_beam = E_beam / (2.0 * (1.0 + nu_beam))
    A_beam = b_sec * h_sec
    Iy_beam = (b_sec * h_sec**3) / 12.0
    Iz_beam = (h_sec * b_sec**3) / 12.0
    J_beam = b_sec * h_sec**3 / 3.0

    story_names: List[str] = list(story.get("story_order_top_to_bottom", []))  # top -> bottom
    story_index = {name: i for i, name in enumerate(story_names)}
    act_pt_map = _active_points_map(story)

    created: List[int] = []
    skips: List[str] = []
    emitted: List[Dict[str, Any]] = []

    try:
        existing_nodes: Set[int] = set(ops.getNodeTags())
    except Exception:
        existing_nodes = set()

    active_lines: Dict[str, List[Dict[str, Any]]] = story.get("active_lines", {})
    for sname, lines in active_lines.items():
        sidx = story_index[sname]
        per_story = _dedupe_last_section_wins(lines)
        for ln in per_story:
            if str(ln.get("type", "")).upper() != "BEAM":
                continue

            pid_i: str = str(ln["i"])
            pid_j: str = str(ln["j"])

            nI = _ensure_node_for(pid_i, sname, sidx, act_pt_map, existing_nodes)
            nJ = _ensure_node_for(pid_j, sname, sidx, act_pt_map, existing_nodes)
            if nI is None or nJ is None:
                skips.append(f"{ln.get('name','?')} @ '{sname}' skipped — endpoint(s) not present on this story")
                continue

            LoffI = float(ln.get("length_off_i", 0.0) or 0.0)  # preserved for artifact
            LoffJ = float(ln.get("length_off_j", 0.0) or 0.0)  # preserved for artifact
            line_name = str(ln.get("name", "?"))

            # Create single element connecting directly between grid nodes
            etag = element_tag("BEAM", line_name, int(sidx))
            transf_tag = 1000000000 + etag  # avoid collisions with columns
            ops.geomTransf('Linear', transf_tag, 0, 0, 1)  # local z axis

            ops.element('elasticBeamColumn', etag, nI, nJ, A_beam, E_beam, G_beam, J_beam, Iy_beam, Iz_beam, transf_tag)
            created.append(etag)

            emitted.append({
                "tag": etag,
                "line": line_name,
                "story": sname,
                "i_node": nI,
                "j_node": nJ,
                "section": ln.get("section"),
                "transf_tag": transf_tag,
                "A": A_beam, "E": E_beam, "G": G_beam, "J": J_beam, "Iy": Iy_beam, "Iz": Iz_beam,
                "length_off_i": LoffI, "length_off_j": LoffJ,  # preserved but unused
            })

    if skips:
        print("[beams] Skips:")
        for s in skips:
            print(" -", s)
    print(f"[beams] Created {len(created)} beam elements.")

    # Emit artifact
    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(os.path.join(OUT_DIR, "beams.json"), "w", encoding="utf-8") as f:
            json.dump({"beams": emitted, "counts": {"created": len(created)}, "skips": skips}, f, indent=2)
        print(f"[beams] Wrote {OUT_DIR}/beams.json")
    except Exception as e:
        print(f"[beams] WARN: failed to write beams.json: {e}")

    return created
