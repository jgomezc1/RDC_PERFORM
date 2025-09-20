# System Architecture (RDC_PERFORM)

## Overview
Goal: translate ETABS `.e2k` into an OpenSeesPy model + machine-readable artifacts, then verify and probe the model.

**Phases**
1. **Phase-1 (Parse & Story Graph)**
   - `e2k_parser.py` → normalized dict (including `LENGTHOFFI`/`LENGTHOFFJ` extraction for future use)
   - `story_builder.py` → `out/story_graph.json` (stories, elevations, active points/lines)
2. **Phase-2 (Domain + Artifacts)**
   - `nodes.py` + `emit_nodes.py` → `out/nodes.json` (domain nodes incl. diaphragm masters)
   - `diaphragms.py` → `out/diaphragms.json` (master/slaves, mass/fix)
   - `beams.py`, `columns.py` → `out/beams.json`, `out/columns.json` (single elements connecting grid nodes)
   - `supports.py` → `out/supports.json`
3. **Explicit Model & Checks**
   - `generate_explicit_model.py` → `out/explicit_model.py` (nonlinear override support)
   - `explicit_runtime_check.py` / `explicit_static_probe.py` → smoke/probe analyses
   - `verify_model.py`, `verify_domain_vs_artifacts.py` → parity checks

**Pipelines**
- `MODEL_translator.py` orchestrates Phase‑2 with strict ordering
- `run_pipeline.py` manages end‑to‑end generation

## Dataflow
`.e2k` → `e2k_parser.py` → `story_builder.py` → `story_graph.json`
→ `MODEL_translator.build_model()` (enforces ordering):
→ `nodes.py` → `supports.py` → `diaphragms.py` → `emit_nodes.py` → `nodes.json`
→ (`columns.py`, `beams.py`) → `columns.json`, `beams.json` (single elements per line)
→ `generate_explicit_model.py` → `explicit_model.py` → checks/probes

## Key Conventions
- **Node tag determinism**: deterministic tagging prevents conflicts.
- **Direct element modeling**: single OpenSees elements connect directly between grid nodes.
- **Per‑element transforms**: unique `geomTransf` tags derived deterministically from element tags.
- **ETABS data preservation**: rigid end data (`LENGTHOFFI`/`LENGTHOFFJ`) preserved in artifacts but not used in modeling.
### Node creation ordering (simplified)
- Grid nodes created from ETABS points via deterministic tagging.
- Diaphragm master nodes created during diaphragm processing.
- All elements connect directly between these grid/master nodes.

## External Interfaces
- OpenSeesPy API: model building, constraints, analysis execution.
- JSON artifacts in `out/` consumed by generators and visualization tools.
- ETABS integration: direct `.e2k` processing with preserved rigid end data for future use.

## Failure Modes to Watch
- Diaphragm/support conflicts: diaphragm creation is skipped on stories with supports.
- Transform tag collisions: per‑element transforms must use unique prefixes (e.g., `1000000000` for beams, `1100000000` for columns).
- Element endpoint mismatches: all elements must connect between existing grid/master nodes.
