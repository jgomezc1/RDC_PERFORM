#!/usr/bin/env python3
"""
Comprehensive analysis of how springs are handled in the KOSMOS_Plat model.
"""
import json

print("=" * 80)
print("SPRING IMPLEMENTATION ANALYSIS")
print("=" * 80)

# 1. ETABS Spring Properties
with open('out/parsed_raw.json', 'r') as f:
    raw = json.load(f)

spring_props = raw.get('spring_properties', {})
print(f"\n1. SPRING PROPERTY DEFINITIONS ({len(spring_props)} types):")
print("-" * 80)

# Show RES_10 (used at Base story)
if 'RES_10' in spring_props:
    props = spring_props['RES_10']
    print(f"RES_10 (used at Base story):")
    print(f"  UX = {props.get('ux', 0):>10,.0f} kN/m")
    print(f"  UY = {props.get('uy', 0):>10,.0f} kN/m")
    print(f"  UZ = {props.get('uz', 0):>10,.0f} kN/m")
    print(f"  RX = {props.get('rx', 0):>10,.0f} kN-m/rad")
    print(f"  RY = {props.get('ry', 0):>10,.0f} kN-m/rad")
    print(f"  RZ = {props.get('rz', 0):>10,.0f} kN-m/rad")

# 2. Story Graph - Spring Assignments
with open('out/story_graph.json', 'r') as f:
    sg = json.load(f)

base_points = sg.get('active_points', {}).get('Base', [])
springs_at_base = [p for p in base_points if p.get('springprop')]

print(f"\n2. SPRING ASSIGNMENTS AT BASE STORY:")
print("-" * 80)
print(f"Total Base points: {len(base_points)}")
print(f"Points with springs: {len(springs_at_base)} (all assigned RES_10)")

# 3. OpenSees Implementation
print(f"\n3. OPENSEES IMPLEMENTATION:")
print("-" * 80)

# Check supports.json
with open('out/supports.json', 'r') as f:
    supports = json.load(f)

print(f"Supports handling:")
print(f"  Total restraints recorded: {len(supports['applied'])}")
print(f"  Applied via fix(): {len(supports.get('applied_via_fix', []))}")
print(f"  Applied via springs: {len(supports.get('applied_via_springs', []))}")

# Check actual spring elements created
print(f"\nSpring elements (zeroLength):")

# Read spring_grounds.json if it exists
try:
    with open('out/spring_grounds.json', 'r') as f:
        grounds = json.load(f)

    ground_nodes = grounds.get('ground_nodes', [])
    print(f"  Ground nodes created: {len(ground_nodes)}")

    if ground_nodes:
        # Show first Base story ground node
        base_grounds = [g for g in ground_nodes if g.get('story') == 'Base']
        if base_grounds:
            g = base_grounds[0]
            print(f"\n  Example Base ground node:")
            print(f"    Tag: {g['tag']} (structural_node + 9000000)")
            print(f"    Structural node: {g['structural_node']}")
            print(f"    Location: ({g['x']:.1f}, {g['y']:.1f}, {g['z']:.1f})")
            print(f"    Story: {g['story']}")
except FileNotFoundError:
    print(f"  ⚠️  spring_grounds.json not found")

# 4. Detailed Examples
print(f"\n4. DETAILED SPRING EXAMPLES:")
print("-" * 80)

# Find point assignments in parsed_raw
point_assigns = raw.get('point_assigns', [])

# Example 1: Base node (19)
print(f"\nEXAMPLE 1: Point 19 at Base (typical foundation node)")
print("-" * 80)

base_assign = [a for a in point_assigns if a.get('point') == '19' and a.get('story') == 'Base']
if base_assign:
    a = base_assign[0]
    print(f"ETABS Definition:")
    print(f"  Point: 19 at Story: Base")
    print(f"  Restraint: {a.get('restraint', 'None')}")
    print(f"  Spring Property: {a.get('springprop', 'None')}")

    springprop = a.get('springprop')
    if springprop and springprop in spring_props:
        props = spring_props[springprop]
        print(f"\n  {springprop} stiffness:")
        print(f"    UX = {props.get('ux', 0):>10,.0f} kN/m")
        print(f"    UY = {props.get('uy', 0):>10,.0f} kN/m")
        print(f"    UZ = {props.get('uz', 0):>10,.0f} kN/m")

    print(f"\nOpenSees Implementation:")
    print(f"  Structural Node: 19015 (tag = 19*1000 + 15)")
    print(f"    - Free node (no fix() applied)")
    print(f"    - Location: (0.0, 11.0, 0.0)")
    print(f"    - Connected to columns C58, C71, etc.")
    print(f"\n  Ground Node: 9019015 (tag = 19015 + 9000000)")
    print(f"    - Same location: (0.0, 11.0, 0.0)")
    print(f"    - Fixed: [1,1,1,1,1,1] (all DOFs)")
    print(f"\n  zeroLength Element: 8019015")
    print(f"    - Connects: Ground 9019015 ↔ Structural 19015")
    print(f"    - Active springs: UX, UY (horizontal)")
    print(f"    - Inactive DOFs (UZ,RX,RY,RZ) constrained by ground node")

# Example 2: Intermediate node (500)
print(f"\n\nEXAMPLE 2: Point 500 at 00_CimS1_m150 (intermediate node)")
print("-" * 80)

# Find point 500
pt_500_assigns = [a for a in point_assigns if a.get('point') == '500']
if pt_500_assigns:
    a = pt_500_assigns[0]
    story = a.get('story', '?')
    print(f"ETABS Definition:")
    print(f"  Point: 500 at Story: {story}")
    print(f"  Restraint: {a.get('restraint', 'None')}")
    print(f"  Spring Property: {a.get('springprop', 'None')}")
    print(f"  Diaphragm: {a.get('diaphragm', 'None')}")

    # Find in story_graph for coordinates
    for s_name, points in sg.get('active_points', {}).items():
        for p in points:
            if str(p.get('id')) == '500':
                print(f"\n  Coordinates at {s_name}:")
                print(f"    x = {p['x']:.3f}")
                print(f"    y = {p['y']:.3f}")
                print(f"    z = {p['z']:.3f}")

                story_index = sg['story_order_top_to_bottom'].index(s_name)
                node_tag = 500 * 1000 + story_index

                print(f"\nOpenSees Implementation:")
                print(f"  Node Tag: {node_tag} (500*1000 + {story_index})")

                if a.get('springprop'):
                    springprop = a.get('springprop')
                    if springprop in spring_props:
                        props = spring_props[springprop]
                        print(f"  Has Spring: {springprop}")
                        print(f"    UX = {props.get('ux', 0):>10,.0f} kN/m")
                        print(f"    UY = {props.get('uy', 0):>10,.0f} kN/m")
                        print(f"    UZ = {props.get('uz', 0):>10,.0f} kN/m")

                        ground_tag = node_tag + 9000000
                        elem_tag = 8000000 + node_tag

                        print(f"\n  Ground Node: {ground_tag}")
                        print(f"  zeroLength Element: {elem_tag}")
                        print(f"    - Connects: Ground {ground_tag} ↔ Structural {node_tag}")
                else:
                    print(f"  No springs (regular structural node)")
                    print(f"  May have diaphragm constraint: {a.get('diaphragm', 'None')}")

                break
else:
    print(f"  Point 500 not found in point_assigns")

# 5. Key Differences Summary
print(f"\n\n5. KEY DIFFERENCES BETWEEN NODE TYPES:")
print("-" * 80)
print(f"\nBase Nodes (e.g., Point 19):")
print(f"  • Have BOTH restraint AND spring properties")
print(f"  • Restraint applied to ground node")
print(f"  • Spring provides soil-structure interaction")
print(f"  • Typical for foundation supports")

print(f"\nIntermediate Nodes (e.g., Point 500):")
print(f"  • May have springs but usually NO restraints")
print(f"  • Part of column connectivity (i or j node)")
print(f"  • Springs may model intermediate soil support")
print(f"  • OR may be regular nodes with no springs")

print(f"\n6. SPRING IMPLEMENTATION VERIFICATION:")
print("-" * 80)

# Count nodes with springs at different stories
spring_counts_by_story = {}
for story_name, points in sg.get('active_points', {}).items():
    count = sum(1 for p in points if p.get('springprop'))
    if count > 0:
        spring_counts_by_story[story_name] = count

print(f"Nodes with springs by story:")
for story, count in sorted(spring_counts_by_story.items(), key=lambda x: sg['story_order_top_to_bottom'].index(x[0])):
    print(f"  {story:20s}: {count:3d} nodes")

print("\n" + "=" * 80)
