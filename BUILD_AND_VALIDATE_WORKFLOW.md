# Build and Validate Workflow

## Overview

This document describes the recommended workflow for building and validating ETABS-to-OpenSees translations. The workflow ensures that all validation is performed on the **final explicit model** (`out/explicit_model.py`), which is the artifact that users will actually execute.

## Why Validate the Explicit Model?

Previously, validation was performed on the runtime OpenSees model (built dynamically by reading artifacts). This had several issues:

1. **Validation ≠ Production**: The runtime model might differ from the explicit model
2. **Reproducibility**: Runtime model depends on correct artifact reading and module state
3. **User Experience**: Users execute `explicit_model.py`, so that's what should be validated

**The new workflow generates `explicit_model.py` first, then validates it.**

## Workflow Phases

### Phase 1: Build Runtime Model and Generate Artifacts

```bash
python build_and_validate.py --build-only
```

This phase:
1. Parses E2K file (path from `config.py`)
2. Builds runtime OpenSees model
3. Generates artifacts (nodes.json, beams.json, columns.json, supports.json, diaphragms.json, springs.json)
4. Generates `out/explicit_model.py` from artifacts

**Artifacts Generated:**
- `out/parsed_raw.json` - Raw parsed E2K data
- `out/story_graph.json` - Story hierarchy and elevation data
- `out/nodes.json` - All node definitions (grid + master)
- `out/supports.json` - Boundary conditions (rigid + springs)
- `out/columns.json` - Column elements
- `out/beams.json` - Beam elements
- `out/diaphragms.json` - Rigid diaphragm constraints
- `out/springs.json` - Spring elements (if applicable)
- **`out/explicit_model.py`** - Standalone OpenSeesPy script

### Phase 2: Validate Explicit Model

```bash
python build_and_validate.py --validate-only
```

This phase:
1. Loads `out/explicit_model.py`
2. Executes the model
3. Runs comprehensive structural validation tests
4. Reports results

**Validation Tests:**
- ✅ Node count verification
- ✅ Element count verification (beams + columns + springs)
- ✅ Support verification
- ✅ Diaphragm constraint verification
- ✅ Section properties validation
- ✅ Lateral load path verification (static analysis)
- ✅ Modal analysis (eigenvalue analysis)

### Combined Workflow (Default)

```bash
python build_and_validate.py
```

Runs both phases sequentially:
1. Build runtime model → Generate artifacts → Generate explicit model
2. Validate explicit model
3. Report results

## Usage Examples

### Full Build and Validation
```bash
# Default: build + generate + validate
python build_and_validate.py

# Skip validation (just build and generate)
python build_and_validate.py --skip-validation
```

### Build Only
```bash
# Generate explicit model, then stop
python build_and_validate.py --build-only
```

### Validation Only
```bash
# Validate existing explicit model
python build_and_validate.py --validate-only
```

## Configuration

The E2K file path is specified in `config.py`:

```python
# config.py
E2K_PATH = "models/your_model.e2k"
OUT_DIR = "out"
```

## Validation Results Interpretation

### ✅ All Tests Passed
Model is ready for analysis. The explicit model can be used for:
- Structural analysis
- Modal analysis
- Nonlinear time history analysis
- Custom analysis workflows

### ⚠️ Warnings
Model may work but has minor issues. Review warnings and decide if they're acceptable for your use case.

### ❌ Critical Failures
Model has serious issues that must be fixed before use. Common failures:

1. **Element Count Mismatch**
   - Expected vs actual element count differs
   - Usually indicates missing or duplicate elements
   - Check artifacts for completeness

2. **Lateral Load Path Failure**
   - Static analysis doesn't converge
   - May indicate numerical issues or constraints problems
   - Check if supports are properly defined

3. **Modal Analysis Failure**
   - Eigenvalue analysis fails
   - Usually indicates missing mass or singular stiffness matrix
   - Check mass definitions and support conditions

## Workflow Best Practices

### 1. Always Regenerate Explicit Model After Changes

If you modify any source code or E2K file:
```bash
python build_and_validate.py --build-only
```

This ensures `explicit_model.py` is up-to-date with your changes.

### 2. Validate Before Using Model

Before running any analysis:
```bash
python build_and_validate.py --validate-only
```

This confirms the model is structurally sound.

### 3. Check Validation Output

Review validation results carefully:
- Element counts should match (beams + columns + springs)
- Modal periods should be reasonable for your structure
- Load path tests should pass in both X and Y directions

### 4. Use Explicit Model for Production

Always use `out/explicit_model.py` for analysis, not the runtime model:

```python
# Good - uses validated explicit model
import importlib.util
spec = importlib.util.spec_from_file_location("explicit_model", "out/explicit_model.py")
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
model.build_model()

# Bad - uses runtime model (not validated)
from src.orchestration.MODEL_translator import build_model
build_model()
```

## Integration with Streamlit Apps

### Model Viewer
```bash
streamlit run apps/model_viewer_APP.py
```
- Visualizes the explicit model
- Shows nodes, elements, supports, springs, diaphragms
- Interactive 3D rendering

### Structural Validation App
```bash
streamlit run apps/structural_validation_app.py
```
- GUI for validation results
- Interactive charts and tables
- Detailed error reporting

### Workflow Integration

Recommended workflow with Streamlit apps:

```bash
# 1. Build and validate
python build_and_validate.py

# 2. View model (verify visually)
streamlit run apps/model_viewer_APP.py

# 3. Review validation details (optional)
streamlit run apps/structural_validation_app.py

# 4. Use explicit model for analysis
python your_analysis_script.py
```

## Troubleshooting

### "❌ BUILD FAILED"
- Check E2K_PATH in config.py
- Verify E2K file is valid
- Review Phase 1 parser output for errors

### "❌ EXPLICIT MODEL GENERATION FAILED"
- Check that all required artifacts were created
- Review `out/` directory for missing files
- Check generation logs for specific errors

### "⚠️ VALIDATION COMPLETED WITH FAILURES"
- Review specific test failures
- Check validation output for error details
- Consult `VALIDATION_ERROR_REPORTING_UPDATE.md` for diagnostics

### Lateral Load Path Test Failing
If the lateral load path test fails but modal analysis passes:
1. Model is likely structurally sound (modal analysis proves this)
2. Issue may be with static analysis setup or spring flexibility
3. Review enhanced error reporting in validation output
4. Consider whether test assumptions apply to your model

## File Locations

```
RDC_PERFORM/
├── build_and_validate.py          # Main workflow script
├── config.py                       # Configuration (E2K_PATH, OUT_DIR)
├── out/
│   ├── explicit_model.py          # ← VALIDATED ARTIFACT (use this!)
│   ├── nodes.json
│   ├── beams.json
│   ├── columns.json
│   ├── supports.json
│   ├── diaphragms.json
│   └── springs.json
├── validation/
│   └── structural_validation.py   # Validation logic
└── apps/
    ├── model_viewer_APP.py
    └── structural_validation_app.py
```

## Summary

The new workflow ensures:
- ✅ All validation is performed on the final artifact (`explicit_model.py`)
- ✅ Users can trust validation results
- ✅ Explicit model is always up-to-date before validation
- ✅ Clear separation between build and validation phases
- ✅ Easy to re-run validation without rebuilding

**Always follow this sequence:**
1. Build → 2. Generate → 3. Validate → 4. Use
