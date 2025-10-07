#!/usr/bin/env python3
"""
Simple test to verify model building and support visualization works.
This bypasses Streamlit entirely.
"""
import json
from openseespy.opensees import wipe, model, getNodeTags, nodeCoord

print("=" * 80)
print("SIMPLE VIEWER TEST - Bypassing Streamlit")
print("=" * 80)

# Step 1: Build model
print("\n1. Building model with MODEL_translator...")
from src.orchestration.MODEL_translator import build_model

wipe()
model("basic", "-ndm", 3, "-ndf", 6)
build_model(stage='all')

# Step 2: Collect nodes (like viewer does)
print("\n2. Collecting nodes from OpenSees domain...")
all_tags = getNodeTags()
nodes_dict = {int(tag): tuple(nodeCoord(int(tag))) for tag in all_tags}

print(f"   Collected {len(nodes_dict)} nodes")

z_coords = [coord[2] for coord in nodes_dict.values()]
z_min, z_max = min(z_coords), max(z_coords)
print(f"   Z range: [{z_min:.3f}, {z_max:.3f}]")

nodes_below_10 = sum(1 for z in z_coords if z < 10.0)
print(f"   Nodes below z=10.00: {nodes_below_10}")

# Step 3: Load supports (like viewer does)
print("\n3. Loading supports from supports.json...")
with open("out/supports.json", "r") as f:
    supports_data = json.load(f)

supports_by_node = {}
for rec in supports_data.get("applied", []):
    n = int(rec.get("node"))
    mask = tuple(int(v) for v in rec.get("mask", []))
    if len(mask) == 6:
        supports_by_node[n] = mask

print(f"   Loaded {len(supports_by_node)} supports")
print(f"   Applied via fix: {len(supports_data.get('applied_via_fix', []))}")
print(f"   Applied via springs: {len(supports_data.get('applied_via_springs', []))}")

# Step 4: Check which supports can be visualized
print("\n4. Checking which supports can be visualized...")
visualizable_supports = {}
missing_supports = {}

for node_tag, mask in supports_by_node.items():
    if node_tag in nodes_dict:
        visualizable_supports[node_tag] = (nodes_dict[node_tag], mask)
    else:
        missing_supports[node_tag] = mask

print(f"   Supports WITH coordinates (can visualize): {len(visualizable_supports)}")
print(f"   Supports WITHOUT coordinates (MISSING): {len(missing_supports)}")

if missing_supports:
    print(f"\n   ❌ Missing support nodes:")
    # Load story graph to get z-coordinates
    with open("out/story_graph.json", "r") as f:
        sg = json.load(f)

    story_index = {name: i for i, name in enumerate(sg["story_order_top_to_bottom"])}

    for tag in list(missing_supports.keys())[:10]:
        # Decode tag
        story_idx = tag % 1000
        point_id = tag // 1000
        story_name = sg["story_order_top_to_bottom"][story_idx]

        # Find point in active_points
        for p in sg["active_points"].get(story_name, []):
            if int(p["id"]) == point_id:
                print(f"      Node {tag}: {story_name}, z={p['z']:.3f}")
                break
else:
    print(f"\n   ✅ All {len(visualizable_supports)} support nodes have coordinates!")
    print(f"\n   Sample support locations:")
    for node_tag, (coords, mask) in list(visualizable_supports.items())[:5]:
        fixed_dofs = [dof for i, dof in enumerate(['UX','UY','UZ','RX','RY','RZ']) if mask[i] == 1]
        print(f"      Node {node_tag}: ({coords[0]:.2f}, {coords[1]:.2f}, {coords[2]:.2f}) - Fixed: {', '.join(fixed_dofs)}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)

if len(nodes_dict) == 4717 and len(visualizable_supports) == 63:
    print("✅ SUCCESS: Model has correct number of nodes and all supports are visualizable!")
elif len(nodes_dict) == 4157:
    print("❌ FAILURE: Only 4157 nodes created (expected 4717)")
    print("   This means Base story nodes are NOT being created")
else:
    print(f"⚠️  UNEXPECTED: {len(nodes_dict)} nodes created, {len(visualizable_supports)} supports visualizable")
