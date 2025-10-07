#!/usr/bin/env python3
"""
Debug script to check if Base story nodes are being created.
"""
import json
from openseespy.opensees import wipe, model, getNodeTags, nodeCoord
from src.model_building.nodes import define_nodes

# Build model
wipe()
model("basic", "-ndm", 3, "-ndf", 6)

print("=" * 60)
print("DIAGNOSTIC: Creating nodes...")
print("=" * 60)

created_tags = define_nodes()

print(f"\nTotal nodes created: {len(created_tags)}")

# Check Base story nodes specifically
with open("out/story_graph.json", "r") as f:
    sg = json.load(f)

story_index = {name: i for i, name in enumerate(sg["story_order_top_to_bottom"])}
base_idx = story_index["Base"]

print(f"\nBase story index: {base_idx}")
print(f"Expected Base story node tags:")

base_points = sg["active_points"]["Base"]
expected_base_tags = []
for p in base_points[:5]:
    tag = int(p["id"]) * 1000 + base_idx
    expected_base_tags.append(tag)
    print(f"  Point {p['id']}: tag {tag}, coords ({p['x']:.2f}, {p['y']:.2f}, {p['z']:.2f})")

print(f"\nChecking if Base nodes exist in OpenSees domain...")
all_tags = set(getNodeTags())
base_nodes_found = []
for tag in expected_base_tags:
    if tag in all_tags:
        coords = nodeCoord(tag)
        base_nodes_found.append(tag)
        print(f"  ✅ Node {tag} EXISTS: {coords}")
    else:
        print(f"  ❌ Node {tag} MISSING")

print(f"\nSummary:")
print(f"  Expected Base nodes (first 5): {len(expected_base_tags)}")
print(f"  Found in domain: {len(base_nodes_found)}")
print(f"  Total nodes in domain: {len(all_tags)}")

if len(base_nodes_found) == 0:
    print("\n❌ NO BASE NODES FOUND - Something is wrong!")
else:
    print(f"\n✅ Base nodes are being created correctly")
