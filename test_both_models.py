#!/usr/bin/env python3
"""
Test both Ejemplo.e2k and EjemploNew.e2k to identify which has the modal analysis issue.
"""
import sys
import os
from pathlib import Path

# Test both models
models_to_test = [
    ("Ejemplo", "models/Ejemplo.e2k"),
    ("EjemploNew", "models/EjemploNew.e2k")
]

results = {}

for model_name, model_path in models_to_test:
    print(f"\n{'='*80}")
    print(f"TESTING MODEL: {model_name}")
    print(f"{'='*80}\n")

    # Update config
    with open("config.py", "r") as f:
        config_lines = f.readlines()

    with open("config.py", "w") as f:
        for line in config_lines:
            if line.strip().startswith("E2K_PATH"):
                if model_name in line:
                    # Uncomment this model
                    f.write(f'E2K_PATH = Path("{model_path}")\n')
                elif "E2K_PATH = Path" in line:
                    # Comment out other models
                    f.write(f"#{line}")
                else:
                    f.write(line)
            else:
                f.write(line)

    print(f"✓ Config updated to use {model_path}")

    # Generate explicit model
    print(f"\n📦 Generating explicit model for {model_name}...")
    ret = os.system("python3 experimental/generate_explicit_model.py > /dev/null 2>&1")

    if ret != 0:
        print(f"❌ Failed to generate explicit model for {model_name}")
        results[model_name] = "BUILD_FAILED"
        continue

    print(f"✓ Explicit model generated")

    # Test modal analysis
    print(f"\n🧪 Running modal analysis test for {model_name}...")
    test_code = """
import sys
sys.path.insert(0, 'out')
from explicit_model import build_model
import openseespy.opensees as ops

try:
    build_model()

    # Get model info
    node_tags = ops.getNodeTags()
    ele_tags = ops.getEleTags()

    print(f"  Nodes: {len(node_tags)}")
    print(f"  Elements: {len(ele_tags)}")

    # Try eigenvalue analysis
    print(f"  Running eigenvalue analysis for 6 modes...")

    ops.wipeAnalysis()
    ops.system('ProfileSPD')
    ops.numberer('RCM')
    ops.constraints('Transformation')
    ops.algorithm('Linear')

    eigenvalues = ops.eigen(6)

    if eigenvalues and len(eigenvalues) == 6:
        import math
        periods = [2 * math.pi / math.sqrt(ev) if ev > 0 else 0 for ev in eigenvalues]
        print(f"  ✓ Modal analysis SUCCESS")
        print(f"  Periods (s): {[f'{p:.3f}' for p in periods[:3]]}")
        sys.exit(0)
    else:
        print(f"  ❌ Modal analysis FAILED - insufficient modes")
        sys.exit(1)

except Exception as e:
    import traceback
    print(f"  ❌ Modal analysis FAILED with error:")
    print(f"  {str(e)}")
    traceback.print_exc()
    sys.exit(1)
"""

    with open("temp_modal_test.py", "w") as f:
        f.write(test_code)

    ret = os.system("python3 temp_modal_test.py 2>&1")

    if ret == 0:
        results[model_name] = "SUCCESS"
    else:
        results[model_name] = "MODAL_FAILED"

    print()

# Summary
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}\n")

for model_name in ["Ejemplo", "EjemploNew"]:
    status = results.get(model_name, "NOT_TESTED")
    symbol = "✓" if status == "SUCCESS" else "❌"
    print(f"{symbol} {model_name:15s}: {status}")

print()

# Cleanup
if os.path.exists("temp_modal_test.py"):
    os.remove("temp_modal_test.py")
