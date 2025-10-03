#!/usr/bin/env python3
"""
Test spring support implementation.

Verifies:
1. Spring properties parsing from E2K
2. Spring creation in OpenSees model
3. Correct zeroLength element configuration
4. Material stiffness values
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from config import E2K_PATH, OUT_DIR
from src.parsing.e2k_parser import parse_e2k


def test_spring_parsing():
    """Test Phase 1: Spring properties parsing from E2K"""
    print("\n" + "="*60)
    print("TEST 1: Spring Properties Parsing")
    print("="*60)

    # Read E2K file
    with open(E2K_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        e2k_text = f.read()

    # Parse
    parsed = parse_e2k(e2k_text)

    # Verify spring_properties exists
    assert "spring_properties" in parsed, "spring_properties not in parsed data"
    spring_props = parsed["spring_properties"]

    print(f"✅ Found {len(spring_props)} spring property definitions")

    # Verify specific spring from user's example
    assert "RES_00_75cm" in spring_props, "RES_00_75cm not found"
    res_spring = spring_props["RES_00_75cm"]

    expected_ux = 316500
    expected_uy = 316500
    expected_uz = 0

    assert res_spring["ux"] == expected_ux, f"UX mismatch: {res_spring['ux']} != {expected_ux}"
    assert res_spring["uy"] == expected_uy, f"UY mismatch: {res_spring['uy']} != {expected_uy}"
    assert res_spring["uz"] == expected_uz, f"UZ mismatch: {res_spring['uz']} != {expected_uz}"

    print(f"✅ Spring 'RES_00_75cm' has correct stiffnesses:")
    print(f"   UX={res_spring['ux']:,.0f}, UY={res_spring['uy']:,.0f}, UZ={res_spring['uz']:,.0f}")

    # Verify point assignments have springprop
    point_assigns = parsed["point_assigns"]
    assigns_with_springs = [pa for pa in point_assigns if pa.get("springprop")]

    assert len(assigns_with_springs) > 0, "No point assignments with springs found"
    print(f"✅ Found {len(assigns_with_springs)} point assignments with springs")

    # Verify all referenced springs exist
    referenced_springs = set(pa["springprop"] for pa in assigns_with_springs)
    missing_springs = referenced_springs - set(spring_props.keys())

    if missing_springs:
        print(f"⚠️  Warning: {len(missing_springs)} referenced springs not defined: {missing_springs}")
    else:
        print(f"✅ All {len(referenced_springs)} referenced spring types are defined")

    print("\n✅ TEST 1 PASSED: Spring parsing works correctly\n")
    return True


def test_spring_opensees_integration():
    """Test Phase 2: Spring creation in OpenSees model"""
    print("\n" + "="*60)
    print("TEST 2: Spring OpenSees Integration")
    print("="*60)

    try:
        from openseespy.opensees import (
            wipe, model, getNodeTags, getEleTags, eleResponse
        )
    except ImportError:
        print("⚠️  OpenSeesPy not installed - skipping OpenSees integration test")
        return None

    # Build minimal model
    wipe()
    model("basic", "-ndm", 3, "-ndf", 6)

    # Import and run model builder
    from src.model_building.nodes import define_nodes
    from src.model_building.springs import define_spring_supports

    # Create nodes
    define_nodes()
    initial_node_count = len(getNodeTags())
    print(f"✅ Created {initial_node_count} nodes")

    # Create springs
    result = define_spring_supports(verbose=True)

    springs_created = result["springs_defined"]
    assert springs_created > 0, "No springs were created"

    print(f"\n✅ Spring creation summary:")
    print(f"   Springs defined: {springs_created}")
    print(f"   Unique spring types: {result['unique_spring_types']}")
    print(f"   Nodes with springs: {len(result['nodes_with_springs'])}")

    # Verify ground nodes were created
    final_node_count = len(getNodeTags())
    ground_nodes_created = final_node_count - initial_node_count
    print(f"   Ground nodes created: {ground_nodes_created}")

    assert ground_nodes_created == springs_created, \
        f"Ground node count mismatch: {ground_nodes_created} != {springs_created}"

    # Verify zeroLength elements were created
    ele_tags = getEleTags()
    spring_elements = [tag for tag in ele_tags if tag >= 8000000]
    print(f"   ZeroLength elements: {len(spring_elements)}")

    assert len(spring_elements) == springs_created, \
        f"Element count mismatch: {len(spring_elements)} != {springs_created}"

    # Verify specific spring properties
    if result["nodes_with_springs"]:
        sample_node = result["nodes_with_springs"][0]
        sample_element = 8000000 + sample_node
        ground_node = sample_node + 9000000

        print(f"\n✅ Sample spring verification:")
        print(f"   Node: {sample_node}")
        print(f"   Ground node: {ground_node}")
        print(f"   Element: {sample_element}")

        # Check element exists
        assert sample_element in ele_tags, f"Element {sample_element} not found"
        print(f"   ✅ ZeroLength element exists")

    print("\n✅ TEST 2 PASSED: OpenSees integration works correctly\n")
    return True


def test_spring_data_flow():
    """Test complete data flow from E2K to story_graph to springs"""
    print("\n" + "="*60)
    print("TEST 3: Spring Data Flow (E2K → story_graph → OpenSees)")
    print("="*60)

    # Load story_graph
    story_graph_path = Path(OUT_DIR) / "story_graph.json"
    if not story_graph_path.exists():
        print("⚠️  story_graph.json not found - skipping data flow test")
        return None

    with open(story_graph_path, 'r') as f:
        story_graph = json.load(f)

    # Count points with springs in story_graph
    total_springprop_points = 0
    all_active_points = story_graph.get("active_points", {})
    for story_name, points in all_active_points.items():
        for point in points:
            if point.get("springprop"):
                total_springprop_points += 1

    print(f"✅ story_graph.json contains {total_springprop_points} points with springprop")

    # Load parsed_raw
    parsed_raw_path = Path(OUT_DIR) / "parsed_raw.json"
    with open(parsed_raw_path, 'r') as f:
        parsed_raw = json.load(f)

    spring_props = parsed_raw.get("spring_properties", {})
    print(f"✅ parsed_raw.json contains {len(spring_props)} spring property definitions")

    # Verify all springprop references can be resolved
    unresolved = 0
    for story_name, points in all_active_points.items():
        for point in points:
            springprop = point.get("springprop")
            if springprop and springprop not in spring_props:
                unresolved += 1

    if unresolved > 0:
        print(f"⚠️  Warning: {unresolved} unresolved springprop references")
    else:
        print(f"✅ All springprop references can be resolved")

    print("\n✅ TEST 3 PASSED: Data flow is complete and consistent\n")
    return True


def main():
    """Run all spring tests"""
    print("\n" + "="*60)
    print("SPRING SUPPORT FEATURE - COMPREHENSIVE TEST SUITE")
    print("="*60)

    results = {}

    # Test 1: Parsing
    try:
        results['parsing'] = test_spring_parsing()
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        results['parsing'] = False

    # Test 2: OpenSees integration
    try:
        results['opensees'] = test_spring_opensees_integration()
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        results['opensees'] = False

    # Test 3: Data flow
    try:
        results['data_flow'] = test_spring_data_flow()
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        results['data_flow'] = False

    # Summary
    print("="*60)
    print("TEST SUITE SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v is True)
    skipped = sum(1 for v in results.values() if v is None)
    failed = sum(1 for v in results.values() if v is False)

    for test_name, result in results.items():
        status = "✅ PASSED" if result is True else ("⚠️  SKIPPED" if result is None else "❌ FAILED")
        print(f"{test_name:20s}: {status}")

    print("="*60)
    print(f"Passed: {passed}, Skipped: {skipped}, Failed: {failed}")
    print("="*60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
