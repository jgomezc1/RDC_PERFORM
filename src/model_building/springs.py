#!/usr/bin/env python3
"""
Define spring supports using OpenSees zeroLength elements.

Springs are defined at nodes using zeroLength elements connecting the node to
a fixed ground node. Each spring can have independent translational (UX, UY, UZ)
and rotational (RX, RY, RZ) stiffnesses.

Data sources (in order of preference):
  1. story_graph.json: Contains active_points with springprop assignments
  2. parsed_raw.json: Contains spring_properties definitions

Node tag convention:
  tag = int(point_id) * 1000 + story_index

Ground nodes for springs:
  ground_tag = node_tag + 9000000  (offset to avoid conflicts)

Element tags for springs:
  element_tag = 8000000 + node_tag  (offset to avoid conflicts with beams/columns)

Usage:
  from src.model_building.springs import define_spring_supports
  define_spring_supports()
"""
from __future__ import annotations

import json
import os
from typing import Dict, Any, List
from pathlib import Path

from openseespy.opensees import (
    node as _ops_node,
    fix as _ops_fix,
    uniaxialMaterial as _ops_uniaxial_material,
    element as _ops_element,
    getNodeTags as _ops_getNodeTags,
)

# Config
try:
    from config import OUT_DIR  # type: ignore
except Exception:
    OUT_DIR = "out"


def _load_json(path: str) -> Dict[str, Any]:
    """Load JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def define_spring_supports(
    story_graph_path: str = None,
    parsed_raw_path: str = None,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Define spring supports using zeroLength elements.

    Parameters
    ----------
    story_graph_path : str, optional
        Path to story_graph.json (default: "out/story_graph.json")
    parsed_raw_path : str, optional
        Path to parsed_raw.json (default: "out/parsed_raw.json")
    verbose : bool, optional
        Print progress messages (default: True)

    Returns
    -------
    dict
        Summary statistics:
        {
            "springs_defined": int,
            "unique_spring_types": int,
            "nodes_with_springs": list of node tags,
            "spring_types_used": dict mapping spring name to usage count
        }
    """
    # Default paths
    if story_graph_path is None:
        story_graph_path = os.path.join(OUT_DIR, "story_graph.json")
    if parsed_raw_path is None:
        parsed_raw_path = os.path.join(OUT_DIR, "parsed_raw.json")

    # Check files exist
    if not os.path.exists(story_graph_path):
        raise FileNotFoundError(f"story_graph.json not found at: {story_graph_path}")
    if not os.path.exists(parsed_raw_path):
        raise FileNotFoundError(f"parsed_raw.json not found at: {parsed_raw_path}")

    # Load data
    story_graph = _load_json(story_graph_path)
    parsed_raw = _load_json(parsed_raw_path)

    # Get spring property definitions
    spring_properties = parsed_raw.get("spring_properties", {})
    if not spring_properties:
        if verbose:
            print("No spring properties found in parsed_raw.json")
        return {
            "springs_defined": 0,
            "unique_spring_types": 0,
            "nodes_with_springs": [],
            "spring_types_used": {}
        }

    # Get existing nodes in domain
    existing_nodes = set(_ops_getNodeTags())

    # Statistics
    springs_created = 0
    nodes_with_springs = []
    spring_types_used: Dict[str, int] = {}

    # Material tag offset for spring materials
    # Start at 900000 to avoid conflicts with structural materials
    material_tag_offset = 900000
    material_tag_counter = 0
    material_tags: Dict[str, Dict[str, int]] = {}  # spring_name -> {dof: mat_tag}

    # Process each story
    story_order = story_graph.get("story_order_top_to_bottom", [])
    all_active_points = story_graph.get("active_points", {})

    if verbose:
        print(f"\nDefining spring supports...")
        print(f"Found {len(spring_properties)} spring property definitions")

    for story_index, story_name in enumerate(story_order):
        # Get active points for this story
        active_points = all_active_points.get(story_name, [])

        for point_data in active_points:
            point_id = point_data.get("id")
            springprop = point_data.get("springprop")

            if not springprop:
                continue

            # Check if spring property definition exists
            if springprop not in spring_properties:
                if verbose:
                    print(f"  Warning: Spring property '{springprop}' not found for point {point_id} @ {story_name}")
                continue

            # Calculate node tag
            try:
                node_tag = int(point_id) * 1000 + story_index
            except (ValueError, TypeError):
                if verbose:
                    print(f"  Warning: Invalid point_id '{point_id}' @ {story_name}")
                continue

            # Check if node exists
            if node_tag not in existing_nodes:
                if verbose:
                    print(f"  Warning: Node {node_tag} (point {point_id} @ {story_name}) not found in domain")
                continue

            # Get spring properties
            spring = spring_properties[springprop]
            stiffnesses = {
                "ux": spring.get("ux", 0.0),
                "uy": spring.get("uy", 0.0),
                "uz": spring.get("uz", 0.0),
                "rx": spring.get("rx", 0.0),
                "ry": spring.get("ry", 0.0),
                "rz": spring.get("rz", 0.0),
            }

            # Skip if all stiffnesses are zero
            if all(v == 0.0 for v in stiffnesses.values()):
                continue

            # Create ground node for this spring
            ground_tag = node_tag + 9000000

            # Get coordinates of the original node (we'll create ground node at same location)
            # For simplicity, create at origin since it's fixed
            _ops_node(ground_tag, 0.0, 0.0, 0.0)
            _ops_fix(ground_tag, 1, 1, 1, 1, 1, 1)  # Fix all DOFs

            # Create or reuse uniaxial materials for this spring property
            if springprop not in material_tags:
                material_tags[springprop] = {}

                # Create materials for each DOF with non-zero stiffness
                for dof_name, stiffness in stiffnesses.items():
                    if stiffness > 0:
                        mat_tag = material_tag_offset + material_tag_counter
                        material_tag_counter += 1

                        # Use Elastic material for linear spring
                        _ops_uniaxial_material("Elastic", mat_tag, stiffness)
                        material_tags[springprop][dof_name] = mat_tag

            # Get material tags for this spring
            spring_mats = material_tags[springprop]

            # Build direction and material lists for zeroLength element
            # OpenSees zeroLength: element('zeroLength', eleTag, *eleNodes, '-mat', *matTags, '-dir', *dirs)
            # Directions: 1=UX, 2=UY, 3=UZ, 4=RX, 5=RY, 6=RZ
            mat_list = []
            dir_list = []

            dof_map = {"ux": 1, "uy": 2, "uz": 3, "rx": 4, "ry": 5, "rz": 6}

            for dof_name, direction in dof_map.items():
                if dof_name in spring_mats:
                    mat_list.append(spring_mats[dof_name])
                    dir_list.append(direction)

            # Only create element if there are active springs
            if mat_list and dir_list:
                element_tag = 8000000 + node_tag

                # zeroLength element connects ground_tag to node_tag
                _ops_element(
                    "zeroLength",
                    element_tag,
                    ground_tag,
                    node_tag,
                    "-mat", *mat_list,
                    "-dir", *dir_list,
                )

                springs_created += 1
                nodes_with_springs.append(node_tag)

                # Track usage
                spring_types_used[springprop] = spring_types_used.get(springprop, 0) + 1

                if verbose and springs_created <= 5:
                    # Print first few for debugging
                    dof_str = ", ".join([f"{d}={stiffnesses[list(dof_map.keys())[d-1]]:,.0f}"
                                        for d in dir_list])
                    print(f"  Spring {springs_created}: Node {node_tag} (pt {point_id} @ {story_name})")
                    print(f"    Type: {springprop}, Stiffnesses: {dof_str}")

    if verbose:
        print(f"\n✅ Created {springs_created} spring supports")
        print(f"   Using {len(spring_types_used)} different spring types")
        if spring_types_used:
            print(f"   Most common: {max(spring_types_used, key=spring_types_used.get)} "
                  f"({spring_types_used[max(spring_types_used, key=spring_types_used.get)]} uses)")

    return {
        "springs_defined": springs_created,
        "unique_spring_types": len(spring_types_used),
        "nodes_with_springs": nodes_with_springs,
        "spring_types_used": spring_types_used,
    }


if __name__ == "__main__":
    # Standalone test - requires OpenSeesPy and existing model
    print("Testing spring support definition...")
    try:
        result = define_spring_supports(verbose=True)
        print("\nTest completed successfully!")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
