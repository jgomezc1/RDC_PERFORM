# OpenSees Model Validator - Standalone Validation Tool

## Overview

The OpenSees Model Validator is a standalone Python script that provides comprehensive validation of your OpenSees models outside of the Streamlit environment. This tool allows for independent verification and generates detailed reports for manual inspection.

## Features

### 🧪 **Comprehensive Testing**
- **Model Integrity**: Node/element connectivity, coordinates, dimensions
- **Geometric Validation**: Joint offsets, rigid ends, transformations
- **Structural Analysis**: Modal analysis with frequencies and periods
- **ETABS Consistency**: Cross-validation with original ETABS data

### 📊 **Detailed Reporting**
- **Text Report**: Human-readable validation summary
- **JSON Data**: Machine-readable detailed results
- **Transformation Analysis**: Complete geometric transformation breakdown
- **Tracking Elements**: Verification of specific elements (B408, C522)

### 🔍 **Independent Verification**
- **Standalone Operation**: Works without Streamlit or web interface
- **Modal Analysis**: Dynamic properties and structural assessment
- **Joint Offset Verification**: Mathematical validation of rigid ends/offsets
- **Artifact Cross-checking**: Validation against beams.json/columns.json

## Usage

### Basic Usage
```bash
# Run with default settings (model from out/model.py)
python opensees_model_validator.py

# Specify custom model file
python opensees_model_validator.py --model path/to/your/model.py

# Specify custom output directory
python opensees_model_validator.py --model out/model.py --output my_validation
```

### Command Line Options
```
--model   : Path to OpenSees model Python file (default: out/model.py)
--output  : Output directory for validation files (default: validation_output)
```

## Output Files

The validator creates two main output files:

### 1. `validation_report.txt`
Human-readable text report containing:
- **Model Information**: Node/element counts, dimensions, bounds
- **Test Results**: Pass/fail status for all validation tests
- **Geometric Transformations**: Summary of joint offsets usage
- **Tracking Elements**: Verification of B408 and C522 elements
- **Modal Analysis**: Fundamental frequency, period, and structural assessment

### 2. `validation_data.json`
Machine-readable JSON file with complete validation data:
- Detailed test results with all diagnostic information
- Complete geometric transformation data for all elements
- Tracking element detailed properties
- Modal analysis results (eigenvalues, frequencies, periods)
- Artifact data cross-validation

## What Gets Validated

### Model Integrity
- ✅ All nodes exist with valid coordinates
- ✅ Elements properly connected to existing nodes
- ✅ No orphaned elements or invalid references
- ✅ Reasonable coordinate ranges and model dimensions
- ✅ No duplicate node coordinates

### Geometric Transformations
- ✅ Beam transformations use `vecxz = [0, 0, 1]` (vertical reference)
- ✅ Column transformations use `vecxz = [1, 0, 0]` (horizontal reference)
- ✅ Joint offsets applied when rigid ends or lateral offsets exist
- ✅ Correct `-jntOffset` parameters for affected elements

### Tracking Elements Verification
- ✅ **BEAM B408 @ 11_P6**: Should have `joint_offset_i = [0.4, 0.0, 0.0]`
- ✅ **COLUMN C522 @ 02_P2**: Should have proper rigid ends + lateral offsets

### Structural Properties
- ✅ Modal analysis successful (eigenvalue computation)
- ✅ Reasonable fundamental frequency and period
- ✅ Structural stiffness assessment

## Example Output

### Sample Text Report Excerpt
```
OpenSees Model Validation Report
==================================================
Generated: 2025-01-27 14:30:15
Model File: out/model.py

MODEL INFORMATION
--------------------
Nodes: 1234
Elements: 861
Dimensions: 3D
DOF per node: 6
X range: [0.00, 65.50]
Y range: [0.00, 30.25]
Z range: [0.00, 14.78]

VALIDATION TEST RESULTS
-------------------------
Overall: 16/16 tests passed (100.0%)

Model Integrity Tests: 5/5 passed (100.0%)
  ✓ Node Existence: All 1234 nodes have valid coordinates
  ✓ Element Connectivity: All 861 elements have valid connectivity
  ✓ Coordinate Validity: Coordinate ranges appear reasonable
  ✓ Model Dimensions: Model dimensions: 65.5m × 30.3m × 14.8m
  ✓ Duplicate Nodes: No duplicate coordinates found among 1234 nodes

GEOMETRIC TRANSFORMATIONS
-------------------------
Total transformations: 861
Transformations with joint offsets: 319
  - Beams with offsets: 234
  - Columns with offsets: 85

TRACKING ELEMENTS VERIFICATION
------------------------------
BEAM B408 @ 11_P6:
  ✓ Element found
  ✓ Joint offsets correct
  Joint offset I: [0.4, 0.0, 0.0]
  Joint offset J: [0.0, 0.0, 0.0]

COLUMN C522 @ 02_P2:
  ✓ Element found
  ✓ Joint offsets correct
  Joint offset I: [-0.05, 0.2, 0.275]
  Joint offset J: [-0.05, 0.2, -0.275]

MODAL ANALYSIS
---------------
Fundamental frequency: 2.145 Hz
Fundamental period: 0.466 sec
Assessment: Normal stiffness
```

## Prerequisites

### Required
- Python 3.7+
- OpenSeesPy: `pip install openseespy`

### Optional (for enhanced features)
- matplotlib: `pip install matplotlib` (for future plotting capabilities)

## Integration with Workflow

This validator is designed to complement your existing workflow:

1. **Generate model** using your ETABS→OpenSees translator
2. **Run validator** to get comprehensive verification
3. **Review reports** for any issues or confirmations
4. **Proceed with analysis** confident in model correctness

## Troubleshooting

### Common Issues

**"OpenSeesPy not available"**
- Install OpenSeesPy: `pip install openseespy`

**"Model file not found"**
- Check the path to your model.py file
- Use `--model` flag to specify correct path

**"No eigenvalues computed"**
- Model may have issues with constraints or stability
- Check the detailed test results for model integrity issues

### When to Use

- **Before major analyses** to verify model correctness
- **After model modifications** to check for regressions
- **For documentation** to include validation proof
- **When debugging** model issues or unexpected behavior
- **For independent verification** outside the Streamlit environment

This standalone validator provides confidence that your OpenSees model accurately represents your ETABS design and is ready for structural analysis.