#!/usr/bin/env python3
"""
OpenSeesPy Model Validation Script

Standalone script for comprehensive OpenSees model validation that can be run
independently of the Streamlit app. Generates detailed reports and diagnostic
information for manual inspection.

Usage:
    python opensees_model_validator.py
    python opensees_model_validator.py --model out/model.py --output validation_report.txt

Features:
- Loads and builds OpenSees model from Python file
- Runs comprehensive validation tests
- Generates detailed text and JSON reports
- Extracts model properties for manual verification
- Creates diagnostic plots (if matplotlib available)
- Validates geometric transformations and joint offsets
"""

import sys
import os
import argparse
import json
import importlib.util
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import openseespy.opensees as ops
    OPENSEES_AVAILABLE = True
except ImportError:
    OPENSEES_AVAILABLE = False
    print("ERROR: OpenSeesPy not available. Please install: pip install openseespy")

try:
    from validation.opensees_model_tests import OpenSeesModelTester, TestSuite, TestResult
    TESTING_FRAMEWORK_AVAILABLE = True
except ImportError:
    TESTING_FRAMEWORK_AVAILABLE = False
    print("WARNING: Testing framework not available")

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class OpenSeesModelValidator:
    """Standalone OpenSees model validator with comprehensive reporting."""

    def __init__(self, model_path: str = "out/model.py", output_dir: str = "validation_output"):
        self.model_path = Path(model_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.model_info = {}
        self.test_results = {}
        self.validation_data = {}

    def load_model(self) -> bool:
        """Load and build the OpenSees model from Python file."""
        if not OPENSEES_AVAILABLE:
            print("ERROR: Cannot load model - OpenSeesPy not available")
            return False

        if not self.model_path.exists():
            print(f"ERROR: Model file not found: {self.model_path}")
            return False

        try:
            print(f"Loading model from: {self.model_path}")

            # Clear any existing model
            ops.wipe()

            # Load the model module
            spec = importlib.util.spec_from_file_location("model", self.model_path)
            model_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(model_module)

            # Build the model
            if hasattr(model_module, 'build_model'):
                model_module.build_model()
            else:
                print("ERROR: Model file must have a build_model() function")
                return False

            # Collect basic model info
            self.model_info = self._collect_model_info()
            print(f"Model loaded successfully: {self.model_info['nodes']} nodes, {self.model_info['elements']} elements")
            return True

        except Exception as e:
            print(f"ERROR loading model: {e}")
            return False

    def _collect_model_info(self) -> Dict[str, Any]:
        """Collect basic model information."""
        try:
            node_tags = ops.getNodeTags()
            element_tags = ops.getEleTags()

            # Calculate model bounds
            coords = [ops.nodeCoord(tag) for tag in node_tags[:100]]  # Sample first 100 nodes
            if coords:
                x_coords = [c[0] for c in coords]
                y_coords = [c[1] for c in coords]
                z_coords = [c[2] for c in coords]

                bounds = {
                    "x_range": [min(x_coords), max(x_coords)],
                    "y_range": [min(y_coords), max(y_coords)],
                    "z_range": [min(z_coords), max(z_coords)]
                }
            else:
                bounds = {}

            return {
                "model_file": str(self.model_path),
                "load_time": datetime.now().isoformat(),
                "nodes": len(node_tags),
                "elements": len(element_tags),
                "ndm": ops.getNDM(),
                "ndf": ops.getNDF(),
                "bounds": bounds
            }
        except Exception as e:
            return {"error": f"Failed to collect model info: {e}"}

    def run_validation_tests(self) -> bool:
        """Run comprehensive validation tests."""
        if not TESTING_FRAMEWORK_AVAILABLE:
            print("WARNING: Testing framework not available - skipping automated tests")
            return True

        try:
            print("Running validation tests...")
            tester = OpenSeesModelTester()
            self.test_results = tester.run_all_tests()

            # Summary statistics
            total_tests = sum(suite.total_tests for suite in self.test_results.values())
            passed_tests = sum(suite.passed_tests for suite in self.test_results.values())

            print(f"Tests completed: {passed_tests}/{total_tests} passed ({passed_tests/total_tests*100:.1f}%)")
            return True

        except Exception as e:
            print(f"ERROR running tests: {e}")
            return False

    def extract_geometric_transformations(self) -> Dict[str, Any]:
        """Extract and analyze geometric transformations."""
        try:
            print("Analyzing geometric transformations...")

            # Load artifact data for transformation analysis
            beam_data = self._load_artifact("beams.json")
            column_data = self._load_artifact("columns.json")

            transformation_info = {
                "beam_transforms": [],
                "column_transforms": [],
                "joint_offset_summary": {
                    "beams_with_offsets": 0,
                    "columns_with_offsets": 0,
                    "total_with_offsets": 0
                }
            }

            # Analyze beam transformations
            if beam_data and "beams" in beam_data:
                for beam in beam_data["beams"]:
                    transform_info = {
                        "element_tag": beam.get("tag"),
                        "line": beam.get("line"),
                        "story": beam.get("story"),
                        "transf_tag": beam.get("transf_tag"),
                        "length_off_i": beam.get("length_off_i", 0.0),
                        "length_off_j": beam.get("length_off_j", 0.0),
                        "joint_offset_i": beam.get("joint_offset_i", [0, 0, 0]),
                        "joint_offset_j": beam.get("joint_offset_j", [0, 0, 0]),
                        "has_joint_offsets": beam.get("has_joint_offsets", False),
                        "vecxz": [0, 0, 1]  # Beam vector
                    }
                    transformation_info["beam_transforms"].append(transform_info)

                    if transform_info["has_joint_offsets"]:
                        transformation_info["joint_offset_summary"]["beams_with_offsets"] += 1

            # Analyze column transformations
            if column_data and "columns" in column_data:
                for column in column_data["columns"]:
                    transform_info = {
                        "element_tag": column.get("tag"),
                        "line": column.get("line"),
                        "story": column.get("story"),
                        "transf_tag": column.get("transf_tag"),
                        "length_off_i": column.get("length_off_i", 0.0),
                        "length_off_j": column.get("length_off_j", 0.0),
                        "offsets_i": column.get("offsets_i", {}),
                        "offsets_j": column.get("offsets_j", {}),
                        "joint_offset_i": column.get("joint_offset_i", [0, 0, 0]),
                        "joint_offset_j": column.get("joint_offset_j", [0, 0, 0]),
                        "has_joint_offsets": column.get("has_joint_offsets", False),
                        "vecxz": [1, 0, 0]  # Column vector
                    }
                    transformation_info["column_transforms"].append(transform_info)

                    if transform_info["has_joint_offsets"]:
                        transformation_info["joint_offset_summary"]["columns_with_offsets"] += 1

            # Calculate totals
            summary = transformation_info["joint_offset_summary"]
            summary["total_with_offsets"] = summary["beams_with_offsets"] + summary["columns_with_offsets"]
            summary["total_transforms"] = len(transformation_info["beam_transforms"]) + len(transformation_info["column_transforms"])

            return transformation_info

        except Exception as e:
            return {"error": f"Failed to extract transformations: {e}"}

    def extract_tracking_elements(self) -> Dict[str, Any]:
        """Extract specific tracking elements for detailed inspection."""
        try:
            print("Extracting tracking elements...")

            tracking_info = {
                "beam_b408": None,
                "column_c522": None,
                "verification_status": {}
            }

            # Load transformation data
            transforms = self.extract_geometric_transformations()

            # Find BEAM B408 @ 11_P6
            for beam in transforms.get("beam_transforms", []):
                if beam.get("line") == "B408" and beam.get("story") == "11_P6":
                    tracking_info["beam_b408"] = beam
                    break

            # Find COLUMN C522 @ 02_P2
            for column in transforms.get("column_transforms", []):
                if column.get("line") == "C522" and column.get("story") == "02_P2":
                    tracking_info["column_c522"] = column
                    break

            # Verification
            tracking_info["verification_status"]["beam_b408_found"] = tracking_info["beam_b408"] is not None
            tracking_info["verification_status"]["column_c522_found"] = tracking_info["column_c522"] is not None

            if tracking_info["beam_b408"]:
                expected_offset_i = [0.4, 0.0, 0.0]  # LENGTHOFFI = 0.4
                actual_offset_i = tracking_info["beam_b408"]["joint_offset_i"]
                tracking_info["verification_status"]["beam_b408_offset_correct"] = (
                    abs(actual_offset_i[0] - expected_offset_i[0]) < 1e-6 and
                    abs(actual_offset_i[1] - expected_offset_i[1]) < 1e-6 and
                    abs(actual_offset_i[2] - expected_offset_i[2]) < 1e-6
                )

            if tracking_info["column_c522"]:
                # Expected: rigid ends (0.275) + lateral offsets (-0.05, 0.2, 0.0)
                # dI = (-0.05, 0.2, 0.275), dJ = (-0.05, 0.2, -0.275)
                expected_offset_i = [-0.05, 0.2, 0.275]
                expected_offset_j = [-0.05, 0.2, -0.275]
                actual_offset_i = tracking_info["column_c522"]["joint_offset_i"]
                actual_offset_j = tracking_info["column_c522"]["joint_offset_j"]

                tracking_info["verification_status"]["column_c522_offset_i_correct"] = (
                    abs(actual_offset_i[0] - expected_offset_i[0]) < 1e-6 and
                    abs(actual_offset_i[1] - expected_offset_i[1]) < 1e-6 and
                    abs(actual_offset_i[2] - expected_offset_i[2]) < 1e-6
                )
                tracking_info["verification_status"]["column_c522_offset_j_correct"] = (
                    abs(actual_offset_j[0] - expected_offset_j[0]) < 1e-6 and
                    abs(actual_offset_j[1] - expected_offset_j[1]) < 1e-6 and
                    abs(actual_offset_j[2] - expected_offset_j[2]) < 1e-6
                )

            return tracking_info

        except Exception as e:
            return {"error": f"Failed to extract tracking elements: {e}"}

    def run_modal_analysis(self) -> Dict[str, Any]:
        """Run modal analysis for dynamic properties."""
        try:
            print("Running modal analysis...")

            # Try to run eigen analysis
            num_modes = 6
            eigenvalues = ops.eigen(num_modes)

            if not eigenvalues:
                return {"error": "No eigenvalues computed - model may be unstable"}

            # Convert to frequencies and periods
            frequencies = []
            periods = []

            for i, eigenval in enumerate(eigenvalues):
                if eigenval > 0:
                    freq = (eigenval ** 0.5) / (2 * 3.14159)
                    period = 1.0 / freq if freq > 0 else float('inf')
                    frequencies.append(freq)
                    periods.append(period)
                else:
                    frequencies.append(0.0)
                    periods.append(float('inf'))

            modal_info = {
                "num_modes_requested": num_modes,
                "num_modes_computed": len(eigenvalues),
                "eigenvalues": eigenvalues,
                "frequencies": frequencies,
                "periods": periods,
                "analysis_successful": True
            }

            # Add assessment
            if frequencies[0] > 0:
                modal_info["fundamental_frequency"] = frequencies[0]
                modal_info["fundamental_period"] = periods[0]

                # Typical building assessment
                if periods[0] < 0.1:
                    modal_info["structure_assessment"] = "Very stiff structure"
                elif periods[0] < 1.0:
                    modal_info["structure_assessment"] = "Normal stiffness"
                elif periods[0] < 3.0:
                    modal_info["structure_assessment"] = "Flexible structure"
                else:
                    modal_info["structure_assessment"] = "Very flexible structure"

            return modal_info

        except Exception as e:
            return {"error": f"Modal analysis failed: {e}"}

    def generate_text_report(self) -> str:
        """Generate comprehensive text report."""
        lines = []
        lines.append("OpenSees Model Validation Report")
        lines.append("=" * 50)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Model File: {self.model_path}")
        lines.append("")

        # Model Info
        lines.append("MODEL INFORMATION")
        lines.append("-" * 20)
        if self.model_info:
            lines.append(f"Nodes: {self.model_info.get('nodes', 'N/A')}")
            lines.append(f"Elements: {self.model_info.get('elements', 'N/A')}")
            lines.append(f"Dimensions: {self.model_info.get('ndm', 'N/A')}D")
            lines.append(f"DOF per node: {self.model_info.get('ndf', 'N/A')}")

            bounds = self.model_info.get('bounds', {})
            if bounds:
                lines.append(f"X range: [{bounds['x_range'][0]:.2f}, {bounds['x_range'][1]:.2f}]")
                lines.append(f"Y range: [{bounds['y_range'][0]:.2f}, {bounds['y_range'][1]:.2f}]")
                lines.append(f"Z range: [{bounds['z_range'][0]:.2f}, {bounds['z_range'][1]:.2f}]")
        lines.append("")

        # Test Results
        if self.test_results:
            lines.append("VALIDATION TEST RESULTS")
            lines.append("-" * 25)

            total_tests = sum(suite.total_tests for suite in self.test_results.values())
            passed_tests = sum(suite.passed_tests for suite in self.test_results.values())
            lines.append(f"Overall: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")
            lines.append("")

            for suite_name, suite in self.test_results.items():
                lines.append(f"{suite.name}: {suite.passed_tests}/{suite.total_tests} passed ({suite.success_rate:.1f}%)")

                for result in suite.results:
                    status = "✓" if result.passed else "✗"
                    lines.append(f"  {status} {result.name}: {result.message}")
                lines.append("")

        # Geometric Transformations
        transforms = self.extract_geometric_transformations()
        if "error" not in transforms:
            lines.append("GEOMETRIC TRANSFORMATIONS")
            lines.append("-" * 25)
            summary = transforms["joint_offset_summary"]
            lines.append(f"Total transformations: {summary['total_transforms']}")
            lines.append(f"Transformations with joint offsets: {summary['total_with_offsets']}")
            lines.append(f"  - Beams with offsets: {summary['beams_with_offsets']}")
            lines.append(f"  - Columns with offsets: {summary['columns_with_offsets']}")
            lines.append("")

        # Tracking Elements
        tracking = self.extract_tracking_elements()
        if "error" not in tracking:
            lines.append("TRACKING ELEMENTS VERIFICATION")
            lines.append("-" * 30)

            status = tracking["verification_status"]

            # BEAM B408
            lines.append("BEAM B408 @ 11_P6:")
            if status.get("beam_b408_found"):
                lines.append("  ✓ Element found")
                if status.get("beam_b408_offset_correct"):
                    lines.append("  ✓ Joint offsets correct")
                else:
                    lines.append("  ✗ Joint offsets incorrect")
                beam_info = tracking["beam_b408"]
                lines.append(f"  Joint offset I: {beam_info['joint_offset_i']}")
                lines.append(f"  Joint offset J: {beam_info['joint_offset_j']}")
            else:
                lines.append("  ✗ Element not found")
            lines.append("")

            # COLUMN C522
            lines.append("COLUMN C522 @ 02_P2:")
            if status.get("column_c522_found"):
                lines.append("  ✓ Element found")
                if status.get("column_c522_offset_i_correct") and status.get("column_c522_offset_j_correct"):
                    lines.append("  ✓ Joint offsets correct")
                else:
                    lines.append("  ✗ Joint offsets incorrect")
                col_info = tracking["column_c522"]
                lines.append(f"  Joint offset I: {col_info['joint_offset_i']}")
                lines.append(f"  Joint offset J: {col_info['joint_offset_j']}")
            else:
                lines.append("  ✗ Element not found")
            lines.append("")

        # Modal Analysis
        modal_info = self.run_modal_analysis()
        if "error" not in modal_info:
            lines.append("MODAL ANALYSIS")
            lines.append("-" * 15)
            lines.append(f"Fundamental frequency: {modal_info.get('fundamental_frequency', 'N/A'):.3f} Hz")
            lines.append(f"Fundamental period: {modal_info.get('fundamental_period', 'N/A'):.3f} sec")
            lines.append(f"Assessment: {modal_info.get('structure_assessment', 'N/A')}")

            lines.append("First 6 modes:")
            for i, (freq, period) in enumerate(zip(modal_info['frequencies'][:6], modal_info['periods'][:6])):
                lines.append(f"  Mode {i+1}: {freq:.3f} Hz, {period:.3f} sec")
        else:
            lines.append("MODAL ANALYSIS")
            lines.append("-" * 15)
            lines.append(f"Error: {modal_info['error']}")

        lines.append("")
        lines.append("End of Report")
        lines.append("=" * 50)

        return "\n".join(lines)

    def _load_artifact(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load JSON artifact data."""
        try:
            artifact_path = PROJECT_ROOT / "out" / filename
            if artifact_path.exists():
                with open(artifact_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def save_validation_data(self):
        """Save all validation data to files."""
        print(f"Saving validation data to: {self.output_dir}")

        # Text report
        text_report = self.generate_text_report()
        with open(self.output_dir / "validation_report.txt", 'w', encoding='utf-8') as f:
            f.write(text_report)

        # JSON data
        validation_data = {
            "model_info": self.model_info,
            "test_results": self._serialize_test_results(),
            "geometric_transformations": self.extract_geometric_transformations(),
            "tracking_elements": self.extract_tracking_elements(),
            "modal_analysis": self.run_modal_analysis(),
            "generation_time": datetime.now().isoformat()
        }

        with open(self.output_dir / "validation_data.json", 'w', encoding='utf-8') as f:
            json.dump(validation_data, f, indent=2, default=str)

        print("Validation files created:")
        print(f"  - {self.output_dir}/validation_report.txt")
        print(f"  - {self.output_dir}/validation_data.json")

    def _serialize_test_results(self) -> Dict[str, Any]:
        """Serialize test results for JSON output."""
        serialized = {}
        for suite_name, suite in self.test_results.items():
            serialized[suite_name] = {
                "name": suite.name,
                "total_tests": suite.total_tests,
                "passed_tests": suite.passed_tests,
                "success_rate": suite.success_rate,
                "results": [
                    {
                        "name": result.name,
                        "category": result.category,
                        "passed": result.passed,
                        "message": result.message,
                        "severity": result.severity,
                        "details": result.details
                    }
                    for result in suite.results
                ]
            }
        return serialized

    def run_full_validation(self) -> bool:
        """Run complete validation process."""
        print("OpenSees Model Validator")
        print("=" * 30)

        if not self.load_model():
            return False

        if not self.run_validation_tests():
            return False

        self.save_validation_data()

        print("\nValidation completed successfully!")
        print(f"Review the generated files in: {self.output_dir}")
        return True


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="OpenSees Model Validator - Comprehensive model validation and reporting"
    )
    parser.add_argument(
        "--model",
        default="out/model.py",
        help="Path to OpenSees model Python file (default: out/model.py)"
    )
    parser.add_argument(
        "--output",
        default="validation_output",
        help="Output directory for validation files (default: validation_output)"
    )

    args = parser.parse_args()

    if not OPENSEES_AVAILABLE:
        print("ERROR: OpenSeesPy not available. Please install: pip install openseespy")
        return 1

    validator = OpenSeesModelValidator(args.model, args.output)

    success = validator.run_full_validation()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())