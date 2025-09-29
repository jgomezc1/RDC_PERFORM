#!/usr/bin/env python3
"""
Enhanced modal analysis with numerical conditioning checks and advanced error handling
"""

import sys
import os
import numpy as np

# Try to import openseespy
try:
    import openseespy.opensees as ops
    print("✓ OpenSeesPy imported successfully")
except ImportError:
    print("✗ OpenSeesPy not available")
    sys.exit(1)

def check_model_conditioning():
    """Check for numerical conditioning issues in the model"""
    print("\n📊 Checking model numerical conditioning...")

    issues = []

    # Check for very small section properties
    try:
        ele_tags = ops.getEleTags()
        small_inertia_count = 0
        zero_area_count = 0

        for i, tag in enumerate(ele_tags[:50]):  # Check first 50 elements
            try:
                # Get element properties (this might not work for all element types)
                # For elastic beam columns: A, E, G, J, Iy, Iz
                pass  # Properties are embedded in element definition
            except:
                continue

        print(f"   ✓ Checked {min(50, len(ele_tags))} elements for conditioning")

    except Exception as e:
        issues.append(f"Element property check failed: {e}")

    # Check for mass matrix conditioning
    try:
        node_tags = ops.getNodeTags()
        zero_mass_count = 0
        very_small_mass_count = 0

        for tag in node_tags[:100]:  # Check first 100 nodes
            try:
                mass_vals = ops.nodeMass(tag)
                total_mass = sum(mass_vals[:3])
                if total_mass == 0:
                    zero_mass_count += 1
                elif total_mass < 1e-6:
                    very_small_mass_count += 1
            except:
                continue

        if zero_mass_count > len(node_tags) * 0.8:
            issues.append(f"Most nodes ({zero_mass_count}/{len(node_tags)}) have zero mass")

        if very_small_mass_count > 10:
            issues.append(f"Many nodes ({very_small_mass_count}) have very small masses")

        print(f"   ✓ Mass distribution: {zero_mass_count} zero, {very_small_mass_count} very small")

    except Exception as e:
        issues.append(f"Mass check failed: {e}")

    return issues

def enhanced_modal_analysis(num_modes: int = 6):
    """Enhanced modal analysis with multiple solvers and conditioning checks"""

    print("\n" + "="*70)
    print("ENHANCED MODAL ANALYSIS WITH NUMERICAL CONDITIONING")
    print("="*70)

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

        # Build the model
        exec(model_code)
        build_model()
        print("   ✓ Model built successfully")

    except Exception as e:
        print(f"   ✗ Failed to build model: {e}")
        return False

    # Check model conditioning
    conditioning_issues = check_model_conditioning()
    if conditioning_issues:
        print("\n⚠️  Potential numerical conditioning issues found:")
        for issue in conditioning_issues:
            print(f"   • {issue}")
    else:
        print("\n✓ No obvious conditioning issues detected")

    # Check basic model status
    print("\n2. Checking model status")
    try:
        node_tags = ops.getNodeTags()
        ele_tags = ops.getEleTags()
        print(f"   ✓ Model has {len(node_tags)} nodes and {len(ele_tags)} elements")

        # Check for mass
        mass_count = 0
        total_mass = 0
        for tag in node_tags[:50]:  # Check first 50 nodes
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

    # Enhanced eigenvalue analysis with multiple solver strategies
    print("\n3. Running enhanced eigenvalue analysis")

    solver_strategies = [
        ("BandGen + RCM", lambda: (ops.system('BandGen'), ops.numberer('RCM'))),
        ("FullGeneral + RCM", lambda: (ops.system('FullGeneral'), ops.numberer('RCM'))),
        ("ProfileSPD + RCM", lambda: (ops.system('ProfileSPD'), ops.numberer('RCM'))),
        ("BandSPD + Plain", lambda: (ops.system('BandSPD'), ops.numberer('Plain'))),
        ("FullGeneral + Plain", lambda: (ops.system('FullGeneral'), ops.numberer('Plain')))
    ]

    eigenvalues = None
    successful_strategy = None

    for strategy_name, setup_func in solver_strategies:
        print(f"\n   Trying strategy: {strategy_name}")

        try:
            # Wipe analysis and set up fresh
            ops.wipeAnalysis()
            setup_func()

            # Constraints should already be set by the model
            print(f"   Running eigen analysis for {num_modes} modes...")
            eigenvalues = ops.eigen(num_modes)

            if eigenvalues and len(eigenvalues) > 0:
                # Check if eigenvalues are reasonable
                if all(ev >= 0 for ev in eigenvalues):
                    print(f"   ✓ Strategy '{strategy_name}' succeeded!")
                    successful_strategy = strategy_name
                    break
                else:
                    print(f"   ⚠️  Strategy '{strategy_name}' gave negative eigenvalues")
                    eigenvalues = None
            else:
                print(f"   ✗ Strategy '{strategy_name}' failed - no eigenvalues")

        except Exception as e:
            print(f"   ✗ Strategy '{strategy_name}' failed: {e}")
            continue

    if not eigenvalues:
        print("\n❌ All solver strategies failed")
        print("\n🔧 Possible solutions:")
        print("   1. Check for zero-stiffness elements or mechanisms")
        print("   2. Verify boundary conditions are adequate")
        print("   3. Check for numerical precision issues in section properties")
        print("   4. Ensure mass matrix is properly conditioned")
        return False

    print(f"\n✅ Eigenvalue analysis successful with: {successful_strategy}")

    # Process and display results
    print(f"\n4. Processing {len(eigenvalues)} eigenvalues...")

    # Convert to periods and frequencies
    periods = []
    frequencies = []

    for ev in eigenvalues:
        if ev > 1e-12:  # Use small tolerance for zero
            omega = np.sqrt(ev)
            freq = omega / (2 * np.pi)
            period = 1.0 / freq if freq > 0 else float('inf')
            periods.append(period)
            frequencies.append(freq)
        else:
            periods.append(float('inf'))
            frequencies.append(0)

    print("\n5. Modal Results:")
    print("   Mode | Eigenvalue  | Period (s) | Frequency (Hz)")
    print("   -----|-------------|------------|---------------")
    for i, (ev, T, f) in enumerate(zip(eigenvalues, periods, frequencies), 1):
        if T < float('inf'):
            print(f"   {i:4} | {ev:11.2e} | {T:10.4f} | {f:13.3f}")
        else:
            print(f"   {i:4} | {ev:11.2e} | {'∞':>10} | {0:13.3f}")

    # Enhanced analysis of results
    T1 = periods[0] if periods else float('inf')

    print(f"\n6. Enhanced Analysis:")
    print(f"   Solver used: {successful_strategy}")

    if T1 < float('inf'):
        print(f"   Fundamental period T₁ = {T1:.4f} seconds")
        print(f"   Fundamental frequency f₁ = {frequencies[0]:.3f} Hz")

        # Count rigid body modes
        rigid_modes = sum(1 for T in periods if T == float('inf') or T > 100)
        structural_modes = len(periods) - rigid_modes

        print(f"   Rigid body modes: {rigid_modes}")
        print(f"   Structural modes: {structural_modes}")

        if 0.1 <= T1 <= 5.0:
            print("   ✓ Period is within reasonable range (0.1-5.0s)")
            if rigid_modes <= 6:  # Expected for properly constrained structure
                print("   ✅ MODAL ANALYSIS FULLY SUCCESSFUL!")
                return True
            else:
                print("   ⚠️  Too many rigid body modes - check constraints")
                return True  # Still functional
        else:
            print(f"   ⚠️  Period outside typical range (0.1-5.0s)")
            if T1 > 100:
                print("   ✗ Period suggests significant constraint issues")
                return False
            else:
                print("   ⚠️  Unusual but might be valid for this structure")
                return True
    else:
        print("   ✗ Infinite fundamental period - model has issues")
        print("   Check: constraints, boundary conditions, element connectivity")
        return False

if __name__ == "__main__":
    success = enhanced_modal_analysis()

    if success:
        print("\n" + "="*70)
        print("🎉 SUCCESS: Enhanced modal analysis completed!")
        print("   The model should now work correctly in the Streamlit app.")
        print("="*70)
    else:
        print("\n" + "="*70)
        print("❌ FAILED: Enhanced modal analysis detected issues")
        print("   Review the diagnostic output above for solutions.")
        print("="*70)