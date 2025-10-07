#!/usr/bin/env python3
"""
Quick test script to run structural validation and see error messages
"""
import sys
sys.path.insert(0, '/mnt/c/Users/jgomez/Desktop/opensees/RDC_PERFORM')

from validation.structural_validation import StructuralValidator

def main():
    print("=" * 80)
    print("Running Structural Validation with Enhanced Error Reporting")
    print("=" * 80)

    validator = StructuralValidator(out_dir="out")

    # Load artifacts
    if not validator.load_artifacts():
        print("❌ Failed to load artifacts")
        return

    print("✓ Artifacts loaded successfully\n")

    # Load the explicit model
    model_path = "out/explicit_model.py"
    if not validator.load_model(model_path):
        print(f"❌ Failed to load model from {model_path}")
        return

    print("✓ Model loaded successfully\n")

    # Run all validation tests
    print("Running validation tests...\n")
    results = validator.run_all_tests()

    # Print results
    critical_failures = []
    warnings = []

    for result in results:
        if result.severity == "critical" and not result.passed:
            critical_failures.append(result)
        elif result.severity == "warning" and not result.passed:
            warnings.append(result)

    print("\n" + "=" * 80)
    print("VALIDATION RESULTS")
    print("=" * 80)

    if critical_failures:
        print(f"\n❌ {len(critical_failures)} critical failure(s) detected\n")
        print("🚨 Critical Failures - Immediate Action Required\n")
        for result in critical_failures:
            print(f"  {result.test_name}:")
            print(f"    {result.message}")
            if result.details:
                print(f"    Details: {result.details}")
            print()

    if warnings:
        print(f"\n⚠️  {len(warnings)} warning(s) detected\n")
        for result in warnings:
            print(f"  {result.test_name}:")
            print(f"    {result.message}")
            print()

    if not critical_failures and not warnings:
        print("\n✅ All validation tests passed!")

    print("=" * 80)

if __name__ == "__main__":
    main()
