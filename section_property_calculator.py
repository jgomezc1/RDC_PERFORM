#!/usr/bin/env python3
"""
Section Property Calculator for ETABS to OpenSees Translation

This module calculates geometric section properties from ETABS frame section
dimensions for use in OpenSees fiber sections or elastic beam-column elements.

Key calculations:
- Area, moment of inertia, torsional constant
- Section moduli for strength calculations
- Shear area factors for frame elements
"""

import json
import math
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SectionProperties:
    """Container for calculated section properties"""
    name: str
    shape: str
    material: str
    depth: float  # D dimension (m)
    width: float  # B dimension (m)
    area: float  # Cross-sectional area (m²)
    Ixx: float  # Moment of inertia about x-x axis (m⁴)
    Iyy: float  # Moment of inertia about y-y axis (m⁴)
    J: float   # Torsional constant (m⁴)
    Sxx: float # Section modulus about x-x axis (m³)
    Syy: float # Section modulus about y-y axis (m³)
    ry: float  # Radius of gyration about y-y axis (m)
    rx: float  # Radius of gyration about x-x axis (m)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'name': self.name,
            'shape': self.shape,
            'material': self.material,
            'dimensions': {
                'depth': self.depth,
                'width': self.width
            },
            'properties': {
                'area': self.area,
                'Ixx': self.Ixx,
                'Iyy': self.Iyy,
                'J': self.J,
                'Sxx': self.Sxx,
                'Syy': self.Syy,
                'rx': self.rx,
                'ry': self.ry
            }
        }


class SectionPropertyCalculator:
    """
    Calculates geometric section properties from ETABS dimensions

    Supports rectangular concrete sections with standard formulas:
    - Area = B × D
    - Ixx = B × D³ / 12 (strong axis for beams)
    - Iyy = D × B³ / 12 (weak axis for beams)
    - J = β × B × D³ (torsional constant with warping factor)
    """

    def __init__(self, parsed_data_path: str = "out/parsed_raw.json"):
        """Initialize calculator with ETABS parsed data"""
        self.parsed_data_path = Path(parsed_data_path)
        self.sections_data = None
        self.section_properties = {}

        self._load_etabs_data()
        self._calculate_all_sections()

    def _load_etabs_data(self):
        """Load frame sections from ETABS data"""
        try:
            with open(self.parsed_data_path, 'r') as f:
                data = json.load(f)

            self.sections_data = data.get('frame_sections', {})

            if not self.sections_data:
                raise ValueError("No frame sections found in ETABS data")

            print(f"Loaded {len(self.sections_data)} frame sections from ETABS")

        except FileNotFoundError:
            raise FileNotFoundError(f"ETABS parsed data not found: {self.parsed_data_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in parsed data: {self.parsed_data_path}")

    def _calculate_rectangular_properties(self, B: float, D: float) -> Dict[str, float]:
        """
        Calculate properties for rectangular concrete section

        Args:
            B: Width (m)
            D: Depth (m)

        Returns:
            Dictionary with calculated geometric properties
        """
        # Basic properties
        area = B * D

        # Moments of inertia
        Ixx = B * D**3 / 12  # Strong axis (typical for beams)
        Iyy = D * B**3 / 12  # Weak axis

        # Torsional constant for rectangular section
        # Using Saint-Venant torsion formula: J = β × a × b³
        # where a is larger dimension, b is smaller dimension
        a = max(B, D)
        b = min(B, D)
        aspect_ratio = a / b

        # β factor from table for rectangular sections
        if aspect_ratio >= 10:
            beta = 0.333
        elif aspect_ratio >= 5:
            beta = 0.299
        elif aspect_ratio >= 3:
            beta = 0.263
        elif aspect_ratio >= 2:
            beta = 0.229
        else:
            beta = 0.141 + 0.196 * (1.0 / aspect_ratio)  # Linear interpolation for aspect_ratio = 1

        J = beta * a * b**3

        # Section moduli
        Sxx = Ixx / (D / 2)  # For bending about x-x axis
        Syy = Iyy / (B / 2)  # For bending about y-y axis

        # Radii of gyration
        rx = math.sqrt(Ixx / area)
        ry = math.sqrt(Iyy / area)

        return {
            'area': area,
            'Ixx': Ixx,
            'Iyy': Iyy,
            'J': J,
            'Sxx': Sxx,
            'Syy': Syy,
            'rx': rx,
            'ry': ry
        }

    def _calculate_all_sections(self):
        """Calculate properties for all frame sections"""
        for section_name, section_data in self.sections_data.items():
            # Extract dimensions
            dimensions = section_data.get('dimensions', {})
            B = dimensions.get('B', 0)  # Width
            D = dimensions.get('D', 0)  # Depth

            if B <= 0 or D <= 0:
                print(f"Warning: Invalid dimensions for section {section_name}: B={B}, D={D}")
                continue

            # Get other properties
            shape = section_data.get('shape', 'Unknown')
            material = section_data.get('material', 'Unknown')

            # Calculate geometric properties (assuming rectangular)
            if 'Rectangular' in shape:
                props_dict = self._calculate_rectangular_properties(B, D)

                # Create section properties object
                properties = SectionProperties(
                    name=section_name,
                    shape=shape,
                    material=material,
                    depth=D,
                    width=B,
                    **props_dict
                )

                self.section_properties[section_name] = properties

                print(f"Section {section_name}: {B:.2f}×{D:.2f}m, A={props_dict['area']:.4f}m², "
                      f"Ixx={props_dict['Ixx']:.6f}m⁴, Iyy={props_dict['Iyy']:.6f}m⁴")

            else:
                print(f"Warning: Unsupported shape '{shape}' for section {section_name}")

    def get_section_properties(self, section_name: str) -> Optional[SectionProperties]:
        """
        Get calculated properties for a specific section

        Args:
            section_name: ETABS section name (e.g., 'V40X55', 'C50x80B')

        Returns:
            SectionProperties object or None if not found
        """
        return self.section_properties.get(section_name)

    def get_all_sections(self) -> Dict[str, SectionProperties]:
        """Get all calculated section properties"""
        return self.section_properties.copy()

    def get_opensees_section_commands(self) -> Dict[str, Dict[str, Any]]:
        """
        Generate OpenSees elastic section commands

        Returns:
            Dictionary mapping section names to OpenSees section data
        """
        commands = {}

        for i, (name, props) in enumerate(self.section_properties.items(), 1):
            # For linear elastic analysis, use elastic beam-column elements
            commands[name] = {
                'tag': i,
                'properties': {
                    'A': props.area,
                    'E': None,  # Will be filled from material properties
                    'G': None,  # Will be calculated as E/(2*(1+ν))
                    'J': props.J,
                    'Iy': props.Iyy,  # Minor axis moment of inertia
                    'Iz': props.Ixx   # Major axis moment of inertia
                },
                'command_template': "ops.element('elasticBeamColumn', {eleTag}, {iNode}, {jNode}, {A}, {E}, {G}, {J}, {Iy}, {Iz}, {transfTag})"
            }

        return commands

    def export_section_properties(self, output_path: str = "out/section_properties.json"):
        """
        Export calculated section properties to JSON file

        Args:
            output_path: Path for output JSON file
        """
        output_data = {
            'sections': {name: props.to_dict() for name, props in self.section_properties.items()},
            'opensees_commands': self.get_opensees_section_commands(),
            'calculation_info': {
                'formulas_used': {
                    'area': 'A = B × D',
                    'Ixx': 'Ixx = B × D³ / 12 (strong axis)',
                    'Iyy': 'Iyy = D × B³ / 12 (weak axis)',
                    'J': 'J = β × a × b³ (Saint-Venant torsion)',
                    'section_modulus': 'S = I / (c) where c is distance to extreme fiber'
                },
                'units': {
                    'dimensions': 'm',
                    'area': 'm²',
                    'moments_of_inertia': 'm⁴',
                    'section_moduli': 'm³'
                }
            }
        }

        output_path = Path(output_path)
        output_path.parent.mkdir(exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"Section properties exported to {output_path}")


def demonstrate_calculator():
    """Demonstrate the section property calculator functionality"""
    print("ETABS Section Property Calculator")
    print("=" * 40)

    try:
        # Create calculator instance
        calculator = SectionPropertyCalculator()

        print(f"\nCalculated properties for {len(calculator.get_all_sections())} sections:")
        print("-" * 60)

        # Show sample sections with their properties
        sections = list(calculator.get_all_sections().items())[:5]
        for section_name, props in sections:
            print(f"\n{section_name} ({props.material}):")
            print(f"  Dimensions: {props.width:.2f} × {props.depth:.2f} m")
            print(f"  Area: {props.area:.4f} m²")
            print(f"  Ixx: {props.Ixx:.6f} m⁴ (strong axis)")
            print(f"  Iyy: {props.Iyy:.6f} m⁴ (weak axis)")
            print(f"  J: {props.J:.6f} m⁴ (torsion)")

        if len(calculator.get_all_sections()) > 5:
            print(f"\n  ... and {len(calculator.get_all_sections())-5} more sections")

        # Export properties
        calculator.export_section_properties()

        print(f"\n✅ Section property calculation completed successfully!")
        print("Properties exported to out/section_properties.json")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    demonstrate_calculator()