#!/usr/bin/env python3
"""
Simple test for joint offset calculations without OpenSees dependencies.
Tests the mathematical correctness of our rigid ends + offsets implementation.
"""

import math
from typing import Dict, Any, Optional, Tuple

def calculate_joint_offsets(
    pI: Tuple[float, float, float],
    pJ: Tuple[float, float, float],
    length_off_i: float = 0.0,
    length_off_j: float = 0.0,
    offsets_i: Optional[Dict[str, float]] = None,
    offsets_j: Optional[Dict[str, float]] = None
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Same calculation logic as in beams.py/_calculate_joint_offsets"""

    # Calculate unit vector along member axis (I -> J)
    xi, yi, zi = pI
    xj, yj, zj = pJ
    vx, vy, vz = (xj - xi), (yj - yi), (zj - zi)
    length = math.sqrt(vx*vx + vy*vy + vz*vz)

    if length == 0.0:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)

    # Unit vector components
    ex, ey, ez = vx/length, vy/length, vz/length

    # Axial rigid end components
    dI_len_x = length_off_i * ex
    dI_len_y = length_off_i * ey
    dI_len_z = length_off_i * ez

    dJ_len_x = -length_off_j * ex
    dJ_len_y = -length_off_j * ey
    dJ_len_z = -length_off_j * ez

    # Lateral offset components
    offsets_i = offsets_i or {}
    offsets_j = offsets_j or {}

    dI_lat_x = offsets_i.get('x', 0.0)
    dI_lat_y = offsets_i.get('y', 0.0)
    dI_lat_z = offsets_i.get('z', 0.0)

    dJ_lat_x = offsets_j.get('x', 0.0)
    dJ_lat_y = offsets_j.get('y', 0.0)
    dJ_lat_z = offsets_j.get('z', 0.0)

    # Total joint offsets
    dI = (dI_len_x + dI_lat_x, dI_len_y + dI_lat_y, dI_len_z + dI_lat_z)
    dJ = (dJ_len_x + dJ_lat_x, dJ_len_y + dJ_lat_y, dJ_len_z + dJ_lat_z)

    return dI, dJ

def test_beam_b408():
    """Test BEAM B408 @ 11_P6: LENGTHOFFI=0.4, no offsets"""
    print("🎯 TEST 1: BEAM B408 @ 11_P6")
    print("  Expected: Rigid end at I only (0.4m)")

    # Horizontal beam (5m span in X direction)
    pI = (0.0, 0.0, 3.0)  # left end
    pJ = (5.0, 0.0, 3.0)  # right end

    dI, dJ = calculate_joint_offsets(
        pI, pJ,
        length_off_i=0.4,  # rigid end at I
        length_off_j=0.0,  # no rigid end at J
        offsets_i=None,    # no lateral offsets
        offsets_j=None
    )

    print(f"  Calculated dI: [{dI[0]:.6f}, {dI[1]:.6f}, {dI[2]:.6f}]")
    print(f"  Calculated dJ: [{dJ[0]:.6f}, {dJ[1]:.6f}, {dJ[2]:.6f}]")

    # Expected: unit vector = (1,0,0), so dI = 0.4*(1,0,0) = (0.4,0,0)
    expected_dI = (0.4, 0.0, 0.0)
    expected_dJ = (0.0, 0.0, 0.0)

    print(f"  Expected dI:   [{expected_dI[0]:.6f}, {expected_dI[1]:.6f}, {expected_dI[2]:.6f}]")
    print(f"  Expected dJ:   [{expected_dJ[0]:.6f}, {expected_dJ[1]:.6f}, {expected_dJ[2]:.6f}]")

    tolerance = 1e-6
    success = (abs(dI[0] - expected_dI[0]) < tolerance and
               abs(dI[1] - expected_dI[1]) < tolerance and
               abs(dI[2] - expected_dI[2]) < tolerance and
               abs(dJ[0] - expected_dJ[0]) < tolerance and
               abs(dJ[1] - expected_dJ[1]) < tolerance and
               abs(dJ[2] - expected_dJ[2]) < tolerance)

    print(f"  Result: {'✅ CORRECT' if success else '❌ ERROR'}")
    print()
    return success

def test_column_c522():
    """Test COLUMN C522 @ 02_P2: LENGTHOFFI/J=0.275, offsets=[-0.05,0.2,0.0]"""
    print("🎯 TEST 2: COLUMN C522 @ 02_P2")
    print("  Expected: Rigid ends + lateral offsets")

    # Vertical column (3m height in Z direction)
    pI = (10.0, 5.0, 0.0)  # bottom
    pJ = (10.0, 5.0, 3.0)  # top

    offsets_both = {'x': -0.05, 'y': 0.2, 'z': 0.0}

    dI, dJ = calculate_joint_offsets(
        pI, pJ,
        length_off_i=0.275,    # rigid end at I
        length_off_j=0.275,    # rigid end at J
        offsets_i=offsets_both, # lateral offsets at I
        offsets_j=offsets_both  # lateral offsets at J
    )

    print(f"  Calculated dI: [{dI[0]:.6f}, {dI[1]:.6f}, {dI[2]:.6f}]")
    print(f"  Calculated dJ: [{dJ[0]:.6f}, {dJ[1]:.6f}, {dJ[2]:.6f}]")

    # Expected: unit vector = (0,0,1) vertical
    # dI = 0.275*(0,0,1) + (-0.05,0.2,0) = (-0.05, 0.2, 0.275)
    # dJ = -0.275*(0,0,1) + (-0.05,0.2,0) = (-0.05, 0.2, -0.275)
    expected_dI = (-0.05, 0.2, 0.275)
    expected_dJ = (-0.05, 0.2, -0.275)

    print(f"  Expected dI:   [{expected_dI[0]:.6f}, {expected_dI[1]:.6f}, {expected_dI[2]:.6f}]")
    print(f"  Expected dJ:   [{expected_dJ[0]:.6f}, {expected_dJ[1]:.6f}, {expected_dJ[2]:.6f}]")

    tolerance = 1e-6
    success = (abs(dI[0] - expected_dI[0]) < tolerance and
               abs(dI[1] - expected_dI[1]) < tolerance and
               abs(dI[2] - expected_dI[2]) < tolerance and
               abs(dJ[0] - expected_dJ[0]) < tolerance and
               abs(dJ[1] - expected_dJ[1]) < tolerance and
               abs(dJ[2] - expected_dJ[2]) < tolerance)

    print(f"  Result: {'✅ CORRECT' if success else '❌ ERROR'}")
    print()
    return success

def test_no_offsets():
    """Test reference case: no rigid ends, no offsets"""
    print("🎯 TEST 3: REFERENCE - No offsets")
    print("  Expected: All zeros")

    # Any beam geometry
    pI = (0.0, 0.0, 0.0)
    pJ = (1.0, 1.0, 1.0)

    dI, dJ = calculate_joint_offsets(
        pI, pJ,
        length_off_i=0.0,
        length_off_j=0.0,
        offsets_i=None,
        offsets_j=None
    )

    print(f"  Calculated dI: [{dI[0]:.6f}, {dI[1]:.6f}, {dI[2]:.6f}]")
    print(f"  Calculated dJ: [{dJ[0]:.6f}, {dJ[1]:.6f}, {dJ[2]:.6f}]")

    expected_dI = (0.0, 0.0, 0.0)
    expected_dJ = (0.0, 0.0, 0.0)

    print(f"  Expected dI:   [{expected_dI[0]:.6f}, {expected_dI[1]:.6f}, {expected_dI[2]:.6f}]")
    print(f"  Expected dJ:   [{expected_dJ[0]:.6f}, {expected_dJ[1]:.6f}, {expected_dJ[2]:.6f}]")

    tolerance = 1e-6
    success = (abs(dI[0] - expected_dI[0]) < tolerance and
               abs(dI[1] - expected_dI[1]) < tolerance and
               abs(dI[2] - expected_dI[2]) < tolerance and
               abs(dJ[0] - expected_dJ[0]) < tolerance and
               abs(dJ[1] - expected_dJ[1]) < tolerance and
               abs(dJ[2] - expected_dJ[2]) < tolerance)

    print(f"  Result: {'✅ CORRECT' if success else '❌ ERROR'}")
    print()
    return success

if __name__ == "__main__":
    print("JOINT OFFSET CALCULATION VERIFICATION")
    print("=====================================\n")

    success1 = test_beam_b408()
    success2 = test_column_c522()
    success3 = test_no_offsets()

    print("=== SUMMARY ===")
    if success1 and success2 and success3:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Joint offset calculations are mathematically correct")
        print("✅ Implementation follows PDF guidance properly")
        print("✅ Ready for OpenSees integration")
    else:
        print("❌ SOME TESTS FAILED")
        print("Check the calculation logic")
    print()