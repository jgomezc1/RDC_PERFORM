# Contributing & Session Bootstrap

## Dev Environment
- Python 3.11+, OpenSeesPy installed.
- `pip install -r requirements.txt` (if present)
- `OUT_DIR` defaults to `out/` (see `config.py`).

## Typical Workflow

### Option 1: Full Pipeline (Recommended)
```bash
# Complete end-to-end pipeline with verification
python run_pipeline.py
```

### Option 2: Step-by-Step Execution
```bash
# Phase-1: Parse .e2k and build story graph
python phase1_run.py

# Phase-2: Build domain objects and artifacts
python MODEL_translator.py

# Phase-3: Generate explicit OpenSees model
python generate_explicit_model.py --out out --explicit out/explicit_model.py
```

### Option 3: Staged Development
```bash
# Build only nodes + supports + diaphragms
python -c "from MODEL_translator import build_model; build_model('nodes')"

# Build up to columns
python -c "from MODEL_translator import build_model; build_model('columns')"

# Build complete model
python -c "from MODEL_translator import build_model; build_model('all')"
```

## Nonlinear Analysis Support
```bash
# Generate model with nonlinear overrides (requires nonlinear_overrides.json)
python generate_explicit_model.py --pullover --nonlinear out/nonlinear_overrides.json
python generate_explicit_model.py --out out --explicit out/explicit_model.py --nonlinear
```

## Verification Ritual (post-generation)
After running the pipeline, always verify that artifacts and explicit models are internally consistent.

```bash
# Complete pipeline with built-in verification
python run_pipeline.py

# Manual verification steps
python verify_model.py --artifacts out --strict
python verify_domain_vs_artifacts.py --artifacts out --stage all --strict

# Quick runtime checks
python explicit_runtime_check.py
python explicit_static_probe.py --P 1.0 --dir X
```

## Visualization Integration
```bash
# Generate explicit model for Streamlit viewer
python generate_explicit_model.py --out out --explicit out/explicit_model.py

# Launch Streamlit viewer (separate application)
streamlit run model_viewer_APP.py
# In sidebar: Browse Files → select explicit_translator.py
```

## Key Files and Artifacts

### Input Files
- `.e2k` file (ETABS export)
- `nonlinear_overrides.json` (optional, for nonlinear analysis)

### Generated Artifacts
- `out/story_graph.json` — Stories, elevations, grid points
- `out/nodes.json` — All node definitions including intermediate nodes
- `out/supports.json` — Boundary conditions
- `out/diaphragms.json` — Rigid diaphragm constraints
- `out/columns.json` — Column elements with segment classification
- `out/beams.json` — Beam elements with segment classification
- `out/explicit_model.py` — Complete OpenSees model

### Verification Reports
- `out/verify_report.json` — Static artifact verification
- `out/verify_runtime_report.json` — Runtime domain verification
- `out/pipeline_summary.json` — Overall pipeline status

## Troubleshooting Common Issues

### Missing Intermediate Nodes
If you see errors about missing nodes, ensure proper execution order:
```bash
# Always run complete pipeline to ensure node registration
python run_pipeline.py
```

### Rigid End Zone Issues
The system automatically handles ETABS rigid end zones through 3-segment splitting. Check `beams.json`/`columns.json` for the `segment` field values: `"rigid_i"`, `"deformable"`, `"rigid_j"`.

### Nonlinear Override Problems
Ensure rigid segments are excluded from nonlinear overrides. The system should automatically filter based on segment classification.
