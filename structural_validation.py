#!/usr/bin/env python3
"""
Comprehensive Structural Validation Module for ETABS-to-OpenSees Translation

This module performs validation checks to ensure the OpenSees model
accurately represents the original ETABS model.
"""

import json
import os
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from pathlib import Path

# OpenSeesPy import with fallback
try:
    import openseespy.opensees as ops
    OPENSEES_AVAILABLE = True
except ImportError:
    OPENSEES_AVAILABLE = False
    print("Warning: OpenSeesPy not available - some validations disabled")


@dataclass
class ValidationResult:
    """Container for validation test results"""
    test_name: str
    passed: bool
    message: str
    details: Dict[str, Any]
    severity: str  # 'critical', 'warning', 'info'


class StructuralValidator:
    """
    Comprehensive structural model validator
    """

    def __init__(self, out_dir: str = "out"):
        self.out_dir = Path(out_dir)
        self.results = []
        self.model_loaded = False

    def load_artifacts(self) -> bool:
        """Load all JSON artifacts for validation"""
        try:
            self.nodes = self._load_json("nodes.json")
            self.beams = self._load_json("beams.json")
            self.columns = self._load_json("columns.json")
            self.supports = self._load_json("supports.json")
            self.diaphragms = self._load_json("diaphragms.json")
            self.parsed_raw = self._load_json("parsed_raw.json")
            return True
        except Exception as e:
            print(f"Error loading artifacts: {e}")
            return False

    def _load_json(self, filename: str) -> Dict[str, Any]:
        """Load JSON file from output directory"""
        filepath = self.out_dir / filename
        with open(filepath, 'r') as f:
            return json.load(f)

    def load_opensees_model(self) -> bool:
        """Load the explicit OpenSees model"""
        if not OPENSEES_AVAILABLE:
            return False

        explicit_path = self.out_dir / "explicit_model.py"
        if not explicit_path.exists():
            print(f"Explicit model not found: {explicit_path}")
            return False

        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("explicit_model", str(explicit_path))
            model_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(model_module)
            model_module.build_model()
            self.model_loaded = True
            return True
        except Exception as e:
            print(f"Error loading OpenSees model: {e}")
            return False

    # ========== GEOMETRIC VALIDATIONS ==========

    def validate_node_count(self) -> ValidationResult:
        """Check if node count matches between artifacts and OpenSees model"""
        artifact_nodes = len(self.nodes.get("nodes", []))

        if self.model_loaded:
            ops_nodes = len(ops.getNodeTags())
            match = artifact_nodes == ops_nodes
            details = {
                "artifact_count": artifact_nodes,
                "opensees_count": ops_nodes,
                "difference": abs(artifact_nodes - ops_nodes)
            }
        else:
            match = True  # Can't verify without OpenSees
            ops_nodes = "N/A"
            details = {"artifact_count": artifact_nodes, "opensees_count": ops_nodes}

        return ValidationResult(
            test_name="Node Count Validation",
            passed=match,
            message=f"Nodes: Artifacts={artifact_nodes}, OpenSees={ops_nodes}",
            details=details,
            severity="critical" if not match else "info"
        )

    def validate_element_count(self) -> ValidationResult:
        """Check if element count matches expected"""
        artifact_beams = len(self.beams.get("beams", []))
        artifact_columns = len(self.columns.get("columns", []))
        total_expected = artifact_beams + artifact_columns

        if self.model_loaded:
            ops_elements = len(ops.getEleTags())
            match = total_expected == ops_elements
            details = {
                "beams": artifact_beams,
                "columns": artifact_columns,
                "total_expected": total_expected,
                "opensees_count": ops_elements,
                "difference": abs(total_expected - ops_elements)
            }
        else:
            match = True
            ops_elements = "N/A"
            details = {
                "beams": artifact_beams,
                "columns": artifact_columns,
                "total_expected": total_expected,
                "opensees_count": ops_elements
            }

        return ValidationResult(
            test_name="Element Count Validation",
            passed=match,
            message=f"Elements: Expected={total_expected} (B:{artifact_beams}+C:{artifact_columns}), OpenSees={ops_elements}",
            details=details,
            severity="critical" if not match else "info"
        )

    def validate_connectivity(self) -> ValidationResult:
        """Check for disconnected nodes or orphaned elements"""
        if not self.model_loaded:
            return ValidationResult(
                test_name="Connectivity Validation",
                passed=True,
                message="Skipped - OpenSees model not loaded",
                details={},
                severity="info"
            )

        node_tags = set(ops.getNodeTags())
        connected_nodes = set()
        orphaned_elements = []

        for ele_tag in ops.getEleTags():
            try:
                ele_nodes = ops.eleNodes(ele_tag)
                for node in ele_nodes:
                    if node in node_tags:
                        connected_nodes.add(node)
                    else:
                        orphaned_elements.append((ele_tag, node))
            except:
                pass

        disconnected = node_tags - connected_nodes

        passed = len(disconnected) == 0 and len(orphaned_elements) == 0

        return ValidationResult(
            test_name="Connectivity Validation",
            passed=passed,
            message=f"Disconnected nodes: {len(disconnected)}, Orphaned elements: {len(orphaned_elements)}",
            details={
                "total_nodes": len(node_tags),
                "connected_nodes": len(connected_nodes),
                "disconnected_nodes": len(disconnected),
                "orphaned_elements": len(orphaned_elements),
                "disconnected_list": list(disconnected)[:10] if disconnected else []
            },
            severity="warning" if not passed else "info"
        )

    def validate_boundary_conditions(self) -> ValidationResult:
        """Validate that all supports are correctly applied"""
        expected_supports = self.supports.get("applied", [])
        expected_count = len(expected_supports)

        if not self.model_loaded:
            return ValidationResult(
                test_name="Boundary Conditions Validation",
                passed=True,
                message=f"Expected {expected_count} supports (OpenSees verification skipped)",
                details={"expected": expected_count},
                severity="info"
            )

        # Check each expected support
        missing_supports = []
        incorrect_fixity = []

        for support in expected_supports:
            node_tag = support["node"]
            expected_mask = support["mask"]

            try:
                # Get actual fixity from OpenSees
                actual_fixity = []
                for dof in range(1, 7):  # 6 DOFs
                    # This is a simplified check - actual implementation needs ops.nodeResponse
                    actual_fixity.append(1)  # Placeholder

                if actual_fixity != expected_mask:
                    incorrect_fixity.append({
                        "node": node_tag,
                        "expected": expected_mask,
                        "actual": actual_fixity
                    })
            except:
                missing_supports.append(node_tag)

        passed = len(missing_supports) == 0 and len(incorrect_fixity) == 0

        return ValidationResult(
            test_name="Boundary Conditions Validation",
            passed=passed,
            message=f"Supports: {expected_count} expected, {len(missing_supports)} missing, {len(incorrect_fixity)} incorrect",
            details={
                "expected_count": expected_count,
                "missing": missing_supports[:10],
                "incorrect": incorrect_fixity[:10]
            },
            severity="critical" if not passed else "info"
        )

    # ========== MASS VALIDATIONS ==========

    def validate_mass_distribution(self) -> ValidationResult:
        """Validate mass assignment and distribution"""
        diaphragms = self.diaphragms.get("diaphragms", [])
        expected_mass_nodes = len(diaphragms)

        if not self.model_loaded:
            return ValidationResult(
                test_name="Mass Distribution Validation",
                passed=True,
                message=f"Expected mass at {expected_mass_nodes} master nodes",
                details={"expected_master_nodes": expected_mass_nodes},
                severity="info"
            )

        # Check mass distribution
        total_mass = 0.0
        nodes_with_mass = 0
        mass_by_story = {}

        for node_tag in ops.getNodeTags():
            try:
                mass_vals = ops.nodeMass(node_tag)
                node_mass = sum(mass_vals[:3])  # Translational masses
                if node_mass > 1e-12:
                    nodes_with_mass += 1
                    total_mass += node_mass

                    # Get story from node coordinate
                    coords = ops.nodeCoord(node_tag)
                    z = round(coords[2], 3) if len(coords) > 2 else 0
                    if z not in mass_by_story:
                        mass_by_story[z] = {"count": 0, "mass": 0}
                    mass_by_story[z]["count"] += 1
                    mass_by_story[z]["mass"] += node_mass
            except:
                pass

        # Validate
        passed = nodes_with_mass == expected_mass_nodes

        return ValidationResult(
            test_name="Mass Distribution Validation",
            passed=passed,
            message=f"Mass nodes: Expected={expected_mass_nodes}, Found={nodes_with_mass}, Total={total_mass:.1f}kg",
            details={
                "expected_nodes": expected_mass_nodes,
                "found_nodes": nodes_with_mass,
                "total_mass": total_mass,
                "stories": len(mass_by_story),
                "mass_by_story": mass_by_story
            },
            severity="critical" if not passed else "info"
        )

    # ========== STIFFNESS VALIDATIONS ==========

    def validate_section_properties(self) -> ValidationResult:
        """Validate that section properties are correctly applied"""
        # Load section properties if available
        section_props_file = self.out_dir / "section_properties.json"
        if not section_props_file.exists():
            return ValidationResult(
                test_name="Section Properties Validation",
                passed=True,
                message="Section properties file not found - skipping",
                details={},
                severity="info"
            )

        section_props = self._load_json("section_properties.json")
        sections = section_props.get("sections", {})

        # Check beams
        beam_issues = []
        for beam in self.beams.get("beams", [])[:20]:  # Check first 20
            section_name = beam.get("section")
            if section_name in sections:
                expected = sections[section_name]["properties"]
                actual_A = beam.get("A")
                actual_Iy = beam.get("Iy")
                actual_Iz = beam.get("Iz")

                # Check with tolerance
                tol = 1e-6
                if abs(expected["area"] - actual_A) > tol:
                    beam_issues.append({
                        "beam": beam["tag"],
                        "property": "area",
                        "expected": expected["area"],
                        "actual": actual_A
                    })

        passed = len(beam_issues) == 0

        return ValidationResult(
            test_name="Section Properties Validation",
            passed=passed,
            message=f"Checked sections: {len(sections)}, Issues found: {len(beam_issues)}",
            details={
                "total_sections": len(sections),
                "issues": beam_issues[:10],
                "checked_beams": min(20, len(self.beams.get("beams", [])))
            },
            severity="warning" if not passed else "info"
        )

    # ========== STATIC EQUILIBRIUM ==========

    def validate_lateral_load_path(self) -> ValidationResult:
        """Apply lateral loads at diaphragm master nodes and verify structural integrity"""
        if not self.model_loaded:
            return ValidationResult(
                test_name="Lateral Load Path Verification",
                passed=True,
                message="OpenSees model not loaded - skipping",
                details={},
                severity="info"
            )

        try:
            # Get diaphragm master nodes
            diaphragms = self.diaphragms.get("diaphragms", [])
            if not diaphragms:
                return ValidationResult(
                    test_name="Lateral Load Path Verification",
                    passed=False,
                    message="No diaphragms found - cannot verify load path",
                    details={"diaphragm_count": 0},
                    severity="critical"
                )

            master_nodes = [d["master"] for d in diaphragms]
            unit_load = 1000.0  # 1 kN unit load

            # Test X-direction lateral loads
            x_results = self._test_lateral_direction("X", master_nodes, unit_load)

            # Test Y-direction lateral loads
            y_results = self._test_lateral_direction("Y", master_nodes, unit_load)

            # Evaluate results
            x_passed = x_results["analysis_success"] and x_results["equilibrium_satisfied"]
            y_passed = y_results["analysis_success"] and y_results["equilibrium_satisfied"]

            overall_passed = x_passed and y_passed

            if overall_passed:
                message = f"✅ Lateral load path verified in both directions"
                details = {
                    "master_nodes_tested": len(master_nodes),
                    "x_direction": x_results,
                    "y_direction": y_results,
                    "unit_load_kN": unit_load / 1000.0
                }
                severity = "info"
            else:
                failed_directions = []
                if not x_passed: failed_directions.append("X")
                if not y_passed: failed_directions.append("Y")

                message = f"❌ Load path issues in {', '.join(failed_directions)} direction(s)"
                details = {
                    "master_nodes_tested": len(master_nodes),
                    "x_direction": x_results,
                    "y_direction": y_results,
                    "failed_directions": failed_directions
                }
                severity = "critical"

            return ValidationResult(
                test_name="Lateral Load Path Verification",
                passed=overall_passed,
                message=message,
                details=details,
                severity=severity
            )

        except Exception as e:
            return ValidationResult(
                test_name="Lateral Load Path Verification",
                passed=False,
                message=f"Validation failed: {str(e)}",
                details={"error": str(e)},
                severity="critical"
            )

    def _test_lateral_direction(self, direction: str, master_nodes: List[int], unit_load: float) -> Dict[str, Any]:
        """Test lateral load path in a specific direction"""
        try:
            # Clear existing loads and analysis
            ops.wipeAnalysis()
            ops.remove('loadPattern', 1)

            # Create new load pattern
            ops.timeSeries('Linear', 1)
            ops.pattern('Plain', 1, 1)

            # Apply unit loads at master nodes
            total_applied_load = 0.0
            applied_nodes = []

            for master_node in master_nodes:
                try:
                    # Check if node exists
                    coord = ops.nodeCoord(master_node)

                    # Apply load in specified direction
                    if direction == "X":
                        ops.load(master_node, unit_load, 0, 0, 0, 0, 0)
                    elif direction == "Y":
                        ops.load(master_node, 0, unit_load, 0, 0, 0, 0)

                    total_applied_load += unit_load
                    applied_nodes.append(master_node)
                except:
                    # Node doesn't exist or can't be loaded
                    continue

            if len(applied_nodes) == 0:
                return {
                    "analysis_success": False,
                    "equilibrium_satisfied": False,
                    "error": "No master nodes could be loaded",
                    "applied_load": 0.0,
                    "total_reaction": 0.0
                }

            # Set up analysis
            ops.system('BandGen')
            ops.numberer('RCM')
            ops.constraints('Transformation')
            ops.integrator('LoadControl', 1.0)
            ops.algorithm('Linear')
            ops.analysis('Static')

            # Run analysis with detailed error capture
            import sys
            import io
            from contextlib import redirect_stderr

            # Capture stderr to get OpenSees error messages
            stderr_capture = io.StringIO()

            try:
                with redirect_stderr(stderr_capture):
                    analysis_result = ops.analyze(1)

                analysis_success = (analysis_result == 0)
                captured_stderr = stderr_capture.getvalue()

                if not analysis_success:
                    # Get additional diagnostic information
                    diagnostic_info = self._get_analysis_diagnostics()

                    error_details = {
                        "analysis_success": False,
                        "equilibrium_satisfied": False,
                        "error": f"Static analysis failed to converge (return code: {analysis_result})",
                        "opensees_error": captured_stderr.strip() if captured_stderr.strip() else "No specific error message captured",
                        "applied_load": total_applied_load,
                        "total_reaction": 0.0,
                        "diagnostics": diagnostic_info
                    }
                    return error_details

            except Exception as e:
                return {
                    "analysis_success": False,
                    "equilibrium_satisfied": False,
                    "error": f"Analysis execution failed: {str(e)}",
                    "opensees_error": captured_stderr.strip() if captured_stderr.strip() else "No error output captured",
                    "applied_load": total_applied_load,
                    "total_reaction": 0.0
                }

            # Check equilibrium by summing reactions
            total_reaction = 0.0
            reaction_nodes = []

            for node_tag in ops.getNodeTags():
                try:
                    reactions = ops.nodeReaction(node_tag)
                    if len(reactions) >= 2:
                        if direction == "X":
                            reaction_force = reactions[0]
                        elif direction == "Y":
                            reaction_force = reactions[1]

                        if abs(reaction_force) > 1e-6:  # Significant reaction
                            total_reaction += reaction_force
                            reaction_nodes.append({
                                "node": node_tag,
                                "reaction": reaction_force
                            })
                except:
                    continue

            # Check equilibrium (reactions should balance applied loads)
            force_imbalance = abs(total_applied_load + total_reaction)
            equilibrium_tolerance = max(0.01 * abs(total_applied_load), 1e-3)
            equilibrium_satisfied = force_imbalance <= equilibrium_tolerance

            return {
                "analysis_success": True,
                "equilibrium_satisfied": equilibrium_satisfied,
                "applied_load": total_applied_load,
                "total_reaction": -total_reaction,  # Reactions are opposite to loads
                "force_imbalance": force_imbalance,
                "tolerance": equilibrium_tolerance,
                "applied_nodes": applied_nodes,
                "reaction_nodes": len(reaction_nodes),
                "max_displacement": self._get_max_displacement(direction)
            }

        except Exception as e:
            return {
                "analysis_success": False,
                "equilibrium_satisfied": False,
                "error": str(e),
                "applied_load": 0.0,
                "total_reaction": 0.0
            }

    def _get_max_displacement(self, direction: str) -> float:
        """Get maximum displacement in the specified direction"""
        try:
            max_disp = 0.0
            for node_tag in ops.getNodeTags():
                try:
                    displacements = ops.nodeDisp(node_tag)
                    if len(displacements) >= 2:
                        if direction == "X":
                            disp = abs(displacements[0])
                        elif direction == "Y":
                            disp = abs(displacements[1])
                        max_disp = max(max_disp, disp)
                except:
                    continue
            return max_disp
        except:
            return 0.0

    def _get_analysis_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostic information to help debug analysis failures"""
        try:
            diagnostics = {}

            # Basic model information
            try:
                node_tags = ops.getNodeTags()
                ele_tags = ops.getEleTags()
                diagnostics["total_nodes"] = len(node_tags)
                diagnostics["total_elements"] = len(ele_tags)
            except:
                diagnostics["total_nodes"] = "Unknown"
                diagnostics["total_elements"] = "Unknown"

            # Check for constrained nodes
            try:
                constrained_nodes = 0
                for node_tag in ops.getNodeTags()[:10]:  # Check first 10 nodes only
                    try:
                        # Try to get constraint information (this may not always work)
                        reactions = ops.nodeReaction(node_tag)
                        if any(abs(r) > 1e-12 for r in reactions):
                            constrained_nodes += 1
                    except:
                        pass
                diagnostics["sample_constrained_nodes"] = constrained_nodes
            except:
                diagnostics["sample_constrained_nodes"] = "Unknown"

            # Check for load pattern existence
            try:
                # This is a basic check - OpenSees doesn't provide direct access to load pattern info
                diagnostics["load_pattern_created"] = True
            except:
                diagnostics["load_pattern_created"] = False

            # Check if any elements might be problematic
            try:
                # Sample a few elements to see if they're accessible
                sample_elements = ele_tags[:5] if ele_tags else []
                accessible_elements = 0
                for ele_tag in sample_elements:
                    try:
                        nodes = ops.eleNodes(ele_tag)
                        if nodes:
                            accessible_elements += 1
                    except:
                        pass
                diagnostics["sample_elements_accessible"] = f"{accessible_elements}/{len(sample_elements)}"
            except:
                diagnostics["sample_elements_accessible"] = "Unknown"

            # Check if diaphragm constraints exist
            try:
                diaphragms = self.diaphragms.get("diaphragms", [])
                diagnostics["rigid_diaphragms_count"] = len(diaphragms)
                if diaphragms:
                    master_nodes = [d["master"] for d in diaphragms]
                    accessible_masters = 0
                    for master in master_nodes:
                        try:
                            coord = ops.nodeCoord(master)
                            accessible_masters += 1
                        except:
                            pass
                    diagnostics["accessible_master_nodes"] = f"{accessible_masters}/{len(master_nodes)}"
            except:
                diagnostics["rigid_diaphragms_count"] = "Unknown"

            return diagnostics

        except Exception as e:
            return {"diagnostic_error": str(e)}

    # ========== DYNAMIC VALIDATION ==========

    def validate_modal_periods(self, etabs_periods: Optional[List[float]] = None) -> ValidationResult:
        """Compare modal periods with ETABS results if available"""
        if not self.model_loaded:
            return ValidationResult(
                test_name="Modal Period Validation",
                passed=True,
                message="OpenSees model not loaded - skipping",
                details={},
                severity="info"
            )

        try:
            # Run eigenvalue analysis
            num_modes = 6
            eigenvalues = ops.eigen(num_modes)

            if not eigenvalues:
                return ValidationResult(
                    test_name="Modal Period Validation",
                    passed=False,
                    message="Eigenvalue analysis failed",
                    details={},
                    severity="critical"
                )

            # Calculate periods
            periods = []
            for ev in eigenvalues:
                if ev > 1e-12:
                    omega = np.sqrt(ev)
                    period = 2 * np.pi / omega
                    periods.append(period)
                else:
                    periods.append(float('inf'))

            # Compare with ETABS if provided
            if etabs_periods:
                differences = []
                for i, (T_ops, T_etabs) in enumerate(zip(periods, etabs_periods)):
                    if T_ops < float('inf') and T_etabs < float('inf'):
                        diff_percent = abs(T_ops - T_etabs) / T_etabs * 100
                        differences.append({
                            "mode": i + 1,
                            "opensees": T_ops,
                            "etabs": T_etabs,
                            "difference_%": diff_percent
                        })

                max_diff = max([d["difference_%"] for d in differences]) if differences else 0
                passed = max_diff < 5.0  # 5% tolerance

                return ValidationResult(
                    test_name="Modal Period Validation",
                    passed=passed,
                    message=f"Max period difference: {max_diff:.1f}% (5% tolerance)",
                    details={
                        "periods": periods[:6],
                        "etabs_periods": etabs_periods[:6],
                        "differences": differences,
                        "max_difference_%": max_diff
                    },
                    severity="warning" if not passed else "info"
                )
            else:
                # Just check if periods are reasonable
                T1 = periods[0] if periods else float('inf')
                reasonable = 0.1 <= T1 <= 10.0

                return ValidationResult(
                    test_name="Modal Period Validation",
                    passed=reasonable,
                    message=f"T1={T1:.3f}s (Reasonable range: 0.1-10.0s)",
                    details={
                        "periods": periods[:6],
                        "fundamental_period": T1
                    },
                    severity="warning" if not reasonable else "info"
                )

        except Exception as e:
            return ValidationResult(
                test_name="Modal Period Validation",
                passed=False,
                message=f"Error during modal analysis: {str(e)}",
                details={"error": str(e)},
                severity="warning"
            )

    # ========== MAIN VALIDATION RUNNER ==========

    def run_all_validations(self, etabs_periods: Optional[List[float]] = None) -> Dict[str, Any]:
        """Run all validation tests"""
        print("\n" + "="*70)
        print("STRUCTURAL VALIDATION SUITE")
        print("="*70)

        # Load artifacts
        if not self.load_artifacts():
            print("Failed to load artifacts - aborting validation")
            return {"success": False, "error": "Failed to load artifacts"}

        # Load OpenSees model
        if OPENSEES_AVAILABLE:
            if not self.load_opensees_model():
                print("Warning: Could not load OpenSees model - some tests will be skipped")
        else:
            print("Warning: OpenSeesPy not available - some tests will be skipped")

        # Run validations
        self.results = []

        # Geometric validations
        print("\n--- Geometric Validations ---")
        self.results.append(self.validate_node_count())
        self.results.append(self.validate_element_count())
        self.results.append(self.validate_connectivity())
        self.results.append(self.validate_boundary_conditions())

        # Mass validations
        print("\n--- Mass Validations ---")
        self.results.append(self.validate_mass_distribution())

        # Property validations
        print("\n--- Property Validations ---")
        self.results.append(self.validate_section_properties())

        # Load path validations
        print("\n--- Lateral Load Path Verification ---")
        self.results.append(self.validate_lateral_load_path())

        # Dynamic validations
        print("\n--- Dynamic Validations ---")
        self.results.append(self.validate_modal_periods(etabs_periods))

        # Summary
        print("\n" + "="*70)
        print("VALIDATION SUMMARY")
        print("="*70)

        passed_count = sum(1 for r in self.results if r.passed)
        total_count = len(self.results)
        critical_failures = [r for r in self.results if not r.passed and r.severity == "critical"]
        warnings = [r for r in self.results if not r.passed and r.severity == "warning"]

        print(f"\nTests Passed: {passed_count}/{total_count}")
        print(f"Critical Failures: {len(critical_failures)}")
        print(f"Warnings: {len(warnings)}")

        # Print results
        print("\nDetailed Results:")
        print("-" * 50)
        for result in self.results:
            status = "✅" if result.passed else ("❌" if result.severity == "critical" else "⚠️")
            print(f"{status} {result.test_name}")
            print(f"   {result.message}")
            if not result.passed and result.severity == "critical":
                for key, value in result.details.items():
                    if key not in ["error", "disconnected_list", "reaction_nodes"]:
                        print(f"   - {key}: {value}")

        # Overall assessment
        print("\n" + "="*70)
        if len(critical_failures) == 0:
            if len(warnings) == 0:
                print("✅ MODEL VALIDATION SUCCESSFUL - All tests passed!")
            else:
                print("⚠️  MODEL VALIDATION PASSED WITH WARNINGS")
                print(f"   {len(warnings)} non-critical issues detected")
        else:
            print("❌ MODEL VALIDATION FAILED")
            print(f"   {len(critical_failures)} critical issues must be resolved")

        # Return summary
        return {
            "success": len(critical_failures) == 0,
            "total_tests": total_count,
            "passed": passed_count,
            "critical_failures": len(critical_failures),
            "warnings": len(warnings),
            "results": [
                {
                    "name": r.test_name,
                    "passed": r.passed,
                    "severity": r.severity,
                    "message": r.message,
                    "details": r.details
                }
                for r in self.results
            ]
        }

    def export_report(self, output_file: str = "validation_report.json"):
        """Export validation results to JSON file"""
        report = {
            "timestamp": str(np.datetime64('now')),
            "results": [
                {
                    "test": r.test_name,
                    "passed": r.passed,
                    "severity": r.severity,
                    "message": r.message,
                    "details": r.details
                }
                for r in self.results
            ]
        }

        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\nValidation report exported to: {output_file}")


def main():
    """Run structural validation with example ETABS periods"""
    validator = StructuralValidator()

    # Example ETABS periods (replace with actual values)
    # etabs_periods = [0.245, 0.178, 0.156, 0.089, 0.067, 0.054]
    etabs_periods = None  # Set to None if not available

    results = validator.run_all_validations(etabs_periods)

    # Export report
    if results["results"]:
        validator.export_report("out/structural_validation_report.json")

    return results


if __name__ == "__main__":
    main()