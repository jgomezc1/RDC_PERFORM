#!/usr/bin/env python3
"""
Comprehensive diagnostic for the modal analysis failure in Ejemplo.e2k.

This script tests the hypothesis that the models are structurally identical
and helps identify where the divergence occurs.
"""
import sys
import json
from pathlib import Path

print("="*80)
print("DIAGNOSTIC: Modal Analysis Failure in Ejemplo.e2k")
print("="*80)

# Check if OpenSeesPy is available
try:
    import openseespy.opensees as ops
    print("\n✓ OpenSeesPy is available")
    HAS_OPENSEES = True
except ImportError:
    print("\n❌ OpenSeesPy not available - can only check artifacts")
    HAS_OPENSEES = False

# Step 1: Verify artifact identity
print("\n" + "="*80)
print("STEP 1: Comparing Artifacts")
print("="*80)

def compare_artifacts(dir1, dir2, name1, name2):
    """Compare JSON artifacts between two directories."""
    import hashlib

    files = ['nodes.json', 'beams.json', 'columns.json', 'supports.json',
             'diaphragms.json', 'springs.json']

    results = {}
    for fname in files:
        path1 = Path(dir1) / fname
        path2 = Path(dir2) / fname

        if not path1.exists() or not path2.exists():
            results[fname] = "MISSING"
            continue

        with open(path1, 'rb') as f:
            hash1 = hashlib.md5(f.read()).hexdigest()
        with open(path2, 'rb') as f:
            hash2 = hashlib.md5(f.read()).hexdigest()

        results[fname] = "IDENTICAL" if hash1 == hash2 else "DIFFERENT"

    print(f"\n{name1} vs {name2}:")
    all_identical = True
    for fname, status in results.items():
        symbol = "✓" if status == "IDENTICAL" else "❌"
        print(f"  {symbol} {fname:20s}: {status}")
        if status != "IDENTICAL":
            all_identical = False

    return all_identical

identical = compare_artifacts('artifacts_Ejemplo', 'artifacts_EjemploNew',
                              'Ejemplo', 'EjemploNew')

if identical:
    print("\n⚠️  CRITICAL: Both models produce IDENTICAL artifacts!")
    print("    → The problem is NOT in the structural model itself")
    print("    → Look for issues in analysis setup, solver, or runtime state")
else:
    print("\n✓ Models differ - investigating specific differences...")

# Step 2: Analyze model statistics
print("\n" + "="*80)
print("STEP 2: Model Statistics")
print("="*80)

def analyze_model(artifact_dir, name):
    """Analyze model statistics from artifacts."""
    print(f"\n{name}:")

    with open(Path(artifact_dir) / 'nodes.json') as f:
        nodes = json.load(f)['nodes']
    with open(Path(artifact_dir) / 'supports.json') as f:
        supports = json.load(f)['applied']
    with open(Path(artifact_dir) / 'beams.json') as f:
        beams = json.load(f)['beams']
    with open(Path(artifact_dir) / 'columns.json') as f:
        columns = json.load(f)['columns']
    with open(Path(artifact_dir) / 'springs.json') as f:
        springs = json.load(f)['elements']
    with open(Path(artifact_dir) / 'diaphragms.json') as f:
        diaphragms = json.load(f)['diaphragms']

    print(f"  Nodes: {len(nodes)}")
    print(f"  Supports: {len(supports)} nodes with boundary conditions")
    print(f"  Springs: {len(springs)} elastic foundations")
    print(f"  Beams: {len(beams)}")
    print(f"  Columns: {len(columns)}")
    print(f"  Diaphragms: {len(diaphragms)}")
    print(f"  Total DOFs: {len(nodes) * 6} = {len(nodes)} nodes × 6 DOF/node")

    # Check for releases
    releases_beams = sum(1 for b in beams if b.get('has_releases', False))
    releases_cols = sum(1 for c in columns if c.get('has_releases', False))
    print(f"  Elements with releases: {releases_beams + releases_cols}")

    # Analyze constraints
    rigid_supports = sum(1 for s in supports if s['mask'] == [1,1,1,1,1,1])
    spring_supports = sum(1 for s in supports if s.get('source') == 'spring_ground')
    etabs_restraints = len(supports) - spring_supports

    print(f"  Constraint breakdown:")
    print(f"    - ETABS restraints: {etabs_restraints}")
    print(f"    - Spring grounds: {spring_supports}")
    print(f"    - Diaphragm constraints: {sum(len(d['slaves']) for d in diaphragms)}")

    return {
        'nodes': len(nodes),
        'supports': len(supports),
        'beams': len(beams),
        'columns': len(columns),
        'springs': len(springs)
    }

stats_ej = analyze_model('artifacts_Ejemplo', 'Ejemplo (FAILING)')
stats_new = analyze_model('artifacts_EjemploNew', 'EjemploNew (WORKING)')

# Step 3: Check for potential issues
print("\n" + "="*80)
print("STEP 3: Checking for Known Issues")
print("="*80)

print("\n⚠️  DOF 702 Error Analysis:")
print("  Error: 'ProfileSPDLinDirectSolver::solve() - aii < minDiagTol (i, aii): (702, -3.90579e-28)'")
print("  → This indicates near-zero diagonal in stiffness matrix at DOF index 702")
print("  → DOF 702 ÷ 6 ≈ Node index 117")

with open('artifacts_Ejemplo/nodes.json') as f:
    nodes = sorted(json.load(f)['nodes'], key=lambda n: n['tag'])
    if len(nodes) > 117:
        problem_node = nodes[117]
        print(f"\n  Potential problem node (index 117):")
        print(f"    Tag: {problem_node['tag']}")
        print(f"    Location: ({problem_node['x']:.2f}, {problem_node['y']:.2f}, {problem_node['z']:.2f})")

# Step 4: Recommendations
print("\n" + "="*80)
print("STEP 4: Diagnostic Recommendations")
print("="*80)

if identical:
    print("\n🔍 Since artifacts are IDENTICAL, the issue is in ANALYSIS EXECUTION:")
    print("\n1. Check analysis script setup:")
    print("   ❌ NOT calling ops.wipe() before build_model()")
    print("   ❌ Different solver settings between tests")
    print("   ❌ Stale model from previous run")
    print("   ❌ Different OpenSeesPy versions")

    print("\n2. REQUIRED analysis setup:")
    print("   ```python")
    print("   import openseespy.opensees as ops")
    print("   ")
    print("   # CRITICAL: Wipe everything first!")
    print("   ops.wipe()")
    print("   ")
    print("   # Build your model")
    print("   from out.explicit_model import build_model")
    print("   build_model()")
    print("   ")
    print("   # Setup analysis")
    print("   ops.wipeAnalysis()")
    print("   ops.system('FullGeneral')  # More robust than ProfileSPD")
    print("   ops.numberer('RCM')")
    print("   ops.constraints('Transformation')  # Required for rigid diaphragms")
    print("   ops.algorithm('Linear')")
    print("   ")
    print("   # Try eigen with more robust solver")
    print("   eigenValues = ops.eigen('-fullGenLapack', 5)")
    print("   ```")

    print("\n3. Verify you're using LATEST artifacts:")
    print("   → Both models were just rebuilt (today)")
    print("   → Check timestamps on your explicit_model.py")
    print("   → Ensure you're importing from correct output directory")

if HAS_OPENSEES:
    print("\n" + "="*80)
    print("STEP 5: Running Live Test")
    print("="*80)

    try:
        print("\nTesting Ejemplo model with robust settings...")
        ops.wipe()

        sys.path.insert(0, 'out')
        from explicit_model import build_model

        build_model()

        n_nodes = len(ops.getNodeTags())
        n_elements = len(ops.getEleTags())
        print(f"✓ Model loaded: {n_nodes} nodes, {n_elements} elements")

        # Try with robust solver
        ops.wipeAnalysis()
        ops.system('FullGeneral')
        ops.numberer('RCM')
        ops.constraints('Transformation')
        ops.algorithm('Linear')

        print("  Running eigenvalue analysis...")
        eigenValues = ops.eigen('-fullGenLapack', 5)

        if len(eigenValues) == 5:
            from math import sqrt, pi
            print("\n✓ SUCCESS! Modal analysis converged")
            for i, lam in enumerate(eigenValues):
                if lam > 0:
                    freq = sqrt(lam) / (2 * pi)
                    period = 1 / freq
                    print(f"  Mode {i+1}: Frequency = {freq:.3f} Hz, Period = {period:.3f} s")
        else:
            print(f"\n⚠️  Got {len(eigenValues)} modes instead of 5")

    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*80)
print("END OF DIAGNOSTIC")
print("="*80)
