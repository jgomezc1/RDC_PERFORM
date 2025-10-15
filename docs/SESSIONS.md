# Session Handoff (Rolling Notes)

---
## [2025-10-14]
**Status:** Documentation Update

**What Changed**
- Updated all documentation to reflect current `-jntOffset` implementation for rigid ends
- Previous 3-segment splitting approach was superseded (circa 2025-10-14)
- No intermediate nodes created; one element per ETABS line

**Files Updated**
- `docs/ADR/0002-rigid-end-zones.md` — Completely rewritten to document current approach
- `docs/GLOSSARY.md` — Updated rigid end zone definition
- `docs/ROADMAP.md` — Marked offset tasks as complete, updated priorities
- `docs/CONTRIBUTING.md` — Removed references to intermediate nodes and segment classification
- `docs/DECISIONS.md` — Updated ADR-0002 summary
- `docs/NONNEGOTIABLES.md` — Added one-element-per-line principle

**Implementation Details**
- Rigid ends: `LENGTHOFFI/J` → axial component of `-jntOffset` vector
- Lateral offsets: `OFFSETX/Y/ZI/J` → lateral component of `-jntOffset` vector
- Combined via vector addition: `d_I = d_I^(len) + Δ_I`
- Applied in `beams.py` / `columns.py` via `_calculate_joint_offsets()`

**Migration Note**
Old artifacts (with intermediate nodes) are incompatible with current code. Always regenerate from E2K files using current pipeline.

---
## [2025-09-09]
**Branch & Commit:** feature/offsets @ 34264e2

**Last Session**
- Rigid ends implemented. Intermediate nodes now registered in nodes.json.

**Next Up**
- Attach intermediate nodes (kind=intermediate) at each story to that story’s rigid diaphragm.


## [2025-09-08]
**Branch & Commit:** feature/offsets @ 34264e2

**Last Session**
- Rigid ends implemented. Intermediate nodes now registered in nodes.json.

**Next Up**
- Attach intermediate nodes (kind=intermediate) at each story to that story’s rigid diaphragm.

## [2025-09-04]
**Branch & Commit:** feature/offsets @ 77f6b85

**Last Session**
- Implemented rigid-end splitting for beams/columns when `LENGTHOFFI/J` present.
- Created intermediate nodes (white nodes) at rigid/deformable interfaces.

**Problem Discovered**
- Intermediate nodes were **not** propagated into `nodes.json`.
- Downstream, `generate_explicit_model.py` references non-existent nodes → model fails.

**Next Up (Wave-1: correctness)**
- Ensure all intermediate nodes created during splitting are **registered** into `nodes.json` before any element emission.
- Add verification: “no element endpoint is missing in `nodes.json`”.

**Risks / Blockers**
- Double-creation of the same intermediate node if multiple lines share geometry.
- Tagging collisions if tag derivation for intermediate nodes isn’t deterministic.

