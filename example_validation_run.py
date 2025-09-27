#!/usr/bin/env python3
"""
Example script showing how to use the OpenSees Model Validator
for comprehensive model validation and reporting.

This script demonstrates the key validation capabilities without
requiring OpenSeesPy to be installed.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from opensees_model_validator import OpenSeesModelValidator

def demonstrate_validation():
    """Demonstrate the key validation capabilities."""
    print("OpenSees Model Validator Demonstration")
    print("=" * 45)

    # Create validator instance
    validator = OpenSeesModelValidator()

    print("1. GEOMETRIC TRANSFORMATION ANALYSIS")
    print("-" * 35)

    # Analyze geometric transformations
    transforms = validator.extract_geometric_transformations()
    if "error" not in transforms:
        summary = transforms["joint_offset_summary"]
        print(f"Total transformations: {summary['total_transforms']}")
        print(f"Transformations with joint offsets: {summary['total_with_offsets']}")
        print(f"  - Beams with offsets: {summary['beams_with_offsets']}")
        print(f"  - Columns with offsets: {summary['columns_with_offsets']}")

        # Show some examples
        print("\nExample beam transformations (first 3):")
        for i, beam in enumerate(transforms["beam_transforms"][:3]):
            print(f"  {beam['line']} @ {beam['story']}: offsets = {beam['has_joint_offsets']}")

        print("\nExample column transformations (first 3):")
        for i, column in enumerate(transforms["column_transforms"][:3]):
            print(f"  {column['line']} @ {column['story']}: offsets = {column['has_joint_offsets']}")
    else:
        print(f"Error: {transforms['error']}")

    print("\n2. TRACKING ELEMENT VERIFICATION")
    print("-" * 30)

    # Verify tracking elements
    tracking = validator.extract_tracking_elements()
    if "error" not in tracking:
        status = tracking["verification_status"]

        print("BEAM B408 @ 11_P6:")
        if status.get("beam_b408_found"):
            print("  ✅ Element found")
            beam = tracking["beam_b408"]
            print(f"  Joint offset I: {beam['joint_offset_i']}")
            print(f"  Joint offset J: {beam['joint_offset_j']}")
            print(f"  Rigid end lengths: I={beam['length_off_i']}, J={beam['length_off_j']}")

            if status.get("beam_b408_offset_correct"):
                print("  ✅ Joint offsets match expected values")
            else:
                print("  ⚠️ Joint offsets may need review")
        else:
            print("  ❌ Element not found")

        print("\nCOLUMN C522 @ 02_P2:")
        if status.get("column_c522_found"):
            print("  ✅ Element found")
            column = tracking["column_c522"]
            print(f"  Joint offset I: {column['joint_offset_i']}")
            print(f"  Joint offset J: {column['joint_offset_j']}")
            print(f"  Rigid end lengths: I={column['length_off_i']}, J={column['length_off_j']}")
            print(f"  Lateral offsets I: {column['offsets_i']}")
            print(f"  Lateral offsets J: {column['offsets_j']}")

            if (status.get("column_c522_offset_i_correct") and
                status.get("column_c522_offset_j_correct")):
                print("  ✅ Joint offsets match expected values")
            else:
                print("  ⚠️ Joint offsets may need review")
        else:
            print("  ❌ Element not found")
    else:
        print(f"Error: {tracking['error']}")

    print("\n3. VALIDATION SUMMARY")
    print("-" * 20)

    # Summarize validation capabilities
    capabilities = [
        "✅ Geometric transformation analysis (beams: vecxz=[0,0,1], columns: vecxz=[1,0,0])",
        "✅ Joint offset validation (rigid ends + lateral offsets)",
        "✅ Tracking element verification (B408, C522)",
        "✅ Artifact data cross-validation",
        "⏳ Modal analysis (requires OpenSeesPy)",
        "⏳ Full test suite execution (requires OpenSeesPy)"
    ]

    for capability in capabilities:
        print(f"  {capability}")

    print(f"\n4. USAGE INSTRUCTIONS")
    print("-" * 20)
    print("To run the full validator with OpenSeesPy:")
    print("  python opensees_model_validator.py")
    print("")
    print("To specify a custom model:")
    print("  python opensees_model_validator.py --model path/to/model.py")
    print("")
    print("Output files will be created in 'validation_output/' directory:")
    print("  - validation_report.txt (human-readable)")
    print("  - validation_data.json (machine-readable)")

    print(f"\n{'='*45}")
    print("Demonstration completed successfully!")
    print("The validator is ready for independent model verification.")

if __name__ == "__main__":
    demonstrate_validation()