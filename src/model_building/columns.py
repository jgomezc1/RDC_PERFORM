"""
Create COLUMN elements as OpenSeesPy elasticBeamColumn members. Writes Phase-2
artifact `columns.json`.

Rules
-----
- **find-next-lower-story**: For a COLUMN line at story S, connect its endpoint
  'i' at story S to endpoint 'j' at the next lower story K where **both** i and j
  appear in that story's active points. If none is found, skip.
- Enforce local-axis convention (configurable): by default **i = bottom, j = top**.
- Auto-initialize OpenSees model if ndm/ndf are zero (no wipe).
- One element per ETABS line, connecting directly between grid nodes.

OpenSeesPy signatures (exact):
    ops.geomTransf('Linear', transf_tag, 1, 0, 0)
    ops.element('elasticBeamColumn', tag, nI, nJ,
                A, E, G, J, Iy, Iz, transf_tag)
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

# Convention: i = bottom, j = top (swap if needed)
try:
    from config import ENFORCE_COLUMN_I_AT_BOTTOM  # type: ignore
except Exception:
    ENFORCE_COLUMN_I_AT_BOTTOM = True

# Rigid end scale (A, Iy, Iz, J are multiplied by this for rigid segments)
try:
    from config import RIGID_END_SCALE  # type: ignore
except Exception:
    RIGID_END_SCALE = 1.0e6

# Prefer project tagging helpers if available
try:
    from src.utilities.tagging import element_tag  # type: ignore
except Exception:
    def element_tag(kind: str, name: str, story_index: int) -> int:  # type: ignore
        s = f"{kind}|{name}|{story_index}".encode("utf-8")
        return int.from_bytes(hashlib.md5(s).digest()[:4], "big") & 0x7FFFFFFF

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
        print(f"[columns] Initialized OpenSees model: ndm={ndm}, ndf={ndf}")


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
                print(f"[columns] WARN: active_point in '{sname}' missing 'id'/'tag'; skipped.")
                continue
            out[(pid, sname)] = (float(p["x"]), float(p["y"]), float(p["z"]))
    return out


def _point_exists(pid: str, sname: str, act_pt_map: Dict[Tuple[str, str], Tuple[float, float, float]]) -> bool:
    return (str(pid), sname) in act_pt_map


def _ensure_node_for(
    pid: str, sname: str, sidx: int, act_pt_map: Dict[Tuple[str, str], Tuple[float, float, float]],
    existing_nodes: Set[int]
) -> Optional[int]:
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


def _get_column_section_properties(section_name: str, parsed_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract material and geometric properties for a column section from parsed .e2k data.
    Uses ETABS-derived material and section property calculators for accurate properties.

    Parameters
    ----------
    section_name : str
        Section name (e.g., "C50x80B")
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
        from src.properties.material_property_calculator import MaterialPropertyCalculator
        from src.properties.section_property_calculator import SectionPropertyCalculator

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

                print(f"[columns] Using ETABS properties for {section_name}: "
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
                print(f"[columns] Warning: Material '{section_props.material}' not found for section '{section_name}'")
        else:
            print(f"[columns] Warning: Section '{section_name}' not found in ETABS calculator")

    except Exception as e:
        print(f"[columns] Warning: Could not load ETABS calculators ({e}), using fallback calculation")

    # Fallback to original calculation method
    return _get_column_section_properties_fallback(section_name, parsed_data)


def _get_column_section_properties_fallback(section_name: str, parsed_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Fallback method for extracting column section properties when ETABS calculators are not available.
    This maintains backward compatibility with the original calculation approach.
    """
    frame_sections = parsed_data.get("frame_sections", {})
    materials = parsed_data.get("materials", {})

    # Default fallback values (original hardcoded)
    defaults = {
        "b_sec": 0.40,  # width [m]
        "h_sec": 0.40,  # depth [m]
        "E": 2.50e10,   # [Pa]
        "nu": 0.20,     # Poisson's ratio
    }

    section_data = frame_sections.get(section_name)
    if not section_data:
        print(f"[columns] Warning: Section '{section_name}' not found, using defaults")
        return _calculate_column_structural_properties(**defaults)

    # Extract dimensions
    dimensions = section_data.get("dimensions", {})
    shape = section_data.get("shape", "")

    if "Rectangular" in shape:
        # ETABS rectangular: D=height, B=width
        h_sec = float(dimensions.get("D", defaults["h_sec"]))  # depth/height
        b_sec = float(dimensions.get("B", defaults["b_sec"]))  # width
    else:
        print(f"[columns] Warning: Unsupported shape '{shape}' for section '{section_name}', using defaults")
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
        print(f"[columns] Using ETABS material {material_name}: fc={fc_mpa:.1f} MPa → E={E/1e9:.1f} GPa")
    else:
        print(f"[columns] Warning: Material '{material_name}' not found in concrete materials, using default E")
        E = defaults["E"]

    return _calculate_column_structural_properties(b_sec=b_sec, h_sec=h_sec, E=E, nu=defaults["nu"])


def _calculate_column_structural_properties(b_sec: float, h_sec: float, E: float, nu: float) -> Dict[str, float]:
    """
    Calculate structural properties for rectangular column section.

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


def define_columns(
    story_path: str = os.path.join(OUT_DIR, "story_graph.json"),
    raw_path: str = os.path.join(OUT_DIR, "parsed_raw.json"),
    *,
    b_sec: float = 0.40,   # width  [m] - deprecated, now calculated from ETABS
    h_sec: float = 0.40,   # depth  [m] - deprecated, now calculated from ETABS
    E_col: float = 2.50e10,  # [Pa] - deprecated, now calculated from ETABS
    nu_col: float = 0.20   # Poisson's ratio - deprecated, now calculated from ETABS
) -> List[int]:
    """
    Build COLUMN elements with the next-lower-story rule.
    Returns the list of created element tags. Also writes OUT_DIR/columns.json.

    Note: Individual section parameters (b_sec, h_sec, E_col, nu_col) are deprecated.
    Properties are now automatically calculated from ETABS data per section.
    """
    # Ensure OpenSees domain exists
    _ensure_ops_model(3, 6)

    story = _load_json(story_path)
    _raw = _load_json(raw_path)

    # Note: Section properties are now calculated per element based on ETABS section data

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

    # Lines are per story; we build columns between consecutive stories where points reappear.
    active_lines: Dict[str, List[Dict[str, Any]]] = story.get("active_lines", {})
    for sname, lines in active_lines.items():
        sidx = story_index[sname]
        per_story = _dedupe_last_section_wins(lines)

        # For each COLUMN line at this story, handle two methods:
        # Method 1: pid_i == pid_j → same point ID, find next lower story with same points
        # Method 2: pid_i != pid_j → different points, both exist at current story only
        for ln in per_story:
            if str(ln.get("type", "")).upper() != "COLUMN":
                continue

            pid_i: str = str(ln["i"])  # ETABS i node
            pid_j: str = str(ln["j"])  # ETABS j node

            # METHOD 2: Explicit multi-point columns (i != j)
            # Points may exist at different stories - need to find the correct story for each
            if pid_i != pid_j:
                # Find which story each point exists at (they might be at different stories!)
                # For points that exist at multiple stories, use the one with LOWEST Z (bottom-most)
                # to create the full column segment
                story_i = None
                story_j = None
                sidx_i = None
                sidx_j = None
                min_z_i = 999999.0
                min_z_j = 999999.0

                # Search for pid_i across all stories from current downward, take lowest Z
                for k in range(sidx, len(story_names)):
                    if _point_exists(pid_i, story_names[k], act_pt_map):
                        coord = act_pt_map.get((pid_i, story_names[k]))
                        if coord and coord[2] < min_z_i:
                            story_i = story_names[k]
                            sidx_i = k
                            min_z_i = coord[2]

                # Search for pid_j across all stories from current downward, take lowest Z
                for k in range(sidx, len(story_names)):
                    if _point_exists(pid_j, story_names[k], act_pt_map):
                        coord = act_pt_map.get((pid_j, story_names[k]))
                        if coord and coord[2] < min_z_j:
                            story_j = story_names[k]
                            sidx_j = k
                            min_z_j = coord[2]

                if story_i is None or story_j is None:
                    skips.append(f"{ln.get('name','?')} @ '{sname}' skipped — Method 2 column: could not locate endpoint stories (i:{story_i}, j:{story_j})")
                    continue

                # Create nodes at their respective stories
                node_i = _ensure_node_for(pid_i, story_i, sidx_i, act_pt_map, existing_nodes)
                node_j = _ensure_node_for(pid_j, story_j, sidx_j, act_pt_map, existing_nodes)

                if node_i is None or node_j is None:
                    skips.append(f"{ln.get('name','?')} @ '{sname}' skipped — Method 2 column nodes missing")
                    continue

                # Get coordinates from correct stories
                coord_i = act_pt_map.get((pid_i, story_i), (0.0, 0.0, 0.0))
                coord_j = act_pt_map.get((pid_j, story_j), (0.0, 0.0, 0.0))

                # Determine which is bottom/top based on Z coordinate
                z_i = coord_i[2]
                z_j = coord_j[2]

                # Check for zero-length columns before creating
                dx = coord_i[0] - coord_j[0]
                dy = coord_i[1] - coord_j[1]
                dz = coord_i[2] - coord_j[2]
                length = (dx**2 + dy**2 + dz**2)**0.5

                if length < 1e-6:
                    skips.append(f"{ln.get('name','?')} @ '{sname}' skipped — Method 2 zero length: pt{pid_i}@{story_i}({coord_i[0]:.2f},{coord_i[1]:.2f},{coord_i[2]:.2f}) to pt{pid_j}@{story_j}({coord_j[0]:.2f},{coord_j[1]:.2f},{coord_j[2]:.2f})")
                    continue

                if z_i < z_j:
                    nBot, nTop = node_i, node_j
                    pBot, pTop = coord_i, coord_j
                else:
                    nBot, nTop = node_j, node_i
                    pBot, pTop = coord_j, coord_i

                # Apply orientation preference
                if ENFORCE_COLUMN_I_AT_BOTTOM:
                    nI, nJ = (nBot, nTop)
                    pI, pJ = pBot, pTop
                else:
                    nI, nJ = (nTop, nBot)
                    pI, pJ = pTop, pBot

                line_name = str(ln.get("name", "?"))
                LoffI = float(ln.get("length_off_i", 0.0) or 0.0)
                LoffJ = float(ln.get("length_off_j", 0.0) or 0.0)

            # METHOD 1: Single-point vertical columns (i == j)
            # Point appears at multiple stories, connect to next lower story
            else:
                # Find next lower story where BOTH points exist
                k_found: Optional[int] = None
                sK: Optional[str] = None
                for k in range(sidx + 1, len(story_names)):
                    sK_candidate = story_names[k]
                    if _point_exists(pid_i, sK_candidate, act_pt_map) and _point_exists(pid_j, sK_candidate, act_pt_map):
                        k_found = k
                        sK = sK_candidate
                        break
                if k_found is None or sK is None:
                    skips.append(f"{ln.get('name','?')} @ '{sname}' skipped — Method 1 column: no lower story with both endpoints")
                    continue

                # Build (nTop, nBot) and their coords
                nTop = _ensure_node_for(pid_i, sname, sidx, act_pt_map, existing_nodes)   # upper
                nBot = _ensure_node_for(pid_j, sK, k_found, act_pt_map, existing_nodes)   # lower
                if nTop is None or nBot is None:
                    skips.append(f"{ln.get('name','?')} @ '{sname}' skipped — Method 1 column: endpoint nodes missing")
                    continue

                # Orientation enforcement (i=bottom, j=top) if requested
                line_name = str(ln.get("name", "?"))
                LoffI = float(ln.get("length_off_i", 0.0) or 0.0)  # preserved for artifact
                LoffJ = float(ln.get("length_off_j", 0.0) or 0.0)  # preserved for artifact

                # Get coordinates for joint offset calculation (before orientation change)
                pBot = act_pt_map.get((pid_j, sK), (0.0, 0.0, 0.0))  # bottom node coords
                pTop = act_pt_map.get((pid_i, sname), (0.0, 0.0, 0.0))  # top node coords

                if not ENFORCE_COLUMN_I_AT_BOTTOM:
                    # Keep ETABS i->j direction (i at S (top), j at K (bottom)):
                    nI, nJ = (nTop, nBot)
                    pI, pJ = pTop, pBot  # coordinates follow node order
                else:
                    # Use bottom->top orientation
                    nI, nJ = (nBot, nTop)
                    pI, pJ = pBot, pTop  # coordinates follow node order

            # Extract offsets from line assigns (columns may have offsets per modeling convention)
            offsets_i = ln.get("offsets_i")
            offsets_j = ln.get("offsets_j")

            # Calculate joint offsets for geomTransf
            dI, dJ = _calculate_joint_offsets(
                pI, pJ, LoffI, LoffJ, offsets_i, offsets_j
            )

            # Get section-specific properties from ETABS data
            section_name = str(ln.get("section", ""))
            props = _get_column_section_properties(section_name, _raw)

            A_col = props["A"]
            E_col = props["E"]
            G_col = props["G"]
            J_col = props["J"]
            Iy_col = props["Iy"]
            Iz_col = props["Iz"]

            # Create single element connecting directly between grid nodes
            etag = element_tag("COLUMN", line_name, int(sidx))
            transf_tag = 1100000000 + etag

            # Apply joint offsets if any non-zero offsets exist
            if any(abs(x) > 1e-12 for x in (*dI, *dJ)):
                ops.geomTransf('Linear', transf_tag, 1, 0, 0, '-jntOffset',
                              dI[0], dI[1], dI[2], dJ[0], dJ[1], dJ[2])
            else:
                ops.geomTransf('Linear', transf_tag, 1, 0, 0)  # no offsets

            ops.element('elasticBeamColumn', etag, nI, nJ, A_col, E_col, G_col, J_col, Iy_col, Iz_col, transf_tag)
            created.append(etag)

            emitted.append({
                "tag": etag,
                "line": line_name,
                "story": sname,
                "i_node": nI,
                "j_node": nJ,
                "section": section_name,
                "transf_tag": transf_tag,
                "A": A_col, "E": E_col, "G": G_col, "J": J_col, "Iy": Iy_col, "Iz": Iz_col,
                "length_off_i": LoffI, "length_off_j": LoffJ,
                "offsets_i": offsets_i, "offsets_j": offsets_j,  # lateral offsets from ETABS
                "joint_offset_i": list(dI), "joint_offset_j": list(dJ),  # calculated joint offsets
                "has_joint_offsets": any(abs(x) > 1e-12 for x in (*dI, *dJ))  # flag for verification
            })

    if skips:
        print("[columns] Skips:")
        for s in skips:
            print(" -", s)
    print(f"[columns] Created {len(created)} column elements.")

    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(os.path.join(OUT_DIR, "columns.json"), "w", encoding="utf-8") as f:
            json.dump({"columns": emitted, "counts": {"created": len(created)}, "skips": skips}, f, indent=2)
        print(f"[columns] Wrote {OUT_DIR}/columns.json")
    except Exception as e:
        print(f"[columns] WARN: failed to write columns.json: {e}")

    return created
