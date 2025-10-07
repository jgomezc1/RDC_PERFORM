#!/usr/bin/env python3
"""
Streamlit Integration for Structural Validation Module

This module provides a user-friendly interface for running
comprehensive structural validation tests.
"""

import streamlit as st
import json
import os
import sys
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
import datetime

# Add project root to path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import the validation module
try:
    from validation.structural_validation import StructuralValidator
    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False
    st.error("Structural validation module not available")


def generate_explicit_model_file() -> bool:
    """Generate explicit_model.py from current model artifacts"""
    try:
        import subprocess
        import sys
        import os

        # Check if generate_explicit_model.py exists (in experimental/ after refactoring)
        generator_script = "experimental/generate_explicit_model.py"
        if not os.path.exists(generator_script):
            return False

        # Check if required artifacts exist
        required_artifacts = [
            "out/nodes.json",
            "out/beams.json",
            "out/columns.json",
            "out/supports.json"
        ]

        missing_artifacts = []
        for artifact in required_artifacts:
            if not os.path.exists(artifact):
                missing_artifacts.append(artifact)

        if missing_artifacts:
            print(f"Missing required artifacts: {missing_artifacts}")
            return False

        # Run the explicit model generator
        result = subprocess.run([
            sys.executable, generator_script
        ], capture_output=True, text=True, cwd=".")

        if result.returncode == 0:
            # Check if the output file was created
            return os.path.exists("out/explicit_model.py")
        else:
            print(f"Generator script failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"Error generating explicit model: {e}")
        return False


def generate_lateral_load_debug_file(etabs_periods: Optional[List[float]] = None) -> str:
    """Generate a standalone OpenSeesPy file for debugging lateral load analysis"""
    try:
        import os
        import json
        from datetime import datetime

        # Check if explicit model exists
        explicit_model_path = "out/explicit_model.py"
        if not os.path.exists(explicit_model_path):
            return None

        # Load diaphragm data
        diaphragms_path = "out/diaphragms.json"
        if not os.path.exists(diaphragms_path):
            return None

        with open(diaphragms_path, 'r') as f:
            diaphragm_data = json.load(f)

        diaphragms = diaphragm_data.get("diaphragms", [])
        if not diaphragms:
            return None

        master_nodes = [d["master"] for d in diaphragms]

        # Read the explicit model content
        with open(explicit_model_path, 'r') as f:
            model_content = f.read()

        # Generate the debug file content
        debug_content = f'''#!/usr/bin/env python3
"""
Lateral Load Path Debug File
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This standalone file tests lateral load analysis for debugging purposes.
It replicates the lateral load path validation but with detailed error reporting.
"""

import openseespy.opensees as ops
import sys
import traceback

def test_lateral_load_analysis():
    """Test lateral load analysis with detailed error reporting"""

    print("="*70)
    print("LATERAL LOAD PATH ANALYSIS DEBUG")
    print("="*70)

    try:
        # Clear any existing model
        ops.wipe()
        print("✓ OpenSees model wiped")

        # Build the model (from explicit_model.py)
        print("\\n--- Building Model ---")
        build_model()
        print("✓ Model built successfully")

        # Get model information
        node_tags = ops.getNodeTags()
        ele_tags = ops.getEleTags()
        print(f"✓ Model info: {{len(node_tags)}} nodes, {{len(ele_tags)}} elements")

        # Test master nodes
        master_nodes = {master_nodes}
        print(f"\\n--- Testing Master Nodes ---")
        print(f"Master nodes to test: {{master_nodes}}")

        accessible_masters = []
        for master in master_nodes:
            try:
                coord = ops.nodeCoord(master)
                accessible_masters.append(master)
                print(f"✓ Master node {{master}}: {{coord}}")
            except Exception as e:
                print(f"✗ Master node {{master}} not accessible: {{e}}")

        if not accessible_masters:
            print("\\n❌ CRITICAL: No master nodes are accessible!")
            return

        # Test both directions
        for direction in ["X", "Y"]:
            print(f"\\n--- Testing {{direction}} Direction ---")
            test_direction(direction, accessible_masters)

    except Exception as e:
        print(f"\\n❌ CRITICAL ERROR in main function: {{e}}")
        print("Full traceback:")
        traceback.print_exc()

def test_direction(direction: str, master_nodes: list):
    """Test lateral load analysis in a specific direction"""

    try:
        # Clear existing analysis and loads
        print(f"Setting up {{direction}} direction analysis...")

        try:
            ops.wipeAnalysis()
            ops.remove('loadPattern', 1)
        except:
            pass  # May not exist yet

        # Create load pattern
        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)
        print("✓ Load pattern created")

        # Apply loads
        unit_load = 1000.0  # 1 kN
        total_applied = 0.0
        applied_nodes = []

        print(f"Applying {{unit_load}}N loads in {{direction}} direction...")

        for master_node in master_nodes:
            try:
                if direction == "X":
                    ops.load(master_node, unit_load, 0, 0, 0, 0, 0)
                elif direction == "Y":
                    ops.load(master_node, 0, unit_load, 0, 0, 0, 0)

                total_applied += unit_load
                applied_nodes.append(master_node)
                print(f"✓ Load applied to node {{master_node}}")

            except Exception as e:
                print(f"✗ Failed to load node {{master_node}}: {{e}}")

        print(f"✓ Total applied load: {{total_applied}}N on {{len(applied_nodes)}} nodes")

        if len(applied_nodes) == 0:
            print("❌ No loads were applied successfully!")
            return

        # Set up analysis
        print("\\nSetting up analysis...")
        ops.system('BandGen')
        ops.numberer('RCM')
        ops.constraints('Transformation')
        ops.integrator('LoadControl', 1.0)
        ops.algorithm('Linear')
        ops.analysis('Static')
        print("✓ Analysis objects created")

        # Run analysis with detailed error reporting
        print("\\nRunning static analysis...")
        print("Command: ops.analyze(1)")

        try:
            result = ops.analyze(1)
            print(f"✓ Analysis completed with return code: {{result}}")

            if result == 0:
                print("✅ Analysis SUCCESSFUL!")

                # Check reactions
                print("\\nChecking equilibrium...")
                total_reaction = 0.0
                reaction_count = 0

                for node_tag in ops.getNodeTags():
                    try:
                        reactions = ops.nodeReaction(node_tag)
                        if len(reactions) >= 2:
                            if direction == "X":
                                reaction_force = reactions[0]
                            elif direction == "Y":
                                reaction_force = reactions[1]

                            if abs(reaction_force) > 1e-6:
                                total_reaction += reaction_force
                                reaction_count += 1

                    except:
                        continue

                print(f"✓ Reactions: {{total_reaction:.3f}}N from {{reaction_count}} nodes")
                imbalance = abs(total_applied + total_reaction)
                print(f"✓ Force imbalance: {{imbalance:.6f}}N")

                if imbalance < 0.01 * abs(total_applied):
                    print("✅ EQUILIBRIUM SATISFIED!")
                else:
                    print("⚠️ Equilibrium not satisfied (may be acceptable)")

            else:
                print(f"❌ Analysis FAILED with return code {{result}}")
                print("Common return codes:")
                print("  -1: Analysis failed to converge")
                print("  -2: Analysis object not properly set")
                print("  -3: Algorithm failed")

        except Exception as e:
            print(f"❌ Analysis execution failed: {{e}}")
            print("Full error traceback:")
            traceback.print_exc()

    except Exception as e:
        print(f"❌ Error in {{direction}} direction test: {{e}}")
        traceback.print_exc()

# Model building function (from explicit_model.py)
{model_content}

if __name__ == "__main__":
    test_lateral_load_analysis()
    print("\\n" + "="*70)
    print("Debug analysis complete. Check output above for errors.")
    print("="*70)
'''

        return debug_content

    except Exception as e:
        print(f"Error generating debug file: {e}")
        return None


def run_structural_validation(etabs_periods: Optional[List[float]] = None) -> Dict[str, Any]:
    """Run comprehensive structural validation"""
    if not VALIDATION_AVAILABLE:
        return {"error": "Validation module not available", "success": False}

    try:
        validator = StructuralValidator()
        results = validator.run_all_validations(etabs_periods)

        # Export report
        if results.get("results"):
            validator.export_report("out/structural_validation_report.json")

        return results
    except Exception as e:
        return {"error": str(e), "success": False}


def display_validation_results(results: Dict[str, Any]):
    """Display validation results in Streamlit"""

    # Overall Status
    if results.get("success"):
        if results.get("warnings", 0) > 0:
            st.warning(f"⚠️ Validation passed with {results['warnings']} warnings")
        else:
            st.success("✅ All structural validations passed!")
    else:
        if "error" in results:
            st.error(f"❌ Validation failed: {results['error']}")
        else:
            st.error(f"❌ {results.get('critical_failures', 0)} critical failures detected")

    # Show critical failures prominently
    if "results" in results and not results.get("success"):
        critical_failures = [test for test in results["results"] if not test["passed"] and test["severity"] == "critical"]
        if critical_failures:
            st.subheader("🚨 Critical Failures - Immediate Action Required")
            for test in critical_failures:
                with st.container():
                    st.error(f"**{test['name']}**: {test['message']}")
                    if test.get("details"):
                        details = test["details"]

                        # Show OpenSees-specific error information prominently
                        if "x_direction" in details or "y_direction" in details:
                            # This is likely a lateral load path validation failure
                            directions = ["x_direction", "y_direction"]
                            for direction in directions:
                                if direction in details and not details[direction].get("analysis_success", True):
                                    dir_data = details[direction]
                                    st.code(f"🔍 {direction.upper()} Analysis Failure:")

                                    if "opensees_error" in dir_data and dir_data["opensees_error"]:
                                        st.code(f"OpenSees Error: {dir_data['opensees_error']}", language="text")

                                    if "error" in dir_data:
                                        st.code(f"Analysis Error: {dir_data['error']}", language="text")

                                    # Show diagnostics if available
                                    if "diagnostics" in dir_data:
                                        diag = dir_data["diagnostics"]
                                        st.code("Diagnostics:")
                                        for key, value in diag.items():
                                            st.code(f"  • {key}: {value}")

                        # Show other details
                        detail_lines = []
                        for key, value in details.items():
                            if key not in ["error", "disconnected_list", "reaction_nodes", "mass_by_story", "x_direction", "y_direction"]:
                                if isinstance(value, (int, float)):
                                    if isinstance(value, float):
                                        detail_lines.append(f"• {key}: {value:.3f}")
                                    else:
                                        detail_lines.append(f"• {key}: {value}")
                                elif isinstance(value, list) and len(value) <= 5:
                                    detail_lines.append(f"• {key}: {value}")
                                elif isinstance(value, str) and len(value) < 100:
                                    detail_lines.append(f"• {key}: {value}")

                        if detail_lines:
                            st.caption("Additional Details: " + " | ".join(detail_lines))
                    st.divider()

    # Summary metrics
    if "total_tests" in results:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Tests", results["total_tests"])
        with col2:
            st.metric("Passed", results["passed"],
                     delta=f"{results['passed']/results['total_tests']*100:.0f}%")
        with col3:
            st.metric("Critical Issues", results.get("critical_failures", 0))
        with col4:
            st.metric("Warnings", results.get("warnings", 0))

    # Detailed results
    if "results" in results:
        st.subheader("📊 Detailed Test Results")

        # Group results by category
        geometric = []
        mass = []
        properties = []
        equilibrium = []
        dynamic = []

        for test in results["results"]:
            name = test["name"]
            if "Node" in name or "Element" in name or "Connect" in name or "Boundary" in name:
                geometric.append(test)
            elif "Mass" in name:
                mass.append(test)
            elif "Section" in name or "Properties" in name:
                properties.append(test)
            elif "Equilibrium" in name or "Load Path" in name or "Lateral" in name:
                equilibrium.append(test)
            elif "Modal" in name or "Period" in name:
                dynamic.append(test)

        # Display by category
        categories = [
            ("🔷 Geometric Validations", geometric),
            ("⚖️ Mass Validations", mass),
            ("📐 Property Validations", properties),
            ("⚡ Lateral Load Path", equilibrium),
            ("🌊 Dynamic Validations", dynamic)
        ]

        for category_name, tests in categories:
            if tests:
                with st.expander(category_name, expanded=True):
                    for test in tests:
                        # Status icon
                        if test["passed"]:
                            icon = "✅"
                        elif test["severity"] == "critical":
                            icon = "❌"
                        else:
                            icon = "⚠️"

                        # Test result
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            st.write(f"{icon} **{test['name']}**")
                        with col2:
                            st.write(test["message"])

                        # Show details for failures
                        if not test["passed"] and test.get("details"):
                            details = test["details"]
                            detail_text = []
                            for key, value in details.items():
                                if key not in ["error", "disconnected_list", "reaction_nodes", "mass_by_story"]:
                                    if isinstance(value, (int, float)):
                                        if isinstance(value, float):
                                            detail_text.append(f"• {key}: {value:.3f}")
                                        else:
                                            detail_text.append(f"• {key}: {value}")
                                    elif isinstance(value, list) and len(value) <= 5:
                                        detail_text.append(f"• {key}: {value}")

                            if detail_text:
                                st.caption("\n".join(detail_text))

                        st.divider()


def add_structural_validation_tab():
    """
    Main function to add structural validation to Streamlit app
    """
    st.header("🏗️ Structural Validation Suite")

    st.markdown("""
    This comprehensive validation suite ensures the OpenSees model accurately
    represents the original ETABS model by checking:
    - **Geometric Fidelity**: Node/element counts, connectivity
    - **Mass Distribution**: Rigid diaphragm mass assignment
    - **Section Properties**: Beam and column properties
    - **Lateral Load Path**: Structural integrity under lateral loads
    - **Dynamic Properties**: Modal periods comparison
    """)

    # Configuration section
    with st.expander("⚙️ Configuration", expanded=False):
        st.subheader("Optional: ETABS Modal Periods")
        st.info("Enter ETABS modal periods for comparison (optional)")

        # Input for ETABS periods
        etabs_input = st.text_input(
            "ETABS Periods (comma-separated, in seconds)",
            placeholder="e.g., 0.245, 0.178, 0.156, 0.089, 0.067, 0.054",
            help="Enter the modal periods from ETABS analysis for comparison"
        )

        etabs_periods = None
        if etabs_input:
            try:
                etabs_periods = [float(x.strip()) for x in etabs_input.split(",")]
                st.success(f"Loaded {len(etabs_periods)} ETABS periods for comparison")
            except:
                st.error("Invalid format - please enter comma-separated numbers")

    # Run validation button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔬 Run Structural Validation", type="primary", use_container_width=True):
            with st.spinner("Running comprehensive structural validation..."):
                results = run_structural_validation(etabs_periods)

                # Store results in session state
                st.session_state.structural_validation_results = results
                st.session_state.validation_timestamp = datetime.datetime.now()

    # Debug file generation
    st.divider()
    st.subheader("🔧 Debug Tools")

    # Check if explicit model exists
    explicit_exists = os.path.exists("out/explicit_model.py")

    if not explicit_exists:
        st.warning("⚠️ No explicit model found. Generate it first to enable debug file creation.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔨 Generate Explicit Model", use_container_width=True, help="Creates explicit_model.py from current model artifacts"):
                with st.spinner("Generating explicit model..."):
                    success = generate_explicit_model_file()
                    if success:
                        st.success("✅ Explicit model generated successfully!")
                        st.rerun()  # Refresh to show the debug button
                    else:
                        st.error("❌ Failed to generate explicit model. Ensure model artifacts exist in 'out/' directory.")

        with col2:
            st.info("💡 **Explicit model includes:**\n- Complete OpenSees model setup\n- All nodes, elements, materials\n- Boundary conditions\n- Rigid diaphragms")

    else:
        st.success("✅ Explicit model available")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔨 Regenerate Explicit Model", use_container_width=True, help="Updates explicit_model.py from current artifacts"):
                with st.spinner("Regenerating explicit model..."):
                    success = generate_explicit_model_file()
                    if success:
                        st.success("✅ Explicit model regenerated!")
                    else:
                        st.error("❌ Failed to regenerate explicit model")

        with col2:
            if st.button("📄 Generate Debug OpenSeesPy File", use_container_width=True, help="Creates a standalone Python file for debugging lateral load analysis"):
                debug_content = generate_lateral_load_debug_file(etabs_periods)
                if debug_content:
                    st.success("Debug file generated successfully!")
                    st.download_button(
                    label="📥 Download lateral_load_debug.py",
                    data=debug_content,
                    file_name="lateral_load_debug.py",
                    mime="text/x-python",
                    use_container_width=True
                )
            else:
                st.error("Failed to generate debug file - ensure model artifacts are available")

    with col2:
        st.info("💡 **Debug file includes:**\n- Complete model setup\n- Lateral load application\n- Analysis execution\n- Error reporting\n- Results extraction")

    # Display results if available
    if hasattr(st.session_state, 'structural_validation_results'):
        st.divider()

        # Show timestamp
        if hasattr(st.session_state, 'validation_timestamp'):
            st.caption(f"Last run: {st.session_state.validation_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        # Display results
        display_validation_results(st.session_state.structural_validation_results)

        # Export options
        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            # Check if report file exists
            report_file = "out/structural_validation_report.json"
            if os.path.exists(report_file):
                with open(report_file, 'r') as f:
                    report_data = f.read()

                st.download_button(
                    label="📥 Download Validation Report (JSON)",
                    data=report_data,
                    file_name=f"validation_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )

        with col2:
            # Create summary CSV
            if "results" in st.session_state.structural_validation_results:
                summary_data = []
                for test in st.session_state.structural_validation_results["results"]:
                    summary_data.append({
                        "Test Name": test["name"],
                        "Status": "PASS" if test["passed"] else "FAIL",
                        "Severity": test["severity"],
                        "Message": test["message"]
                    })

                df = pd.DataFrame(summary_data)
                csv = df.to_csv(index=False)

                st.download_button(
                    label="📊 Download Summary (CSV)",
                    data=csv,
                    file_name=f"validation_summary_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    # Help section
    with st.expander("❓ Understanding Results", expanded=False):
        st.markdown("""
        ### Test Severity Levels:
        - **❌ Critical**: Must be fixed for valid model
        - **⚠️ Warning**: Should be reviewed but may be acceptable
        - **✅ Passed**: Test successful

        ### Key Validations:
        1. **Node/Element Count**: Ensures all structural members are translated
        2. **Connectivity**: Checks for orphaned elements or disconnected nodes
        3. **Mass Distribution**: Validates rigid diaphragm mass assignment
        4. **Lateral Load Path**: Verifies structural integrity under lateral loads
        5. **Modal Periods**: Compares dynamic properties with ETABS (if provided)

        ### Acceptable Tolerances:
        - Modal periods: ±5% difference from ETABS
        - Static equilibrium: ±1% load imbalance
        - Section properties: ±0.01% variation
        """)


def standalone_app():
    """Run as standalone Streamlit app"""
    st.set_page_config(
        page_title="Structural Validation",
        page_icon="🏗️",
        layout="wide"
    )

    st.title("🏗️ ETABS to OpenSees Model Validation")

    add_structural_validation_tab()


if __name__ == "__main__":
    standalone_app()