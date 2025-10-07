#!/usr/bin/env python3
"""
Step-by-step test to find where nodes are deleted.
"""
import sys

# Force clean module cache
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith('src.'):
        del sys.modules[mod_name]

from openseespy.opensees import wipe, model, getNodeTags

print("=" * 80)
print("STEP-BY-STEP NODE TRACKING TEST")
print("=" * 80)

wipe()
model("basic", "-ndm", 3, "-ndf", 6)

print("\n--- STEP 1: define_nodes() ---")
from src.model_building.nodes import define_nodes
define_nodes()
count_1 = len(getNodeTags())
print(f">>> Node count after define_nodes(): {count_1}")

print("\n--- STEP 2: define_point_restraints_from_e2k() ---")
from src.model_building.supports import define_point_restraints_from_e2k
define_point_restraints_from_e2k()
count_2 = len(getNodeTags())
print(f">>> Node count after restraints: {count_2}")
if count_2 != count_1:
    print(f"!!! NODES CHANGED: {count_2 - count_1:+d}")

print("\n--- STEP 3: define_spring_supports() ---")
from src.model_building.springs import define_spring_supports
define_spring_supports(verbose=True)
count_3 = len(getNodeTags())
print(f">>> Node count after springs: {count_3}")
if count_3 != count_2:
    print(f"!!! NODES CHANGED: {count_3 - count_2:+d}")

print("\n--- STEP 4: define_rigid_diaphragms() ---")
from src.model_building.diaphragms import define_rigid_diaphragms
define_rigid_diaphragms()
count_4 = len(getNodeTags())
print(f">>> Node count after diaphragms: {count_4}")
if count_4 != count_3:
    print(f"!!! NODES CHANGED: {count_4 - count_3:+d}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"After define_nodes():     {count_1}")
print(f"After restraints:         {count_2} ({count_2-count_1:+d})")
print(f"After springs:            {count_3} ({count_3-count_2:+d})")
print(f"After diaphragms:         {count_4} ({count_4-count_3:+d})")
print(f"\nFinal node count: {count_4}")
print(f"Expected:         4717")
print(f"Difference:       {count_4 - 4717}")

if count_4 == 4717:
    print("\n✅ SUCCESS: All nodes present!")
else:
    print(f"\n❌ FAILURE: Missing {4717 - count_4} nodes")

    # Find which step lost nodes
    if count_1 < 4717:
        print("   Nodes lost in: define_nodes()")
    elif count_2 < count_1:
        print("   Nodes lost in: define_point_restraints_from_e2k()")
    elif count_3 < count_2:
        print("   Nodes lost in: define_spring_supports()")
    elif count_4 < count_3:
        print("   Nodes lost in: define_rigid_diaphragms()")
