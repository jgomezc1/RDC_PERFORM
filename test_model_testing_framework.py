#!/usr/bin/env python3
"""
Test script to verify the OpenSees model testing framework.
This script can be run independently to test the framework functionality.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_framework_import():
    """Test that the testing framework can be imported."""
    try:
        from opensees_model_tests import OpenSeesModelTester, TestResult, TestSuite
        print("✅ Testing framework imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import testing framework: {e}")
        return False

def test_without_opensees():
    """Test framework behavior without an active OpenSees model."""
    try:
        from opensees_model_tests import OpenSeesModelTester

        tester = OpenSeesModelTester()
        results = tester.run_all_tests()

        print(f"✅ Framework handles no-model case gracefully")
        print(f"   Returned {len(results)} result categories")

        # Check if we get an error category when no model is present
        if "error" in results:
            error_suite = results["error"]
            print(f"   Error suite contains {len(error_suite.results)} results")
            if error_suite.results:
                print(f"   First error: {error_suite.results[0].message}")

        return True
    except Exception as e:
        print(f"❌ Framework failed without OpenSees model: {e}")
        return False

def test_test_result_creation():
    """Test TestResult and TestSuite creation."""
    try:
        from opensees_model_tests import TestResult, TestSuite

        # Create a test result
        result = TestResult(
            name="Sample Test",
            category="Test Category",
            passed=True,
            message="This is a test message",
            details={"key": "value"}
        )

        # Create a test suite
        suite = TestSuite("Sample Suite")
        suite.results.append(result)

        print("✅ TestResult and TestSuite creation works")
        print(f"   Suite has {suite.total_tests} tests")
        print(f"   Success rate: {suite.success_rate:.1f}%")

        return True
    except Exception as e:
        print(f"❌ Failed to create test objects: {e}")
        return False

def test_artifact_loading():
    """Test artifact data loading capabilities."""
    try:
        from opensees_model_tests import OpenSeesModelTester

        tester = OpenSeesModelTester()

        # Test artifact loading
        beam_data = tester._load_artifact_data("beams.json")
        column_data = tester._load_artifact_data("columns.json")

        print("✅ Artifact loading methods work")
        if beam_data:
            print(f"   Found beams.json with {len(beam_data.get('beams', []))} beams")
        else:
            print("   No beams.json found (expected if not generated yet)")

        if column_data:
            print(f"   Found columns.json with {len(column_data.get('columns', []))} columns")
        else:
            print("   No columns.json found (expected if not generated yet)")

        return True
    except Exception as e:
        print(f"❌ Artifact loading failed: {e}")
        return False

def test_tracking_elements():
    """Test tracking element configuration."""
    try:
        from opensees_model_tests import OpenSeesModelTester

        tester = OpenSeesModelTester()

        print("✅ Tracking elements configured")
        for key, element in tester.tracking_elements.items():
            print(f"   {key}: {element['line']} @ {element['story']} ({element['type']})")

        return True
    except Exception as e:
        print(f"❌ Tracking elements test failed: {e}")
        return False

def test_streamlit_integration():
    """Test Streamlit integration functions."""
    try:
        # This simulates what would happen in Streamlit
        from opensees_model_tests import run_model_tests

        # Test with empty categories (should return empty dict)
        results = run_model_tests([])
        print("✅ Streamlit integration function exists")
        print(f"   Empty categories returned: {len(results)} results")

        return True
    except ImportError:
        print("⚠️ Streamlit integration function not found (expected if model_viewer_APP.py not imported)")
        return True  # This is expected
    except Exception as e:
        print(f"❌ Streamlit integration test failed: {e}")
        return False

def main():
    """Run all framework tests."""
    print("OpenSees Model Testing Framework Verification")
    print("=" * 50)

    tests = [
        ("Framework Import", test_framework_import),
        ("No OpenSees Model Handling", test_without_opensees),
        ("Test Object Creation", test_test_result_creation),
        ("Artifact Loading", test_artifact_loading),
        ("Tracking Elements", test_tracking_elements),
        ("Streamlit Integration", test_streamlit_integration),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            if test_func():
                passed += 1
            else:
                print(f"   Test failed")
        except Exception as e:
            print(f"   Test crashed: {e}")

    print(f"\n{'='*50}")
    print(f"Framework Verification Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Framework is ready for use.")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)