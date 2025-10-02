#!/usr/bin/env python3
"""
Material Property Calculator for ETABS to OpenSees Translation

This module extracts material properties from ETABS parsed data and calculates
OpenSees-compatible material properties using standard concrete mechanics formulas.

Key conversions:
- Elastic modulus from compressive strength using ACI 318 formula
- Unit conversions from ETABS (Pa) to OpenSees (Pa)
- Material name mapping for lookup during element generation
"""

import json
import math
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class MaterialProperties:
    """Container for calculated material properties"""
    name: str
    fc: float  # Compressive strength (Pa)
    Ec: float  # Elastic modulus (Pa)
    weight_per_volume: float  # Unit weight (N/m³)
    poisson_ratio: float = 0.2  # Standard concrete value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'name': self.name,
            'fc': self.fc,
            'Ec': self.Ec,
            'weight_per_volume': self.weight_per_volume,
            'poisson_ratio': self.poisson_ratio
        }


class MaterialPropertyCalculator:
    """
    Calculates OpenSees material properties from ETABS data

    Uses standard concrete mechanics formulas:
    - ACI 318: Ec = 4700 * sqrt(fc') for normal weight concrete
    - Unit conversions and safety factors as appropriate
    """

    def __init__(self, parsed_data_path: str = "out/parsed_raw.json"):
        """Initialize calculator with ETABS parsed data"""
        self.parsed_data_path = Path(parsed_data_path)
        self.materials_data = None
        self.sections_data = None
        self.material_properties = {}

        self._load_etabs_data()
        self._calculate_all_materials()

    def _load_etabs_data(self):
        """Load and extract materials and sections from ETABS data"""
        try:
            with open(self.parsed_data_path, 'r') as f:
                data = json.load(f)

            self.materials_data = data.get('materials', {}).get('concrete', {})
            self.sections_data = data.get('frame_sections', {})

            if not self.materials_data:
                raise ValueError("No concrete materials found in ETABS data")

            print(f"Loaded {len(self.materials_data)} concrete materials from ETABS")
            print(f"Loaded {len(self.sections_data)} frame sections from ETABS")

        except FileNotFoundError:
            raise FileNotFoundError(f"ETABS parsed data not found: {self.parsed_data_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in parsed data: {self.parsed_data_path}")

    def _calculate_elastic_modulus(self, fc: float, weight_per_volume: float) -> float:
        """
        Calculate elastic modulus using ACI 318 formula

        Args:
            fc: Compressive strength in Pa
            weight_per_volume: Unit weight in N/m³

        Returns:
            Elastic modulus in Pa
        """
        # Convert fc from Pa to MPa for calculation
        fc_mpa = fc / 1e6

        # ACI 318 formula: Ec = 4700 * sqrt(fc') for normal weight concrete
        # fc' is in MPa, result is in MPa
        ec_mpa = 4700 * math.sqrt(fc_mpa)

        # Convert back to Pa
        ec_pa = ec_mpa * 1e6

        return ec_pa

    def _calculate_all_materials(self):
        """Calculate properties for all concrete materials"""
        for material_name, material_data in self.materials_data.items():
            fc = material_data['fc']  # Already in Pa from ETABS
            weight = material_data['weight_per_volume']  # Already in N/m³

            # Calculate elastic modulus
            ec = self._calculate_elastic_modulus(fc, weight)

            # Create material properties object
            properties = MaterialProperties(
                name=material_name,
                fc=fc,
                Ec=ec,
                weight_per_volume=weight
            )

            self.material_properties[material_name] = properties

            print(f"Material {material_name}: fc = {fc/1e6:.1f} MPa → Ec = {ec/1e6:.0f} MPa")

    def get_material_properties(self, material_name: str) -> Optional[MaterialProperties]:
        """
        Get calculated properties for a specific material

        Args:
            material_name: ETABS material name (e.g., 'H210', 'H280')

        Returns:
            MaterialProperties object or None if not found
        """
        return self.material_properties.get(material_name)

    def get_all_materials(self) -> Dict[str, MaterialProperties]:
        """Get all calculated material properties"""
        return self.material_properties.copy()

    def get_section_material_mapping(self) -> Dict[str, str]:
        """
        Create mapping from section name to material name

        Returns:
            Dictionary mapping section names to material names
        """
        mapping = {}
        for section_name, section_data in self.sections_data.items():
            material_name = section_data.get('material')
            if material_name:
                mapping[section_name] = material_name

        return mapping

    def export_material_properties(self, output_path: str = "out/material_properties.json"):
        """
        Export calculated material properties to JSON file

        Args:
            output_path: Path for output JSON file
        """
        output_data = {
            'materials': {name: props.to_dict() for name, props in self.material_properties.items()},
            'section_material_mapping': self.get_section_material_mapping(),
            'calculation_info': {
                'formula_used': 'ACI 318: Ec = 4700 * sqrt(fc) for normal weight concrete',
                'units': {
                    'fc': 'Pa (Pascals)',
                    'Ec': 'Pa (Pascals)',
                    'weight_per_volume': 'N/m³'
                }
            }
        }

        output_path = Path(output_path)
        output_path.parent.mkdir(exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"Material properties exported to {output_path}")

    def get_opensees_material_commands(self) -> Dict[str, str]:
        """
        Generate OpenSees material definition commands

        Returns:
            Dictionary mapping material names to OpenSees commands
        """
        commands = {}

        for i, (name, props) in enumerate(self.material_properties.items(), 1):
            # Use Concrete01 material model for linear elastic behavior
            command = f"ops.uniaxialMaterial('Concrete01', {i}, -{props.fc}, -0.002, 0.0, -0.004)"
            commands[name] = {
                'tag': i,
                'command': command,
                'properties': props.to_dict()
            }

        return commands


def demonstrate_calculator():
    """Demonstrate the material property calculator functionality"""
    print("ETABS Material Property Calculator")
    print("=" * 40)

    try:
        # Create calculator instance
        calculator = MaterialPropertyCalculator()

        print(f"\nCalculated properties for {len(calculator.get_all_materials())} materials:")
        print("-" * 50)

        # Show all materials with their properties
        for material_name, props in calculator.get_all_materials().items():
            print(f"\n{material_name}:")
            print(f"  fc = {props.fc/1e6:.1f} MPa")
            print(f"  Ec = {props.Ec/1e6:.0f} MPa")
            print(f"  γ = {props.weight_per_volume:.0f} N/m³")

        print(f"\nSection-Material Mapping:")
        print("-" * 25)
        mapping = calculator.get_section_material_mapping()
        for section, material in list(mapping.items())[:5]:  # Show first 5
            print(f"  {section} → {material}")
        print(f"  ... and {len(mapping)-5} more sections")

        # Export properties
        calculator.export_material_properties()

        print(f"\n✅ Material property calculation completed successfully!")
        print("Properties exported to out/material_properties.json")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    demonstrate_calculator()