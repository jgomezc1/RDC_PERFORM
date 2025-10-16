#!/usr/bin/env python3
"""
Static Model Validator - Analyzes OpenSees model WITHOUT running it

Parses the explicit_model.py and artifact JSON files to detect structural issues
without requiring openseespy to be installed.
"""
import json
import re
import math
from collections import defaultdict, deque
from pathlib import Path


def load_artifacts():
    """Load all artifact files"""
    artifacts = {}
    artifact_files = ['nodes.json', 'beams.json', 'columns.json', 'supports.json', 'springs.json', 'diaphragms.json']

    for filename in artifact_files:
        filepath = Path('out') / filename
        if filepath.exists():
            with open(filepath, 'r') as f:
                artifacts[filename.replace('.json', '')] = json.load(f)
        else:
            print(f"⚠ WARNING: {filename} not found")
            artifacts[filename.replace('.json', '')] = {}

    return artifacts


def parse_explicit_model(filepath='out/explicit_model.py'):
    """Parse explicit_model.py to extract nodes and elements"""
    with open(filepath, 'r') as f:
        content = f.read()

    # Parse nodes: node(tag, x, y, z)
    nodes = {}
    for match in re.finditer(r"node\((\d+),\s*([-\d.e+]+),\s*([-\d.e+]+),\s*([-\d.e+]+)\)", content):
        tag = int(match.group(1))
        x, y, z = float(match.group(2)), float(match.group(3)), float(match.group(4))
        nodes[tag] = (x, y, z)

    # Parse elements: element('elasticBeamColumn', tag, i_node, j_node, ...)
    elements = []
    for match in re.finditer(r"element\('elasticBeamColumn',\s*(\d+),\s*(\d+),\s*(\d+),", content):
        etag = int(match.group(1))
        i_node = int(match.group(2))
        j_node = int(match.group(3))
        elements.append((etag, i_node, j_node))

    # Parse zeroLength elements: element('zeroLength', tag, i_node, j_node, ...)
    zero_length_elements = []
    for match in re.finditer(r"element\('zeroLength',\s*(\d+),\s*(\d+),\s*(\d+),", content):
        etag = int(match.group(1))
        i_node = int(match.group(2))
        j_node = int(match.group(3))
        zero_length_elements.append((etag, i_node, j_node))

    # Parse fix commands: fix(node, dof1, dof2, ...)
    fixed_nodes = {}
    for match in re.finditer(r"fix\((\d+),\s*(.*?)\)", content):
        ntag = int(match.group(1))
        dofs = [int(d.strip()) for d in match.group(2).split(',')]
        fixed_nodes[ntag] = dofs

    # Parse rigidDiaphragm commands
    diaphragms = []
    for match in re.finditer(r"rigidDiaphragm\((.*?),\s*(\d+),\s*\[(.*?)\]", content):
        plane = match.group(1).strip("'\"")
        master = int(match.group(2))
        slaves = [int(s.strip()) for s in match.group(3).split(',')]
        diaphragms.append({'plane': plane, 'master': master, 'slaves': slaves})

    return {
        'nodes': nodes,
        'elements': elements,
        'zero_length_elements': zero_length_elements,
        'fixed_nodes': fixed_nodes,
        'diaphragms': diaphragms
    }


def validate_model():
    """Main validation function"""
    print(f"\n{'='*70}")
    print(f"STATIC STRUCTURAL STABILITY VALIDATION")
    print(f"{'='*70}\n")

    # Load data
    print("Loading artifacts and model...")
    artifacts = load_artifacts()
    model = parse_explicit_model()

    nodes = model['nodes']
    elements = model['elements']
    zero_length_elements = model['zero_length_elements']
    fixed_nodes = model['fixed_nodes']
    diaphragms = model['diaphragms']

    print(f"Model loaded: {len(nodes)} nodes, {len(elements)} frame elements, {len(zero_length_elements)} springs")
    print(f"{'='*70}\n")

    issues = []

    # =================================================================
    # CHECK 1: Disconnected Nodes
    # =================================================================
    print("CHECK 1: Disconnected Nodes")
    print("-" * 70)

    # Build connectivity map
    node_connectivity = defaultdict(set)
    for etag, i_node, j_node in elements:
        node_connectivity[i_node].add(etag)
        node_connectivity[j_node].add(etag)

    # Get spring structural nodes (these connect to springs, not frame elements)
    spring_structural_nodes = set()
    spring_ground_nodes = set()
    if 'springs' in artifacts:
        for elem in artifacts['springs'].get('elements', []):
            spring_structural_nodes.add(elem.get('structural_node'))
        for gn in artifacts['springs'].get('ground_nodes', []):
            spring_ground_nodes.add(gn.get('tag'))

    # Find disconnected nodes
    disconnected = []
    for ntag in nodes:
        if ntag not in node_connectivity:
            # Check if it's a spring ground node (expected to be disconnected from frames)
            if ntag not in spring_ground_nodes:
                # Check if it's a spring structural node (connects via spring only)
                if ntag not in spring_structural_nodes:
                    disconnected.append(ntag)

    if disconnected:
        issues.append(f"ERROR: {len(disconnected)} nodes completely disconnected")
        print(f"  ❌ FAIL: {len(disconnected)} nodes not connected to ANY elements")
        print(f"     Node tags: {sorted(disconnected)[:20]}")
        for ntag in disconnected[:5]:
            coord = nodes[ntag]
            print(f"       Node {ntag} at ({coord[0]:.2f}, {coord[1]:.2f}, {coord[2]:.2f})")
    else:
        print(f"  ✓ PASS: All structural nodes connected")

    # =================================================================
    # CHECK 2: Zero-Length Frame Elements
    # =================================================================
    print("\nCHECK 2: Zero-Length Frame Elements")
    print("-" * 70)

    zero_length_frames = []
    for etag, i_node, j_node in elements:
        if i_node in nodes and j_node in nodes:
            coord_i = nodes[i_node]
            coord_j = nodes[j_node]
            dist = math.sqrt(sum((ci - cj)**2 for ci, cj in zip(coord_i, coord_j)))

            if dist < 1e-6:  # Less than 1 micron
                zero_length_frames.append((etag, i_node, j_node, dist))

    if zero_length_frames:
        issues.append(f"ERROR: {len(zero_length_frames)} frame elements with zero length")
        print(f"  ❌ FAIL: {len(zero_length_frames)} elasticBeamColumn elements with zero length")
        for etag, i, j, dist in zero_length_frames[:10]:
            print(f"       Element {etag}: nodes {i}-{j}, length={dist:.2e}m")
    else:
        print(f"  ✓ PASS: No zero-length frame elements")

    # =================================================================
    # CHECK 3: Duplicate Node Locations
    # =================================================================
    print("\nCHECK 3: Duplicate Node Locations")
    print("-" * 70)

    coord_to_nodes = defaultdict(list)
    for ntag, coord in nodes.items():
        rounded_coord = tuple(round(c, 6) for c in coord)  # Round to micron
        coord_to_nodes[rounded_coord].append(ntag)

    duplicates = {coord: ntags for coord, ntags in coord_to_nodes.items() if len(ntags) > 1}

    if duplicates:
        issues.append(f"WARNING: {len(duplicates)} locations with duplicate nodes")
        print(f"  ⚠ WARNING: {len(duplicates)} locations have multiple nodes")
        for coord, ntags in list(duplicates.items())[:10]:
            print(f"       At ({coord[0]:.2f}, {coord[1]:.2f}, {coord[2]:.2f}): nodes {ntags}")
    else:
        print(f"  ✓ PASS: No duplicate node locations")

    # =================================================================
    # CHECK 4: Support Analysis
    # =================================================================
    print("\nCHECK 4: Support Coverage")
    print("-" * 70)

    # Count fixed DOFs
    total_fixed_dofs = 0
    supported_nodes = set()

    for ntag, dofs in fixed_nodes.items():
        total_fixed_dofs += sum(dofs)
        if sum(dofs) > 0:
            supported_nodes.add(ntag)

    # Add spring supports
    spring_supported_nodes = spring_structural_nodes

    # Count spring DOFs (typically 2 per spring: ux and uy)
    spring_dofs = len(zero_length_elements) * 2

    total_support_dofs = total_fixed_dofs + spring_dofs

    print(f"  Fixed DOFs: {total_fixed_dofs}")
    print(f"  Spring DOFs: {spring_dofs}")
    print(f"  Total support DOFs: {total_support_dofs}")
    print(f"  Supported nodes (fixed): {len(supported_nodes)}")
    print(f"  Supported nodes (springs): {len(spring_supported_nodes)}")

    if total_fixed_dofs < 6:
        issues.append(f"ERROR: Only {total_fixed_dofs} fixed DOFs - need at least 6 for 3D stability")
        print(f"  ❌ FAIL: Insufficient fixed supports ({total_fixed_dofs} < 6)")
    else:
        print(f"  ✓ PASS: Adequate support")

    # Check support distribution
    if supported_nodes:
        support_coords = [nodes[n] for n in supported_nodes if n in nodes]
        if len(support_coords) >= 2:
            xs = [c[0] for c in support_coords]
            ys = [c[1] for c in support_coords]
            zs = [c[2] for c in support_coords]

            dx = max(xs) - min(xs)
            dy = max(ys) - min(ys)
            dz = max(zs) - min(zs)

            print(f"  Support spread: Δx={dx:.2f}m, Δy={dy:.2f}m, Δz={dz:.2f}m")

            if dx < 0.1 and dy < 0.1:
                issues.append("ERROR: All fixed supports concentrated at nearly same XY location")
                print(f"  ❌ FAIL: Supports too concentrated (no moment resistance)")

    # =================================================================
    # CHECK 5: Structural Connectivity (Disconnected Parts)
    # =================================================================
    print("\nCHECK 5: Structural Connectivity")
    print("-" * 70)

    def find_connected_components(nodes_set, element_list):
        """BFS to find connected components"""
        visited = set()
        components = []

        # Build adjacency for frame elements only
        adjacency = defaultdict(set)
        for _, i_node, j_node in element_list:
            if i_node in nodes_set and j_node in nodes_set:
                adjacency[i_node].add(j_node)
                adjacency[j_node].add(i_node)

        for start_node in nodes_set:
            if start_node in visited:
                continue
            if start_node in spring_ground_nodes:  # Skip spring ground nodes
                continue

            # BFS
            component = set()
            queue = deque([start_node])

            while queue:
                node = queue.popleft()
                if node in visited:
                    continue
                visited.add(node)
                component.add(node)

                for neighbor in adjacency[node]:
                    if neighbor not in visited:
                        queue.append(neighbor)

            if len(component) > 0:
                components.append(component)

        return components

    # Find components in frame structure
    frame_nodes = set(nodes.keys()) - spring_ground_nodes
    components = find_connected_components(frame_nodes, elements)

    if len(components) > 1:
        issues.append(f"ERROR: Structure has {len(components)} disconnected parts")
        print(f"  ❌ FAIL: {len(components)} disconnected structural components detected")

        for i, comp in enumerate(components):
            comp_supported = any(n in supported_nodes or n in spring_supported_nodes for n in comp)
            print(f"     Component {i+1}: {len(comp)} nodes, supported: {comp_supported}")

            if not comp_supported:
                issues.append(f"ERROR: Component {i+1} has NO supports")
                print(f"       ⚠ This component is completely floating!")

                # Show some node coordinates from this component
                sample_nodes = list(comp)[:3]
                for n in sample_nodes:
                    if n in nodes:
                        coord = nodes[n]
                        print(f"          Node {n}: ({coord[0]:.2f}, {coord[1]:.2f}, {coord[2]:.2f})")
    else:
        print(f"  ✓ PASS: Structure is fully connected ({len(components)} component)")

    # =================================================================
    # CHECK 6: Rigid Diaphragm Validation
    # =================================================================
    print("\nCHECK 6: Rigid Diaphragm Configuration")
    print("-" * 70)

    if diaphragms:
        print(f"  Found {len(diaphragms)} rigid diaphragms")

        for i, d in enumerate(diaphragms):
            master = d['master']
            slaves = d['slaves']

            # Check master exists
            if master not in nodes:
                issues.append(f"ERROR: Diaphragm {i} master node {master} does not exist")
                print(f"  ❌ Diaphragm {i}: Master node {master} MISSING")

            # Check slaves exist
            missing_slaves = [s for s in slaves if s not in nodes]
            if missing_slaves:
                issues.append(f"ERROR: Diaphragm {i} has {len(missing_slaves)} missing slave nodes")
                print(f"  ❌ Diaphragm {i}: {len(missing_slaves)}/{len(slaves)} slaves MISSING")
            else:
                print(f"  ✓ Diaphragm {i}: master={master}, {len(slaves)} slaves OK")
    else:
        print(f"  ⚠ INFO: No rigid diaphragms found")

    # =================================================================
    # CHECK 7: Weak Connectivity
    # =================================================================
    print("\nCHECK 7: Weak Node Connectivity")
    print("-" * 70)

    # Check for nodes connected to only 1 element
    slave_nodes = set()
    for d in diaphragms:
        slave_nodes.update(d['slaves'])

    weak_nodes = []
    for ntag in nodes:
        if ntag in spring_ground_nodes:
            continue

        conn_count = len(node_connectivity[ntag])
        is_supported = ntag in supported_nodes or ntag in spring_supported_nodes
        in_diaphragm = ntag in slave_nodes

        if conn_count == 1 and not is_supported and not in_diaphragm:
            weak_nodes.append((ntag, conn_count))

    if weak_nodes:
        issues.append(f"WARNING: {len(weak_nodes)} nodes with single element connection and no support")
        print(f"  ⚠ WARNING: {len(weak_nodes)} potentially unstable nodes")
        for ntag, conn in weak_nodes[:10]:
            coord = nodes[ntag]
            print(f"       Node {ntag} at ({coord[0]:.2f}, {coord[1]:.2f}, {coord[2]:.2f}): {conn} element")
    else:
        print(f"  ✓ PASS: All nodes adequately connected or supported")

    # =================================================================
    # CHECK 8: Analysis of Specific Problem Areas
    # =================================================================
    print("\nCHECK 8: Problem Area Analysis")
    print("-" * 70)

    # If we know a specific DOF is problematic (like DOF 702), analyze it
    # DOF numbering in OpenSees: DOF = (node_internal_number - 1) * 6 + dof_local
    # But node numbering is assigned by numberer, so we can't directly map back

    # Instead, look for patterns that commonly cause issues
    problematic_patterns = []

    # Pattern 1: Nodes with only vertical elements (columns) and no lateral restraint
    for ntag, connected_eles in node_connectivity.items():
        if ntag in spring_ground_nodes or ntag in slave_nodes:
            continue

        if len(connected_eles) >= 2:
            # Check if all elements are vertical (same X,Y coordinates)
            coords_i = [nodes.get(ntag, (0, 0, 0))]
            coords_j = []

            for etag in list(connected_eles)[:10]:  # Check first 10 elements
                # Find the element
                for e_tag, e_i, e_j in elements:
                    if e_tag == etag:
                        other_node = e_j if e_i == ntag else e_i
                        if other_node in nodes:
                            coords_j.append(nodes[other_node])
                        break

            # Check if all connections are vertical
            node_xy = (nodes[ntag][0], nodes[ntag][1])
            all_vertical = all(
                abs(c[0] - node_xy[0]) < 0.01 and abs(c[1] - node_xy[1]) < 0.01
                for c in coords_j
            )

            if all_vertical and ntag not in supported_nodes and ntag not in spring_supported_nodes:
                problematic_patterns.append((ntag, "Only vertical connections, no lateral restraint"))

    if problematic_patterns:
        issues.append(f"WARNING: {len(problematic_patterns)} nodes with potentially unstable connectivity")
        print(f"  ⚠ WARNING: Found {len(problematic_patterns)} nodes with problematic patterns")
        for ntag, reason in problematic_patterns[:5]:
            coord = nodes[ntag]
            print(f"       Node {ntag} at ({coord[0]:.2f}, {coord[1]:.2f}, {coord[2]:.2f}): {reason}")
    else:
        print(f"  ✓ PASS: No obvious problematic connectivity patterns")

    # =================================================================
    # SUMMARY
    # =================================================================
    print(f"\n{'='*70}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*70}")

    error_count = len([i for i in issues if i.startswith('ERROR')])
    warning_count = len([i for i in issues if i.startswith('WARNING')])

    is_stable = error_count == 0

    if is_stable:
        print(f"✅ MODEL APPEARS STRUCTURALLY SOUND")
        print(f"  {warning_count} warnings, {error_count} errors")
    else:
        print(f"❌ MODEL HAS STRUCTURAL DEFECTS")
        print(f"  {warning_count} warnings, {error_count} errors")
        print(f"\n🔴 CRITICAL ISSUES:")
        for issue in issues:
            if issue.startswith('ERROR'):
                print(f"  • {issue}")

    if warning_count > 0:
        print(f"\n⚠️  WARNINGS:")
        for issue in issues:
            if issue.startswith('WARNING'):
                print(f"  • {issue}")

    print(f"\n{'='*70}\n")

    # Save report
    report = {
        'is_stable': is_stable,
        'error_count': error_count,
        'warning_count': warning_count,
        'issues': issues,
        'model_stats': {
            'nodes': len(nodes),
            'frame_elements': len(elements),
            'spring_elements': len(zero_length_elements),
            'diaphragms': len(diaphragms),
            'supported_nodes': len(supported_nodes),
            'spring_supported_nodes': len(spring_supported_nodes)
        }
    }

    with open('out/stability_report.json', 'w') as f:
        json.dump(report, f, indent=2)

    print(f"📄 Detailed report saved to: out/stability_report.json\n")

    return is_stable, issues


if __name__ == "__main__":
    try:
        is_stable, issues = validate_model()
        exit(0 if is_stable else 1)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        exit(2)
