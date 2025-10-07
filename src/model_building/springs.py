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


def _save_json(path: str, data: Dict[str, Any]) -> None:
    """Save JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def define_spring_supports(
    story_graph_path: str = None,
    parsed_raw_path: str = None,
    supports_path: str = None,
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
    supports_path : str, optional
        Path to supports.json to check for restraints (default: "out/supports.json")
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
    if supports_path is None:
        supports_path = os.path.join(OUT_DIR, "supports.json")

    # Check files exist
    if not os.path.exists(story_graph_path):
        raise FileNotFoundError(f"story_graph.json not found at: {story_graph_path}")
    if not os.path.exists(parsed_raw_path):
        raise FileNotFoundError(f"parsed_raw.json not found at: {parsed_raw_path}")

    # Load data
    story_graph = _load_json(story_graph_path)
    parsed_raw = _load_json(parsed_raw_path)

    # Load restraints (supports.json) to avoid creating springs on fixed DOFs
    restraints = {}  # {node_tag: (ux, uy, uz, rx, ry, rz) mask}
    if os.path.exists(supports_path):
        supports_data = _load_json(supports_path)
        for rec in supports_data.get("applied", []):
            node_tag = rec.get("node")
            mask = tuple(rec.get("mask", [0,0,0,0,0,0]))
            if len(mask) == 6:
                restraints[node_tag] = mask

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
    ground_nodes_data: List[Dict[str, Any]] = []  # Track ground nodes for export
    spring_elements_data: List[Dict[str, Any]] = []  # Track spring elements for export
    spring_materials_data: List[Dict[str, Any]] = []  # Track materials for export
    ground_node_fixities: List[Dict[str, Any]] = []  # Track ground node fixities for supports.json

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

            # Create ground node for this spring at same coordinates as structural node
            ground_tag = node_tag + 9000000

            # Get coordinates from story_graph
            coords = (point_data.get("x", 0.0), point_data.get("y", 0.0), point_data.get("z", 0.0))
            _ops_node(ground_tag, *coords)

            # Record ground node data for export
            ground_nodes_data.append({
                "tag": ground_tag,
                "x": coords[0],
                "y": coords[1],
                "z": coords[2],
                "story": story_name,
                "story_index": story_index,
                "structural_node": node_tag,
                "kind": "spring_ground"
            })

            # Apply restraints to GROUND node (not the structural node!)
            # If this node has RESTRAINT in ETABS, apply it to the ground node
            if node_tag in restraints:
                restraint_mask = restraints[node_tag]
                _ops_fix(ground_tag, *restraint_mask)
                ground_node_fixities.append({
                    "node": ground_tag,
                    "mask": list(restraint_mask),
                    "source": "ETABS_restraint"
                })
                if verbose and springs_created < 3:
                    print(f"  Ground node {ground_tag}: Applied restraint mask {restraint_mask}")
            else:
                # No explicit restraint - fix all DOFs (standard spring-to-ground)
                _ops_fix(ground_tag, 1, 1, 1, 1, 1, 1)
                ground_node_fixities.append({
                    "node": ground_tag,
                    "mask": [1, 1, 1, 1, 1, 1],
                    "source": "spring_ground"
                })

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

                        # Record material for export
                        spring_materials_data.append({
                            "tag": mat_tag,
                            "type": "Elastic",
                            "E": stiffness,
                            "spring_property": springprop,
                            "dof": dof_name
                        })

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

                try:
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

                    # Record element for export
                    spring_elements_data.append({
                        "tag": element_tag,
                        "type": "zeroLength",
                        "ground_node": ground_tag,
                        "structural_node": node_tag,
                        "materials": mat_list,
                        "directions": dir_list,
                        "spring_property": springprop,
                        "story": story_name
                    })

                    if verbose and springs_created <= 5:
                        # Print first few for debugging
                        dof_str = ", ".join([f"{list(dof_map.keys())[d-1].upper()}={stiffnesses[list(dof_map.keys())[d-1]]:,.0f}"
                                            for d in dir_list])
                        print(f"  Spring {springs_created}: Structural node {node_tag} ↔ Ground node {ground_tag}")
                        print(f"    Location: ({coords[0]:.2f}, {coords[1]:.2f}, {coords[2]:.2f})")
                        print(f"    Type: {springprop}, Active DOFs: {dof_str}")
                except Exception as e:
                    print(f"  ERROR: Failed to create spring element {element_tag} for node {node_tag}: {e}")
                    continue

    if verbose:
        print(f"\n✅ Created {springs_created} spring supports")
        print(f"   Using {len(spring_types_used)} different spring types")
        if spring_types_used:
            print(f"   Most common: {max(spring_types_used, key=spring_types_used.get)} "
                  f"({spring_types_used[max(spring_types_used, key=spring_types_used.get)]} uses)")

    # Save comprehensive spring data to artifact
    springs_artifact = {
        "version": 2,  # Incremented version for new structure
        "ground_nodes": ground_nodes_data,
        "materials": spring_materials_data,
        "elements": spring_elements_data,
        "counts": {
            "ground_nodes": len(ground_nodes_data),
            "materials": len(spring_materials_data),
            "elements": len(spring_elements_data)
        }
    }
    springs_path = os.path.join(OUT_DIR, "springs.json")
    _save_json(springs_path, springs_artifact)
    if verbose:
        print(f"   Saved springs artifact: {len(ground_nodes_data)} nodes, "
              f"{len(spring_materials_data)} materials, {len(spring_elements_data)} elements")

    # Also save legacy format for backward compatibility
    ground_nodes_artifact = {
        "version": 1,
        "ground_nodes": ground_nodes_data,
        "count": len(ground_nodes_data)
    }
    ground_nodes_path = os.path.join(OUT_DIR, "spring_grounds.json")
    _save_json(ground_nodes_path, ground_nodes_artifact)

    # Append ground node fixities to supports.json
    if ground_node_fixities:
        supports_path = os.path.join(OUT_DIR, "supports.json")
        try:
            supports_data = _load_json(supports_path)
            # Append to the 'applied' list
            if 'applied' not in supports_data:
                supports_data['applied'] = []
            supports_data['applied'].extend(ground_node_fixities)
            _save_json(supports_path, supports_data)
            if verbose:
                print(f"   Appended {len(ground_node_fixities)} ground node fixities to supports.json")
        except Exception as e:
            print(f"   Warning: Could not update supports.json: {e}")

    return {
        "springs_defined": springs_created,
        "unique_spring_types": len(spring_types_used),
        "nodes_with_springs": nodes_with_springs,
        "spring_types_used": spring_types_used,
        "ground_nodes_count": len(ground_nodes_data),
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
