# Roadmap (Near-Term)

## 0–2 weeks
- ✅ Rigid end zones via `-jntOffset` (COMPLETE - no intermediate nodes needed)
- ✅ Per-element `geomTransf` for all beams/columns (COMPLETE)
- Strengthen validation for joint offset correctness
- Add visualization for offset vectors in model viewer
- Parameterize sections/materials (remove remaining placeholders)

## 2–6 weeks
- ✅ `-jntOffset` support for offsets (COMPLETE - handles LENGTHOFFI/J + OFFSETX/Y/Z)
- Enhance nonlinear material support (fiber sections, plastic hinges)
- Expand validation probes: eigen checks per story; lateral pushover by story master
- Add support for wall elements and shell elements

## Nice-to-have
- CI job that runs `explicit_runtime_check.py` on PRs.
