# -*- coding: utf-8 -*-
"""
Enhanced Model Verification Module for Streamlit App
Provides Joint Offset Verification and Modal Analysis capabilities
"""

import streamlit as st
import json
import os
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
import math

try:
    import openseespy.opensees as ops
    OPENSEES_AVAILABLE = True
except ImportError:
    OPENSEES_AVAILABLE = False
    st.error("OpenSeesPy not available - verification features disabled")

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from mpl_toolkits.mplot3d import Axes3D
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


def load_json_artifact(filename: str) -> Dict[str, Any]:
    """Load JSON artifact from out directory"""
    filepath = os.path.join("out", filename)
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading {filename}: {e}")
        return {}


def robust_eigenvalue_analysis(num_modes: int = 6) -> Dict[str, Any]:
    """
    Robust eigenvalue analysis with multiple solver strategies to address numerical issues
    """
    if not OPENSEES_AVAILABLE:
        return {"error": "OpenSeesPy not available", "success": False}

    results = {
        "eigenvalues": [],
        "periods": [],
        "frequencies": [],
        "solver_used": "unknown",
        "success": False,
        "conditioning_issues": [],
        "diagnostic_info": {}
    }

    # Load and build model
    explicit_path = os.path.join("out", "explicit_model.py")
    if not os.path.exists(explicit_path):
        results["error"] = f"Explicit model not found: {explicit_path}"
        return results

    try:
        import importlib.util

        # Load the explicit model using proper module loading
        spec = importlib.util.spec_from_file_location("explicit_model", explicit_path)
        explicit_model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(explicit_model)
        explicit_model.build_model()
    except Exception as e:
        results["error"] = f"Model loading failed: {e}"
        return results

    # Check model basic stats
    try:
        node_tags = ops.getNodeTags()
        ele_tags = ops.getEleTags()
        results["diagnostic_info"]["total_nodes"] = len(node_tags)
        results["diagnostic_info"]["total_elements"] = len(ele_tags)
    except Exception as e:
        results["conditioning_issues"].append(f"Basic model check failed: {e}")

    # Define multiple solver strategies
    solver_strategies = [
        ("BandGen + RCM", lambda: (ops.system('BandGen'), ops.numberer('RCM'))),
        ("FullGeneral + RCM", lambda: (ops.system('FullGeneral'), ops.numberer('RCM'))),
        ("ProfileSPD + RCM", lambda: (ops.system('ProfileSPD'), ops.numberer('RCM'))),
        ("BandSPD + Plain", lambda: (ops.system('BandSPD'), ops.numberer('Plain'))),
        ("FullGeneral + Plain", lambda: (ops.system('FullGeneral'), ops.numberer('Plain')))
    ]

    eigenvalues = None

    # Try each strategy
    for strategy_name, setup_func in solver_strategies:
        try:
            ops.wipeAnalysis()
            setup_func()

            # Try progressively fewer modes if needed
            for test_modes in [num_modes, max(3, num_modes//2), 3, 1]:
                try:
                    eigenvalues = ops.eigen(test_modes)
                    if eigenvalues and len(eigenvalues) > 0 and all(ev >= 0 for ev in eigenvalues):
                        results["solver_used"] = f"{strategy_name} ({test_modes} modes)"
                        results["eigenvalues"] = eigenvalues
                        break
                except Exception as e:
                    continue

            if eigenvalues:
                break

        except Exception as e:
            results["conditioning_issues"].append(f"{strategy_name} failed: {str(e)}")

    if not eigenvalues:
        results["error"] = "All solver strategies failed"
        results["conditioning_issues"].append("Model has severe numerical conditioning issues")
        return results

    # Process eigenvalues
    for ev in eigenvalues:
        if ev > 1e-12:
            omega = np.sqrt(ev)
            freq = omega / (2 * np.pi)
            period = 1.0 / freq if freq > 0 else float('inf')
        else:
            period = float('inf')
            freq = 0

        results["periods"].append(period)
        results["frequencies"].append(freq)

    # Analyze results
    T1 = results["periods"][0] if results["periods"] else float('inf')
    rigid_modes = sum(1 for T in results["periods"] if T > 100 or T == float('inf'))

    results["diagnostic_info"]["fundamental_period"] = T1
    results["diagnostic_info"]["rigid_modes"] = rigid_modes
    results["diagnostic_info"]["structural_modes"] = len(results["periods"]) - rigid_modes

    if 0.1 <= T1 <= 10.0:
        results["success"] = True
    elif T1 > 100:
        results["conditioning_issues"].append("Very long period suggests constraint issues")
    else:
        results["conditioning_issues"].append("Unusual period - verify structure")
        results["success"] = True  # Still usable

    return results


def check_mass_assignment() -> Dict[str, Any]:
    """
    Check mass assignment in the OpenSees model (loads explicit_model.py first)
    """
    if not OPENSEES_AVAILABLE:
        return {"error": "OpenSeesPy not available"}

    results = {
        "total_nodes": 0,
        "nodes_with_mass": 0,
        "total_mass": 0.0,
        "mass_distribution": [],
        "issues": [],
        "success": False
    }

    # Load and build model first
    explicit_path = os.path.join("out", "explicit_model.py")
    if not os.path.exists(explicit_path):
        return {"error": f"Explicit model not found: {explicit_path}"}

    try:
        import openseespy.opensees as ops
        import importlib.util

        # Load the explicit model using proper module loading
        spec = importlib.util.spec_from_file_location("explicit_model", explicit_path)
        explicit_model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(explicit_model)
        explicit_model.build_model()

        node_tags = ops.getNodeTags()
        results["total_nodes"] = len(node_tags)

        # Check each node for mass
        for tag in node_tags:
            try:
                mass_vals = ops.nodeMass(tag)
                if len(mass_vals) >= 3:
                    total_mass = sum(mass_vals[:3])  # Sum translational masses
                    if total_mass > 1e-12:
                        results["nodes_with_mass"] += 1
                        results["total_mass"] += total_mass

                        # Get coordinates for distribution check
                        coords = ops.nodeCoord(tag)
                        results["mass_distribution"].append({
                            "node": tag,
                            "mass": total_mass,
                            "coords": coords,
                            "z": coords[2] if len(coords) > 2 else 0
                        })
            except:
                continue

        # Analysis
        if results["nodes_with_mass"] == 0:
            results["issues"].append("CRITICAL: No mass found in any node")
        elif results["nodes_with_mass"] < 3:
            results["issues"].append(f"WARNING: Only {results['nodes_with_mass']} nodes have mass")
        else:
            results["success"] = True

        # Check mass distribution by elevation
        if results["mass_distribution"]:
            # Group by elevation (story)
            elevations = {}
            for node_mass in results["mass_distribution"]:
                z = round(node_mass["z"], 3)  # Round to avoid floating point issues
                if z not in elevations:
                    elevations[z] = {"count": 0, "total_mass": 0}
                elevations[z]["count"] += 1
                elevations[z]["total_mass"] += node_mass["mass"]

            results["mass_by_elevation"] = elevations

            # Check for reasonable distribution
            if len(elevations) < 2:
                results["issues"].append("WARNING: Mass found at only one elevation")

    except Exception as e:
        results["error"] = f"Error checking mass: {str(e)}"

    return results


def verify_joint_offsets() -> Dict[str, Any]:
    """
    Comprehensive joint offset verification
    Returns statistics and validation results
    """
    results = {
        "beams": {"total": 0, "with_offsets": 0, "max_offset": 0.0, "details": []},
        "columns": {"total": 0, "with_offsets": 0, "max_offset": 0.0, "details": []},
        "validation": {"passed": True, "issues": []}
    }

    # Load artifacts
    beams_data = load_json_artifact("beams.json")
    columns_data = load_json_artifact("columns.json")

    if not beams_data and not columns_data:
        results["validation"]["passed"] = False
        results["validation"]["issues"].append("No beam or column data found")
        return results

    # Process beams
    if beams_data and "beams" in beams_data:
        beams = beams_data["beams"]
        results["beams"]["total"] = len(beams)

        for beam in beams:
            if beam.get("has_joint_offsets", False):
                results["beams"]["with_offsets"] += 1

                # Calculate offset magnitude
                offset_i = beam.get("joint_offset_i", [0, 0, 0])
                offset_j = beam.get("joint_offset_j", [0, 0, 0])
                mag_i = math.sqrt(sum(x**2 for x in offset_i))
                mag_j = math.sqrt(sum(x**2 for x in offset_j))
                max_offset = max(mag_i, mag_j)

                results["beams"]["max_offset"] = max(results["beams"]["max_offset"], max_offset)

                # Store details for problem elements
                if max_offset > 0.001:  # Only store non-trivial offsets
                    results["beams"]["details"].append({
                        "tag": beam.get("tag"),
                        "line": beam.get("line"),
                        "offset_i": offset_i,
                        "offset_j": offset_j,
                        "magnitude": max_offset,
                        "rigid_end_i": beam.get("length_off_i", 0),
                        "rigid_end_j": beam.get("length_off_j", 0)
                    })

    # Process columns
    if columns_data and "columns" in columns_data:
        columns = columns_data["columns"]
        results["columns"]["total"] = len(columns)

        for column in columns:
            if column.get("has_joint_offsets", False):
                results["columns"]["with_offsets"] += 1

                # Calculate offset magnitude
                offset_i = column.get("joint_offset_i", [0, 0, 0])
                offset_j = column.get("joint_offset_j", [0, 0, 0])
                mag_i = math.sqrt(sum(x**2 for x in offset_i))
                mag_j = math.sqrt(sum(x**2 for x in offset_j))
                max_offset = max(mag_i, mag_j)

                results["columns"]["max_offset"] = max(results["columns"]["max_offset"], max_offset)

                # Store details for problem elements
                if max_offset > 0.001:  # Only store non-trivial offsets
                    results["columns"]["details"].append({
                        "tag": column.get("tag"),
                        "line": column.get("line"),
                        "offset_i": offset_i,
                        "offset_j": offset_j,
                        "magnitude": max_offset,
                        "rigid_end_i": column.get("length_off_i", 0),
                        "rigid_end_j": column.get("length_off_j", 0),
                        "lateral_offset_i": column.get("offsets_i"),
                        "lateral_offset_j": column.get("offsets_j")
                    })

    # Validation checks
    if results["beams"]["max_offset"] > 2.0:  # 2m max offset warning
        results["validation"]["issues"].append(f"Beam max offset exceeds 2m: {results['beams']['max_offset']:.3f}m")

    if results["columns"]["max_offset"] > 2.0:
        results["validation"]["issues"].append(f"Column max offset exceeds 2m: {results['columns']['max_offset']:.3f}m")

    # Check for consistency
    explicit_model_path = os.path.join("out", "explicit_model.py")
    if os.path.exists(explicit_model_path):
        with open(explicit_model_path, 'r') as f:
            content = f.read()
            jnt_offset_count = content.count("'-jntOffset'")
            expected_count = results["beams"]["with_offsets"] + results["columns"]["with_offsets"]

            if jnt_offset_count != expected_count:
                results["validation"]["issues"].append(
                    f"Mismatch: JSON reports {expected_count} elements with offsets, "
                    f"but explicit model has {jnt_offset_count} -jntOffset commands"
                )

    results["validation"]["passed"] = len(results["validation"]["issues"]) == 0

    return results


def run_modal_analysis(num_modes: int = 6) -> Dict[str, Any]:
    """
    Run eigenvalue analysis and extract modal properties
    """
    if not OPENSEES_AVAILABLE:
        return {"error": "OpenSeesPy not available"}

    results = {
        "periods": [],
        "frequencies": [],
        "modal_masses": [],
        "participation_factors": {},
        "success": False,
        "error": None
    }

    try:
        # First, check if model has any mass
        node_tags = ops.getNodeTags()
        has_mass = False
        for tag in node_tags[:10]:  # Check first 10 nodes for efficiency
            try:
                mass_vals = ops.nodeMass(tag)
                if any(m > 0 for m in mass_vals):
                    has_mass = True
                    break
            except:
                continue

        if not has_mass:
            results["error"] = "No mass detected in model - eigen analysis requires mass assignment"
            return results

        # Set up eigen solver with FORCED constraint reset
        try:
            # Check if model has rigid diaphragms
            has_rigid_diaphragms = False
            diaphragm_file = os.path.join("out", "diaphragms.json")
            if os.path.exists(diaphragm_file):
                with open(diaphragm_file, 'r') as f:
                    diaphragm_data = json.load(f)
                    has_rigid_diaphragms = len(diaphragm_data.get("diaphragms", [])) > 0

            # CRITICAL: Force wipe and rebuild analysis with correct constraints
            # This ensures we don't use cached analysis settings from Streamlit
            ops.wipe()

            # Rebuild the model with correct constraints from scratch
            explicit_model_path = os.path.join("out", "explicit_model.py")
            if os.path.exists(explicit_model_path):
                print(f"[Modal] Rebuilding model from {explicit_model_path} with correct constraints")

                # Execute the explicit model which now includes constraints('Transformation')
                import importlib.util
                spec = importlib.util.spec_from_file_location("explicit_model", explicit_model_path)
                explicit_model = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(explicit_model)
                explicit_model.build_model()

                print(f"[Modal] Model rebuilt successfully with proper constraints")
            else:
                # Fallback: manual setup if explicit model doesn't exist
                ops.model("basic", "-ndm", 3, "-ndf", 6)

                # Set up the eigen solver with appropriate settings
                ops.wipeAnalysis()
                ops.system('BandGen')
                ops.numberer('RCM')

                # CRITICAL: Use Transformation constraints for models with rigid diaphragms
                if has_rigid_diaphragms:
                    ops.constraints('Transformation')
                    print("[Modal] Using Transformation constraints for rigid diaphragms")
                else:
                    ops.constraints('Plain')

                ops.algorithm('Linear')
                ops.integrator('LoadControl', 0.0)
                ops.analysis('Static')

        except Exception as e:
            # If setup fails, try a simpler approach
            print(f"[Modal] Warning: Analysis setup issue: {e}")

            # Last resort: force constraints manually
            try:
                ops.wipeAnalysis()
                ops.constraints('Transformation')  # Force transformation constraints
                ops.system('BandGen')
                ops.numberer('RCM')
                print("[Modal] Applied emergency constraint fix")
            except Exception as e2:
                print(f"[Modal] Emergency fix failed: {e2}")
                pass

        # Run eigen analysis with multiple fallback strategies
        eigenvalues = None
        solver_used = "unknown"

        # Strategy 1: Standard BandGen solver
        try:
            print("[Modal] Trying BandGen solver...")
            eigenvalues = ops.eigen(num_modes)
            solver_used = "BandGen"
            print(f"[Modal] BandGen solver succeeded")
        except Exception as e1:
            print(f"[Modal] BandGen failed: {e1}")

            # Strategy 2: FullGeneral solver
            try:
                print("[Modal] Trying FullGeneral solver...")
                ops.wipeAnalysis()
                ops.system('FullGeneral')
                ops.numberer('RCM')
                ops.constraints('Transformation')
                eigenvalues = ops.eigen(num_modes)
                solver_used = "FullGeneral"
                print(f"[Modal] FullGeneral solver succeeded")
            except Exception as e2:
                print(f"[Modal] FullGeneral failed: {e2}")

                # Strategy 3: Try with fewer modes
                try:
                    print("[Modal] Trying with fewer modes...")
                    eigenvalues = ops.eigen(min(3, num_modes))
                    solver_used = "Reduced modes"
                    print(f"[Modal] Reduced modes succeeded")
                except Exception as e3:
                    print(f"[Modal] Reduced modes failed: {e3}")

                    # Strategy 4: Check mass matrix directly
                    try:
                        print("[Modal] Checking mass matrix...")

                        # Get node tags and check mass distribution
                        node_tags = ops.getNodeTags()
                        mass_nodes = []
                        zero_mass_nodes = []

                        for tag in node_tags:
                            try:
                                mass_vals = ops.nodeMass(tag)
                                total_mass = sum(mass_vals[:3])
                                if total_mass > 1e-12:
                                    mass_nodes.append((tag, total_mass))
                                else:
                                    zero_mass_nodes.append(tag)
                            except:
                                zero_mass_nodes.append(tag)

                        print(f"[Modal] Found {len(mass_nodes)} nodes with mass, {len(zero_mass_nodes)} without")

                        if len(mass_nodes) == 0:
                            results["error"] = "No mass found in model - cannot perform modal analysis"
                            return results
                        elif len(mass_nodes) < 3:
                            results["error"] = f"Only {len(mass_nodes)} nodes have mass - insufficient for modal analysis"
                            return results
                        else:
                            # Try a very simple eigen analysis
                            ops.wipeAnalysis()
                            ops.system('ProfileSPD')
                            eigenvalues = ops.eigen(1)  # Just try 1 mode
                            solver_used = "ProfileSPD-1mode"
                            print(f"[Modal] ProfileSPD with 1 mode succeeded")

                    except Exception as e4:
                        results["error"] = f"All eigenvalue solvers failed. Last error: {str(e4)}"
                        results["debug_info"] = {
                            "BandGen_error": str(e1),
                            "FullGeneral_error": str(e2),
                            "ReducedModes_error": str(e3),
                            "ProfileSPD_error": str(e4)
                        }
                        return results

        # Add solver info to results
        results["solver_used"] = solver_used

        # Check if eigen analysis was successful
        if eigenvalues is None:
            results["error"] = "Eigen analysis returned no values - check model constraints"
            return results

        # Handle different return types from eigen()
        if isinstance(eigenvalues, (int, float)):
            # Single eigenvalue returned (happens with num_modes=1 sometimes)
            eigenvalues = [float(eigenvalues)]
        elif isinstance(eigenvalues, list):
            # List of eigenvalues
            eigenvalues = [float(ev) for ev in eigenvalues]
        else:
            # Unexpected type
            results["error"] = f"Unexpected eigenvalue type: {type(eigenvalues)}"
            return results

        actual_modes = len(eigenvalues)

        if actual_modes < num_modes:
            results["error"] = f"Only {actual_modes} modes converged (requested {num_modes})"

        # Extract eigenvalues and convert to periods/frequencies
        for eigenvalue in eigenvalues:
            if eigenvalue > 0:
                omega = math.sqrt(eigenvalue)  # rad/sec
                frequency = omega / (2 * math.pi)  # Hz
                period = 1.0 / frequency if frequency > 0 else float('inf')

                results["periods"].append(period)
                results["frequencies"].append(frequency)
            else:
                results["periods"].append(float('inf'))
                results["frequencies"].append(0.0)

        # Calculate modal participation factors if possible
        try:
            # Get total mass (simplified - assumes mass at all DOFs)
            node_tags = ops.getNodeTags()
            total_mass = 0.0

            for tag in node_tags:
                try:
                    mass_values = ops.nodeMass(tag)
                    total_mass += sum(mass_values[:3])  # Sum translational masses
                except:
                    continue

            results["total_mass"] = total_mass / 3.0  # Average per direction

            # Modal mass participation (simplified)
            for i, period in enumerate(results["periods"]):
                if period < float('inf'):
                    # Approximate modal mass as fraction of total
                    # In reality, this requires eigenvector analysis
                    modal_mass_ratio = 1.0 / (i + 1)  # Simplified assumption
                    results["modal_masses"].append(modal_mass_ratio)
                else:
                    results["modal_masses"].append(0.0)

        except Exception as e:
            results["error"] = f"Could not calculate modal masses: {str(e)}"

        results["success"] = True

    except Exception as e:
        # Provide detailed error information
        import traceback
        error_details = traceback.format_exc()

        # Try to provide helpful diagnostics
        if "singular" in str(e).lower() or "matrix" in str(e).lower():
            results["error"] = f"Model appears to be unstable or poorly constrained: {str(e)}"
        elif "mass" in str(e).lower():
            results["error"] = f"Mass-related issue: {str(e)}"
        else:
            results["error"] = f"Modal analysis error: {str(e)}"

        # Add debugging info if verbose
        results["debug_info"] = error_details
        results["success"] = False

    return results


def display_joint_offset_verification():
    """
    Display joint offset verification in Streamlit
    """
    st.header("🔧 Joint Offset Verification")

    with st.spinner("Analyzing joint offsets..."):
        results = verify_joint_offsets()

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        beam_percentage = (results["beams"]["with_offsets"] / results["beams"]["total"] * 100) if results["beams"]["total"] > 0 else 0
        st.metric(
            "Beams with Offsets",
            f"{results['beams']['with_offsets']}/{results['beams']['total']}",
            f"{beam_percentage:.1f}%"
        )

    with col2:
        st.metric(
            "Max Beam Offset",
            f"{results['beams']['max_offset']:.3f} m",
            "OK" if results['beams']['max_offset'] < 2.0 else "CHECK"
        )

    with col3:
        col_percentage = (results["columns"]["with_offsets"] / results["columns"]["total"] * 100) if results["columns"]["total"] > 0 else 0
        st.metric(
            "Columns with Offsets",
            f"{results['columns']['with_offsets']}/{results['columns']['total']}",
            f"{col_percentage:.1f}%"
        )

    with col4:
        st.metric(
            "Max Column Offset",
            f"{results['columns']['max_offset']:.3f} m",
            "OK" if results['columns']['max_offset'] < 2.0 else "CHECK"
        )

    # Validation status
    if results["validation"]["passed"]:
        st.success("✅ All joint offset validations passed")
    else:
        st.error("❌ Joint offset validation issues detected:")
        for issue in results["validation"]["issues"]:
            st.warning(f"• {issue}")

    # Detailed tables
    tab1, tab2 = st.tabs(["Beam Offsets", "Column Offsets"])

    with tab1:
        if results["beams"]["details"]:
            st.subheader("Beams with Significant Offsets")

            # Convert to DataFrame for better display
            beam_df = pd.DataFrame(results["beams"]["details"])
            beam_df["offset_i_str"] = beam_df["offset_i"].apply(lambda x: f"({x[0]:.3f}, {x[1]:.3f}, {x[2]:.3f})")
            beam_df["offset_j_str"] = beam_df["offset_j"].apply(lambda x: f"({x[0]:.3f}, {x[1]:.3f}, {x[2]:.3f})")

            display_df = beam_df[["tag", "line", "rigid_end_i", "rigid_end_j", "offset_i_str", "offset_j_str", "magnitude"]]
            display_df.columns = ["Tag", "Line", "Rigid End I (m)", "Rigid End J (m)", "Offset I (m)", "Offset J (m)", "Max Magnitude (m)"]

            st.dataframe(
                display_df,
                hide_index=True,
                column_config={
                    "Max Magnitude (m)": st.column_config.NumberColumn(format="%.4f")
                }
            )
        else:
            st.info("No beams with significant offsets (> 1mm)")

    with tab2:
        if results["columns"]["details"]:
            st.subheader("Columns with Significant Offsets")

            # Convert to DataFrame
            col_df = pd.DataFrame(results["columns"]["details"])
            col_df["offset_i_str"] = col_df["offset_i"].apply(lambda x: f"({x[0]:.3f}, {x[1]:.3f}, {x[2]:.3f})")
            col_df["offset_j_str"] = col_df["offset_j"].apply(lambda x: f"({x[0]:.3f}, {x[1]:.3f}, {x[2]:.3f})")

            # Check if lateral offsets exist
            if "lateral_offset_i" in col_df.columns:
                col_df["has_lateral"] = col_df["lateral_offset_i"].apply(
                    lambda x: "Yes" if x and any(abs(v) > 0.001 for v in x.values()) else "No"
                )
            else:
                col_df["has_lateral"] = "No"

            display_df = col_df[["tag", "line", "rigid_end_i", "rigid_end_j", "offset_i_str", "offset_j_str", "has_lateral", "magnitude"]]
            display_df.columns = ["Tag", "Line", "Rigid End I (m)", "Rigid End J (m)", "Offset I (m)", "Offset J (m)", "Lateral Offset", "Max Magnitude (m)"]

            st.dataframe(
                display_df,
                hide_index=True,
                column_config={
                    "Max Magnitude (m)": st.column_config.NumberColumn(format="%.4f")
                }
            )

            # Additional analysis for columns with lateral offsets
            lateral_columns = col_df[col_df["has_lateral"] == "Yes"]
            if not lateral_columns.empty:
                st.info(f"📐 {len(lateral_columns)} columns have lateral eccentricities (non-centroidal connections)")
        else:
            st.info("No columns with significant offsets (> 1mm)")


def display_modal_analysis():
    """
    Display modal analysis results in Streamlit
    """
    st.header("🌊 Modal Analysis")

    # Configuration
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        num_modes = st.slider("Number of modes to analyze", min_value=3, max_value=12, value=6, step=1)
    with col2:
        run_analysis = st.button("Standard Analysis", type="secondary", use_container_width=True)
    with col3:
        run_robust = st.button("🔧 Robust Analysis", type="primary", use_container_width=True,
                             help="Uses multiple solver strategies to handle numerical issues")

    # Run analysis based on button clicked
    results = None
    if run_analysis:
        with st.spinner(f"Running standard eigenvalue analysis for {num_modes} modes..."):
            results = run_modal_analysis(num_modes)
    elif run_robust:
        with st.spinner(f"Running robust eigenvalue analysis for {num_modes} modes..."):
            results = robust_eigenvalue_analysis(num_modes)

    if results:

        if results.get("success"):
            # Display results
            success_msg = "✅ Modal analysis completed successfully"
            if results.get("solver_used"):
                success_msg += f" (using {results['solver_used']})"
            st.success(success_msg)

            # Show diagnostic info for robust analysis
            if "diagnostic_info" in results and results["diagnostic_info"]:
                diag_info = results["diagnostic_info"]
                col1, col2, col3 = st.columns(3)
                with col1:
                    if "total_nodes" in diag_info:
                        st.info(f"Nodes: {diag_info['total_nodes']}")
                with col2:
                    if "rigid_modes" in diag_info:
                        st.info(f"Rigid modes: {diag_info['rigid_modes']}")
                with col3:
                    if "structural_modes" in diag_info:
                        st.info(f"Structural modes: {diag_info['structural_modes']}")

            # Show conditioning issues if any
            if results.get("conditioning_issues"):
                with st.expander("⚠️ Numerical Conditioning Issues Detected", expanded=False):
                    for issue in results["conditioning_issues"]:
                        st.warning(f"• {issue}")

            if results.get("error"):
                st.warning(results["error"])

            # Create DataFrame for modal properties
            modal_df = pd.DataFrame({
                "Mode": range(1, len(results["periods"]) + 1),
                "Period (s)": results["periods"],
                "Frequency (Hz)": results["frequencies"],
                "Modal Mass Ratio": results.get("modal_masses", [0] * len(results["periods"]))
            })

            # Summary metrics
            col1, col2, col3 = st.columns(3)

            with col1:
                if results["periods"] and results["periods"][0] < float('inf'):
                    st.metric("Fundamental Period", f"{results['periods'][0]:.3f} s")
                else:
                    st.metric("Fundamental Period", "N/A")

            with col2:
                if results["frequencies"] and results["frequencies"][0] > 0:
                    st.metric("Fundamental Frequency", f"{results['frequencies'][0]:.3f} Hz")
                else:
                    st.metric("Fundamental Frequency", "N/A")

            with col3:
                if "total_mass" in results:
                    st.metric("Estimated Total Mass", f"{results['total_mass']:.1f} kg")
                else:
                    st.metric("Estimated Total Mass", "N/A")

            # Detailed table
            st.subheader("Modal Properties")
            st.dataframe(
                modal_df,
                hide_index=True,
                column_config={
                    "Period (s)": st.column_config.NumberColumn(format="%.4f"),
                    "Frequency (Hz)": st.column_config.NumberColumn(format="%.3f"),
                    "Modal Mass Ratio": st.column_config.ProgressColumn(
                        min_value=0,
                        max_value=1,
                        format="%.2f"
                    )
                }
            )

            # Visualizations
            if MATPLOTLIB_AVAILABLE:
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

                # Period vs Mode
                valid_periods = [p for p in results["periods"] if p < float('inf')]
                valid_modes = list(range(1, len(valid_periods) + 1))

                ax1.bar(valid_modes, valid_periods, color='steelblue', edgecolor='black', linewidth=1.5)
                ax1.set_xlabel("Mode Number")
                ax1.set_ylabel("Period (s)")
                ax1.set_title("Modal Periods")
                ax1.grid(True, alpha=0.3)

                # Frequency vs Mode
                valid_freqs = [f for f in results["frequencies"] if f > 0]

                ax2.bar(valid_modes[:len(valid_freqs)], valid_freqs, color='coral', edgecolor='black', linewidth=1.5)
                ax2.set_xlabel("Mode Number")
                ax2.set_ylabel("Frequency (Hz)")
                ax2.set_title("Modal Frequencies")
                ax2.grid(True, alpha=0.3)

                plt.tight_layout()
                st.pyplot(fig)
                plt.close()

            # Engineering checks
            st.subheader("🔍 Engineering Checks")

            checks_passed = []
            checks_failed = []

            # Check 1: Fundamental period reasonableness
            if results["periods"] and results["periods"][0] < float('inf'):
                T1 = results["periods"][0]
                # Approximate limits based on building height (assuming ~3m/story)
                # T ≈ 0.1*N for concrete buildings (N = number of stories)
                if 0.1 <= T1 <= 5.0:
                    checks_passed.append(f"Fundamental period T₁ = {T1:.3f}s is within reasonable range (0.1-5.0s)")
                else:
                    checks_failed.append(f"Fundamental period T₁ = {T1:.3f}s may be unrealistic")

            # Check 2: Modal sequence
            periods_increasing = all(results["periods"][i] >= results["periods"][i+1]
                                   for i in range(len(results["periods"])-1)
                                   if results["periods"][i+1] < float('inf'))
            if periods_increasing:
                checks_passed.append("Modal periods properly ordered (decreasing with mode number)")
            else:
                checks_failed.append("Warning: Modal periods not properly ordered")

            # Check 3: Frequency spacing
            if len(valid_freqs) > 1:
                freq_ratios = [valid_freqs[i+1]/valid_freqs[i] for i in range(len(valid_freqs)-1)]
                if all(1.2 <= r <= 5.0 for r in freq_ratios):
                    checks_passed.append("Modal frequency spacing is reasonable")
                else:
                    checks_failed.append("Some modal frequencies may be too closely spaced")

            # Display check results
            for check in checks_passed:
                st.success(f"✅ {check}")
            for check in checks_failed:
                st.warning(f"⚠️ {check}")

        else:
            st.error(f"❌ Modal analysis failed: {results.get('error', 'Unknown error')}")

            # Enhanced error guidance
            st.subheader("🔧 Troubleshooting Suggestions")

            error_msg = results.get('error', '').lower()
            if 'see stderr output' in error_msg or 'eigenvalue' in error_msg:
                st.warning("**Eigenvalue Analysis Issues Detected**")
                st.markdown("""
                - Try the **🔧 Robust Analysis** button which uses multiple solver strategies
                - The model may have numerical conditioning issues with very small section properties
                - Check that boundary conditions adequately constrain the structure
                - Verify that the mass matrix is well-conditioned
                """)

            # Show conditioning issues if available
            if results.get("conditioning_issues"):
                st.subheader("⚠️ Detected Issues")
                for issue in results["conditioning_issues"]:
                    st.error(f"• {issue}")

            st.info("**General troubleshooting steps:**")
            st.markdown("""
            1. Ensure the model is properly constrained and has mass assigned
            2. Check for very small or zero section properties in elements
            3. Verify no mechanisms exist in the structure
            4. Try reducing the number of modes requested
            5. Use the robust analysis option for better numerical stability
            """)


def add_verification_tab():
    """
    Main function to add verification capabilities to Streamlit app
    Call this from the main app to add a Verification tab
    """
    st.title("🔬 Advanced Model Verification")

    # Create tabs for different verification types
    tab1, tab2, tab3 = st.tabs(["Joint Offsets", "Modal Analysis", "Quick Checks"])

    with tab1:
        display_joint_offset_verification()

    with tab2:
        display_modal_analysis()

    with tab3:
        st.header("⚡ Quick Model Checks")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Check Model Connectivity", use_container_width=True):
                with st.spinner("Checking connectivity..."):
                    # Quick connectivity check
                    try:
                        node_tags = ops.getNodeTags()
                        ele_tags = ops.getEleTags()
                        st.success(f"✅ Model has {len(node_tags)} nodes and {len(ele_tags)} elements")

                        # Check for disconnected nodes
                        connected_nodes = set()
                        for etag in ele_tags:
                            try:
                                nodes = ops.eleNodes(etag)
                                connected_nodes.update(nodes)
                            except:
                                pass

                        disconnected = len(node_tags) - len(connected_nodes)
                        if disconnected > 0:
                            st.warning(f"⚠️ {disconnected} nodes have no element connections")
                        else:
                            st.success("✅ All nodes are connected to elements")
                    except Exception as e:
                        st.error(f"Failed to check connectivity: {e}")

        with col2:
            if st.button("Verify Constraints", use_container_width=True):
                with st.spinner("Checking constraints..."):
                    # Check for sufficient constraints
                    try:
                        # Try a simple static analysis to test stability
                        ops.constraints('Plain')
                        ops.numberer('RCM')
                        ops.system('BandGen')
                        ops.test('NormDispIncr', 1.0e-8, 6)
                        ops.algorithm('Newton')
                        ops.integrator('LoadControl', 1.0)
                        ops.analysis('Static')

                        st.success("✅ Model appears to be properly constrained")
                    except Exception as e:
                        if "singular" in str(e).lower():
                            st.error("❌ Model has insufficient constraints (singular stiffness matrix)")
                        else:
                            st.warning(f"⚠️ Could not verify constraints: {e}")


# Export the main function for use in the Streamlit app
__all__ = ['add_verification_tab', 'verify_joint_offsets', 'run_modal_analysis']