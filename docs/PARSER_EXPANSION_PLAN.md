# E2K Parser Expansion Plan

## Overview
Systematic expansion of e2k_parser.py to capture comprehensive ETABS features while maintaining backward compatibility and deterministic behavior.

## Architecture Principles

### 1. Incremental Section Addition
- Follow existing `_extract_section()` pattern
- Each new section gets dedicated parsing function
- Regex-based parsing with compiled patterns
- Normalized output structures

### 2. Artifact Versioning Strategy
```python
# Current version structure (phase1_run.py:26)
raw["_artifacts_version"] = "1.1"  # LENGTHOFFI/J support

# Proposed expansion:
raw["_artifacts_version"] = "2.0"  # Material properties + Frame sections
raw["_materials_version"] = "1.0"  # Track material schema separately
raw["_sections_version"] = "1.0"   # Track section schema separately
```

### 3. Backward Compatibility
- New fields are optional and additive
- Existing parsers continue to work
- Version gates protect new feature usage
- Legacy fallbacks for missing data

## New E2K Sections to Parse

### Phase 1: Material Properties
```
$ MATERIAL PROPERTIES
MATERIAL "STEEL" TYPE "Steel" WEIGHTPERVOLUME 7833.414
MATERIAL "STEEL" SYMTYPE "Isotropic" E 2.039E+10 U 0.3 A 1.17E-05
MATERIAL "STEEL" FY 3.515E+07 FU 4.570E+07 FYE 3.867E+07 FUE 5.027E+07
MATERIAL "CONC" TYPE "Concrete" WEIGHTPERVOLUME 2403
MATERIAL "CONC" FC 2812279
```

### Phase 2: Rebar Definitions
```
$ REBAR DEFINITIONS
REBARDEFINITION "#4" AREA 0.000129032 DIA 0.0127
REBARDEFINITION "#5" AREA 0.0001999996 DIA 0.015875
```

### Phase 3: Frame Sections
```
$ FRAME SECTIONS
FRAMESECTION "C50x80C" MATERIAL "H350" SHAPE "Concrete Rectangular" D 0.5 B 0.8
FRAMESECTION "P100" MATERIAL "H210" SHAPE "Concrete Circle" D 1
```

### Phase 4: Concrete Sections (RC Details)
```
$ CONCRETE SECTIONS
CONCRETESECTION "C50x80C" MATERIAL "H350" SHAPE "Rectangular"
CONCRETESECTION "C50x80C" REBARMAT "STEEL" DESIGNTYPE "Beam"
```

## Implementation Strategy

### Step 1: Parser Functions (e2k_parser.py)
```python
def _parse_materials(text: str) -> Dict[str, Any]:
    """Parse MATERIAL PROPERTIES section"""

def _parse_rebar_definitions(text: str) -> List[Dict[str, Any]]:
    """Parse REBAR DEFINITIONS section"""

def _parse_frame_sections(text: str) -> Dict[str, Any]:
    """Parse FRAME SECTIONS section"""

def _parse_concrete_sections(text: str) -> Dict[str, Any]:
    """Parse CONCRETE SECTIONS section"""
```

### Step 2: Enhanced Output Schema
```python
{
  # Existing fields (preserved)
  "stories": [...],
  "points": {...},
  "point_assigns": [...],
  "lines": {...},
  "line_assigns": [...],
  "diaphragm_names": [...],

  # New comprehensive sections
  "materials": {
    "steel": {"STEEL": {"type": "Steel", "E": 2.039e10, "fy": 3.515e7, ...}},
    "concrete": {"CONC": {"type": "Concrete", "fc": 2812279, ...}},
    "properties": {"STEEL": {...}, "CONC": {...}}
  },
  "rebar_definitions": {
    "#4": {"area": 0.000129032, "diameter": 0.0127},
    "#5": {"area": 0.0001999996, "diameter": 0.015875}
  },
  "frame_sections": {
    "C50x80C": {
      "material": "H350",
      "shape": "Concrete Rectangular",
      "dimensions": {"D": 0.5, "B": 0.8},
      "properties": {...}
    }
  },
  "concrete_sections": {...},

  # Versioning
  "_artifacts_version": "2.0",
  "_materials_version": "1.0",
  "_sections_version": "1.0"
}
```

### Step 3: Validation Framework
```python
def validate_materials(materials: Dict[str, Any]) -> List[str]:
    """Validate material properties completeness"""

def validate_sections(sections: Dict[str, Any], materials: Dict[str, Any]) -> List[str]:
    """Validate section-material references"""

def validate_artifacts_compatibility(version: str) -> bool:
    """Check if downstream tools support artifact version"""
```

### Step 4: Integration Points

#### MODEL_translator.py Integration
```python
# Access material properties for realistic section calculations
def get_material_properties(section_name: str) -> Dict[str, float]:
    materials = load_materials_from_artifacts()
    sections = load_sections_from_artifacts()
    return calculate_section_properties(section_name, materials, sections)
```

#### generate_explicit_model.py Integration
```python
# Use actual material properties in explicit models
def _emit_realistic_sections(materials: Dict, sections: Dict) -> None:
    """Emit sections with actual E, fc, fy values from ETABS"""
```

## Implementation Phases

### Phase A (Weeks 1-2): Material Properties
- Parse MATERIAL PROPERTIES section
- Support Steel/Concrete/Custom materials
- Validate material property completeness
- Update artifact versioning to 2.0

### Phase B (Weeks 3-4): Frame Sections
- Parse FRAME SECTIONS with dimensional data
- Link sections to materials
- Calculate derived properties (A, I, etc.)
- Validation for section-material consistency

### Phase C (Weeks 5-6): Rebar & RC Details
- Parse REBAR DEFINITIONS
- Parse CONCRETE SECTIONS reinforcement
- Support for reinforced concrete detailing
- Advanced validation for RC compatibility

### Phase D (Weeks 7-8): Integration & Testing
- Update downstream tools for new artifacts
- Comprehensive regression testing
- Performance optimization
- Documentation updates

## Benefits

1. **Realistic Analysis**: Use actual ETABS material properties
2. **Comprehensive Support**: Handle complex ETABS models
3. **Future-Proof**: Extensible architecture for additional sections
4. **Validation**: Comprehensive checks for model consistency
5. **Backward Compatible**: Existing workflows unaffected

## Risk Mitigation

1. **Version Gates**: New features behind version checks
2. **Fallback Values**: Graceful degradation for missing data
3. **Incremental Rollout**: Phase-by-phase implementation
4. **Regression Testing**: Existing functionality preserved
5. **Schema Evolution**: Controlled artifact format changes