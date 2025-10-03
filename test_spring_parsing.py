#!/usr/bin/env python3
"""Quick test to verify spring properties parsing."""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

from src.parsing.e2k_parser import parse_e2k
from config import E2K_PATH

# Read the E2K file
with open(E2K_PATH, 'r', encoding='utf-8', errors='ignore') as f:
    e2k_text = f.read()

# Parse it
parsed = parse_e2k(e2k_text)

# Check if spring properties were parsed
spring_props = parsed.get("spring_properties", {})

print("=" * 60)
print("SPRING PROPERTIES PARSING TEST")
print("=" * 60)

if spring_props:
    print(f"\n✅ Found {len(spring_props)} spring properties:")

    # Show first 5 spring properties
    for i, (name, props) in enumerate(list(spring_props.items())[:5]):
        print(f"\n  {i+1}. {name}:")
        print(f"     UX: {props['ux']:,.0f}")
        print(f"     UY: {props['uy']:,.0f}")
        print(f"     UZ: {props['uz']:,.0f}")
        print(f"     RX: {props['rx']:,.0f}")
        print(f"     RY: {props['ry']:,.0f}")
        print(f"     RZ: {props['rz']:,.0f}")

    if len(spring_props) > 5:
        print(f"\n  ... and {len(spring_props) - 5} more")

    # Check specific spring from user's example
    if "RES_00_75cm" in spring_props:
        print("\n✅ Found user's example spring 'RES_00_75cm':")
        res_spring = spring_props["RES_00_75cm"]
        print(f"   Expected: UX=316500, UY=316500, UZ=0")
        print(f"   Parsed:   UX={res_spring['ux']}, UY={res_spring['uy']}, UZ={res_spring['uz']}")

        if (res_spring['ux'] == 316500 and
            res_spring['uy'] == 316500 and
            res_spring['uz'] == 0):
            print("   ✅ Values match perfectly!")
        else:
            print("   ❌ Values don't match!")
    else:
        print("\n❌ Could not find 'RES_00_75cm' spring")

    # Count how many point assigns have springs
    point_assigns_with_springs = [pa for pa in parsed.get("point_assigns", [])
                                   if pa.get("springprop")]
    print(f"\n✅ Found {len(point_assigns_with_springs)} point assignments with springs")

    # Show a few examples
    if point_assigns_with_springs:
        print("\n  Example point assignments with springs:")
        for i, pa in enumerate(point_assigns_with_springs[:3]):
            spring_name = pa.get("springprop")
            if spring_name in spring_props:
                spring = spring_props[spring_name]
                print(f"    {i+1}. Point {pa['point']} @ {pa['story']}: {spring_name}")
                print(f"       Stiffness: UX={spring['ux']:,.0f}, UY={spring['uy']:,.0f}, UZ={spring['uz']:,.0f}")
            else:
                print(f"    {i+1}. Point {pa['point']} @ {pa['story']}: {spring_name} (NOT FOUND IN PROPERTIES)")

else:
    print("\n❌ No spring properties found!")

print("\n" + "=" * 60)
print("PARSING VERSION INFO")
print("=" * 60)
print(f"Artifacts version: {parsed.get('_artifacts_version')}")
print(f"Springs version: {parsed.get('_springs_version')}")
print("=" * 60)
