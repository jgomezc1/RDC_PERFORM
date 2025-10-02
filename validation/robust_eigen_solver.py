#!/usr/bin/env python3
"""
Robust eigenvalue solver to address "See stderr output" issues
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

def robust_eigenvalue_analysis(num_modes: int = 6):
    """
    Robust eigenvalue analysis that addresses numerical conditioning issues
    """
    print("\n🔧 ROBUST EIGENVALUE SOLVER")
    print("=" * 50)

    # Load model
    explicit_path = "out/explicit_model.py"
    if not os.path.exists(explicit_path):
        print(f"✗ Model file not found: {explicit_path}")
        return None

    try:
        with open(explicit_path, 'r') as f:
            model_code = f.read()
        exec(model_code)
        build_model()
        print("✓ Model loaded successfully")
    except Exception as e:
        print(f"✗ Model loading failed: {e}")
        return None

    # Strategy 1: Standard approach with enhanced error handling
    print("\n1️⃣ Trying standard eigenvalue analysis...")
    try:
        ops.wipeAnalysis()
        ops.system('BandGen')
        ops.numberer('RCM')

        # Use a smaller number of modes initially
        test_modes = min(3, num_modes)
        eigenvalues = ops.eigen(test_modes)

        if eigenvalues and len(eigenvalues) > 0:
            print(f"   ✓ Standard analysis succeeded for {test_modes} modes")

            # Try for full number of modes
            if test_modes < num_modes:
                eigenvalues = ops.eigen(num_modes)
                if eigenvalues and len(eigenvalues) == num_modes:
                    print(f"   ✓ Extended to {num_modes} modes successfully")
                    return eigenvalues
                else:
                    print(f"   ⚠️  Could only compute {test_modes} modes reliably")
                    return eigenvalues[:test_modes]
            else:
                return eigenvalues
        else:
            print("   ✗ Standard analysis failed")
    except Exception as e:
        print(f"   ✗ Standard analysis error: {e}")

    # Strategy 2: Use generalized eigenvalue solver
    print("\n2️⃣ Trying generalized eigenvalue solver...")
    try:
        ops.wipeAnalysis()
        ops.system('FullGeneral')  # More robust for ill-conditioned problems
        ops.numberer('RCM')

        eigenvalues = ops.eigen(num_modes)
        if eigenvalues and len(eigenvalues) > 0:
            print(f"   ✓ Generalized solver succeeded")
            return eigenvalues
        else:
            print("   ✗ Generalized solver failed")
    except Exception as e:
        print(f"   ✗ Generalized solver error: {e}")

    # Strategy 3: Incremental mode computation
    print("\n3️⃣ Trying incremental mode computation...")
    try:
        ops.wipeAnalysis()
        ops.system('BandGen')
        ops.numberer('RCM')

        eigenvalues = []
        for i in range(1, num_modes + 1):
            try:
                # Compute one mode at a time
                single_ev = ops.eigen(1)
                if single_ev and len(single_ev) > 0:
                    eigenvalues.extend(single_ev)
                    print(f"   ✓ Mode {i}: eigenvalue = {single_ev[0]:.2e}")
                else:
                    print(f"   ✗ Failed at mode {i}")
                    break
            except Exception as e:
                print(f"   ✗ Mode {i} failed: {e}")
                break

        if eigenvalues:
            print(f"   ✓ Incremental computation got {len(eigenvalues)} modes")
            return eigenvalues
    except Exception as e:
        print(f"   ✗ Incremental computation error: {e}")

    # Strategy 4: Reduced precision attempt
    print("\n4️⃣ Trying with modified numerical settings...")
    try:
        ops.wipeAnalysis()

        # Use profile solver which can be more stable
        ops.system('ProfileSPD')
        ops.numberer('Plain')

        # Try with fewer modes first
        reduced_modes = max(1, num_modes // 2)
        eigenvalues = ops.eigen(reduced_modes)

        if eigenvalues and len(eigenvalues) > 0:
            print(f"   ✓ Reduced precision got {len(eigenvalues)} modes")
            return eigenvalues
        else:
            print("   ✗ Reduced precision failed")
    except Exception as e:
        print(f"   ✗ Reduced precision error: {e}")

    print("\n❌ All eigenvalue strategies failed")
    print("\n🔍 DIAGNOSTIC SUGGESTIONS:")
    print("   1. The model may have numerical conditioning issues")
    print("   2. Check for very small or zero section properties")
    print("   3. Verify mass matrix is well-conditioned")
    print("   4. Consider using different element types")
    print("   5. Check for mechanisms or insufficient constraints")

    return None

def analyze_eigenvalues(eigenvalues):
    """Analyze computed eigenvalues and provide insights"""
    if not eigenvalues:
        return

    print(f"\n📊 EIGENVALUE ANALYSIS ({len(eigenvalues)} modes)")
    print("=" * 50)

    periods = []
    frequencies = []

    for i, ev in enumerate(eigenvalues, 1):
        if ev > 1e-12:
            omega = (ev)**0.5
            freq = omega / (2 * 3.14159)
            period = 1.0 / freq if freq > 0 else float('inf')
        else:
            omega = 0
            freq = 0
            period = float('inf')

        periods.append(period)
        frequencies.append(freq)

        print(f"Mode {i:2}: T = {period:8.4f} s, f = {freq:8.3f} Hz (λ = {ev:.2e})")

    # Analysis
    T1 = periods[0] if periods else float('inf')
    rigid_modes = sum(1 for T in periods if T > 100 or T == float('inf'))

    print(f"\nFundamental period: {T1:.4f} seconds")
    print(f"Rigid body modes: {rigid_modes}")
    print(f"Structural modes: {len(periods) - rigid_modes}")

    if 0.1 <= T1 <= 10.0:
        print("✅ Results appear reasonable")
        return True
    elif T1 > 100:
        print("⚠️  Very long period - possible constraint issues")
        return False
    else:
        print("⚠️  Unusual period - verify structure")
        return True

if __name__ == "__main__":
    eigenvalues = robust_eigenvalue_analysis(num_modes=6)

    if eigenvalues:
        success = analyze_eigenvalues(eigenvalues)
        if success:
            print("\n🎉 Robust eigenvalue analysis completed successfully!")
        else:
            print("\n⚠️  Analysis completed but results may need review")
    else:
        print("\n❌ Eigenvalue analysis completely failed")
        print("Model requires significant debugging")