# System Architecture (RDC_PERFORM)

## Overview
Goal: translate ETABS `.e2k` into an OpenSeesPy model + machine-readable artifacts, then verify and probe the model with **advanced rigid end zone handling**.

**Phases**
1. **Phase-1 (Parse & Story Graph)**
   - `e2k_parser.py` → normalized dict (including `LENGTHOFFI`/`LENGTHOFFJ` extraction)
   - `story_builder.py` → `out/story_graph.json` (stories, elevations, active points/lines with rigid-end metadata)
2. **Phase-2 (Domain + Artifacts)**
   - `nodes.py` + `emit_nodes.py` → `out/nodes.json` (domain nodes incl. diaphragm masters **and** intermediate nodes)
   - `diaphragms.py` → `out/diaphragms.json` (master/slaves, mass/fix)
   - `beams.py`, `columns.py` → `out/beams.json`, `out/columns.json` (3‑segment splitting for rigid ends: `rigid_i` → `deformable` → `rigid_j`)
   - `supports.py` → `out/supports.json`
3. **Explicit Model & Checks**
   - `generate_explicit_model.py` → `out/explicit_model.py` (nonlinear override support with rigid‑segment protection)
   - `explicit_runtime_check.py` / `explicit_static_probe.py` → smoke/probe analyses
   - `verify_model.py`, `verify_domain_vs_artifacts.py` → parity checks

**Pipelines**
- `MODEL_translator.py` orchestrates Phase‑2 with strict ordering
- `run_pipeline.py` manages end‑to‑end generation

## Dataflow
`.e2k` → `e2k_parser.py` → `story_builder.py` → `story_graph.json`
→ `MODEL_translator.build_model()` (enforces ordering):
→ `nodes.py` → `supports.py` → `diaphragms.py` → `emit_nodes.py` → `nodes.json`
→ (`columns.py`, `beams.py`) → `columns.json`, `beams.json` (with segment metadata)
→ `generate_explicit_model.py` → `explicit_model.py` → checks/probes

## Key Conventions
- **Node tag determinism**: deterministic tagging prevents conflicts.
- **Rigid end innovation**: `rigid_end_utils.split_with_rigid_ends(...)` converts single ETABS members into 2–3 OpenSees segments.
- **Per‑element transforms**: unique `geomTransf` tags derived deterministically from element tags.
- **Segment classification**: elements labeled `rigid_i`, `deformable`, `rigid_j`; rigid segments use stiffness properties scaled by `RIGID_END_SCALE`.
### Node creation ordering (critical)
- Any process that creates new nodes (e.g., rigid‑end splitting) must **register nodes first** in the centralized registry → flushed to `out/nodes.json`.
- Only then may `beams.json` / `columns.json` be emitted, ensuring their `i_node`/`j_node` exist.
- Preferred API: `emit_nodes.register_intermediate_node(story, x, y, z, source="rigid_end") -> tag` (deterministic tags required).

## External Interfaces
- OpenSeesPy API: model building, constraints, analysis execution.
- JSON artifacts in `out/` consumed by generators and visualization tools.
- ETABS integration: direct `.e2k` processing with full rigid‑zone support.

## Failure Modes to Watch
- Missing intermediate nodes: rigid‑end splitting creates nodes that must be registered **before** element emission.
- Diaphragm/support conflicts: diaphragm creation is skipped on stories with supports.
- Transform tag collisions: per‑element transforms must use unique prefixes (e.g., `1000000000` for beams, `1100000000` for columns).
- Nonlinear override misapplication: rigid segments must **never** receive nonlinear properties.
