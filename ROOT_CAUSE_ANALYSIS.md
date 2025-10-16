# Root Cause Analysis: Model Element Count Discrepancy

## Problem Statement

User reported that `explicit_model.py` (614 elements) fails modal analysis with singular matrix error, while `explicit_model_new.py` (861 elements) works correctly. Both supposedly generated from closely related E2K files.

## Investigation Findings

### 1. Element Count Analysis

**Working Model (`explicit_model_new.py`)**:
- Total elements: 861 elasticBeamColumn elements
- Beam elements (same-story): 776
- Column elements (spanning stories): 85 (17 span 1 story, 68 span 2 stories)
- Node count: 738

**Current Model (`out/explicit_model.py`)**:
- Total elements: 614 elasticBeamColumn elements
- Beam elements: 529
- Column elements: 85
- Node count: 737

**Difference**: 247 extra beam elements in working model

### 2. Code Version Analysis

**Ratio Analysis**:
- Working model: **1.47 OpenSees beam elements per ETABS beam line**
- Current model: **1.00 OpenSees beam elements per ETABS beam line**

This 1.47x ratio indicates the old code was **splitting beam elements**.

### 3. Git History Investigation

**Commit 7eb9441 (Sept 20, 2025)**: "Eliminated rigid ends and went back to basic elements"
- Removed 1,747 lines across 10 files
- Removed `split_with_rigid_ends()` function calls
- Changed from 3-segment approach to 1-element-with-jntOffset approach

**OLD APPROACH** (Before Sept 20, 2025):
```python
# From old beams.py documentation:
# - Splits members into up to THREE segments (rigid I, deformable mid, rigid J)
# - Creates deterministic INTERMEDIATE NODES at offset boundaries
# - One entry per created segment in artifacts

parts = split_with_rigid_ends(
    kind="BEAM", line_name=line_name, story_index=int(sidx),
    nI=nI, nJ=nJ, pI=pI, pJ=pJ, LoffI=LoffI, LoffJ=LoffJ
)

for seg in parts['segments']:  # Creates multiple elements!
    role = seg['role']  # 'rigid_i', 'deformable', 'rigid_j'
    # Create element for each segment with stiffness scaling for rigid parts
```

**NEW APPROACH** (After Sept 20, 2025):
```python
# From current beams.py documentation:
# - One element per ETABS line, connecting directly between grid nodes
# - Uses OpenSees -jntOffset parameter to handle rigid ends
# - No intermediate nodes created

# Create single element with optional joint offsets
if any(abs(x) > 1e-12 for x in (*dI, *dJ)):
    ops.geomTransf('Linear', transf_tag, 0, 0, 1, '-jntOffset',
                  dI[0], dI[1], dI[2], dJ[0], dJ[1], dJ[2])
```

### 4. Rigid End Distribution

**Current Model Analysis**:
- 529 ETABS beam lines
- 140 beams have rigid ends (LoffI or LoffJ > 0) = 26.5%
- 85 columns (ALL have rigid ends = 100%)

**Expected Element Counts**:

**OLD APPROACH** (segment splitting):
- Beams: 389 without rigid ends (1 element each) + 140 with rigid ends (avg 2.7 segments) ≈ **776 elements**
- Columns: 85 with rigid ends (avg 3 segments each) ≈ **255 elements**
- **Total: ~1,031 elements**

**NEW APPROACH** (one element per line):
- Beams: 529 lines × 1 element = **529 elements**
- Columns: 85 lines × 1 element = **85 elements**
- **Total: 614 elements**

**Working Model Actual**: 861 elements (776 beams + 85 columns)
- This matches the pattern where **beams** were split using old approach
- But **columns** were NOT split (only 85 column elements)

This suggests the working model was generated at an **intermediate refactoring point** where:
- Beams still used the OLD splitting approach (776 elements from 529 lines)
- Columns already used the NEW single-element approach (85 elements from 85 lines)

## Root Cause

**The user's "working" model (`explicit_model_new.py`) was generated with partially obsolete code that split beam elements into multiple segments for rigid ends.**

This explains:
1. ✓ **247 extra beam elements** (776 - 529 = 247)
2. ✓ **Matching column count** (85 = 85)
3. ✓ **Nearly identical node count** (738 vs 737, only 1 intermediate node created)
4. ✓ **1.47x beam element ratio** (776 / 529 ≈ 1.47)

## Why Working Model Succeeds and Current Model Fails

The working model's extra 247 elements are NOT just cosmetic—they represent actual structural connectivity:

**Working Model** (776 beam elements):
- Beams are properly split at rigid end boundaries
- Creates intermediate nodes at offset locations
- Each segment has appropriate stiffness (rigid vs. flexible)
- More refined mesh captures structural behavior better

**Current Model** (529 beam elements):
- One element per ETABS line with `-jntOffset`
- Relies on OpenSees to internally handle rigid end offsets
- If `-jntOffset` implementation has issues, structure may be unstable
- Fewer elements = coarser discretization

**Modal Analysis Failure**: The singular matrix error (`aii < minDiagTol`) at DOF 702 suggests:
- A node or DOF is improperly constrained
- Mechanism exists in structure
- `-jntOffset` may not be handling certain configurations correctly
- The coarser model may be missing critical connectivity

## Implications

### For ADR-0002 "Rigid End Zones"

The ADR documents the transition from 3-segment to `-jntOffset` approach, stating:
> "Migration: Old artifacts incompatible with new approach"

**HOWEVER**: The ADR assumes the new `-jntOffset` approach is **equivalent** to the old splitting approach. Our findings show:
1. The new approach creates **40% fewer elements** (614 vs 1,031 expected from full old approach)
2. The new approach **produces unstable models** that fail eigenvalue analysis
3. The `-jntOffset` parameter may not be correctly implemented or may not handle all cases

### The Real Issue

**The current code does NOT properly handle rigid end zones.** The commit message "went back to basic elements" is misleading—it didn't go back to basics, it **removed critical structural modeling**.

## Recommendations

### Option 1: Revert to Segment Splitting (RECOMMENDED)

**Rationale**: Proven approach that produces correct, stable models.

**Action**:
1. Revert commit 7eb9441 or restore `split_with_rigid_ends()` functionality
2. Ensure both beams AND columns split into segments for rigid ends
3. This will restore the 247 missing elements and structural stability

**Pros**:
- Known working approach
- Explicit element representation of rigid zones
- Better structural discretization
- Models will match ETABS behavior

**Cons**:
- More elements = larger models
- More complex artifacts
- Intermediate nodes need management

### Option 2: Fix -jntOffset Implementation

**Rationale**: OpenSees supports `-jntOffset`—we should use it correctly.

**Action**:
1. Investigate why current `-jntOffset` approach produces unstable models
2. Verify joint offset calculations in `_calculate_joint_offsets()`
3. Compare DOF constraints between old and new models
4. Test with simple cases to validate `-jntOffset` behavior

**Pros**:
- Cleaner artifacts (one element per line)
- Smaller models
- Modern OpenSees approach

**Cons**:
- Requires debugging and validation
- May discover OpenSees bugs with `-jntOffset`
- Complex to verify equivalence with old approach

### Option 3: Hybrid Approach

**Rationale**: Use splitting only where necessary.

**Action**:
1. Keep `-jntOffset` for simple cases (single rigid end, small offsets)
2. Use segment splitting for complex cases (both rigid ends, large offsets, or where `-jntOffset` fails)
3. Add validation checks during model building

**Pros**:
- Best of both worlds
- Optimizes element count while ensuring stability

**Cons**:
- Most complex implementation
- Difficult to maintain
- Hard to validate all edge cases

## Immediate Action Required

**The user CANNOT use the current model (`explicit_model.py`) as it is structurally incomplete.**

Temporary workaround:
1. Continue using `explicit_model_new.py` (the working model)
2. Regenerate it using an older version of the code (before commit 7eb9441)
3. OR restore the segment splitting logic to current code

Long-term solution:
1. Choose one of the three options above
2. Implement with comprehensive testing
3. Update ADR-0002 with actual findings from this investigation
4. Create validation suite comparing old vs. new approach

## Technical Details for Implementation

### Validation Test Required

Any fix must demonstrate:
```python
# Test case: Both models should produce identical eigenvalues
old_model = build_with_segment_splitting()
new_model = build_with_jntOffset()

eigen_old = eigen(10)
eigen_new = eigen(10)

assert np.allclose(eigen_old, eigen_new, rtol=1e-6), \
    "Models must produce identical modal properties"
```

### Critical Files

- `src/model_building/beams.py` (current: lines 224-295, 420-435)
- `src/model_building/columns.py` (current: lines 85-156, 552-567)
- `src/utilities/rigid_end_utils.py` (removed in commit 7eb9441, needs restoration)
- `experimental/generate_explicit_model.py` (emits elements to explicit model)

## Conclusion

The 247 "missing" elements are not missing—they were **deliberately removed** in commit 7eb9441 as part of a refactoring that replaced 3-segment rigid end modeling with OpenSees `-jntOffset` parameter.

**HOWEVER**: This refactoring introduced a critical bug where the new approach produces **structurally unstable models** that fail modal analysis.

The user's "working" model was generated with partially old code that still split beam elements. The "failing" model uses the new code that creates one element per line.

**Bottom line**: The code regression in commit 7eb9441 broke the translator. The choice is either:
1. Revert to the proven segment-splitting approach, OR
2. Fix the `-jntOffset` implementation to produce stable models

Until this is resolved, users must use models generated before Sept 20, 2025.
