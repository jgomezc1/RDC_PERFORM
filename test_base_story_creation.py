#!/usr/bin/env python3
"""
Test if Base story nodes are being created correctly.
"""
import json
from pathlib import Path

# Check story_graph.json
print("=" * 80)
print("1. Checking story_graph.json")
print("=" * 80)

with open("out/story_graph.json", "r") as f:
    sg = json.load(f)

story_order = sg["story_order_top_to_bottom"]
story_index = {name: i for i, name in enumerate(story_order)}

print(f"Total stories: {len(story_order)}")
print(f"Base story index: {story_index['Base']}")

base_points = sg["active_points"]["Base"]
print(f"Base story active_points count: {len(base_points)}")

# Show first 3 Base points
print(f"\nFirst 3 Base story points:")
for p in base_points[:3]:
    print(f"  ID={p['id']}, X={p['x']:.2f}, Y={p['y']:.2f}, Z={p['z']:.2f}")

# Now test if define_nodes() creates them
print("\n" + "=" * 80)
print("2. Testing define_nodes() function")
print("=" * 80)

from openseespy.opensees import wipe, model, getNodeTags, nodeCoord
from src.model_building.nodes import define_nodes

wipe()
model("basic", "-ndm", 3, "-ndf", 6)

print("\nCalling define_nodes()...")
created_tags = define_nodes()

print(f"Total tags returned by define_nodes(): {len(created_tags)}")

# Check if Base nodes were created
base_idx = story_index["Base"]
expected_base_tags = [int(p["id"]) * 1000 + base_idx for p in base_points]

print(f"\nExpected Base node tags (first 5): {expected_base_tags[:5]}")

# Check in created_tags set
base_in_created = [tag for tag in expected_base_tags if tag in created_tags]
print(f"Base tags found in created_tags: {len(base_in_created)}/{len(expected_base_tags)}")

# Check in OpenSees domain
all_opensees_tags = set(getNodeTags())
print(f"\nTotal nodes in OpenSees domain: {len(all_opensees_tags)}")

base_in_opensees = [tag for tag in expected_base_tags if tag in all_opensees_tags]
print(f"Base tags found in OpenSees domain: {len(base_in_opensees)}/{len(expected_base_tags)}")

if len(base_in_opensees) > 0:
    print(f"\n✅ SUCCESS: Base nodes ARE being created!")
    print(f"Example coordinates:")
    for tag in base_in_opensees[:3]:
        coords = nodeCoord(tag)
        print(f"  Node {tag}: ({coords[0]:.2f}, {coords[1]:.2f}, {coords[2]:.2f})")
else:
    print(f"\n❌ FAILURE: Base nodes are NOT being created in OpenSees!")
    print(f"\nDebugging info:")
    print(f"  created_tags is set: {isinstance(created_tags, set)}")
    print(f"  Sample from created_tags (first 5): {sorted(list(created_tags))[:5]}")

    # Check if ANY nodes at Base story elevation were created
    base_z = base_points[0]["z"]
    nodes_at_base_z = []
    for tag in all_opensees_tags:
        coords = nodeCoord(tag)
        if abs(coords[2] - base_z) < 0.001:
            nodes_at_base_z.append(tag)

    print(f"  Nodes at z≈{base_z}: {len(nodes_at_base_z)}")
    if nodes_at_base_z:
        print(f"  Example: {nodes_at_base_z[:5]}")
