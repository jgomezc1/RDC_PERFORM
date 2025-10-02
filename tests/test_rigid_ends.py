#!/usr/bin/env python3
"""
Test script to verify rigid ends and end offsets implementation.
Tests the specific tracking elements we selected for verification.
"""

import sys
import math
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.model_building.beams import _calculate_joint_offsets
from src.parsing import e2k_parser

def test_joint_offset_calculation():
    """Test the joint offset calculation function with our tracking elements."""

    print("=== TESTING JOINT OFFSET CALCULATION ===\n")

    # Parse the e2k file to get our tracking data
    text = Path('models/EjemploNew.e2k').read_text(encoding='utf-8', errors='ignore')
    result = e2k_parser.parse_e2k(text)
    line_assigns = result.get('line_assigns', [])

    # TRACKING ELEMENT 1: BEAM B408 @ 11_P6 (rigid end at I only)
    beam_b408 = next((entry for entry in line_assigns
                      if entry.get('line') == 'B408' and entry.get('story') == '11_P6'), None)

    if beam_b408:
        print("🎯 TRACKING ELEMENT 1: BEAM B408 @ 11_P6")
        print(f"  LENGTHOFFI: {beam_b408.get('length_off_i')} m")
        print(f"  LENGTHOFFJ: {beam_b408.get('length_off_j')} m")
        print(f"  Offsets I: {beam_b408.get('offsets_i')}")
        print(f"  Offsets J: {beam_b408.get('offsets_j')}")

        # Mock coordinates for calculation (horizontal beam example)
        pI = (0.0, 0.0, 3.0)  # left end
        pJ = (5.0, 0.0, 3.0)  # right end (5m span)

        dI, dJ = _calculate_joint_offsets(
            pI, pJ,
            beam_b408.get('length_off_i', 0.0),
            beam_b408.get('length_off_j', 0.0),
            beam_b408.get('offsets_i'),
            beam_b408.get('offsets_j')
        )

        print(f"  Calculated dI: [{dI[0]:.6f}, {dI[1]:.6f}, {dI[2]:.6f}]")
        print(f"  Calculated dJ: [{dJ[0]:.6f}, {dJ[1]:.6f}, {dJ[2]:.6f}]")

        # Verify calculation: unit vector = (1, 0, 0), LENGTHOFFI = 0.4
        expected_dI = (0.4, 0.0, 0.0)  # +0.4 * unit_vector
        expected_dJ = (0.0, 0.0, 0.0)  # no rigid end at J

        print(f"  Expected dI:   [{expected_dI[0]:.6f}, {expected_dI[1]:.6f}, {expected_dI[2]:.6f}]")
        print(f"  Expected dJ:   [{expected_dJ[0]:.6f}, {expected_dJ[1]:.6f}, {expected_dJ[2]:.6f}]")

        tolerance = 1e-6
        if (abs(dI[0] - expected_dI[0]) < tolerance and
            abs(dI[1] - expected_dI[1]) < tolerance and
            abs(dI[2] - expected_dI[2]) < tolerance and
            abs(dJ[0] - expected_dJ[0]) < tolerance and
            abs(dJ[1] - expected_dJ[1]) < tolerance and
            abs(dJ[2] - expected_dJ[2]) < tolerance):
            print("  ✅ BEAM CALCULATION CORRECT")
        else:
            print("  ❌ BEAM CALCULATION ERROR")
        print()

    # TRACKING ELEMENT 2: COLUMN C522 @ 02_P2 (rigid ends + offsets)
    col_c522 = next((entry for entry in line_assigns
                     if entry.get('line') == 'C522' and entry.get('story') == '02_P2'), None)

    if col_c522:
        print("🎯 TRACKING ELEMENT 2: COLUMN C522 @ 02_P2")
        print(f"  LENGTHOFFI: {col_c522.get('length_off_i')} m")
        print(f"  LENGTHOFFJ: {col_c522.get('length_off_j')} m")
        print(f"  Offsets I: {col_c522.get('offsets_i')}")
        print(f"  Offsets J: {col_c522.get('offsets_j')}")

        # Mock coordinates for calculation (vertical column example)
        pI = (10.0, 5.0, 0.0)  # bottom
        pJ = (10.0, 5.0, 3.0)  # top (3m height)

        dI, dJ = _calculate_joint_offsets(
            pI, pJ,
            col_c522.get('length_off_i', 0.0),
            col_c522.get('length_off_j', 0.0),
            col_c522.get('offsets_i'),
            col_c522.get('offsets_j')
        )

        print(f"  Calculated dI: [{dI[0]:.6f}, {dI[1]:.6f}, {dI[2]:.6f}]")
        print(f"  Calculated dJ: [{dJ[0]:.6f}, {dJ[1]:.6f}, {dJ[2]:.6f}]")

        # Verify calculation:
        # unit vector = (0, 0, 1) vertical
        # LENGTHOFFI = 0.275, LENGTHOFFJ = 0.275
        # Offsets I/J = [-0.05, 0.2, 0.0]
        expected_dI = (-0.05 + 0.275*0, 0.2 + 0.275*0, 0.0 + 0.275*1)  # offset + rigid
        expected_dJ = (-0.05 - 0.275*0, 0.2 - 0.275*0, 0.0 - 0.275*1)  # offset - rigid

        print(f"  Expected dI:   [{expected_dI[0]:.6f}, {expected_dI[1]:.6f}, {expected_dI[2]:.6f}]")
        print(f"  Expected dJ:   [{expected_dJ[0]:.6f}, {expected_dJ[1]:.6f}, {expected_dJ[2]:.6f}]")

        tolerance = 1e-6
        if (abs(dI[0] - expected_dI[0]) < tolerance and
            abs(dI[1] - expected_dI[1]) < tolerance and
            abs(dI[2] - expected_dI[2]) < tolerance and
            abs(dJ[0] - expected_dJ[0]) < tolerance and
            abs(dJ[1] - expected_dJ[1]) < tolerance and
            abs(dJ[2] - expected_dJ[2]) < tolerance):
            print("  ✅ COLUMN CALCULATION CORRECT")
        else:
            print("  ❌ COLUMN CALCULATION ERROR")
        print()

def test_element_data_extraction():
    """Test that we can extract the correct data for our tracking elements."""

    print("=== TESTING ELEMENT DATA EXTRACTION ===\n")

    # Parse the e2k file
    text = Path('models/EjemploNew.e2k').read_text(encoding='utf-8', errors='ignore')
    result = e2k_parser.parse_e2k(text)
    line_assigns = result.get('line_assigns', [])

    # Count elements with rigid ends and offsets
    beams_with_rigid = [entry for entry in line_assigns
                        if 'B' in entry.get('line', '') and
                        (entry.get('length_off_i') or entry.get('length_off_j'))]

    columns_with_offsets = [entry for entry in line_assigns
                           if 'C' in entry.get('line', '') and
                           (entry.get('offsets_i') or entry.get('offsets_j'))]

    columns_with_rigid = [entry for entry in line_assigns
                         if 'C' in entry.get('line', '') and
                         (entry.get('length_off_i') or entry.get('length_off_j'))]

    print(f"📊 Data Summary:")
    print(f"  Total line assigns: {len(line_assigns)}")
    print(f"  Beams with rigid ends: {len(beams_with_rigid)}")
    print(f"  Columns with offsets: {len(columns_with_offsets)}")
    print(f"  Columns with rigid ends: {len(columns_with_rigid)}")
    print()

    # Verify our tracking elements are found
    beam_b408 = next((entry for entry in line_assigns
                      if entry.get('line') == 'B408' and entry.get('story') == '11_P6'), None)
    col_c522 = next((entry for entry in line_assigns
                     if entry.get('line') == 'C522' and entry.get('story') == '02_P2'), None)

    if beam_b408 and col_c522:
        print("✅ Both tracking elements found in parsed data")
    else:
        print("❌ Tracking elements not found!")
        if not beam_b408:
            print("   Missing: BEAM B408 @ 11_P6")
        if not col_c522:
            print("   Missing: COLUMN C522 @ 02_P2")
    print()

if __name__ == "__main__":
    print("RIGID ENDS AND END OFFSETS VERIFICATION\n")
    print("Testing implementation against selected tracking elements...\n")

    test_element_data_extraction()
    test_joint_offset_calculation()

    print("=== VERIFICATION COMPLETE ===")
    print("If all tests show ✅, the implementation is working correctly!")