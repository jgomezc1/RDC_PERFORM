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


def _get_section_properties(section_name: str, parsed_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract material and geometric properties for a given section from parsed .e2k data.
    Uses ETABS-derived material and section property calculators for accurate properties.

    Parameters
    ----------
    section_name : str
        Section name (e.g., "V40X55")
    parsed_data : dict
        Parsed .e2k data containing materials and frame_sections

    Returns
    -------
    dict
        Properties with keys: A, E, G, J, Iy, Iz, b_sec, h_sec
        Falls back to hardcoded values if section not found.
    """
    # Import calculators (lazy import to avoid circular dependencies)
    try:
        from material_property_calculator import MaterialPropertyCalculator
        from section_property_calculator import SectionPropertyCalculator

        # Initialize calculators with parsed data path
        material_calc = MaterialPropertyCalculator()
        section_calc = SectionPropertyCalculator()

        # Get section properties from ETABS calculations
        section_props = section_calc.get_section_properties(section_name)
        if section_props:
            # Get material properties for this section
            material_props = material_calc.get_material_properties(section_props.material)

            if material_props:
                # Calculate shear modulus
                E = material_props.Ec
                nu = material_props.poisson_ratio
                G = E / (2.0 * (1.0 + nu))

                print(f"[beams] Using ETABS properties for {section_name}: "
                      f"E={E/1e9:.1f} GPa, A={section_props.area:.4f} m²")

                return {
                    "A": section_props.area,
                    "E": E,
                    "G": G,
                    "J": section_props.J,
                    "Iy": section_props.Iyy,  # Minor axis
                    "Iz": section_props.Ixx,  # Major axis
                    "b_sec": section_props.width,
                    "h_sec": section_props.depth
                }
            else:
                print(f"[beams] Warning: Material '{section_props.material}' not found for section '{section_name}'")
        else:
            print(f"[beams] Warning: Section '{section_name}' not found in ETABS calculator")

    except Exception as e:
        print(f"[beams] Warning: Could not load ETABS calculators ({e}), using fallback calculation")

    # Fallback to original calculation method
    return _get_section_properties_fallback(section_name, parsed_data)


def _get_section_properties_fallback(section_name: str, parsed_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Fallback method for extracting section properties when ETABS calculators are not available.
    This maintains backward compatibility with the original calculation approach.
    """
    frame_sections = parsed_data.get("frame_sections", {})
    materials = parsed_data.get("materials", {})

    # Default fallback values (original hardcoded)
    defaults = {
        "b_sec": 0.40,  # width [m]
        "h_sec": 0.50,  # depth [m]
        "E": 2.50e10,   # [Pa]
        "nu": 0.20,     # Poisson's ratio
    }

    section_data = frame_sections.get(section_name)
    if not section_data:
        print(f"[beams] Warning: Section '{section_name}' not found, using defaults")
        return _calculate_structural_properties(**defaults)

    # Extract dimensions
    dimensions = section_data.get("dimensions", {})
    shape = section_data.get("shape", "")

    if "Rectangular" in shape:
        # ETABS rectangular: D=height, B=width
        h_sec = float(dimensions.get("D", defaults["h_sec"]))  # depth/height
        b_sec = float(dimensions.get("B", defaults["b_sec"]))  # width
    else:
        print(f"[beams] Warning: Unsupported shape '{shape}' for section '{section_name}', using defaults")
        h_sec = defaults["h_sec"]
        b_sec = defaults["b_sec"]

    # Extract material properties from concrete materials
    material_name = section_data.get("material")
    concrete_materials = materials.get("concrete", {})
    material_data = concrete_materials.get(material_name, {}) if material_name else {}

    # Determine Young's modulus E
    if material_data and "fc" in material_data:
        # For concrete, estimate E from fc using ACI formula: E ≈ 4700√fc [MPa]
        fc_pa = float(material_data["fc"])  # Already in Pa from ETABS
        fc_mpa = fc_pa / 1e6  # Convert to MPa
        E = 4700 * (fc_mpa ** 0.5) * 1e6  # Convert back to Pa
        print(f"[beams] Using ETABS material {material_name}: fc={fc_mpa:.1f} MPa → E={E/1e9:.1f} GPa")
    else:
        print(f"[beams] Warning: Material '{material_name}' not found in concrete materials, using default E")
        E = defaults["E"]

    return _calculate_structural_properties(b_sec=b_sec, h_sec=h_sec, E=E, nu=defaults["nu"])


def _calculate_structural_properties(b_sec: float, h_sec: float, E: float, nu: float) -> Dict[str, float]:
    """
    Calculate structural properties for rectangular section.

    Parameters
    ----------
    b_sec : float
        Width [m]
    h_sec : float
        Height/depth [m]
    E : float
        Young's modulus [Pa]
    nu : float
        Poisson's ratio

    Returns
    -------
    dict
        Structural properties: A, E, G, J, Iy, Iz, b_sec, h_sec
    """
    G = E / (2.0 * (1.0 + nu))
    A = b_sec * h_sec
    Iy = (b_sec * h_sec**3) / 12.0  # Moment of inertia about y-axis
    Iz = (h_sec * b_sec**3) / 12.0  # Moment of inertia about z-axis
    J = b_sec * h_sec**3 / 3.0      # Torsional constant (rectangular approximation)

    return {
        "A": A, "E": E, "G": G, "J": J, "Iy": Iy, "Iz": Iz,
        "b_sec": b_sec, "h_sec": h_sec
    }


def _calculate_joint_offsets(
    pI: Tuple[float, float, float],
    pJ: Tuple[float, float, float],
    length_off_i: float = 0.0,
    length_off_j: float = 0.0,
    offsets_i: Optional[Dict[str, float]] = None,
    offsets_j: Optional[Dict[str, float]] = None
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """
    Calculate joint offsets for OpenSees geomTransf based on ETABS rigid ends and offsets.

    Implementation follows PDF guidance:
    - d_I = d_I^(len) + Δ_I (axial rigid end + lateral offset)
    - d_J = d_J^(len) + Δ_J (axial rigid end + lateral offset)

    Parameters
    ----------
    pI, pJ : tuple
        Grid node coordinates (x, y, z) for I and J ends
    length_off_i, length_off_j : float
        LENGTHOFFI/J from ETABS (rigid end lengths)
    offsets_i, offsets_j : dict
        OFFSETX/Y/ZI/J from ETABS (lateral eccentricities)

    Returns
    -------
    tuple
        (dI, dJ) where each is (dx, dy, dz) for -jntOffset parameter
    """
    import math

    # Calculate unit vector along member axis (I -> J)
    xi, yi, zi = pI
    xj, yj, zj = pJ
    vx, vy, vz = (xj - xi), (yj - yi), (zj - zi)
    length = math.sqrt(vx*vx + vy*vy + vz*vz)

    if length == 0.0:
        # Degenerate case
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)

    # Unit vector components
    ex, ey, ez = vx/length, vy/length, vz/length

    # Axial rigid end components (along member axis)
    # d_I^(len) = +L_I * e (positive direction from I toward J)
    # d_J^(len) = -L_J * e (negative direction from J toward I)
    dI_len_x = length_off_i * ex
    dI_len_y = length_off_i * ey
    dI_len_z = length_off_i * ez

    dJ_len_x = -length_off_j * ex
    dJ_len_y = -length_off_j * ey
    dJ_len_z = -length_off_j * ez

    # Lateral offset components (from ETABS OFFSETX/Y/ZI/J)
    offsets_i = offsets_i or {}
    offsets_j = offsets_j or {}

    dI_lat_x = offsets_i.get('x', 0.0)
    dI_lat_y = offsets_i.get('y', 0.0)
    dI_lat_z = offsets_i.get('z', 0.0)

    dJ_lat_x = offsets_j.get('x', 0.0)
    dJ_lat_y = offsets_j.get('y', 0.0)
    dJ_lat_z = offsets_j.get('z', 0.0)

    # Total joint offsets (axial + lateral)
    dI = (dI_len_x + dI_lat_x, dI_len_y + dI_lat_y, dI_len_z + dI_lat_z)
    dJ = (dJ_len_x + dJ_lat_x, dJ_len_y + dJ_lat_y, dJ_len_z + dJ_lat_z)

    return dI, dJ


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
) -> List[int]:
    """
    Builds BEAM elements per-story with "last section wins" within each story.
    Uses actual section and material properties from parsed .e2k data.
    Returns the list of created element tags. Also writes OUT_DIR/beams.json.
    """
    # Ensure OpenSees domain exists
    _ensure_ops_model(3, 6)

    story = _load_json(story_path)
    _raw = _load_json(raw_path)  # Contains parsed .e2k data with materials/sections

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
            section_name = ln.get("section", "")

            # Get section-specific properties from parsed .e2k data
            section_props = _get_section_properties(section_name, _raw)
            A_beam = section_props["A"]
            E_beam = section_props["E"]
            G_beam = section_props["G"]
            J_beam = section_props["J"]
            Iy_beam = section_props["Iy"]
            Iz_beam = section_props["Iz"]

            # Get node coordinates for joint offset calculation
            pI = act_pt_map.get((pid_i, sname), (0.0, 0.0, 0.0))
            pJ = act_pt_map.get((pid_j, sname), (0.0, 0.0, 0.0))

            # Extract offsets from line assigns (beams typically have none per modeling convention)
            offsets_i = ln.get("offsets_i")
            offsets_j = ln.get("offsets_j")

            # Calculate joint offsets for geomTransf
            dI, dJ = _calculate_joint_offsets(
                pI, pJ, LoffI, LoffJ, offsets_i, offsets_j
            )

            # Create single element connecting directly between grid nodes
            etag = element_tag("BEAM", line_name, int(sidx))
            transf_tag = 1000000000 + etag  # avoid collisions with columns (unchanged)

            # Apply joint offsets if any non-zero offsets exist
            if any(abs(x) > 1e-12 for x in (*dI, *dJ)):
                ops.geomTransf('Linear', transf_tag, 0, 0, 1, '-jntOffset',
                              dI[0], dI[1], dI[2], dJ[0], dJ[1], dJ[2])
            else:
                ops.geomTransf('Linear', transf_tag, 0, 0, 1)  # no offsets

            ops.element('elasticBeamColumn', etag, nI, nJ, A_beam, E_beam, G_beam, J_beam, Iy_beam, Iz_beam, transf_tag)
            created.append(etag)

            emitted.append({
                "tag": etag,
                "line": line_name,
                "story": sname,
                "i_node": nI,
                "j_node": nJ,
                "section": section_name,
                "transf_tag": transf_tag,
                "A": A_beam, "E": E_beam, "G": G_beam, "J": J_beam, "Iy": Iy_beam, "Iz": Iz_beam,
                "length_off_i": LoffI, "length_off_j": LoffJ,
                "offsets_i": offsets_i, "offsets_j": offsets_j,  # lateral offsets from ETABS
                "joint_offset_i": list(dI), "joint_offset_j": list(dJ),  # calculated joint offsets
                "has_joint_offsets": any(abs(x) > 1e-12 for x in (*dI, *dJ))  # flag for verification
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
