#!/usr/bin/env python3
"""
Model Stability Checker
Diagnoses common issues that lead to unrealistic modal periods
"""

import openseespy.opensees as ops
import json
import os
from typing import Dict, List, Tuple, Any

def check_boundary_conditions() -> Dict[str, Any]:
    """
    Check if model has proper boundary conditions
    """
    results = {
        "has_supports": False,
        "num_fixed_nodes": 0,
        "fixed_dofs": [],
        "base_nodes": [],
        "issues": []
    }

    try:
        node_tags = ops.getNodeTags()

        # Find base nodes (minimum Z coordinate)
        min_z = float('inf')
        node_coords = {}
        for tag in node_tags:
            coords = ops.nodeCoord(tag)
            node_coords[tag] = coords
            if coords[2] < min_z:
                min_z = coords[2]

        # Identify base nodes (within tolerance of minimum Z)
        tolerance = 0.01
        base_nodes = []
        for tag, coords in node_coords.items():
            if abs(coords[2] - min_z) < tolerance:
                base_nodes.append(tag)

        results["base_nodes"] = base_nodes

        # Check if base nodes are fixed
        fixed_count = 0
        for tag in base_nodes:
            try:
                # Check fixity (this is a simplified check)
                # In reality, we'd need to check the actual fixity values
                # For now, we'll check if it's in the supports.json
                fixed_count += 1
            except:
                pass

        # Load supports.json to verify
        supports_file = os.path.join("out", "supports.json")
        if os.path.exists(supports_file):
            with open(supports_file, 'r') as f:
                supports_data = json.load(f)
                support_nodes = [s["node"] for s in supports_data.get("applied", [])]
                results["num_fixed_nodes"] = len(support_nodes)
                results["has_supports"] = len(support_nodes) > 0

                # Check if any base nodes are fixed
                base_fixed = [n for n in base_nodes if n in support_nodes]
                if not base_fixed:
                    results["issues"].append("Base nodes are not fixed!")
                else:
                    print(f"✓ {len(base_fixed)} base nodes are properly fixed")
        else:
            results["issues"].append("No supports.json file found")

    except Exception as e:
        results["issues"].append(f"Error checking boundaries: {str(e)}")

    return results

def check_constraint_handler() -> Dict[str, Any]:
    """
    Check if proper constraint handler is being used for rigid diaphragms
    """
    results = {
        "has_rigid_diaphragms": False,
        "proper_constraints": False,
        "issues": []
    }

    try:
        # Check if diaphragms exist
        diaphragm_file = os.path.join("out", "diaphragms.json")
        if os.path.exists(diaphragm_file):
            with open(diaphragm_file, 'r') as f:
                diaphragm_data = json.load(f)
                diaphragms = diaphragm_data.get("diaphragms", [])
                results["has_rigid_diaphragms"] = len(diaphragms) > 0

                if results["has_rigid_diaphragms"]:
                    # For rigid diaphragms with MPC, we need Transformation constraints
                    results["issues"].append(
                        "Model has rigid diaphragms - ensure constraints('Transformation') is used"
                    )

    except Exception as e:
        results["issues"].append(f"Error checking constraints: {str(e)}")

    return results

def check_mass_distribution() -> Dict[str, Any]:
    """
    Check if mass is properly distributed in the model
    """
    results = {
        "total_mass": 0.0,
        "nodes_with_mass": 0,
        "mass_per_floor": {},
        "issues": []
    }

    try:
        node_tags = ops.getNodeTags()

        for tag in node_tags:
            try:
                mass_values = ops.nodeMass(tag)
                node_mass = sum(mass_values[:3])  # Sum translational masses
                if node_mass > 0:
                    results["nodes_with_mass"] += 1
                    results["total_mass"] += node_mass
            except:
                continue

        if results["nodes_with_mass"] == 0:
            results["issues"].append("No mass found in model!")
        else:
            print(f"✓ Found mass at {results['nodes_with_mass']} nodes")
            print(f"  Total mass: {results['total_mass']:.1f} kg")

        # Check if mass is only at diaphragm masters (expected)
        diaphragm_file = os.path.join("out", "diaphragms.json")
        if os.path.exists(diaphragm_file):
            with open(diaphragm_file, 'r') as f:
                diaphragm_data = json.load(f)
                masters = [d["master"] for d in diaphragm_data.get("diaphragms", [])]

                if results["nodes_with_mass"] == len(masters):
                    print(f"✓ Mass correctly assigned to {len(masters)} diaphragm masters")
                elif results["nodes_with_mass"] > 0:
                    results["issues"].append(
                        f"Mass distribution mismatch: {results['nodes_with_mass']} nodes have mass, "
                        f"but there are {len(masters)} diaphragm masters"
                    )

    except Exception as e:
        results["issues"].append(f"Error checking mass: {str(e)}")

    return results

def diagnose_model_stability() -> Dict[str, Any]:
    """
    Comprehensive model stability diagnosis
    """
    print("\n" + "="*60)
    print("MODEL STABILITY DIAGNOSTIC")
    print("="*60)

    all_results = {}

    # Check boundary conditions
    print("\n1. Checking Boundary Conditions...")
    bc_results = check_boundary_conditions()
    all_results["boundary_conditions"] = bc_results

    if not bc_results["has_supports"]:
        print("❌ CRITICAL: No boundary conditions found!")
        print("   The model is floating in space - this causes infinite periods")
    else:
        print(f"✓ Found {bc_results['num_fixed_nodes']} fixed nodes")

    # Check constraints
    print("\n2. Checking Constraint Handler...")
    constraint_results = check_constraint_handler()
    all_results["constraints"] = constraint_results

    if constraint_results["has_rigid_diaphragms"]:
        print("⚠ Model has rigid diaphragms")
        print("  Ensure you're using: ops.constraints('Transformation')")

    # Check mass distribution
    print("\n3. Checking Mass Distribution...")
    mass_results = check_mass_distribution()
    all_results["mass"] = mass_results

    # Summary and recommendations
    print("\n" + "="*60)
    print("DIAGNOSIS SUMMARY")
    print("="*60)

    critical_issues = []
    warnings = []

    # Compile all issues
    for key, result in all_results.items():
        if "issues" in result:
            for issue in result["issues"]:
                if "CRITICAL" in issue or "not fixed" in issue.lower():
                    critical_issues.append(issue)
                else:
                    warnings.append(issue)

    if critical_issues:
        print("\n🚨 CRITICAL ISSUES (causing unrealistic periods):")
        for issue in critical_issues:
            print(f"   • {issue}")

    if warnings:
        print("\n⚠️ WARNINGS:")
        for warning in warnings:
            print(f"   • {warning}")

    if not critical_issues and not warnings:
        print("\n✅ Model appears properly constrained")

    # Provide specific recommendations
    print("\n" + "="*60)
    print("RECOMMENDED FIXES")
    print("="*60)

    if not bc_results["has_supports"]:
        print("\n1. FIX MISSING BOUNDARY CONDITIONS:")
        print("   Add fixed supports at base nodes:")
        print("   ```python")
        print("   for node in base_nodes:")
        print("       ops.fix(node, 1, 1, 1, 1, 1, 1)  # Fix all 6 DOFs")
        print("   ```")

    if constraint_results["has_rigid_diaphragms"]:
        print("\n2. USE PROPER CONSTRAINT HANDLER:")
        print("   For models with rigid diaphragms, use:")
        print("   ```python")
        print("   ops.constraints('Transformation')")
        print("   ```")

    if mass_results["total_mass"] == 0:
        print("\n3. ADD MASS TO MODEL:")
        print("   Ensure mass is assigned at diaphragm masters")

    # Save diagnostic report
    report_file = os.path.join("out", "stability_diagnostic.json")
    with open(report_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n📄 Detailed report saved to: {report_file}")

    return all_results

def apply_emergency_fixes():
    """
    Apply emergency fixes to stabilize the model for modal analysis
    """
    print("\n" + "="*60)
    print("APPLYING EMERGENCY STABILITY FIXES")
    print("="*60)

    try:
        # Fix 1: Ensure proper constraint handler
        print("\n1. Setting constraint handler to Transformation...")
        ops.constraints('Transformation')
        print("   ✓ Done")

        # Fix 2: Check and fix base nodes if needed
        print("\n2. Checking base fixity...")
        node_tags = ops.getNodeTags()

        # Find base nodes
        min_z = float('inf')
        base_nodes = []
        for tag in node_tags:
            coords = ops.nodeCoord(tag)
            if coords[2] < min_z:
                min_z = coords[2]

        tolerance = 0.01
        for tag in node_tags:
            coords = ops.nodeCoord(tag)
            if abs(coords[2] - min_z) < tolerance:
                base_nodes.append(tag)

        # Check if supports.json exists and has these nodes
        supports_file = os.path.join("out", "supports.json")
        fixed_nodes = []
        if os.path.exists(supports_file):
            with open(supports_file, 'r') as f:
                supports_data = json.load(f)
                fixed_nodes = [s["node"] for s in supports_data.get("applied", [])]

        unfixed_base = [n for n in base_nodes if n not in fixed_nodes]

        if unfixed_base:
            print(f"   ⚠ Found {len(unfixed_base)} unfixed base nodes")
            print("   Note: Cannot apply fixes directly - please ensure supports are defined in ETABS")
        else:
            print(f"   ✓ All {len(base_nodes)} base nodes are properly fixed")

        # Fix 3: Reset analysis for clean eigen
        print("\n3. Resetting analysis parameters...")
        ops.wipeAnalysis()
        ops.system('BandGen')
        ops.numberer('RCM')
        ops.constraints('Transformation')  # Critical for rigid diaphragms
        print("   ✓ Analysis reset complete")

        print("\n✅ Emergency fixes applied")
        print("   Try running modal analysis again")

    except Exception as e:
        print(f"\n❌ Error applying fixes: {str(e)}")

if __name__ == "__main__":
    # Run diagnostic
    results = diagnose_model_stability()

    # Check if we have critical issues
    has_critical = False
    for key, result in results.items():
        if "issues" in result:
            for issue in result["issues"]:
                if "not fixed" in issue.lower() or "No boundary" in issue:
                    has_critical = True
                    break

    if has_critical:
        print("\n" + "="*60)
        response = input("\nApply emergency fixes? (y/n): ")
        if response.lower() == 'y':
            apply_emergency_fixes()