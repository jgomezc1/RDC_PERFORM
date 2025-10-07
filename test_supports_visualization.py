#!/usr/bin/env python3
"""Test if supports visualization is working correctly."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import json

# Load the actual data
print("Loading artifacts...")
with open('out/nodes.json') as f:
    nodes_data = json.load(f)
nodes_dict = {n['tag']: (n['x'], n['y'], n['z']) for n in nodes_data['nodes']}

with open('out/supports.json') as f:
    supports = json.load(f)
supports_dict = {s['node']: tuple(s['mask']) for s in supports['applied']}

with open('out/diaphragms.json') as f:
    diaphragms = json.load(f)
master_nodes = set(d['master'] for d in diaphragms['diaphragms'])

print(f"✅ Loaded {len(nodes_dict)} nodes")
print(f"✅ Loaded {len(supports_dict)} supports")
print(f"✅ Loaded {len(master_nodes)} master nodes")

# Simulate the view_utils_App._supports_traces function
def test_supports_traces(
    nodes,
    supports_by_node,
    dofs,
    size=0.25,
    exclude=None
):
    """Test support trace generation"""
    if not nodes or not supports_by_node:
        return []

    excl = set(exclude or [])

    traces_count = 0
    nodes_with_supports = 0

    for n, mask in supports_by_node.items():
        if n in excl or n not in nodes:
            continue

        nodes_with_supports += 1
        ux, uy, uz, rx, ry, rz = mask

        # Count which DOFs will be shown
        dof_count = 0
        if ux and dofs.get('UX', True):
            dof_count += 1
        if uy and dofs.get('UY', True):
            dof_count += 1
        if uz and dofs.get('UZ', True):
            dof_count += 1
        if rx and dofs.get('RX', True):
            dof_count += 1
        if ry and dofs.get('RY', True):
            dof_count += 1
        if rz and dofs.get('RZ', True):
            dof_count += 1

        traces_count += dof_count

    return traces_count, nodes_with_supports

# Test with all DOFs enabled
dofs_all = {"UX": True, "UY": True, "UZ": True, "RX": True, "RY": True, "RZ": True}
traces, nodes_shown = test_supports_traces(
    nodes=nodes_dict,
    supports_by_node=supports_dict,
    dofs=dofs_all,
    size=0.25,
    exclude=master_nodes
)

print(f"\n✅ Test Results:")
print(f"   Nodes with supports (excluding masters): {nodes_shown}")
print(f"   Expected traces (DOFs × nodes): {traces}")

# Check specific node
test_node = 19015
if test_node in supports_dict:
    print(f"\n✅ Sample node {test_node}:")
    print(f"   Coordinates: {nodes_dict.get(test_node, 'NOT FOUND')}")
    print(f"   Mask: {supports_dict[test_node]}")
    print(f"   Is master: {test_node in master_nodes}")

# Check if supports are at the base
base_story_nodes = [tag for tag in supports_dict.keys() if tag % 1000 == 15]
print(f"\n✅ Supports at story index 15 (Base): {len(base_story_nodes)}")

# Check if we're filtering them out somehow
all_nodes_at_z0 = [tag for tag, (x,y,z) in nodes_dict.items() if abs(z) < 0.01]
supports_at_z0 = [tag for tag in supports_dict.keys() if tag in all_nodes_at_z0]
print(f"✅ All nodes at z≈0: {len(all_nodes_at_z0)}")
print(f"✅ Supports at z≈0: {len(supports_at_z0)}")

# Now import the actual visualization function to test
print("\n" + "="*60)
print("Testing actual view_utils_App function...")
print("="*60)

try:
    sys.path.insert(0, 'apps')
    from view_utils_App import _supports_traces

    actual_traces = _supports_traces(
        nodes=nodes_dict,
        supports_by_node=supports_dict,
        dofs=dofs_all,
        size=0.25,
        exclude=master_nodes
    )

    print(f"✅ Generated {len(actual_traces)} trace objects")

    # Check trace details
    for i, trace in enumerate(actual_traces[:3]):
        print(f"   Trace {i}: {trace.name if hasattr(trace, 'name') else 'unnamed'}")
        if hasattr(trace, 'x'):
            num_points = len([x for x in trace.x if x is not None])
            print(f"      Points: {num_points}")

except Exception as e:
    print(f"❌ Error loading actual function: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("CONCLUSION")
print("="*60)

if nodes_shown == len(supports_dict):
    print("✅ All supports should be visible (no masters overlap)")
    print(f"   Expected to see {traces} support markers in the 3D view")
else:
    print(f"⚠️  Some supports may be filtered: {nodes_shown}/{len(supports_dict)}")
