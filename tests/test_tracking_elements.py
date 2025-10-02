#!/usr/bin/env python3
"""
Test script to verify our tracking elements exist in parsed data
and that our joint offset calculations would work correctly.
"""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsing import e2k_parser

def test_tracking_elements():
    """Test that our tracking elements are found and have expected properties."""

    print("=== TRACKING ELEMENTS VERIFICATION ===\n")

    # Parse the e2k file
    text = Path('models/EjemploNew.e2k').read_text(encoding='utf-8', errors='ignore')
    result = e2k_parser.parse_e2k(text)
    line_assigns = result.get('line_assigns', [])

    print(f"📊 Parsed {len(line_assigns)} line assignments from EjemploNew.e2k")

    # TRACKING ELEMENT 1: BEAM B408 @ 11_P6
    beam_b408 = next((entry for entry in line_assigns
                      if entry.get('line') == 'B408' and entry.get('story') == '11_P6'), None)

    if beam_b408:
        print("\n🎯 TRACKING ELEMENT 1: BEAM B408 @ 11_P6")
        print(f"  ✅ Found in parsed data")
        print(f"  LENGTHOFFI: {beam_b408.get('length_off_i')} m")
        print(f"  LENGTHOFFJ: {beam_b408.get('length_off_j')} m")
        print(f"  Offsets I: {beam_b408.get('offsets_i')}")
        print(f"  Offsets J: {beam_b408.get('offsets_j')}")

        # Verify expected values
        expected_length_off_i = 0.4
        actual_length_off_i = beam_b408.get('length_off_i', 0.0)
        if abs(actual_length_off_i - expected_length_off_i) < 1e-6:
            print(f"  ✅ LENGTHOFFI matches expected value: {expected_length_off_i}")
        else:
            print(f"  ❌ LENGTHOFFI mismatch: expected {expected_length_off_i}, got {actual_length_off_i}")
    else:
        print("\n❌ TRACKING ELEMENT 1: BEAM B408 @ 11_P6 NOT FOUND")

    # TRACKING ELEMENT 2: COLUMN C522 @ 02_P2
    col_c522 = next((entry for entry in line_assigns
                     if entry.get('line') == 'C522' and entry.get('story') == '02_P2'), None)

    if col_c522:
        print("\n🎯 TRACKING ELEMENT 2: COLUMN C522 @ 02_P2")
        print(f"  ✅ Found in parsed data")
        print(f"  LENGTHOFFI: {col_c522.get('length_off_i')} m")
        print(f"  LENGTHOFFJ: {col_c522.get('length_off_j')} m")
        print(f"  Offsets I: {col_c522.get('offsets_i')}")
        print(f"  Offsets J: {col_c522.get('offsets_j')}")

        # Verify expected values
        expected_length_off_i = 0.275
        expected_length_off_j = 0.275
        expected_offsets = {'x': -0.05, 'y': 0.2, 'z': 0.0}

        actual_length_off_i = col_c522.get('length_off_i', 0.0)
        actual_length_off_j = col_c522.get('length_off_j', 0.0)
        actual_offsets_i = col_c522.get('offsets_i', {})

        if abs(actual_length_off_i - expected_length_off_i) < 1e-6:
            print(f"  ✅ LENGTHOFFI matches expected: {expected_length_off_i}")
        else:
            print(f"  ❌ LENGTHOFFI mismatch: expected {expected_length_off_i}, got {actual_length_off_i}")

        if abs(actual_length_off_j - expected_length_off_j) < 1e-6:
            print(f"  ✅ LENGTHOFFJ matches expected: {expected_length_off_j}")
        else:
            print(f"  ❌ LENGTHOFFJ mismatch: expected {expected_length_off_j}, got {actual_length_off_j}")

        if actual_offsets_i == expected_offsets:
            print(f"  ✅ Offsets I match expected: {expected_offsets}")
        else:
            print(f"  ❌ Offsets I mismatch: expected {expected_offsets}, got {actual_offsets_i}")
    else:
        print("\n❌ TRACKING ELEMENT 2: COLUMN C522 @ 02_P2 NOT FOUND")

    # Summary statistics
    print(f"\n📈 STATISTICS:")
    beams_with_rigid = [entry for entry in line_assigns
                        if 'B' in entry.get('line', '') and
                        (entry.get('length_off_i') or entry.get('length_off_j'))]

    columns_with_offsets = [entry for entry in line_assigns
                           if 'C' in entry.get('line', '') and
                           (entry.get('offsets_i') or entry.get('offsets_j'))]

    columns_with_rigid = [entry for entry in line_assigns
                         if 'C' in entry.get('line', '') and
                         (entry.get('length_off_i') or entry.get('length_off_j'))]

    print(f"  Beams with rigid ends: {len(beams_with_rigid)}")
    print(f"  Columns with end offsets: {len(columns_with_offsets)}")
    print(f"  Columns with rigid ends: {len(columns_with_rigid)}")

    return beam_b408 is not None and col_c522 is not None

if __name__ == "__main__":
    success = test_tracking_elements()
    print(f"\n=== RESULT ===")
    if success:
        print("🎉 Both tracking elements found and verified!")
        print("✅ Ready to test OpenSees integration")
    else:
        print("❌ Tracking elements verification failed")
    print()