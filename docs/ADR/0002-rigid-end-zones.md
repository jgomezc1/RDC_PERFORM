# ADR-0002 — Rigid End Zones via geomTransf Joint Offsets

## Status
**Accepted** — 2025-10-14 (Supersedes previous 3-segment approach)

## Context
ETABS allows definition of rigid end zones and nodal offsets using:
- `LENGTHOFFI` / `LENGTHOFFJ` — Rigid end lengths along member axis
- `OFFSETX/Y/ZI/J` — Lateral eccentricities at member ends

These must be accurately represented in OpenSeesPy to match ETABS structural behavior.

### Previous Approach (Deprecated 2025-10-14)
Originally, the system split members into 2-3 physical segments with inflated properties to approximate rigid behavior. This required:
- Creating intermediate nodes at rigid/deformable interfaces
- Managing node registration and deterministic tagging
- Handling multiple elements per ETABS line

**Problems with segment splitting:**
- Increased model complexity (3× elements per member)
- Numerical conditioning issues with extreme property ratios
- Complex downstream handling (filtering rigid vs deformable segments)
- Intermediate node management overhead

## Decision
Use OpenSees' native `-jntOffset` parameter in `geomTransf` to handle both rigid ends and lateral offsets in a single element.

### Implementation
Each ETABS beam/column → **single** OpenSees `elasticBeamColumn` element with:

1. **Direct grid-to-grid connection** (no intermediate nodes)
2. **Combined offset vectors** calculated as:
   ```
   d_I = d_I^(len) + Δ_I    (axial rigid end + lateral offset)
   d_J = d_J^(len) + Δ_J    (axial rigid end + lateral offset)
   ```
   Where:
   - `d_I^(len) = +LENGTHOFFI * e` (unit vector along member, I→J direction)
   - `d_J^(len) = -LENGTHOFFJ * e` (unit vector along member, opposite direction)
   - `Δ_I = (OFFSETXI, OFFSETYI, OFFSETZI)` (Cartesian offset)
   - `Δ_J = (OFFSETXJ, OFFSETYJ, OFFSETZJ)` (Cartesian offset)

3. **Applied via geomTransf:**
   ```python
   ops.geomTransf('Linear', transf_tag, vecxz_x, vecxz_y, vecxz_z,
                  '-jntOffset',
                  dI[0], dI[1], dI[2],  # I-end offset
                  dJ[0], dJ[1], dJ[2])  # J-end offset
   ```

### Code Location
- `src/model_building/beams.py` — Lines 216-287 (`_calculate_joint_offsets`)
- `src/model_building/columns.py` — Lines 77-148 (`_calculate_joint_offsets`)

### Artifact Preservation
- `LENGTHOFFI/J` and `OFFSETX/Y/ZI/J` preserved in `beams.json`/`columns.json`
- Joint offset vectors stored as `joint_offset_i` / `joint_offset_j`
- Flag `has_joint_offsets` indicates if `-jntOffset` was used

## Consequences

### Positive
- **Simplified model:** One element per ETABS line (no intermediate nodes)
- **Exact rigid behavior:** OpenSees handles rigid offsets internally with correct kinematics
- **Better numerics:** No property inflation needed
- **Cleaner artifacts:** Direct correspondence between ETABS lines and OpenSees elements
- **Easier validation:** Element counts match ETABS model

### Negative
- **OpenSees version dependency:** Requires OpenSeesPy with `-jntOffset` support
- **Less explicit:** Rigid zones not visible as separate elements in visualization
- **Black box:** Offset mechanics handled internally by OpenSees

### Migration Notes
- Previous `rigid_end_utils.py` module deprecated but retained for reference
- Old ADR-0002 approach removed circa 2025-10-14
- Artifacts from old approach incompatible (different node/element counts)

## Verification
The validation framework checks:
1. **Transform verification:** All elements with offsets use `-jntOffset`
2. **Artifact completeness:** Joint offset vectors stored in JSON
3. **Geometric consistency:** Offset magnitudes reasonable relative to member length

See `validation/opensees_model_tests.py` for detailed checks.

## References
- OpenSees Command Manual: [geomTransf](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/elements/geomTransf.html)
- `-jntOffset` parameter documentation for joint offsets
- `src/utilities/rigid_end_utils.py` — Deprecated implementation (kept for reference)

## Future Extensions
- Support for `-jntMass` parameter (mass offsets at ends)
- Visualization enhancements to show offset vectors in model viewer
- Validation against ETABS results for models with complex offset patterns
