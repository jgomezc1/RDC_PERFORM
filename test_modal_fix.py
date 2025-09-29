#!/usr/bin/env python3
"""
Test modal analysis with the corrected explicit model
"""

import sys
import os

# Try to import openseespy
try:
    import openseespy.opensees as ops
    print("✓ OpenSeesPy imported successfully")
except ImportError:
    print("✗ OpenSeesPy not available")
    sys.exit(1)

def test_modal_analysis():
    """Test modal analysis with corrected constraints"""

    print("\n" + "="*60)
    print("TESTING MODAL ANALYSIS WITH CORRECTED CONSTRAINTS")
    print("="*60)

    # Load and execute the explicit model
    explicit_path = "out/explicit_model.py"
    if not os.path.exists(explicit_path):
        print(f"✗ Explicit model not found: {explicit_path}")
        return False

    print(f"\n1. Loading explicit model from {explicit_path}")

    try:
        # Execute the model file
        with open(explicit_path, 'r') as f:
            model_code = f.read()

        # Check if constraints are in the model
        if "constraints('Transformation')" in model_code:
            print("   ✓ Found constraints('Transformation') in model")
        else:
            print("   ✗ No constraints('Transformation') found - this is the problem!")
            return False

        # Execute and build the model
        exec(model_code)
        build_model()
        print("   ✓ Model built successfully")

    except Exception as e:
        print(f"   ✗ Failed to build model: {e}")
        return False

    # Check model status
    print("\n2. Checking model status")
    try:
        node_tags = ops.getNodeTags()
        ele_tags = ops.getEleTags()
        print(f"   ✓ Model has {len(node_tags)} nodes and {len(ele_tags)} elements")

        # Check for mass
        mass_count = 0
        total_mass = 0
        for tag in node_tags[:20]:  # Check first 20 nodes
            try:
                mass_vals = ops.nodeMass(tag)
                node_mass = sum(mass_vals[:3])
                if node_mass > 0:
                    mass_count += 1
                    total_mass += node_mass
            except:
                continue

        if mass_count > 0:
            print(f"   ✓ Found mass at {mass_count} nodes (total: {total_mass:.1f} kg)")
        else:
            print("   ✗ No mass found in model")
            return False

    except Exception as e:
        print(f"   ✗ Error checking model: {e}")
        return False

    # Run modal analysis
    print("\n3. Running modal analysis")
    try:
        # Set up analysis - should already have constraints from model
        ops.wipeAnalysis()
        ops.system('BandGen')
        ops.numberer('RCM')
        # constraints should already be set by the model

        print("   Running eigen analysis for 6 modes...")
        eigenvalues = ops.eigen(6)

        if not eigenvalues:
            print("   ✗ No eigenvalues computed")
            return False

        print(f"   ✓ Computed {len(eigenvalues)} eigenvalues")

        # Convert to periods and frequencies
        periods = []
        frequencies = []

        for ev in eigenvalues:
            if ev > 0:
                omega = (ev)**0.5
                freq = omega / (2 * 3.14159)
                period = 1.0 / freq if freq > 0 else float('inf')
                periods.append(period)
                frequencies.append(freq)
            else:
                periods.append(float('inf'))
                frequencies.append(0)

        print("\n4. Modal Results:")
        print("   Mode | Period (s) | Frequency (Hz)")
        print("   -----|------------|---------------")
        for i, (T, f) in enumerate(zip(periods, frequencies), 1):
            if T < float('inf'):
                print(f"   {i:4} | {T:10.4f} | {f:13.3f}")
            else:
                print(f"   {i:4} | {'∞':>10} | {0:13.3f}")

        # Check if results are reasonable
        T1 = periods[0] if periods else float('inf')

        print(f"\n5. Analysis:")
        if T1 < float('inf'):
            print(f"   Fundamental period T₁ = {T1:.4f} seconds")
            if 0.1 <= T1 <= 5.0:
                print("   ✓ Period is within reasonable range (0.1-5.0s)")
                print("   ✅ MODAL ANALYSIS SUCCESSFUL!")
                return True
            else:
                print(f"   ⚠️ Period outside typical range (0.1-5.0s)")
                if T1 > 100:
                    print("   ✗ Period suggests constraint issues still exist")
                    return False
                else:
                    print("   ⚠️ Unusual but might be valid for this structure")
                    return True
        else:
            print("   ✗ Infinite period - model has rigid body modes")
            print("   ✗ CONSTRAINTS NOT WORKING PROPERLY")
            return False

    except Exception as e:
        print(f"   ✗ Modal analysis failed: {e}")
        return False

if __name__ == "__main__":
    success = test_modal_analysis()

    if success:
        print("\n" + "="*60)
        print("🎉 SUCCESS: Modal analysis working correctly!")
        print("   The Streamlit app should now show realistic periods.")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("❌ FAILED: Modal analysis still has issues")
        print("   Check the explicit model generation.")
        print("="*60)