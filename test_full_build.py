#!/usr/bin/env python3
"""
Test full model build outside of Streamlit to verify all nodes are created.
"""
from openseespy.opensees import wipe, model, getNodeTags, nodeCoord
import sys
import importlib

print("=" * 80)
print("Testing full model build with MODEL_translator")
print("=" * 80)

# Force reload of all modules to get latest code
print("\nForce reloading modules...")
modules_to_reload = [
    'src.orchestration.MODEL_translator',
    'src.model_building.nodes',
    'src.model_building.supports',
    'src.model_building.springs',
    'src.model_building.diaphragms',
    'src.model_building.columns',
    'src.model_building.beams',
    'src.model_building.emit_nodes',
]
for mod_name in modules_to_reload:
    if mod_name in sys.modules:
        del sys.modules[mod_name]
        print(f"  Removed {mod_name} from cache")

# Import and build
from src.orchestration.MODEL_translator import build_model
print("Modules reloaded.\n")

wipe()
model("basic", "-ndm", 3, "-ndf", 6)

print("\nBuilding model with stage='all'...")
build_model(stage='all')

# Collect nodes
all_tags = getNodeTags()
print(f"\n✅ Build complete!")
print(f"Total nodes in OpenSees domain: {len(all_tags)}")

# Check z-range
z_coords = [nodeCoord(tag)[2] for tag in all_tags]
z_min, z_max = min(z_coords), max(z_coords)
print(f"Z range: [{z_min:.3f}, {z_max:.3f}]")

nodes_below_10 = sum(1 for z in z_coords if z < 10.0)
print(f"Nodes below z=10.00: {nodes_below_10}")

# Check Base story specifically
import json
with open("out/story_graph.json", "r") as f:
    sg = json.load(f)

story_index = {name: i for i, name in enumerate(sg["story_order_top_to_bottom"])}
base_idx = story_index["Base"]
base_points = sg["active_points"]["Base"]

expected_base_tags = [int(p["id"]) * 1000 + base_idx for p in base_points]
base_in_domain = sum(1 for tag in expected_base_tags if tag in set(all_tags))

print(f"\nBase story nodes: {base_in_domain}/{len(expected_base_tags)}")

if base_in_domain == len(expected_base_tags):
    print("✅ All Base nodes created successfully!")
else:
    print(f"❌ Missing {len(expected_base_tags) - base_in_domain} Base nodes!")

# Check supports
with open("out/supports.json", "r") as f:
    supports = json.load(f)

print(f"\nSupports in supports.json:")
print(f"  Total in 'applied': {len(supports['applied'])}")
print(f"  Applied via fix: {len(supports.get('applied_via_fix', []))}")
print(f"  Applied via springs: {len(supports.get('applied_via_springs', []))}")

# Check if support nodes exist in domain
support_nodes = [rec['node'] for rec in supports['applied']]
support_nodes_in_domain = sum(1 for node in support_nodes if node in set(all_tags))

print(f"\nSupport nodes in OpenSees domain: {support_nodes_in_domain}/{len(support_nodes)}")

if support_nodes_in_domain == len(support_nodes):
    print("✅ All support nodes exist in domain!")
else:
    missing_support_nodes = [n for n in support_nodes if n not in set(all_tags)]
    print(f"❌ Missing {len(missing_support_nodes)} support nodes from domain!")
    print(f"   First 5 missing: {missing_support_nodes[:5]}")

    # Check their z-coordinates from story_graph
    for tag in missing_support_nodes[:5]:
        # Decode tag
        story_idx = tag % 1000
        point_id = tag // 1000
        story_name = sg["story_order_top_to_bottom"][story_idx]

        # Find point in active_points
        for p in sg["active_points"].get(story_name, []):
            if int(p["id"]) == point_id:
                print(f"      Node {tag}: Point {point_id} @ {story_name}, z={p['z']:.3f}")
                break
