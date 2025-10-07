#!/usr/bin/env python3
"""
Diagnostic: Check what nodes are actually in the OpenSees domain after full build.
This simulates exactly what the viewer does.
"""
import sys
import json

# Force clean module cache (like the viewer does)
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith('src.'):
        del sys.modules[mod_name]

from openseespy.opensees import wipe, model, getNodeTags, nodeCoord

print("=" * 80)
print("VIEWER NODE COLLECTION DIAGNOSTIC")
print("=" * 80)

# Build model exactly as viewer does
wipe()
model("basic", "-ndm", 3, "-ndf", 6)

from src.orchestration.MODEL_translator import build_model
print("\nBuilding model with stage='all'...")
build_model(stage='all')

# Collect nodes exactly as viewer does
print("\nCollecting nodes from OpenSees domain...")
node_tags = getNodeTags()
nodes = {int(tag): tuple(nodeCoord(int(tag))) for tag in node_tags}

# Analyze
z_coords = [coord[2] for coord in nodes.values()]
z_min, z_max = min(z_coords), max(z_coords)

print(f"\n📊 RESULTS:")
print(f"   Total nodes collected: {len(nodes)}")
print(f"   Z range: [{z_min:.3f}, {z_max:.3f}]")

nodes_at_z0 = sum(1 for z in z_coords if abs(z) < 0.01)
nodes_below_5 = sum(1 for z in z_coords if z < 5.0)
nodes_below_10 = sum(1 for z in z_coords if z < 10.0)

print(f"   Nodes at z≈0: {nodes_at_z0}")
print(f"   Nodes below z=5: {nodes_below_5}")
print(f"   Nodes below z=10: {nodes_below_10}")

# Check Base story specifically
with open("out/story_graph.json", "r") as f:
    sg = json.load(f)

story_index = {name: i for i, name in enumerate(sg["story_order_top_to_bottom"])}
base_idx = story_index["Base"]
base_points = sg["active_points"]["Base"]

expected_base_tags = [int(p["id"]) * 1000 + base_idx for p in base_points]
base_in_domain = sum(1 for tag in expected_base_tags if tag in nodes)

print(f"\n🏗️  BASE STORY CHECK:")
print(f"   Expected Base nodes: {len(expected_base_tags)}")
print(f"   Found in domain: {base_in_domain}")
print(f"   Missing: {len(expected_base_tags) - base_in_domain}")

if base_in_domain < len(expected_base_tags):
    print(f"\n❌ PROBLEM: Base story nodes are missing from OpenSees domain!")
    print(f"   This explains why the building appears to float above supports.")

    # Check a few missing nodes
    missing = [tag for tag in expected_base_tags if tag not in nodes]
    print(f"\n   First 5 missing Base node tags: {missing[:5]}")
else:
    print(f"\n✅ All Base story nodes present in domain!")

    # Check their coordinates
    base_z = [nodes[tag][2] for tag in expected_base_tags if tag in nodes]
    print(f"   Base node Z range: [{min(base_z):.3f}, {max(base_z):.3f}]")

print("\n" + "=" * 80)
