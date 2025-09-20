#!/usr/bin/env python3
"""Test script for e2k parser material properties functionality"""

import e2k_parser
import json

def test_material_parsing():
    print("Testing e2k parser with material properties...")

    try:
        result = e2k_parser.parse_e2k('models/Ejemplo.e2k')

        print(f"✓ Parser executed successfully")
        print(f"✓ Artifacts version: {result.get('_artifacts_version')}")
        print(f"✓ Stories found: {len(result.get('stories', []))}")
        print(f"✓ Points found: {len(result.get('points', {}))}")
        print(f"✓ Materials found: {len(result.get('materials', {}))}")
        print(f"✓ Rebar definitions found: {len(result.get('rebar_definitions', {}))}")
        print(f"✓ Frame sections found: {len(result.get('frame_sections', {}))}")

        # Check materials detail
        materials = result.get('materials', {})
        if materials:
            print("\nMaterial categories:")
            for category, data in materials.items():
                print(f"  {category}: {len(data) if isinstance(data, dict) else 'N/A'} items")
                if isinstance(data, dict) and data:
                    first_key = next(iter(data.keys()))
                    first_item = data[first_key]
                    if isinstance(first_item, dict):
                        print(f"    Sample properties: {list(first_item.keys())}")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_material_parsing()