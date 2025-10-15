# -*- coding: utf-8 -*-
"""
release_utils.py

Utility functions for parsing and handling ETABS end releases in OpenSees.

ETABS Release Notation:
-----------------------
Release strings like "M2J M3J" or "TI M2I M3I" specify which DOFs are released at member ends.

Format: "[DOF][I|J] [DOF][I|J] ..."

DOF Types:
- TI/TJ   : Torsion (local-1 axis, axial rotation)
- V2I/V2J : Shear force along local-2 axis
- V3I/V3J : Shear force along local-3 axis
- M2I/M2J : Moment about local-2 axis
- M3I/M3J : Moment about local-3 axis
- FI/FJ   : Axial force (local-1 axis)

End Suffix:
- I : Release at I-end (start node)
- J : Release at J-end (end node)

OpenSees Release Codes:
-----------------------
OpenSees element command uses: element(..., '-release', relI, relJ)

Release codes:
- 0 : No release (fully fixed)
- 1 : Moment release about local-3 axis (M3)
- 2 : Moment release about local-2 axis (M2)
- 3 : Both moment releases (M2 + M3) - creates a pin
- 4 : M3 + axial force (F)
- 5 : M2 + axial force (F)
- 6 : M2 + M3 + axial force (F) - full release

Note: OpenSees doesn't directly support torsion (T) or shear (V2, V3) releases
in standard frame elements. These require special handling or zero-length elements.

Examples:
---------
ETABS → OpenSees
"M2J M3J"       → relI=0, relJ=3  (pin at J-end)
"M2I M3I"       → relI=3, relJ=0  (pin at I-end)
"M3J"           → relI=0, relJ=1  (partial release at J)
"TI M2I M3I"    → relI=3, relJ=0  (pin + warning about torsion)
"FI M2I M3I"    → relI=6, relJ=0  (full release at I)
"""
from __future__ import annotations
from typing import Tuple, List, Dict, Any
import re


def parse_etabs_release(release_string: str) -> Tuple[int, int, Dict[str, Any]]:
    """
    Parse ETABS release string into OpenSees release codes.

    Parameters
    ----------
    release_string : str
        ETABS release string like "M2J M3J" or "TI M2I M3I"

    Returns
    -------
    tuple
        (relI, relJ, metadata)
        - relI : int, release code for I-end (0-6)
        - relJ : int, release code for J-end (0-6)
        - metadata : dict with parsing details and warnings

    Examples
    --------
    >>> parse_etabs_release("M2J M3J")
    (0, 3, {...})  # Pin at J-end

    >>> parse_etabs_release("M2I M3I")
    (3, 0, {...})  # Pin at I-end

    >>> parse_etabs_release("M3J")
    (0, 1, {...})  # M3 release at J-end
    """
    # Initialize
    relI = 0
    relJ = 0
    metadata = {
        "original": release_string,
        "warnings": [],
        "i_releases": [],
        "j_releases": []
    }

    if not release_string or not isinstance(release_string, str):
        return relI, relJ, metadata

    # Parse release tokens
    # Pattern: optional DOF type (T, F, V2, V3, M2, M3) + end (I or J)
    # Examples: "M2J", "TI", "V3J", "FI"
    release_pattern = re.compile(r'\b([TFV]?\d?[MV]?\d?)([IJ])\b', re.IGNORECASE)
    tokens = release_pattern.findall(release_string.upper())

    # Track which DOFs are released at each end
    i_dofs = set()
    j_dofs = set()

    for dof_type, end in tokens:
        # Normalize DOF type
        dof_type = dof_type.upper()

        # Categorize DOF
        is_moment_2 = dof_type in ("M2", "2")
        is_moment_3 = dof_type in ("M3", "3")
        is_torsion = dof_type in ("T", "TI", "TJ")[:1]  # Just "T"
        is_axial = dof_type in ("F", "FI", "FJ")[:1]    # Just "F"
        is_shear_2 = dof_type in ("V2",)
        is_shear_3 = dof_type in ("V3",)

        # Add to appropriate end
        if end == "I":
            metadata["i_releases"].append(dof_type)
            if is_moment_2:
                i_dofs.add("M2")
            elif is_moment_3:
                i_dofs.add("M3")
            elif is_axial:
                i_dofs.add("F")
            elif is_torsion:
                i_dofs.add("T")
                metadata["warnings"].append(
                    "Torsion release (TI) not directly supported in OpenSees frame elements"
                )
            elif is_shear_2:
                i_dofs.add("V2")
                metadata["warnings"].append(
                    "Shear release (V2I) not directly supported in OpenSees frame elements"
                )
            elif is_shear_3:
                i_dofs.add("V3")
                metadata["warnings"].append(
                    "Shear release (V3I) not directly supported in OpenSees frame elements"
                )
        else:  # end == "J"
            metadata["j_releases"].append(dof_type)
            if is_moment_2:
                j_dofs.add("M2")
            elif is_moment_3:
                j_dofs.add("M3")
            elif is_axial:
                j_dofs.add("F")
            elif is_torsion:
                j_dofs.add("T")
                metadata["warnings"].append(
                    "Torsion release (TJ) not directly supported in OpenSees frame elements"
                )
            elif is_shear_2:
                j_dofs.add("V2")
                metadata["warnings"].append(
                    "Shear release (V2J) not directly supported in OpenSees frame elements"
                )
            elif is_shear_3:
                j_dofs.add("V3")
                metadata["warnings"].append(
                    "Shear release (V3J) not directly supported in OpenSees frame elements"
                )

    # Convert to OpenSees codes
    relI = _dof_set_to_release_code(i_dofs)
    relJ = _dof_set_to_release_code(j_dofs)

    metadata["relI"] = relI
    metadata["relJ"] = relJ

    return relI, relJ, metadata


def _dof_set_to_release_code(dofs: set) -> int:
    """
    Convert set of released DOFs to OpenSees release code.

    OpenSees codes:
    - 0: No release
    - 1: M3 only
    - 2: M2 only
    - 3: M2 + M3 (pin)
    - 4: M3 + F
    - 5: M2 + F
    - 6: M2 + M3 + F (full release)

    Parameters
    ----------
    dofs : set
        Set of DOF strings like {"M2", "M3", "F"}

    Returns
    -------
    int
        OpenSees release code (0-6)
    """
    has_m2 = "M2" in dofs
    has_m3 = "M3" in dofs
    has_f = "F" in dofs

    # Build code based on combination
    if not has_m2 and not has_m3 and not has_f:
        return 0  # No release
    elif has_m2 and has_m3 and has_f:
        return 6  # Full release
    elif has_m2 and has_f:
        return 5  # M2 + F
    elif has_m3 and has_f:
        return 4  # M3 + F
    elif has_m2 and has_m3:
        return 3  # Pin (both moments)
    elif has_m2:
        return 2  # M2 only
    elif has_m3:
        return 1  # M3 only
    else:
        return 0  # Fallback


def release_code_to_description(code: int) -> str:
    """
    Convert OpenSees release code to human-readable description.

    Parameters
    ----------
    code : int
        OpenSees release code (0-6)

    Returns
    -------
    str
        Description of the release condition
    """
    descriptions = {
        0: "Fixed (no release)",
        1: "M3 released",
        2: "M2 released",
        3: "Pin (M2+M3 released)",
        4: "M3+F released",
        5: "M2+F released",
        6: "Full release (M2+M3+F)"
    }
    return descriptions.get(code, f"Unknown code {code}")


def validate_release_string(release_string: str) -> Dict[str, Any]:
    """
    Validate an ETABS release string and return detailed information.

    Parameters
    ----------
    release_string : str
        ETABS release string to validate

    Returns
    -------
    dict
        Validation results with keys:
        - valid: bool
        - relI, relJ: int
        - warnings: List[str]
        - unsupported_features: List[str]
    """
    relI, relJ, metadata = parse_etabs_release(release_string)

    # Check for unsupported features
    unsupported = []
    for warning in metadata.get("warnings", []):
        if "not directly supported" in warning:
            unsupported.append(warning)

    return {
        "valid": True,
        "relI": relI,
        "relJ": relJ,
        "relI_description": release_code_to_description(relI),
        "relJ_description": release_code_to_description(relJ),
        "warnings": metadata.get("warnings", []),
        "unsupported_features": unsupported,
        "i_releases": metadata.get("i_releases", []),
        "j_releases": metadata.get("j_releases", [])
    }


# Quick test function for development
if __name__ == "__main__":
    # Test cases from the actual model
    test_cases = [
        "M2J M3J",       # Pin at J (168 instances)
        "TI M2I M3I",    # Pin at I + torsion (53 instances)
        "M2I M3I",       # Pin at I (3 instances)
        "TJ M2J M3J",    # Pin at J + torsion (1 instance)
    ]

    print("End Release Parser Test\n" + "="*60)
    for release_str in test_cases:
        result = validate_release_string(release_str)
        print(f"\nRelease: \"{release_str}\"")
        print(f"  OpenSees codes: relI={result['relI']}, relJ={result['relJ']}")
        print(f"  I-end: {result['relI_description']}")
        print(f"  J-end: {result['relJ_description']}")
        if result['warnings']:
            print(f"  Warnings:")
            for w in result['warnings']:
                print(f"    - {w}")
