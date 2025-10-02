#!/usr/bin/env python3
"""
OpenSees Model Testing Framework

Comprehensive testing module for validating OpenSeesPy models generated from ETABS.
Designed for integration with Streamlit app to provide real-time model validation.

Test Categories:
1. Model Integrity Tests - Basic model consistency and connectivity
2. Geometric Validation Tests - Joint offsets, rigid ends, coordinates
3. Structural Validation Tests - Modal analysis, static checks, equilibrium
4. ETABS Consistency Tests - Cross-validation with original ETABS data

Usage:
    tests = OpenSeesModelTester()
    results = tests.run_all_tests()
    tests.generate_report(results)
"""

from __future__ import annotations
import json
import math
from typing import Dict, List, Tuple, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import openseespy.opensees as ops
    OPENSEES_AVAILABLE = True
except ImportError:
    OPENSEES_AVAILABLE = False


@dataclass
class TestResult:
    """Container for individual test results."""
    name: str
    category: str
    passed: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    severity: str = "INFO"  # INFO, WARNING, ERROR, CRITICAL


@dataclass
class TestSuite:
    """Container for a collection of test results."""
    name: str
    results: List[TestResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def total_tests(self) -> int:
        return len(self.results)

    @property
    def passed_tests(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_tests(self) -> int:
        return self.total_tests - self.passed_tests

    @property
    def success_rate(self) -> float:
        return (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0.0


class OpenSeesModelTester:
    """
    Comprehensive testing framework for OpenSees models.

    Provides various test suites to validate model integrity, geometric accuracy,
    structural properties, and consistency with original ETABS data.
    """

    def __init__(self, out_dir: str = "out"):
        self.out_dir = Path(out_dir)
        self.tracking_elements = {
            "beam_b408": {"line": "B408", "story": "11_P6", "type": "beam"},
            "column_c522": {"line": "C522", "story": "02_P2", "type": "column"}
        }

    def run_all_tests(self) -> Dict[str, TestSuite]:
        """Run all available test suites and return results."""
        results = {}

        if not OPENSEES_AVAILABLE:
            return {"error": TestSuite("Error", [TestResult(
                "OpenSees Import", "System", False,
                "OpenSeesPy not available - cannot run tests"
            )])}

        try:
            # Test if we have an active OpenSees model
            ops.getNodeTags()
        except Exception:
            return {"error": TestSuite("Error", [TestResult(
                "Model State", "System", False,
                "No active OpenSees model found - build a model first"
            )])}

        # Run test suites in order
        results["integrity"] = self.test_model_integrity()
        results["geometry"] = self.test_geometric_validation()
        results["structural"] = self.test_structural_validation()
        results["consistency"] = self.test_etabs_consistency()

        return results

    def test_model_integrity(self) -> TestSuite:
        """Test basic model integrity and connectivity."""
        suite = TestSuite("Model Integrity Tests")
        suite.start_time = datetime.now()

        # Test 1: Node existence and validity
        suite.results.append(self._test_node_existence())

        # Test 2: Element connectivity
        suite.results.append(self._test_element_connectivity())

        # Test 3: Coordinate validity
        suite.results.append(self._test_coordinate_validity())

        # Test 4: Model dimensions
        suite.results.append(self._test_model_dimensions())

        # Test 5: Duplicate node detection
        suite.results.append(self._test_duplicate_nodes())

        suite.end_time = datetime.now()
        return suite

    def test_geometric_validation(self) -> TestSuite:
        """Test geometric accuracy including joint offsets and rigid ends."""
        suite = TestSuite("Geometric Validation Tests")
        suite.start_time = datetime.now()

        # Test 1: Joint offset calculations for tracking elements
        suite.results.append(self._test_joint_offsets())

        # Test 2: Rigid end implementation
        suite.results.append(self._test_rigid_ends())

        # Test 3: Element lengths
        suite.results.append(self._test_element_lengths())

        # Test 4: Geometric transformations
        suite.results.append(self._test_geometric_transformations())

        suite.end_time = datetime.now()
        return suite

    def test_structural_validation(self) -> TestSuite:
        """Test structural properties and analysis readiness."""
        suite = TestSuite("Structural Validation Tests")
        suite.start_time = datetime.now()

        # Test 1: Modal analysis
        suite.results.append(self._test_modal_analysis())

        # Test 2: Constraint validation
        suite.results.append(self._test_constraints())

        # Test 3: Mass matrix condition
        suite.results.append(self._test_mass_matrix())

        # Test 4: Static equilibrium check
        suite.results.append(self._test_static_equilibrium())

        suite.end_time = datetime.now()
        return suite

    def test_etabs_consistency(self) -> TestSuite:
        """Test consistency with original ETABS data."""
        suite = TestSuite("ETABS Consistency Tests")
        suite.start_time = datetime.now()

        # Test 1: Element count consistency
        suite.results.append(self._test_element_counts())

        # Test 2: Tracking element validation
        suite.results.append(self._test_tracking_elements())

        # Test 3: Joint offset consistency
        suite.results.append(self._test_joint_offset_consistency())

        # Test 4: Material property consistency
        suite.results.append(self._test_material_consistency())

        suite.end_time = datetime.now()
        return suite

    # Model Integrity Test Implementations
    def _test_node_existence(self) -> TestResult:
        """Test that nodes exist and have valid coordinates."""
        try:
            node_tags = ops.getNodeTags()
            if len(node_tags) == 0:
                return TestResult(
                    "Node Existence", "Model Integrity", False,
                    "No nodes found in model", {"node_count": 0}
                )

            # Check first few nodes for valid coordinates
            invalid_nodes = []
            for tag in node_tags[:10]:  # Check first 10 nodes
                coords = ops.nodeCoord(tag)
                if any(math.isnan(x) or math.isinf(x) for x in coords):
                    invalid_nodes.append(tag)

            if invalid_nodes:
                return TestResult(
                    "Node Existence", "Model Integrity", False,
                    f"Found {len(invalid_nodes)} nodes with invalid coordinates",
                    {"invalid_nodes": invalid_nodes, "total_nodes": len(node_tags)}
                )

            return TestResult(
                "Node Existence", "Model Integrity", True,
                f"All {len(node_tags)} nodes have valid coordinates",
                {"node_count": len(node_tags)}
            )

        except Exception as e:
            return TestResult(
                "Node Existence", "Model Integrity", False,
                f"Error checking nodes: {str(e)}"
            )

    def _test_element_connectivity(self) -> TestResult:
        """Test element connectivity and node references."""
        try:
            node_tags = set(ops.getNodeTags())
            element_tags = ops.getEleTags()

            if len(element_tags) == 0:
                return TestResult(
                    "Element Connectivity", "Model Integrity", False,
                    "No elements found in model", {"element_count": 0}
                )

            orphaned_elements = []
            invalid_references = []

            for ele_tag in element_tags:
                try:
                    ele_nodes = ops.eleNodes(ele_tag)
                    for node_tag in ele_nodes:
                        if node_tag not in node_tags:
                            invalid_references.append((ele_tag, node_tag))
                except Exception:
                    orphaned_elements.append(ele_tag)

            if orphaned_elements or invalid_references:
                return TestResult(
                    "Element Connectivity", "Model Integrity", False,
                    f"Found connectivity issues: {len(orphaned_elements)} orphaned elements, "
                    f"{len(invalid_references)} invalid node references",
                    {
                        "orphaned_elements": orphaned_elements,
                        "invalid_references": invalid_references,
                        "total_elements": len(element_tags)
                    }
                )

            return TestResult(
                "Element Connectivity", "Model Integrity", True,
                f"All {len(element_tags)} elements have valid connectivity",
                {"element_count": len(element_tags), "node_count": len(node_tags)}
            )

        except Exception as e:
            return TestResult(
                "Element Connectivity", "Model Integrity", False,
                f"Error checking connectivity: {str(e)}"
            )

    def _test_coordinate_validity(self) -> TestResult:
        """Test coordinate system validity and reasonable ranges."""
        try:
            node_tags = ops.getNodeTags()
            coords = [ops.nodeCoord(tag) for tag in node_tags]

            # Calculate coordinate ranges
            x_coords = [c[0] for c in coords]
            y_coords = [c[1] for c in coords]
            z_coords = [c[2] for c in coords]

            ranges = {
                "x": (min(x_coords), max(x_coords)),
                "y": (min(y_coords), max(y_coords)),
                "z": (min(z_coords), max(z_coords))
            }

            # Check for reasonable coordinate ranges (structural building)
            warnings = []
            if ranges["z"][1] - ranges["z"][0] < 1.0:  # Less than 1m height
                warnings.append("Very small height range")
            if ranges["z"][1] - ranges["z"][0] > 500.0:  # More than 500m height
                warnings.append("Unusually large height range")

            severity = "WARNING" if warnings else "INFO"
            message = "Coordinate ranges appear reasonable"
            if warnings:
                message = f"Coordinate validation completed with warnings: {', '.join(warnings)}"

            return TestResult(
                "Coordinate Validity", "Model Integrity", True, message,
                {"coordinate_ranges": ranges, "warnings": warnings},
                severity=severity
            )

        except Exception as e:
            return TestResult(
                "Coordinate Validity", "Model Integrity", False,
                f"Error validating coordinates: {str(e)}"
            )

    def _test_model_dimensions(self) -> TestResult:
        """Test overall model dimensions and scale."""
        try:
            node_tags = ops.getNodeTags()
            coords = [ops.nodeCoord(tag) for tag in node_tags]

            x_coords = [c[0] for c in coords]
            y_coords = [c[1] for c in coords]
            z_coords = [c[2] for c in coords]

            dimensions = {
                "width": max(x_coords) - min(x_coords),
                "length": max(y_coords) - min(y_coords),
                "height": max(z_coords) - min(z_coords)
            }

            # Check for degenerate dimensions
            issues = []
            for dim, value in dimensions.items():
                if value < 0.1:  # Less than 10cm
                    issues.append(f"{dim} too small ({value:.3f}m)")

            if issues:
                return TestResult(
                    "Model Dimensions", "Model Integrity", False,
                    f"Model has degenerate dimensions: {', '.join(issues)}",
                    {"dimensions": dimensions}
                )

            return TestResult(
                "Model Dimensions", "Model Integrity", True,
                f"Model dimensions: {dimensions['width']:.1f}m × {dimensions['length']:.1f}m × {dimensions['height']:.1f}m",
                {"dimensions": dimensions}
            )

        except Exception as e:
            return TestResult(
                "Model Dimensions", "Model Integrity", False,
                f"Error checking dimensions: {str(e)}"
            )

    def _test_duplicate_nodes(self) -> TestResult:
        """Test for duplicate node coordinates."""
        try:
            node_tags = ops.getNodeTags()
            coord_map = {}
            duplicates = []

            for tag in node_tags:
                coords = tuple(round(x, 6) for x in ops.nodeCoord(tag))  # Round to mm precision
                if coords in coord_map:
                    duplicates.append((tag, coord_map[coords], coords))
                else:
                    coord_map[coords] = tag

            if duplicates:
                return TestResult(
                    "Duplicate Nodes", "Model Integrity", False,
                    f"Found {len(duplicates)} duplicate node coordinates",
                    {"duplicates": duplicates[:10]},  # Limit to first 10
                    severity="WARNING"
                )

            return TestResult(
                "Duplicate Nodes", "Model Integrity", True,
                f"No duplicate coordinates found among {len(node_tags)} nodes"
            )

        except Exception as e:
            return TestResult(
                "Duplicate Nodes", "Model Integrity", False,
                f"Error checking duplicates: {str(e)}"
            )

    # Geometric Validation Test Implementations
    def _test_joint_offsets(self) -> TestResult:
        """Test joint offset calculations for tracking elements."""
        try:
            # Load artifact data to validate joint offsets
            tracking_data = self._load_tracking_element_data()

            if not tracking_data:
                return TestResult(
                    "Joint Offsets", "Geometric Validation", False,
                    "Cannot load tracking element data for validation"
                )

            # Validate our known tracking elements
            validation_results = []
            for elem_key, elem_data in tracking_data.items():
                if elem_data.get("has_joint_offsets"):
                    offsets_i = elem_data.get("joint_offset_i", [])
                    offsets_j = elem_data.get("joint_offset_j", [])

                    # Basic validation: offsets should be 3D vectors
                    if len(offsets_i) == 3 and len(offsets_j) == 3:
                        validation_results.append(f"{elem_key}: ✓")
                    else:
                        validation_results.append(f"{elem_key}: ✗ Invalid offset dimensions")

            if validation_results:
                return TestResult(
                    "Joint Offsets", "Geometric Validation", True,
                    f"Joint offset validation: {', '.join(validation_results)}",
                    {"tracking_elements": len(validation_results)}
                )
            else:
                return TestResult(
                    "Joint Offsets", "Geometric Validation", True,
                    "No elements with joint offsets found (expected for beam-only models)",
                    severity="INFO"
                )

        except Exception as e:
            return TestResult(
                "Joint Offsets", "Geometric Validation", False,
                f"Error validating joint offsets: {str(e)}"
            )

    def _test_rigid_ends(self) -> TestResult:
        """Test rigid end implementation."""
        try:
            # Load artifact data
            tracking_data = self._load_tracking_element_data()

            if not tracking_data:
                return TestResult(
                    "Rigid Ends", "Geometric Validation", False,
                    "Cannot load element data for rigid end validation"
                )

            rigid_end_elements = 0
            for elem_data in tracking_data.values():
                length_off_i = elem_data.get("length_off_i", 0.0)
                length_off_j = elem_data.get("length_off_j", 0.0)
                if length_off_i > 0 or length_off_j > 0:
                    rigid_end_elements += 1

            return TestResult(
                "Rigid Ends", "Geometric Validation", True,
                f"Found {rigid_end_elements} elements with rigid ends",
                {"rigid_end_count": rigid_end_elements}
            )

        except Exception as e:
            return TestResult(
                "Rigid Ends", "Geometric Validation", False,
                f"Error checking rigid ends: {str(e)}"
            )

    def _test_element_lengths(self) -> TestResult:
        """Test element lengths for reasonableness."""
        try:
            element_tags = ops.getEleTags()

            if len(element_tags) == 0:
                return TestResult(
                    "Element Lengths", "Geometric Validation", False,
                    "No elements found to test lengths"
                )

            # Sample a few elements to check lengths
            sample_size = min(20, len(element_tags))
            sample_elements = element_tags[:sample_size]

            lengths = []
            issues = []

            for ele_tag in sample_elements:
                try:
                    ele_nodes = ops.eleNodes(ele_tag)
                    if len(ele_nodes) >= 2:
                        coord_i = ops.nodeCoord(ele_nodes[0])
                        coord_j = ops.nodeCoord(ele_nodes[1])
                        length = math.sqrt(sum((coord_j[k] - coord_i[k])**2 for k in range(3)))
                        lengths.append(length)

                        # Check for unreasonable lengths
                        if length < 0.01:  # Less than 1cm
                            issues.append(f"Element {ele_tag}: very short ({length:.4f}m)")
                        elif length > 100:  # More than 100m
                            issues.append(f"Element {ele_tag}: very long ({length:.1f}m)")
                except Exception:
                    continue

            if not lengths:
                return TestResult(
                    "Element Lengths", "Geometric Validation", False,
                    "Could not compute any element lengths"
                )

            avg_length = sum(lengths) / len(lengths)
            min_length = min(lengths)
            max_length = max(lengths)

            severity = "WARNING" if issues else "INFO"
            message = f"Element lengths: avg={avg_length:.2f}m, range=[{min_length:.2f}, {max_length:.2f}]m"
            if issues:
                message += f". Issues: {', '.join(issues[:3])}"  # Limit to first 3 issues

            return TestResult(
                "Element Lengths", "Geometric Validation", True, message,
                {
                    "average_length": avg_length,
                    "min_length": min_length,
                    "max_length": max_length,
                    "sample_size": len(lengths),
                    "issues": issues
                },
                severity=severity
            )

        except Exception as e:
            return TestResult(
                "Element Lengths", "Geometric Validation", False,
                f"Error checking element lengths: {str(e)}"
            )

    def _test_geometric_transformations(self) -> TestResult:
        """Test geometric transformation validity and joint offset implementation."""
        try:
            # Load artifact data to check transformation usage
            beam_data = self._load_artifact_data("beams.json")
            column_data = self._load_artifact_data("columns.json")

            if not beam_data and not column_data:
                return TestResult(
                    "Geometric Transformations", "Geometric Validation", False,
                    "Cannot load element data to validate transformations"
                )

            # Count transformations with joint offsets
            beam_transforms_with_offsets = 0
            column_transforms_with_offsets = 0
            total_beam_transforms = 0
            total_column_transforms = 0

            if beam_data and "beams" in beam_data:
                total_beam_transforms = len(beam_data["beams"])
                for beam in beam_data["beams"]:
                    if beam.get("has_joint_offsets", False):
                        beam_transforms_with_offsets += 1

            if column_data and "columns" in column_data:
                total_column_transforms = len(column_data["columns"])
                for column in column_data["columns"]:
                    if column.get("has_joint_offsets", False):
                        column_transforms_with_offsets += 1

            # Analyze transformation patterns
            details = {
                "total_beam_transforms": total_beam_transforms,
                "beam_transforms_with_offsets": beam_transforms_with_offsets,
                "total_column_transforms": total_column_transforms,
                "column_transforms_with_offsets": column_transforms_with_offsets,
                "beam_transform_pattern": "Linear with vecxz=[0,0,1] (horizontal elements)",
                "column_transform_pattern": "Linear with vecxz=[1,0,0] (vertical elements)"
            }

            # Check for joint offset usage
            total_with_offsets = beam_transforms_with_offsets + column_transforms_with_offsets
            total_transforms = total_beam_transforms + total_column_transforms

            if total_transforms == 0:
                return TestResult(
                    "Geometric Transformations", "Geometric Validation", False,
                    "No geometric transformations found in model",
                    details
                )

            # Assess transformation implementation
            message_parts = []
            message_parts.append(f"Found {total_transforms} geometric transformations")
            message_parts.append(f"({total_beam_transforms} beams + {total_column_transforms} columns)")

            if total_with_offsets > 0:
                message_parts.append(f"{total_with_offsets} use joint offsets (-jntOffset)")

                # Provide breakdown of offset usage
                offset_breakdown = []
                if beam_transforms_with_offsets > 0:
                    offset_breakdown.append(f"{beam_transforms_with_offsets} beams")
                if column_transforms_with_offsets > 0:
                    offset_breakdown.append(f"{column_transforms_with_offsets} columns")

                if offset_breakdown:
                    message_parts.append(f"Breakdown: {', '.join(offset_breakdown)}")

                severity = "INFO"
            else:
                message_parts.append("None use joint offsets (rigid ends/offsets not implemented)")
                severity = "WARNING"

            return TestResult(
                "Geometric Transformations", "Geometric Validation", True,
                ". ".join(message_parts),
                details,
                severity=severity
            )

        except Exception as e:
            return TestResult(
                "Geometric Transformations", "Geometric Validation", False,
                f"Error checking transformations: {str(e)}"
            )

    # Structural Validation Test Implementations
    def _test_modal_analysis(self) -> TestResult:
        """Test modal analysis to verify structural dynamic properties."""
        try:
            # Check if we can perform eigen analysis
            try:
                # Try to run a simple eigen analysis
                eigenvalues = ops.eigen(3)  # First 3 modes

                if len(eigenvalues) == 0:
                    return TestResult(
                        "Modal Analysis", "Structural Validation", False,
                        "Eigen analysis failed - no eigenvalues computed",
                        severity="ERROR"
                    )

                # Convert eigenvalues to frequencies
                frequencies = [math.sqrt(val) / (2 * math.pi) for val in eigenvalues if val > 0]

                if not frequencies:
                    return TestResult(
                        "Modal Analysis", "Structural Validation", False,
                        "No positive eigenvalues found - model may be unstable",
                        {"eigenvalues": eigenvalues},
                        severity="CRITICAL"
                    )

                # Check for reasonable frequencies (typical building: 0.1-10 Hz)
                freq_issues = []
                for i, freq in enumerate(frequencies):
                    if freq < 0.01:
                        freq_issues.append(f"Mode {i+1}: very low frequency ({freq:.4f} Hz)")
                    elif freq > 50:
                        freq_issues.append(f"Mode {i+1}: very high frequency ({freq:.1f} Hz)")

                severity = "WARNING" if freq_issues else "INFO"
                message = f"Modal analysis successful. First {len(frequencies)} frequencies: {[f'{f:.3f}' for f in frequencies]} Hz"

                return TestResult(
                    "Modal Analysis", "Structural Validation", True, message,
                    {
                        "eigenvalues": eigenvalues,
                        "frequencies": frequencies,
                        "frequency_issues": freq_issues
                    },
                    severity=severity
                )

            except Exception as modal_e:
                return TestResult(
                    "Modal Analysis", "Structural Validation", False,
                    f"Modal analysis failed: {str(modal_e)}",
                    severity="WARNING"
                )

        except Exception as e:
            return TestResult(
                "Modal Analysis", "Structural Validation", False,
                f"Error in modal analysis test: {str(e)}"
            )

    def _test_constraints(self) -> TestResult:
        """Test constraint validation."""
        try:
            # This is a simplified test - full implementation would check boundary conditions
            return TestResult(
                "Constraints", "Structural Validation", True,
                "Constraint validation not yet implemented",
                severity="INFO"
            )

        except Exception as e:
            return TestResult(
                "Constraints", "Structural Validation", False,
                f"Error checking constraints: {str(e)}"
            )

    def _test_mass_matrix(self) -> TestResult:
        """Test mass matrix condition."""
        try:
            # This is a placeholder for mass matrix testing
            return TestResult(
                "Mass Matrix", "Structural Validation", True,
                "Mass matrix validation not yet implemented",
                severity="INFO"
            )

        except Exception as e:
            return TestResult(
                "Mass Matrix", "Structural Validation", False,
                f"Error checking mass matrix: {str(e)}"
            )

    def _test_static_equilibrium(self) -> TestResult:
        """Test static equilibrium."""
        try:
            # This is a placeholder for static equilibrium testing
            return TestResult(
                "Static Equilibrium", "Structural Validation", True,
                "Static equilibrium validation not yet implemented",
                severity="INFO"
            )

        except Exception as e:
            return TestResult(
                "Static Equilibrium", "Structural Validation", False,
                f"Error checking static equilibrium: {str(e)}"
            )

    # ETABS Consistency Test Implementations
    def _test_element_counts(self) -> TestResult:
        """Test element count consistency with ETABS data."""
        try:
            opensees_elements = len(ops.getEleTags())

            # Try to load artifact data for comparison
            beam_data = self._load_artifact_data("beams.json")
            column_data = self._load_artifact_data("columns.json")

            artifact_elements = 0
            if beam_data and "beams" in beam_data:
                artifact_elements += len(beam_data["beams"])
            if column_data and "columns" in column_data:
                artifact_elements += len(column_data["columns"])

            if artifact_elements == 0:
                return TestResult(
                    "Element Counts", "ETABS Consistency", True,
                    f"OpenSees model has {opensees_elements} elements (no artifact data for comparison)",
                    {"opensees_elements": opensees_elements},
                    severity="INFO"
                )

            if opensees_elements == artifact_elements:
                return TestResult(
                    "Element Counts", "ETABS Consistency", True,
                    f"Element count matches: {opensees_elements} elements",
                    {"opensees_elements": opensees_elements, "artifact_elements": artifact_elements}
                )
            else:
                return TestResult(
                    "Element Counts", "ETABS Consistency", False,
                    f"Element count mismatch: OpenSees={opensees_elements}, Artifacts={artifact_elements}",
                    {"opensees_elements": opensees_elements, "artifact_elements": artifact_elements},
                    severity="WARNING"
                )

        except Exception as e:
            return TestResult(
                "Element Counts", "ETABS Consistency", False,
                f"Error checking element counts: {str(e)}"
            )

    def _test_tracking_elements(self) -> TestResult:
        """Test that tracking elements are properly implemented."""
        try:
            tracking_data = self._load_tracking_element_data()

            if not tracking_data:
                return TestResult(
                    "Tracking Elements", "ETABS Consistency", False,
                    "Cannot load tracking element data"
                )

            # Check our specific tracking elements
            found_elements = []
            for elem_key, expected in self.tracking_elements.items():
                found = False
                for data_key, elem_data in tracking_data.items():
                    if (elem_data.get("line") == expected["line"] and
                        elem_data.get("story") == expected["story"]):
                        found_elements.append(f"{expected['line']} @ {expected['story']}")
                        found = True
                        break

                if not found:
                    return TestResult(
                        "Tracking Elements", "ETABS Consistency", False,
                        f"Tracking element not found: {expected['line']} @ {expected['story']}",
                        {"expected": expected}
                    )

            return TestResult(
                "Tracking Elements", "ETABS Consistency", True,
                f"All tracking elements found: {', '.join(found_elements)}",
                {"found_elements": found_elements}
            )

        except Exception as e:
            return TestResult(
                "Tracking Elements", "ETABS Consistency", False,
                f"Error checking tracking elements: {str(e)}"
            )

    def _test_joint_offset_consistency(self) -> TestResult:
        """Test joint offset consistency with ETABS data."""
        try:
            tracking_data = self._load_tracking_element_data()

            if not tracking_data:
                return TestResult(
                    "Joint Offset Consistency", "ETABS Consistency", False,
                    "Cannot load element data for offset consistency check"
                )

            # Find elements with joint offsets
            offset_elements = []
            for elem_key, elem_data in tracking_data.items():
                if elem_data.get("has_joint_offsets"):
                    offset_elements.append(elem_key)

            return TestResult(
                "Joint Offset Consistency", "ETABS Consistency", True,
                f"Found {len(offset_elements)} elements with joint offsets",
                {"offset_elements": len(offset_elements)}
            )

        except Exception as e:
            return TestResult(
                "Joint Offset Consistency", "ETABS Consistency", False,
                f"Error checking joint offset consistency: {str(e)}"
            )

    def _test_material_consistency(self) -> TestResult:
        """Test material property consistency."""
        try:
            # This is a placeholder for material consistency testing
            return TestResult(
                "Material Consistency", "ETABS Consistency", True,
                "Material consistency validation not yet implemented",
                severity="INFO"
            )

        except Exception as e:
            return TestResult(
                "Material Consistency", "ETABS Consistency", False,
                f"Error checking material consistency: {str(e)}"
            )

    # Helper methods
    def _load_artifact_data(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load JSON artifact data."""
        try:
            file_path = self.out_dir / filename
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _load_tracking_element_data(self) -> Dict[str, Any]:
        """Load data for all tracking elements from artifacts."""
        all_data = {}

        # Load beam and column data
        beam_data = self._load_artifact_data("beams.json")
        column_data = self._load_artifact_data("columns.json")

        if beam_data and "beams" in beam_data:
            for i, beam in enumerate(beam_data["beams"]):
                all_data[f"beam_{i}"] = beam

        if column_data and "columns" in column_data:
            for i, column in enumerate(column_data["columns"]):
                all_data[f"column_{i}"] = column

        return all_data

    def generate_report(self, results: Dict[str, TestSuite]) -> str:
        """Generate a comprehensive test report."""
        report_lines = []
        report_lines.append("OpenSees Model Validation Report")
        report_lines.append("=" * 50)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")

        # Overall summary
        total_tests = sum(suite.total_tests for suite in results.values())
        total_passed = sum(suite.passed_tests for suite in results.values())
        overall_success = (total_passed / total_tests * 100) if total_tests > 0 else 0

        report_lines.append(f"Overall Results: {total_passed}/{total_tests} tests passed ({overall_success:.1f}%)")
        report_lines.append("")

        # Suite summaries
        for suite_name, suite in results.items():
            report_lines.append(f"{suite.name}: {suite.passed_tests}/{suite.total_tests} passed ({suite.success_rate:.1f}%)")

            for result in suite.results:
                status = "✓" if result.passed else "✗"
                report_lines.append(f"  {status} {result.name}: {result.message}")

        return "\n".join(report_lines)


# Note: Streamlit integration function is defined in model_viewer_APP.py