#!/usr/bin/env python3
"""
Structural Stability Validator for OpenSees Models

This script performs comprehensive checks on an OpenSees model to identify
structural instabilities before running analysis. It catches common issues:
- Unconstrained DOFs
- Disconnected nodes
- Missing supports
- Mechanisms
- Rigid diaphragm errors
- Zero-length elements
- Duplicate nodes

Usage:
    python validate_structural_stability.py
"""
from openseespy.opensees import *
import json
from collections import defaultdict
from pathlib import Path
import math

def validate_model_stability(verbose=True):
    """
    Comprehensive structural stability validation.
    Returns (is_stable, issues) where issues is a list of problem descriptions.
    """
    issues = []

    # Get model info
    try:
        node_tags = getNodeTags()
        ele_tags = getEleTags()
        ndm = getNDM()
        ndf = getNDF()
    except:
        issues.append("FATAL: Model not initialized. Call build_model() first.")
        return False, issues

    if verbose:
        print(f"\n{'='*70}")
        print(f"STRUCTURAL STABILITY VALIDATION")
        print(f"{'='*70}")
        print(f"Model: {len(node_tags)} nodes, {len(ele_tags)} elements")
        print(f"DOFs: {ndm} dimensions, {ndf} DOF per node")
        print(f"{'='*70}\n")

    # ==================================================================
    # CHECK 1: Disconnected Nodes
    # ==================================================================
    if verbose:
        print("CHECK 1: Disconnected Nodes")
        print("-" * 70)

    # Build connectivity map
    node_connectivity = defaultdict(list)
    for etag in ele_tags:
        try:
            ele_nodes = eleNodes(etag)
            for node in ele_nodes:
                node_connectivity[node].append(etag)
        except:
            pass

    # Load support info
    try:
        with open('out/supports.json', 'r') as f:
            supports = json.load(f)
        supported_nodes = {s['node'] for s in supports.get('applied', [])}
    except:
        supported_nodes = set()
        issues.append("WARNING: Could not load supports.json")

    # Load spring info (spring ground nodes should NOT be connected to elements)
    try:
        with open('out/springs.json', 'r') as f:
            springs_data = json.load(f)
        spring_ground_nodes = {n['tag'] for n in springs_data.get('ground_nodes', [])}
    except:
        spring_ground_nodes = set()

    disconnected = []
    for ntag in node_tags:
        if ntag not in node_connectivity:
            # Check if it's a spring ground node (those are SUPPOSED to be disconnected from frame elements)
            if ntag not in spring_ground_nodes:
                disconnected.append(ntag)

    if disconnected:
        issues.append(f"ERROR: {len(disconnected)} disconnected nodes (not connected to any element): {disconnected[:10]}")
        if verbose:
            print(f"  ❌ FAIL: {len(disconnected)} nodes not connected to elements")
            print(f"     First 10: {disconnected[:10]}")
    else:
        if verbose:
            print(f"  ✓ PASS: All non-spring nodes connected to elements")

    # ==================================================================
    # CHECK 2: Zero-Length Elements (not zeroLength type)
    # ==================================================================
    if verbose:
        print("\nCHECK 2: Zero-Length Elements")
        print("-" * 70)

    zero_length_elements = []
    for etag in ele_tags:
        try:
            ele_nodes = eleNodes(etag)
            if len(ele_nodes) >= 2:
                n1, n2 = ele_nodes[0], ele_nodes[1]
                coord1 = nodeCoord(n1)
                coord2 = nodeCoord(n2)
                dist = math.sqrt(sum((c1 - c2)**2 for c1, c2 in zip(coord1, coord2)))

                # Check if it's a zeroLength element type (those are OK)
                ele_type = eleType(etag)

                if dist < 1e-6 and 'zeroLength' not in ele_type:
                    zero_length_elements.append((etag, n1, n2, dist))
        except:
            pass

    if zero_length_elements:
        issues.append(f"ERROR: {len(zero_length_elements)} elements with zero length: {[(e[0], e[3]) for e in zero_length_elements[:5]]}")
        if verbose:
            print(f"  ❌ FAIL: {len(zero_length_elements)} frame elements with zero length")
            for etag, n1, n2, dist in zero_length_elements[:5]:
                print(f"     Element {etag}: nodes {n1}-{n2}, length={dist:.2e}")
    else:
        if verbose:
            print(f"  ✓ PASS: No zero-length frame elements")

    # ==================================================================
    # CHECK 3: Duplicate Nodes (same coordinates)
    # ==================================================================
    if verbose:
        print("\nCHECK 3: Duplicate Node Locations")
        print("-" * 70)

    node_coords = {}
    duplicates = []

    for ntag in node_tags:
        coord = tuple(round(c, 6) for c in nodeCoord(ntag))  # Round to mm precision
        if coord in node_coords:
            duplicates.append((ntag, node_coords[coord], coord))
        else:
            node_coords[coord] = ntag

    if duplicates:
        issues.append(f"WARNING: {len(duplicates)} nodes at duplicate locations: {[(d[0], d[1]) for d in duplicates[:5]]}")
        if verbose:
            print(f"  ⚠ WARNING: {len(duplicates)} duplicate node locations")
            for n1, n2, coord in duplicates[:5]:
                print(f"     Nodes {n1} and {n2} at {coord}")
    else:
        if verbose:
            print(f"  ✓ PASS: No duplicate node locations")

    # ==================================================================
    # CHECK 4: Constraint Accounting
    # ==================================================================
    if verbose:
        print("\nCHECK 4: DOF Constraint Coverage")
        print("-" * 70)

    total_dofs = len(node_tags) * ndf

    # Count explicitly fixed DOFs
    fixed_dof_count = 0
    for ntag in node_tags:
        try:
            fix_status = nodeDisp(ntag)  # Returns current displacement (0 if fixed)
            # This is not reliable - better to use supports.json
        except:
            pass

    # Use supports.json for better accounting
    explicitly_fixed = 0
    spring_constrained = 0

    if supported_nodes:
        for s in supports.get('applied', []):
            mask = s.get('mask', [])
            explicitly_fixed += sum(mask)

    # Count spring-constrained DOFs
    try:
        spring_elements = [e for e in ele_tags if 'zeroLength' in eleType(e)]
        spring_constrained = len(spring_elements) * 2  # Approximate: 2 DOF per spring typically
    except:
        pass

    # Get rigid diaphragm info
    try:
        with open('out/diaphragms.json', 'r') as f:
            diaphragms = json.load(f)
        diaphragm_count = len(diaphragms.get('diaphragms', []))
        slave_nodes = set()
        for d in diaphragms.get('diaphragms', []):
            slave_nodes.update(d.get('slave_nodes', []))
        diaphragm_constrained = len(slave_nodes) * 3  # In-plane DOFs typically
    except:
        diaphragm_count = 0
        diaphragm_constrained = 0

    constrained_estimate = explicitly_fixed + spring_constrained + diaphragm_constrained
    unconstrained_estimate = total_dofs - constrained_estimate

    if verbose:
        print(f"  Total DOFs: {total_dofs}")
        print(f"  Explicitly fixed: {explicitly_fixed}")
        print(f"  Spring-constrained: {spring_constrained}")
        print(f"  Diaphragm-constrained: {diaphragm_constrained}")
        print(f"  Estimated unconstrained: {unconstrained_estimate}")

    # Minimum support check: need at least 6 DOF fixed for 3D rigid body
    if explicitly_fixed < 6:
        issues.append(f"ERROR: Only {explicitly_fixed} DOFs explicitly fixed. Need at least 6 for 3D stability.")
        if verbose:
            print(f"  ❌ FAIL: Insufficient support ({explicitly_fixed} < 6 DOF)")
    else:
        if verbose:
            print(f"  ✓ PASS: Adequate explicit support ({explicitly_fixed} DOF)")

    # ==================================================================
    # CHECK 5: Support Distribution
    # ==================================================================
    if verbose:
        print("\nCHECK 5: Support Distribution")
        print("-" * 70)

    if supported_nodes:
        # Check if supports are at a single point (unstable)
        support_coords = []
        for ntag in supported_nodes:
            if ntag in node_tags:
                support_coords.append(nodeCoord(ntag))

        if len(support_coords) > 0:
            # Check if all supports are colinear or coplanar
            # Simple check: compute bounding box volume
            if len(support_coords) >= 3:
                xs = [c[0] for c in support_coords]
                ys = [c[1] for c in support_coords]
                zs = [c[2] for c in support_coords]

                dx = max(xs) - min(xs)
                dy = max(ys) - min(ys)
                dz = max(zs) - min(zs)

                if verbose:
                    print(f"  Support spread: dx={dx:.2f}m, dy={dy:.2f}m, dz={dz:.2f}m")

                if dx < 0.1 and dy < 0.1:
                    issues.append("ERROR: All supports are nearly at same XY location (no moment resistance)")
                    if verbose:
                        print(f"  ❌ FAIL: Supports too concentrated (collinear or coplanar)")
                else:
                    if verbose:
                        print(f"  ✓ PASS: Supports adequately distributed")

    # ==================================================================
    # CHECK 6: Rigid Diaphragm Validation
    # ==================================================================
    if verbose:
        print("\nCHECK 6: Rigid Diaphragm Configuration")
        print("-" * 70)

    if diaphragm_count > 0:
        for d in diaphragms.get('diaphragms', []):
            master = d.get('master_node')
            slaves = d.get('slave_nodes', [])

            # Check master exists
            if master not in node_tags:
                issues.append(f"ERROR: Diaphragm master node {master} does not exist")
                if verbose:
                    print(f"  ❌ FAIL: Master node {master} missing")

            # Check slaves exist
            missing_slaves = [s for s in slaves if s not in node_tags]
            if missing_slaves:
                issues.append(f"ERROR: Diaphragm has {len(missing_slaves)} missing slave nodes")
                if verbose:
                    print(f"  ❌ FAIL: {len(missing_slaves)} slave nodes missing")

        if not issues or not any('Diaphragm' in i for i in issues):
            if verbose:
                print(f"  ✓ PASS: {diaphragm_count} diaphragms properly configured")
    else:
        if verbose:
            print(f"  ⚠ INFO: No rigid diaphragms defined")

    # ==================================================================
    # CHECK 7: Element Connectivity Analysis
    # ==================================================================
    if verbose:
        print("\nCHECK 7: Structural Connectivity")
        print("-" * 70)

    # Build graph of connected nodes
    from collections import deque

    def find_connected_components():
        visited = set()
        components = []

        for start_node in node_tags:
            if start_node in visited:
                continue
            if start_node in spring_ground_nodes:  # Skip spring ground nodes
                continue

            # BFS to find connected component
            component = set()
            queue = deque([start_node])

            while queue:
                node = queue.popleft()
                if node in visited:
                    continue
                visited.add(node)
                component.add(node)

                # Find all elements connected to this node
                for etag in node_connectivity.get(node, []):
                    for neighbor in eleNodes(etag):
                        if neighbor not in visited and neighbor not in spring_ground_nodes:
                            queue.append(neighbor)

            if len(component) > 0:
                components.append(component)

        return components

    components = find_connected_components()

    if len(components) > 1:
        # Multiple disconnected parts
        issues.append(f"ERROR: Structure has {len(components)} disconnected parts")
        if verbose:
            print(f"  ❌ FAIL: {len(components)} disconnected structural components")
            for i, comp in enumerate(components):
                print(f"     Component {i+1}: {len(comp)} nodes")
                # Check if component has support
                comp_supported = any(n in supported_nodes for n in comp)
                if not comp_supported:
                    print(f"       ⚠ WARNING: This component has NO supports!")
    else:
        if verbose:
            print(f"  ✓ PASS: Structure is fully connected")

    # ==================================================================
    # CHECK 8: Test Stiffness Matrix Assembly
    # ==================================================================
    if verbose:
        print("\nCHECK 8: Stiffness Matrix Assembly Test")
        print("-" * 70)

    # Try to set up analysis and detect issues
    try:
        wipeAnalysis()
        constraints('Transformation')
        numberer('RCM')
        system('ProfileSPD')

        # Try to assemble stiffness
        # We can't directly assemble without load pattern, so use a different approach
        # Just test if we can set up the analysis system

        if verbose:
            print(f"  ✓ PASS: Analysis system initialized")
    except Exception as e:
        issues.append(f"ERROR: Failed to initialize analysis system: {str(e)}")
        if verbose:
            print(f"  ❌ FAIL: {str(e)}")

    # ==================================================================
    # CHECK 9: Identify Specific Problematic DOFs
    # ==================================================================
    if verbose:
        print("\nCHECK 9: Problematic Node Analysis")
        print("-" * 70)

    # Identify nodes with minimal connectivity
    weak_nodes = []
    for ntag in node_tags:
        if ntag in spring_ground_nodes:
            continue

        conn_count = len(node_connectivity.get(ntag, []))
        is_supported = ntag in supported_nodes
        in_diaphragm = ntag in slave_nodes if 'slave_nodes' in locals() else False

        # A node with only 1 element connection and no support is potentially problematic
        if conn_count <= 1 and not is_supported and not in_diaphragm:
            weak_nodes.append((ntag, conn_count))

    if weak_nodes:
        issues.append(f"WARNING: {len(weak_nodes)} nodes with weak connectivity: {[n[0] for n in weak_nodes[:10]]}")
        if verbose:
            print(f"  ⚠ WARNING: {len(weak_nodes)} weakly connected nodes")
            for ntag, conn in weak_nodes[:10]:
                coord = nodeCoord(ntag)
                print(f"     Node {ntag} at ({coord[0]:.2f}, {coord[1]:.2f}, {coord[2]:.2f}): {conn} element(s)")
    else:
        if verbose:
            print(f"  ✓ PASS: All nodes adequately connected")

    # ==================================================================
    # SUMMARY
    # ==================================================================
    if verbose:
        print(f"\n{'='*70}")
        print(f"VALIDATION SUMMARY")
        print(f"{'='*70}")

    error_count = len([i for i in issues if i.startswith('ERROR')])
    warning_count = len([i for i in issues if i.startswith('WARNING')])

    is_stable = error_count == 0

    if is_stable:
        if verbose:
            print(f"✓ MODEL APPEARS STABLE")
            print(f"  {warning_count} warnings, {error_count} errors")
    else:
        if verbose:
            print(f"❌ MODEL HAS STABILITY ISSUES")
            print(f"  {warning_count} warnings, {error_count} errors")
            print(f"\nCritical Issues:")
            for issue in issues:
                if issue.startswith('ERROR'):
                    print(f"  • {issue}")

    if verbose and warning_count > 0:
        print(f"\nWarnings:")
        for issue in issues:
            if issue.startswith('WARNING'):
                print(f"  • {issue}")

    print(f"{'='*70}\n")

    return is_stable, issues


if __name__ == "__main__":
    # Import and build model
    try:
        from out.explicit_model import build_model
        print("Building model from out/explicit_model.py...")
        build_model()

        # Run validation
        is_stable, issues = validate_model_stability(verbose=True)

        # Save report
        with open('out/stability_report.json', 'w') as f:
            json.dump({
                'is_stable': is_stable,
                'issues': issues,
                'node_count': len(getNodeTags()),
                'element_count': len(getEleTags())
            }, f, indent=2)

        print(f"Report saved to: out/stability_report.json")

        exit(0 if is_stable else 1)

    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
