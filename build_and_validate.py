#!/usr/bin/env python3
"""
Build and Validate Workflow
============================

This script orchestrates the complete ETABS-to-OpenSees translation and validation workflow:

1. Parse E2K file and build runtime OpenSees model
2. Generate artifacts (nodes.json, beams.json, columns.json, etc.)
3. Generate explicit_model.py from artifacts
4. Run comprehensive validation on explicit_model.py
5. Display validation results

This ensures all validation is performed on the final artifact that users will actually execute.

Usage:
    python build_and_validate.py --e2k models/your_model.e2k
    python build_and_validate.py --e2k models/your_model.e2k --skip-validation
    python build_and_validate.py --validate-only  # Just validate existing explicit model
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import OUT_DIR


def build_runtime_model() -> bool:
    """
    Build the runtime OpenSees model and generate all artifacts.

    This phase:
    1. Runs Phase 1 parser (E2K -> parsed_raw.json + story_graph.json)
    2. Builds runtime OpenSees model with MODEL_translator
    3. Generates all artifacts (nodes.json, beams.json, columns.json, etc.)

    Returns:
        bool: True if successful, False otherwise
    """
    print("=" * 80)
    print("PHASE 1: Building Runtime Model and Generating Artifacts")
    print("=" * 80)

    try:
        # Step 1: Run Phase 1 parser to generate story_graph.json
        print("\n📄 Phase 1a: Parsing E2K file...")
        from src.parsing.phase1_run import main as phase1_main

        try:
            phase1_main()
        except Exception as e:
            print(f"❌ Phase 1 parser failed: {e}")
            return False

        # Verify Phase 1 outputs
        required_phase1 = [
            os.path.join(OUT_DIR, "parsed_raw.json"),
            os.path.join(OUT_DIR, "story_graph.json")
        ]

        missing = [p for p in required_phase1 if not os.path.exists(p)]
        if missing:
            print(f"❌ Phase 1 failed to generate required files:")
            for p in missing:
                print(f"   - {p}")
            return False

        print("✓ Phase 1 complete (parsed_raw.json, story_graph.json generated)")

        # Step 2: Build runtime OpenSees model
        print("\n🔨 Phase 1b: Building OpenSees runtime model...")
        try:
            import openseespy.opensees as ops
        except ImportError:
            print("❌ OpenSeesPy not available")
            return False

        from src.orchestration.MODEL_translator import build_model

        # Build complete model (nodes, supports, springs, diaphragms, columns, beams)
        build_model(stage='all')

        print(f"\n✓ Runtime model built successfully")
        print(f"✓ Artifacts saved to: {OUT_DIR}/")

        # Verify all expected artifacts were created
        expected_artifacts = [
            "nodes.json",
            "supports.json",
            "columns.json",
            "beams.json",
            "diaphragms.json"
        ]

        created_artifacts = []
        for artifact in expected_artifacts:
            path = os.path.join(OUT_DIR, artifact)
            if os.path.exists(path):
                created_artifacts.append(artifact)

        print(f"\n📦 Artifacts created: {', '.join(created_artifacts)}")

        # Check for optional artifacts
        springs_path = os.path.join(OUT_DIR, "springs.json")
        if os.path.exists(springs_path):
            print("   + springs.json (spring supports detected)")

        return True

    except Exception as e:
        print(f"❌ Runtime model build failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_explicit_model() -> bool:
    """
    Generate explicit_model.py from artifacts.

    This is the standalone OpenSeesPy script that contains all model data
    and can be executed independently without reading JSON artifacts.
    """
    print("\n" + "=" * 80)
    print("PHASE 2: Generating Explicit Model")
    print("=" * 80)

    try:
        # Run the explicit model generator
        from experimental.generate_explicit_model import _build_explicit, NLOverrides

        out_path = os.path.join(OUT_DIR, "explicit_model.py")
        nodes_path = os.path.join(OUT_DIR, "nodes.json")
        supports_path = os.path.join(OUT_DIR, "supports.json")
        diaph_path = os.path.join(OUT_DIR, "diaphragms.json")
        cols_path = os.path.join(OUT_DIR, "columns.json")
        beams_path = os.path.join(OUT_DIR, "beams.json")
        springs_path = os.path.join(OUT_DIR, "springs.json")

        # Check that required artifacts exist
        required_artifacts = [nodes_path, supports_path, cols_path, beams_path]
        missing = [p for p in required_artifacts if not os.path.exists(p)]

        if missing:
            print(f"❌ Missing required artifacts:")
            for path in missing:
                print(f"   - {path}")
            return False

        print(f"\n📝 Generating explicit model from artifacts...")

        # Load nonlinear overrides (if any)
        ov = NLOverrides.load(None)

        # Generate explicit model
        _build_explicit(
            ndm=3,
            ndf=6,
            out_path=out_path,
            nodes_path=nodes_path,
            supports_path=supports_path,
            diaph_path=diaph_path,
            cols_path=cols_path,
            beams_path=beams_path,
            springs_path=springs_path,
            ov=ov
        )

        if not os.path.exists(out_path):
            print(f"❌ Explicit model was not created at {out_path}")
            return False

        # Get file stats
        file_size = os.path.getsize(out_path)
        with open(out_path, 'r') as f:
            line_count = sum(1 for _ in f)

        print(f"✓ Explicit model generated: {out_path}")
        print(f"  Size: {file_size:,} bytes")
        print(f"  Lines: {line_count:,}")

        return True

    except Exception as e:
        print(f"❌ Explicit model generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_validation() -> bool:
    """
    Run comprehensive validation on explicit_model.py.

    This performs all structural validation tests on the final artifact.
    """
    print("\n" + "=" * 80)
    print("PHASE 3: Validating Explicit Model")
    print("=" * 80)

    try:
        from validation.structural_validation import StructuralValidator

        explicit_path = os.path.join(OUT_DIR, "explicit_model.py")

        if not os.path.exists(explicit_path):
            print(f"❌ Explicit model not found: {explicit_path}")
            print("   Run without --validate-only to build the model first")
            return False

        print(f"\n🔍 Validating: {explicit_path}")

        # Create validator
        validator = StructuralValidator(out_dir=OUT_DIR)

        # Run all validation tests (loads artifacts and model internally)
        print("\n🧪 Running validation suite...")

        result_dict = validator.run_all_validations(etabs_periods=None)

        # The run_all_validations method already prints detailed results
        # Just need to return success status
        success = result_dict.get("success", False)

        return success

    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Build ETABS-to-OpenSees model and validate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script orchestrates the complete workflow:
  1. Parse E2K file (from config.py E2K_PATH)
  2. Build runtime OpenSees model
  3. Generate explicit_model.py
  4. Validate explicit_model.py

The E2K file path is read from config.py (E2K_PATH variable).
        """
    )

    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation phase (only build model and generate explicit)"
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only run validation on existing explicit_model.py (skip build)"
    )

    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Build runtime model and generate explicit model, then stop (skip validation)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.validate_only and args.build_only:
        print("❌ Cannot use both --validate-only and --build-only")
        sys.exit(1)

    success = True

    # Display E2K path from config
    if not args.validate_only:
        try:
            from config import E2K_PATH
            print(f"\n📋 Using E2K file from config: {E2K_PATH}")
            if not os.path.exists(E2K_PATH):
                print(f"❌ E2K file not found: {E2K_PATH}")
                print("   Please update config.py with correct E2K_PATH")
                sys.exit(1)
        except ImportError:
            print("❌ Cannot import E2K_PATH from config.py")
            sys.exit(1)

    # Phase 1 & 2: Build model and generate explicit (unless validate-only)
    if not args.validate_only:
        # Build runtime model
        if not build_runtime_model():
            print("\n❌ BUILD FAILED")
            sys.exit(1)

        # Generate explicit model
        if not generate_explicit_model():
            print("\n❌ EXPLICIT MODEL GENERATION FAILED")
            sys.exit(1)

    # Phase 3: Validation (unless skipped)
    if not args.skip_validation and not args.build_only:
        if not run_validation():
            print("\n⚠️  VALIDATION COMPLETED WITH FAILURES")
            success = False
        else:
            print("\n✅ VALIDATION PASSED")

    # Final summary
    print("\n" + "=" * 80)
    if args.build_only:
        print("✅ BUILD COMPLETE (validation skipped)")
        print("\nGenerated:")
        print(f"  - Artifacts: {OUT_DIR}/")
        print(f"  - Explicit model: {OUT_DIR}/explicit_model.py")
        print("\nTo run validation:")
        print("  python build_and_validate.py --validate-only")
    elif args.validate_only:
        if success:
            print("✅ VALIDATION PASSED")
        else:
            print("⚠️  VALIDATION FAILED")
    elif success:
        print("✅ BUILD AND VALIDATION COMPLETE")
        print("\nNext steps:")
        print(f"  - Review artifacts in: {OUT_DIR}/")
        print(f"  - Use explicit model: {OUT_DIR}/explicit_model.py")
        print("  - View model: streamlit run apps/model_viewer_APP.py")
        print("  - Run structural validation app: streamlit run apps/structural_validation_app.py")
    else:
        print("⚠️  BUILD COMPLETE BUT VALIDATION FAILED")
        print("\nReview validation errors above and fix issues before using the model.")
    print("=" * 80)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
