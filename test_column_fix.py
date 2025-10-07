#!/usr/bin/env python3
"""
Test script to verify Method 2 columns are now created correctly.
This should show columns connecting Base story (z=0) to elevated structure.
"""
import sys
import json

# Force clean module cache
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith('src.'):
        del sys.modules[mod_name]

from openseespy.opensees import wipe, model, getNodeTags, nodeCoord

print("=" * 80)
print("COLUMN FIX VERIFICATION TEST")
print("=" * 80)

# Build model
wipe()
model("basic", "-ndm", 3, "-ndf", 6)

from src.orchestration.MODEL_translator import build_model
print("\nBuilding model with stage='all'...")
build_model(stage='all')

# Load columns.json to check what was created
with open('out/columns.json', 'r') as f:
    cols_data = json.load(f)

with open('out/nodes.json', 'r') as f:
    nodes_data = json.load(f)

columns = cols_data.get('columns', [])
node_lookup = {n['tag']: n for n in nodes_data['nodes']}

print(f"\n📊 COLUMN STATISTICS:")
print(f"   Total columns created: {len(columns)}")

# Check for columns connecting to Base (z≈0)
columns_to_base = []
for c in columns:
    i_node = c.get('i_node')
    j_node = c.get('j_node')

    if i_node in node_lookup and j_node in node_lookup:
        z_i = node_lookup[i_node]['z']
        z_j = node_lookup[j_node]['z']

        if abs(z_i) < 0.1 or abs(z_j) < 0.1:
            columns_to_base.append((c, z_i, z_j))

print(f"   Columns connected to Base (z≈0): {len(columns_to_base)}")

if columns_to_base:
    print(f"\n✅ SUCCESS! Columns now connect to Base story")
    print(f"\nFirst 5 columns to Base:")
    for c, z_i, z_j in columns_to_base[:5]:
        tag = c.get('tag')
        i_node = c.get('i_node')
        j_node = c.get('j_node')
        print(f"   Column {tag}: node {i_node} (z={z_i:.1f}) → node {j_node} (z={z_j:.1f})")

    # Check Z-range of bottom nodes
    z_bottom = [min(z_i, z_j) for _, z_i, z_j in columns_to_base]
    z_top = [max(z_i, z_j) for _, z_i, z_j in columns_to_base]

    print(f"\n   Bottom node Z range: [{min(z_bottom):.3f}, {max(z_bottom):.3f}]")
    print(f"   Top node Z range: [{min(z_top):.3f}, {max(z_top):.3f}]")
else:
    print(f"\n❌ FAILURE! Still no columns connecting to Base")

# Check Method 2 column detection
skipped = cols_data.get('skipped', [])
method2_skips = [s for s in skipped if 'Method 2' in s]
method1_skips = [s for s in skipped if 'Method 1' in s]

print(f"\n📋 SKIPPED COLUMNS:")
print(f"   Method 1 skips: {len(method1_skips)}")
print(f"   Method 2 skips: {len(method2_skips)}")

if method2_skips:
    print(f"\n   First 3 Method 2 skips:")
    for msg in method2_skips[:3]:
        print(f"      {msg}")

print("\n" + "=" * 80)
