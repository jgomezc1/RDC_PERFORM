"""
Phase 1: Robust parser for ETABS .e2k essentials.

Extracts:
- STORIES (top->bottom listing; we will compute absolute elevations later)
- POINT COORDINATES
- POINT ASSIGNS  (now recognizes DIAPH and DIAPHRAGM)
- LINE CONNECTIVITIES
- LINE ASSIGNS
  * section/frameprop
  * longitudinal rigid ends: LENGTHOFFI, LENGTHOFFJ
  * nodal offsets: OFFSETXI, OFFSETYI, OFFSETZI, OFFSETXJ, OFFSETYJ, OFFSETZJ
- DIAPHRAGM NAMES

Notes
-----
ETABS examples observed in the wild:
    POINTASSIGN "56" "01_P2_m170" DIAPH "D1"
Some exports use DIAPHRAGM instead of DIAPH. We accept BOTH and normalize to
the unified key 'diaphragm' in the output.

For $ LINE ASSIGNS we now parse both:
  - QUOTED tokens:  SECTION/SECT/FRAMEPROP, PIER, SPANDREL, LOCALAXIS, RELEASE
  - NUMERIC (unquoted) tokens: LENGTHOFFI/J, OFFSETS I/J for X/Y/Z
"""
from __future__ import annotations
import re
from typing import Dict, Any, List, Optional


def _extract_section(text: str, title_regex: str) -> str:
    """
    Return the text between a section header matching title_regex and the next
    section header, or the end of file if none.
    """
    m = re.search(title_regex + r'[^\n]*\n', text, flags=re.IGNORECASE | re.MULTILINE)
    if not m:
        return ""
    start = m.end()
    n = re.search(r'^\s*\$[^\n]*\n', text[start:], flags=re.MULTILINE)
    end = start + n.start() if n else len(text)
    return text[start:end]


def _to_float_or_none(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_float_or_default(s: Optional[str], default: float = 0.0) -> float:
    """Convert string to float with default fallback."""
    if s is None:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _parse_materials(text: str) -> Dict[str, Any]:
    """
    Parse MATERIAL PROPERTIES section.

    Returns
    -------
    {
      "steel": {"STEEL": {"type": "Steel", "E": 2.039e10, "fy": 3.515e7, ...}},
      "concrete": {"CONC": {"type": "Concrete", "fc": 2812279, ...}},
      "properties": {"STEEL": {...}, "CONC": {...}}  # All materials by name
    }
    """
    materials_txt = _extract_section(text, r'^\s*\$ MATERIAL PROPERTIES')
    if not materials_txt.strip():
        return {"steel": {}, "concrete": {}, "properties": {}}

    material_lines = [ln for ln in materials_txt.splitlines() if ln.strip() and not ln.strip().startswith('$')]

    # Pattern to match MATERIAL lines with various property types
    material_pat = re.compile(
        r'^\s*MATERIAL\s+"([^"]+)"\s+(.+)$',
        re.IGNORECASE
    )

    materials_data: Dict[str, Dict[str, Any]] = {}

    for ln in material_lines:
        m = material_pat.match(ln)
        if not m:
            continue

        mat_name = m.group(1)
        props_str = m.group(2)

        # Initialize material if not exists
        if mat_name not in materials_data:
            materials_data[mat_name] = {"name": mat_name}

        # Parse different property types
        if "TYPE" in props_str:
            # Basic type definition: TYPE "Steel" WEIGHTPERVOLUME 7833.414
            type_match = re.search(r'TYPE\s+"([^"]+)"', props_str, re.IGNORECASE)
            if type_match:
                materials_data[mat_name]["type"] = type_match.group(1)

            weight_match = re.search(r'WEIGHTPERVOLUME\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
            if weight_match:
                materials_data[mat_name]["weight_per_volume"] = _to_float_or_default(weight_match.group(1))

        elif "SYMTYPE" in props_str:
            # Mechanical properties: SYMTYPE "Isotropic" E 2.039E+10 U 0.3 A 1.17E-05
            symtype_match = re.search(r'SYMTYPE\s+"([^"]+)"', props_str, re.IGNORECASE)
            if symtype_match:
                materials_data[mat_name]["symtype"] = symtype_match.group(1)

            # Extract E, U, A values
            e_match = re.search(r'\bE\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
            if e_match:
                materials_data[mat_name]["E"] = _to_float_or_default(e_match.group(1))

            u_match = re.search(r'\bU\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
            if u_match:
                materials_data[mat_name]["poisson"] = _to_float_or_default(u_match.group(1))

            a_match = re.search(r'\bA\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
            if a_match:
                materials_data[mat_name]["thermal_coeff"] = _to_float_or_default(a_match.group(1))

        elif "FY" in props_str:
            # Steel strength properties: FY 3.515E+07 FU 4.570E+07 FYE 3.867E+07 FUE 5.027E+07
            fy_match = re.search(r'FY\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
            if fy_match:
                materials_data[mat_name]["fy"] = _to_float_or_default(fy_match.group(1))

            fu_match = re.search(r'FU\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
            if fu_match:
                materials_data[mat_name]["fu"] = _to_float_or_default(fu_match.group(1))

            fye_match = re.search(r'FYE\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
            if fye_match:
                materials_data[mat_name]["fye"] = _to_float_or_default(fye_match.group(1))

            fue_match = re.search(r'FUE\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
            if fue_match:
                materials_data[mat_name]["fue"] = _to_float_or_default(fue_match.group(1))

        elif "FC" in props_str:
            # Concrete strength: FC 2812279
            fc_match = re.search(r'FC\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
            if fc_match:
                materials_data[mat_name]["fc"] = _to_float_or_default(fc_match.group(1))

        elif "HYSTYPE" in props_str:
            # Hysteretic behavior properties
            hystype_match = re.search(r'HYSTYPE\s+"([^"]+)"', props_str, re.IGNORECASE)
            if hystype_match:
                materials_data[mat_name]["hystype"] = hystype_match.group(1)

    # Categorize materials by type
    steel_materials = {}
    concrete_materials = {}

    for mat_name, props in materials_data.items():
        mat_type = props.get("type", "").lower()
        if "steel" in mat_type:
            steel_materials[mat_name] = props
        elif "concrete" in mat_type:
            concrete_materials[mat_name] = props

    return {
        "steel": steel_materials,
        "concrete": concrete_materials,
        "properties": materials_data
    }


def _parse_rebar_definitions(text: str) -> Dict[str, Any]:
    """
    Parse REBAR DEFINITIONS section.

    Returns
    -------
    {
      "#4": {"area": 0.000129032, "diameter": 0.0127},
      "#5": {"area": 0.0001999996, "diameter": 0.015875},
      ...
    }
    """
    rebar_txt = _extract_section(text, r'^\s*\$ REBAR DEFINITIONS')
    if not rebar_txt.strip():
        return {}

    rebar_lines = [ln for ln in rebar_txt.splitlines() if ln.strip() and not ln.strip().startswith('$')]

    # Pattern: REBARDEFINITION "#4" AREA 0.000129032 DIA 0.0127
    rebar_pat = re.compile(
        r'^\s*REBARDEFINITION\s+"([^"]+)"\s+AREA\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s+DIA\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)',
        re.IGNORECASE
    )

    rebar_data = {}

    for ln in rebar_lines:
        m = rebar_pat.match(ln)
        if m:
            rebar_name = m.group(1)
            area = _to_float_or_default(m.group(2))
            diameter = _to_float_or_default(m.group(3))

            rebar_data[rebar_name] = {
                "area": area,
                "diameter": diameter
            }

    return rebar_data


def _parse_frame_sections(text: str) -> Dict[str, Any]:
    """
    Parse FRAME SECTIONS section.

    Returns
    -------
    {
      "C50x80C": {
        "material": "H350",
        "shape": "Concrete Rectangular",
        "dimensions": {"D": 0.5, "B": 0.8},
        "properties": {"JMOD": 0.1, ...}
      },
      ...
    }
    """
    sections_txt = _extract_section(text, r'^\s*\$ FRAME SECTIONS')
    if not sections_txt.strip():
        return {}

    section_lines = [ln for ln in sections_txt.splitlines() if ln.strip() and not ln.strip().startswith('$')]

    # Pattern: FRAMESECTION "C50x80C" MATERIAL "H350" SHAPE "Concrete Rectangular" D 0.5 B 0.8 NOTIONALUSERVALUE 0.1
    section_pat = re.compile(
        r'^\s*FRAMESECTION\s+"([^"]+)"\s+(.+)$',
        re.IGNORECASE
    )

    sections_data = {}

    for ln in section_lines:
        m = section_pat.match(ln)
        if not m:
            continue

        section_name = m.group(1)
        props_str = m.group(2)

        # Initialize or update section
        if section_name not in sections_data:
            sections_data[section_name] = {"name": section_name, "dimensions": {}, "properties": {}}

        section = sections_data[section_name]

        # Parse MATERIAL
        material_match = re.search(r'MATERIAL\s+"([^"]+)"', props_str, re.IGNORECASE)
        if material_match:
            section["material"] = material_match.group(1)

        # Parse SHAPE
        shape_match = re.search(r'SHAPE\s+"([^"]+)"', props_str, re.IGNORECASE)
        if shape_match:
            section["shape"] = shape_match.group(1)

        # Parse dimensions (D, B for rectangular; D for circular)
        d_match = re.search(r'\bD\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
        if d_match:
            section["dimensions"]["D"] = _to_float_or_default(d_match.group(1))

        b_match = re.search(r'\bB\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
        if b_match:
            section["dimensions"]["B"] = _to_float_or_default(b_match.group(1))

        # Parse additional properties
        jmod_match = re.search(r'JMOD\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
        if jmod_match:
            section["properties"]["JMOD"] = _to_float_or_default(jmod_match.group(1))

        notional_match = re.search(r'NOTIONALUSERVALUE\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
        if notional_match:
            section["properties"]["NOTIONALUSERVALUE"] = _to_float_or_default(notional_match.group(1))

    return sections_data


def _parse_spring_properties(text: str) -> Dict[str, Any]:
    """
    Parse POINT SPRING PROPERTIES section.

    Returns
    -------
    {
      "RES_00_75cm": {
        "name": "RES_00_75cm",
        "ux": 316500,
        "uy": 316500,
        "uz": 0,
        "rx": 0,
        "ry": 0,
        "rz": 0
      },
      ...
    }
    """
    springs_txt = _extract_section(text, r'^\s*\$ POINT SPRING PROPERTIES')
    if not springs_txt.strip():
        return {}

    spring_lines = [ln for ln in springs_txt.splitlines() if ln.strip() and not ln.strip().startswith('$')]

    # Pattern: POINTSPRING "RES_00_75cm" STIFFNESSOPTION "USERDEFINED" UX 316500 UY 316500 UZ 0
    spring_pat = re.compile(
        r'^\s*POINTSPRING\s+"([^"]+)"\s+(.+)$',
        re.IGNORECASE
    )

    springs_data = {}

    for ln in spring_lines:
        m = spring_pat.match(ln)
        if not m:
            continue

        spring_name = m.group(1)
        props_str = m.group(2)

        # Initialize spring with default zero stiffnesses
        if spring_name not in springs_data:
            springs_data[spring_name] = {
                "name": spring_name,
                "ux": 0.0,
                "uy": 0.0,
                "uz": 0.0,
                "rx": 0.0,
                "ry": 0.0,
                "rz": 0.0
            }

        spring = springs_data[spring_name]

        # Parse translational stiffnesses
        ux_match = re.search(r'\bUX\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
        if ux_match:
            spring["ux"] = _to_float_or_default(ux_match.group(1))

        uy_match = re.search(r'\bUY\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
        if uy_match:
            spring["uy"] = _to_float_or_default(uy_match.group(1))

        uz_match = re.search(r'\bUZ\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
        if uz_match:
            spring["uz"] = _to_float_or_default(uz_match.group(1))

        # Parse rotational stiffnesses
        rx_match = re.search(r'\bRX\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
        if rx_match:
            spring["rx"] = _to_float_or_default(rx_match.group(1))

        ry_match = re.search(r'\bRY\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
        if ry_match:
            spring["ry"] = _to_float_or_default(ry_match.group(1))

        rz_match = re.search(r'\bRZ\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', props_str, re.IGNORECASE)
        if rz_match:
            spring["rz"] = _to_float_or_default(rz_match.group(1))

    return springs_data


def parse_e2k(text: str) -> Dict[str, Any]:
    """
    Parse ETABS .e2k text into a normalized dict used by Phase-1.

    Returns
    -------
    {
      "stories":        [ { "name", "height", "elev", "similar_to", "masterstory" }, ... ],
      "points":         { pid: { "x", "y", "third", "has_three" }, ... },
      "point_assigns":  [ { "point", "story", "diaphragm", "springprop", "extra" }, ... ],
      "lines":          { lname: { "name", "kind", "i", "j" }, ... },
      "line_assigns":   [
                          {
                            "line", "story", "section",
                            "length_off_i", "length_off_j",
                            "offsets_i": {"x","y","z"}, "offsets_j": {"x","y","z"},
                            "extra"
                          }, ...
                        ],
      "diaphragm_names":[ "D1", "D2", ... ],
      "spring_properties": { "RES_00_75cm": { "name", "ux", "uy", "uz", "rx", "ry", "rz" }, ... }
    }
    """
    # STORIES
    stories_txt = _extract_section(text, r'^\s*\$ STORIES')
    story_lines = [ln for ln in stories_txt.splitlines() if ln.strip()]
    story_pat = re.compile(
        r'^\s*STORY\s+"([^"]+)"'                     # name
        r'(?:\s+HEIGHT\s+([-+]?\d+(?:\.\d+)?))?'     # height
        r'(?:\s+ELEV\s+([-+]?\d+(?:\.\d+)?))?'       # explicit elev
        r'(?:\s+SIMILARTO\s+"([^"]+)")?'             # similar_to
        r'(?:\s+MASTERSTORY\s+"([^"]+)")?',          # masterstory
        re.IGNORECASE
    )
    stories: List[Dict[str, Any]] = []
    for ln in story_lines:
        m = story_pat.match(ln)
        if m:
            stories.append({
                "name": m.group(1),
                "height": _to_float_or_none(m.group(2)),
                "elev": _to_float_or_none(m.group(3)),
                "similar_to": m.group(4),
                "masterstory": m.group(5),
            })

    # POINT COORDINATES
    pt_txt = _extract_section(text, r'^\s*\$ POINT COORDINATES')
    pt_lines = [ln for ln in pt_txt.splitlines() if ln.strip()]
    pt_pat = re.compile(
        r'^\s*POINT\s+"([^"]+)"\s+([-+]?\d+(?:\.\d+)?)\s+([-+]?\d+(?:\.\d+)?)(?:\s+([-+]?\d+(?:\.\d+)?))?',
        re.IGNORECASE
    )
    points: Dict[str, Dict[str, Any]] = {}
    for ln in pt_lines:
        m = pt_pat.match(ln)
        if not m:
            continue
        pid = m.group(1)
        points[pid] = {
            "x": float(m.group(2)),
            "y": float(m.group(3)),
            "third": _to_float_or_none(m.group(4)),
            "has_three": m.group(4) is not None,
        }

    # POINT ASSIGNS  (recognize DIAPH and DIAPHRAGM)
    pa_txt = _extract_section(text, r'^\s*\$ POINT ASSIGNS')
    pa_lines = [ln for ln in pa_txt.splitlines() if ln.strip()]
    pa_head = re.compile(r'^\s*POINTASSIGN\s+"([^"]+)"\s+"([^"]+)"(.*)$', re.IGNORECASE)
    # Tokens of the form: TOKEN "value"
    token = re.compile(
        r'\b('
        r'DIAPHRAGM|DIAPH|'         # diaphragm synonyms
        r'SPRINGPROP|POINTMASS|RESTRAINT|FRAMEPROP|JOINTPATTERN|SPCONSTRAINT'
        r')\b\s+"([^"]+)"',
        re.IGNORECASE
    )
    point_assigns: List[Dict[str, Any]] = []
    for ln in pa_lines:
        m = pa_head.match(ln)
        if not m:
            continue
        pid, story, tail = m.group(1), m.group(2), m.group(3) or ""
        # Build a dict of tokens; if duplicates appear, the last one wins
        found: Dict[str, str] = {}
        for k, v in token.findall(tail):
            found[k.upper()] = v
        diaphragm = found.get("DIAPHRAGM") or found.get("DIAPH")  # normalize
        point_assigns.append({
            "point": pid,
            "story": story,
            "diaphragm": diaphragm,
            "springprop": found.get("SPRINGPROP"),
            "extra": {k: v for k, v in found.items() if k not in ("DIAPHRAGM", "DIAPH", "SPRINGPROP")},
        })

    # LINE CONNECTIVITIES
    lc_txt = _extract_section(text, r'^\s*\$ LINE CONNECTIVITIES')
    lc_lines = [ln for ln in lc_txt.splitlines() if ln.strip()]
    lc_pat = re.compile(r'^\s*LINE\s+"([^"]+)"\s+([A-Z]+)\s+"([^"]+)"\s+"([^"]+)"', re.IGNORECASE)
    lines: Dict[str, Dict[str, Any]] = {}
    for ln in lc_lines:
        m = lc_pat.match(ln)
        if not m:
            continue
        lines[m.group(1)] = {
            "name": m.group(1),
            "kind": m.group(2).upper(),
            "i": m.group(3),
            "j": m.group(4),
        }

    # LINE ASSIGNS
    la_txt = _extract_section(text, r'^\s*\$ LINE ASSIGNS')
    la_lines = [ln for ln in la_txt.splitlines() if ln.strip()]

    # Header: LINEASSIGN "<line>" "<story>" <tail>
    la_head = re.compile(r'^\s*LINEASSIGN\s+"([^"]+)"\s+"([^"]+)"(.*)$', re.IGNORECASE)

    # (A) QUOTED tokens: TOKEN "value"
    la_token_quoted = re.compile(
        r'\b(SECTION|SECT|FRAMEPROP|PIER|SPANDREL|LOCALAXIS|RELEASE)\b\s+"([^"]+)"',
        re.IGNORECASE
    )

    # (B) NUMERIC (unquoted) tokens: TOKEN number
    #   - LENGTHOFFI, LENGTHOFFJ
    #   - OFFSETXI, OFFSETYI, OFFSETZI, OFFSETXJ, OFFSETYJ, OFFSETZJ
    la_token_numeric = re.compile(
        r'\b('
        r'LENGTHOFFI|LENGTHOFFJ|'
        r'OFFSETXI|OFFSETYI|OFFSETZI|'
        r'OFFSETXJ|OFFSETYJ|OFFSETZJ'
        r')\b\s+([-+]?\d+(?:\.\d+)?)',
        re.IGNORECASE
    )

    # Use dictionary to consolidate multiple LINEASSIGN entries per (line, story) pair
    line_assigns_map: Dict[tuple, Dict[str, Any]] = {}

    for ln in la_lines:
        m = la_head.match(ln)
        if not m:
            continue
        lname, story, tail = m.group(1), m.group(2), m.group(3) or ""
        key = (lname, story)

        # Collect quoted tokens
        found_str: Dict[str, str] = {k.upper(): v for k, v in la_token_quoted.findall(tail)}
        section = found_str.get("SECTION") or found_str.get("SECT") or found_str.get("FRAMEPROP")

        # Collect numeric tokens
        found_num: Dict[str, float] = {}
        for k, v in la_token_numeric.findall(tail):
            found_num[k.upper()] = float(v)

        # Get or create entry for this (line, story) pair
        if key not in line_assigns_map:
            line_assigns_map[key] = {
                "line": lname,
                "story": story,
            }

        entry = line_assigns_map[key]

        # Update section (from first entry that has it)
        if section and not entry.get("section"):
            entry["section"] = section

        # Update rigid end offsets
        length_off_i = found_num.get("LENGTHOFFI")
        length_off_j = found_num.get("LENGTHOFFJ")
        if length_off_i is not None:
            entry["length_off_i"] = length_off_i
        if length_off_j is not None:
            entry["length_off_j"] = length_off_j

        # Update nodal offsets
        offsets_i = {
            "x": found_num.get("OFFSETXI"),
            "y": found_num.get("OFFSETYI"),
            "z": found_num.get("OFFSETZI"),
        }
        offsets_i = {k: v for k, v in offsets_i.items() if v is not None}
        if offsets_i:
            entry["offsets_i"] = offsets_i

        offsets_j = {
            "x": found_num.get("OFFSETXJ"),
            "y": found_num.get("OFFSETYJ"),
            "z": found_num.get("OFFSETZJ"),
        }
        offsets_j = {k: v for k, v in offsets_j.items() if v is not None}
        if offsets_j:
            entry["offsets_j"] = offsets_j

        # Preserve extras for any future tokens (quoted + numeric)
        # Merge extra properties from all entries for this line
        if "extra" not in entry:
            entry["extra"] = {}
        extra: Dict[str, Any] = {}
        extra.update(found_str)
        extra.update(found_num)
        entry["extra"].update(extra)

    # Convert consolidated map back to list
    line_assigns: List[Dict[str, Any]] = []
    for entry in line_assigns_map.values():
        # Clean up empty extra dict
        if entry.get("extra") and not entry["extra"]:
            del entry["extra"]
        line_assigns.append(entry)

    # DIAPHRAGM NAMES
    dn_txt = _extract_section(text, r'^\s*\$ DIAPHRAGM NAMES')
    dn_lines = [ln for ln in dn_txt.splitlines() if ln.strip()]
    dn_pat = re.compile(r'^\s*DIAPHRAGM\s+"([^"]+)"', re.IGNORECASE)
    diaphragm_names: List[str] = []
    for ln in dn_lines:
        m = dn_pat.match(ln)
        if m:
            diaphragm_names.append(m.group(1))

    # MATERIAL PROPERTIES (New in v2.0)
    materials = _parse_materials(text)

    # REBAR DEFINITIONS (New in v2.0)
    rebar_definitions = _parse_rebar_definitions(text)

    # FRAME SECTIONS (New in v2.0)
    frame_sections = _parse_frame_sections(text)

    # SPRING PROPERTIES (New in v2.1)
    spring_properties = _parse_spring_properties(text)

    return {
        "stories": stories,
        "points": points,
        "point_assigns": point_assigns,
        "lines": lines,
        "line_assigns": line_assigns,
        "diaphragm_names": diaphragm_names,
        "materials": materials,
        "rebar_definitions": rebar_definitions,
        "frame_sections": frame_sections,
        "spring_properties": spring_properties,
        "_artifacts_version": "2.1",
        "_materials_version": "1.0",
        "_sections_version": "1.0",
        "_springs_version": "1.0",
    }


def validate_materials(materials: Dict[str, Any]) -> List[str]:
    """Validate material properties completeness and consistency"""
    problems = []

    steel = materials.get("steel", {})
    concrete = materials.get("concrete", {})
    properties = materials.get("properties", {})

    # Check for essential steel properties
    for name, props in properties.items():
        if props.get("type") in ["Steel", "Kinematic"]:
            if not props.get("fy"):
                problems.append(f"Steel material '{name}' missing yield strength (fy)")
            if not props.get("fu"):
                problems.append(f"Steel material '{name}' missing ultimate strength (fu)")

    # Check for essential concrete properties
    for name, props in concrete.items():
        if not props.get("fc"):
            problems.append(f"Concrete material '{name}' missing compressive strength (fc)")
        if not props.get("weight_per_volume"):
            problems.append(f"Concrete material '{name}' missing weight per volume")

    return problems


def validate_sections(frame_sections: Dict[str, Any], materials: Dict[str, Any]) -> List[str]:
    """Validate frame sections and their material references"""
    problems = []

    all_materials = set(materials.get("properties", {}).keys())

    for section_name, section_data in frame_sections.items():
        material = section_data.get("material")
        if material and material not in all_materials:
            problems.append(f"Frame section '{section_name}' references unknown material '{material}'")

        shape = section_data.get("shape")
        if not shape:
            problems.append(f"Frame section '{section_name}' missing shape definition")

        dimensions = section_data.get("dimensions", {})
        if not dimensions:
            problems.append(f"Frame section '{section_name}' missing dimensions")

    return problems


def validate_rebar_definitions(rebar_definitions: Dict[str, Any]) -> List[str]:
    """Validate rebar definitions completeness"""
    problems = []

    for rebar_name, props in rebar_definitions.items():
        if not props.get("area"):
            problems.append(f"Rebar '{rebar_name}' missing area")
        if not props.get("diameter"):
            problems.append(f"Rebar '{rebar_name}' missing diameter")

        # Check area/diameter consistency (rough check)
        area = props.get("area", 0)
        diameter = props.get("diameter", 0)
        if area > 0 and diameter > 0:
            calculated_area = 3.14159 * (diameter / 2) ** 2
            if abs(area - calculated_area) / calculated_area > 0.1:  # 10% tolerance
                problems.append(f"Rebar '{rebar_name}' area/diameter inconsistency")

    return problems


def validate_artifacts_compatibility(version: str) -> bool:
    """Check if artifact version is supported"""
    supported_versions = ["1.0", "1.1", "2.0"]
    return version in supported_versions


def validate_expanded_artifacts(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Comprehensive validation of expanded e2k artifacts"""
    validation_report = {
        "valid": True,
        "problems": [],
        "warnings": [],
        "version_info": {
            "artifacts": parsed_data.get("_artifacts_version"),
            "materials": parsed_data.get("_materials_version"),
            "sections": parsed_data.get("_sections_version"),
        }
    }

    # Version compatibility
    artifacts_version = parsed_data.get("_artifacts_version", "1.0")
    if not validate_artifacts_compatibility(artifacts_version):
        validation_report["problems"].append(f"Unsupported artifacts version: {artifacts_version}")
        validation_report["valid"] = False

    # Material validation
    materials = parsed_data.get("materials", {})
    if materials:
        material_problems = validate_materials(materials)
        validation_report["problems"].extend(material_problems)

    # Section validation
    frame_sections = parsed_data.get("frame_sections", {})
    if frame_sections:
        section_problems = validate_sections(frame_sections, materials)
        validation_report["problems"].extend(section_problems)

    # Rebar validation
    rebar_definitions = parsed_data.get("rebar_definitions", {})
    if rebar_definitions:
        rebar_problems = validate_rebar_definitions(rebar_definitions)
        validation_report["problems"].extend(rebar_problems)

    # Legacy section counts (warnings for empty sections)
    stories = parsed_data.get("stories", [])
    points = parsed_data.get("points", {})
    lines = parsed_data.get("lines", {})

    if not stories:
        validation_report["warnings"].append("No stories found - verify STORIES section exists")
    if not points:
        validation_report["warnings"].append("No points found - verify POINT COORDINATES section exists")
    if not lines:
        validation_report["warnings"].append("No lines found - verify LINE CONNECTIVITIES section exists")

    # Final validation status
    if validation_report["problems"]:
        validation_report["valid"] = False

    return validation_report
