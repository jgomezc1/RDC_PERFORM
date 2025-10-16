# Model Validation Checklist

## Quick Diagnosis Tool

```bash
# Run this after EVERY model translation:
python static_model_validator.py
```

## What to Look For

### ✅ HEALTHY MODEL (Safe to Analyze)
```
CHECK 1: ✓ PASS: All structural nodes connected
CHECK 2: ✓ PASS: No zero-length frame elements
CHECK 3: ✓ PASS: No duplicate node locations
CHECK 4: ✓ PASS: Adequate support
CHECK 5: ✓ PASS: Structure is fully connected (1 component)
CHECK 6: ✓ PASS: Rigid diaphragms properly configured
CHECK 7: ✓ PASS: All nodes adequately connected
CHECK 8: ✓ PASS: No obvious problematic patterns

SUMMARY: ✅ MODEL APPEARS STRUCTURALLY SOUND
```

### ❌ BROKEN MODEL (DO NOT ANALYZE)
```
CHECK 5: ❌ FAIL: 956 disconnected structural components

SUMMARY: ❌ MODEL HAS STRUCTURAL DEFECTS
```

## Common Problems and Fixes

| Problem | Symptom | Fix in ETABS |
|---------|---------|--------------|
| **Disconnected Components** | "956 disconnected components" | Merge points, redraw connections |
| **Duplicate Nodes** | "628 locations with duplicates" | Edit → Merge Points (tolerance 0.001m) |
| **Orphaned Nodes** | "13 nodes not connected" | Delete unused points or connect them |
| **No Support** | "Only X fixed DOFs" | Add restraints/springs at base |
| **Collinear Supports** | "Supports too concentrated" | Distribute supports spatially |

## ETABS Pre-Export Checklist

Before exporting .e2k file:

```
☐ 1. Edit → Merge Duplicate Points (tolerance: 0.001m)
☐ 2. Analyze → Check Model → Review ALL warnings
☐ 3. Analyze → Run Analysis → Verify it completes
☐ 4. Display → Show Mode Shapes → Check they look reasonable
☐ 5. File → Export → .e2k format
```

## OpenSees Post-Translation Checklist

After generating explicit_model.py:

```
☐ 1. python static_model_validator.py
☐ 2. Review output: Must show 0 errors
☐ 3. Check out/stability_report.json
☐ 4. Only proceed to analysis if validation passes
```

## Validation Red Flags

**STOP and fix in ETABS if you see:**
- ❌ More than 10 disconnected components
- ❌ More than 50 duplicate node locations
- ❌ Any component with no supports
- ❌ Fewer than 6 fixed DOFs
- ❌ More than 100 orphaned nodes

**Investigate if you see:**
- ⚠️ 2-10 disconnected components (may be intentional for staged construction)
- ⚠️ 10-50 duplicate nodes (minor cleanup needed)
- ⚠️ Nodes with single element connection (check if supported or in diaphragm)

## Eigenvalue Analysis Command

Only run this AFTER validation passes:

```python
from out.explicit_model import build_model
from openseespy.opensees import *

build_model()
wipeAnalysis()
constraints('Transformation')
numberer('RCM')
system('FullGeneral')  # Most robust solver

numEigen = 6
eigenValues = eigen(numEigen)

print("\nEigenvalue Results:")
print("=" * 50)
from math import sqrt, pi
for i, lam in enumerate(eigenValues):
    if lam > 0:
        freq = sqrt(lam) / (2 * pi)
        period = 1 / freq
        print(f"Mode {i+1}: T={period:.3f}s, f={freq:.3f}Hz")
    else:
        print(f"Mode {i+1}: INVALID (λ={lam})")
        print("   ⚠️ Negative eigenvalue = structural instability!")
```

## Interpreting Results

### Good Results:
```
Mode 1: T=2.450s, f=0.408Hz  ← Fundamental period (longest)
Mode 2: T=1.932s, f=0.518Hz
Mode 3: T=1.785s, f=0.560Hz
...
All eigenvalues positive ✓
```

### Bad Results:
```
ProfileSPDLinDirectSolver::solve() - aii < minDiagTol (i, aii): (702, -3.90579e-28)
```
**Meaning**: DOF 702 is unconstrained or part of mechanism
**Action**: Run validator, fix structural defects, try again

```
Mode 1: INVALID (λ=-0.00012)
Mode 2: INVALID (λ=-0.00008)
```
**Meaning**: Negative eigenvalues = instability or rigid body modes
**Action**: Check supports, check connectivity

## File Reference

| File | Purpose |
|------|---------|
| `static_model_validator.py` | Main validation tool |
| `out/stability_report.json` | Detailed validation results |
| `out/explicit_model.py` | Generated OpenSees model |
| `STRUCTURAL_DEFECTS_FOUND.md` | Detailed problem analysis |

## Quick Commands

```bash
# Full rebuild and validate
python build_and_validate.py

# Validate existing model
python static_model_validator.py

# View validation report
cat out/stability_report.json | python -m json.tool

# Count errors
grep -c "ERROR" out/stability_report.json

# Switch between E2K files (edit config.py)
# Then regenerate:
python build_and_validate.py
```

## Support

If validation passes but analysis still fails:
1. Check `out/stability_report.json` for warnings
2. Review weak connectivity nodes
3. Check if problem is specific to certain solver/numberer
4. Verify material properties are reasonable
5. Check if mode count requested is too high

If validation fails with many errors:
1. Open ETABS model
2. Fix structural defects there
3. Re-export .e2k
4. Re-translate and re-validate

---

**Remember**: The validator is your first line of defense. Never skip it!
