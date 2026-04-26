"""
Comprehensive Unit Conversion System.
Supports Length, Area, Volume, Mass, Temperature, Speed, Time, Pressure,
Energy, Power, Data Storage, and Angle conversions.
"""

from typing import Dict, Callable, Optional, Tuple, List, cast
from dataclasses import dataclass
from enum import Enum, auto


class ConversionCategory(Enum):
    """Categories of unit conversions."""
    LENGTH = auto()
    AREA = auto()
    VOLUME = auto()
    MASS = auto()
    TEMPERATURE = auto()
    SPEED = auto()
    TIME = auto()
    PRESSURE = auto()
    ENERGY = auto()
    POWER = auto()
    DATA = auto()
    ANGLE = auto()


@dataclass
class Unit:
    """Represents a unit with its conversion factor and display information."""
    name: str
    symbol: str
    to_base: float  # Conversion factor to base unit
    from_base: Optional[Callable[[float], float]] = None  # Special conversion from base (for temp)
    to_base_func: Optional[Callable[[float], float]] = None  # Special conversion to base (for temp)


class ConversionManager:
    """Manages all unit conversions."""

    def __init__(self):
        self._conversions: Dict[ConversionCategory, Dict[str, Unit]] = {}
        self._setup_all_conversions()

    def _setup_all_conversions(self) -> None:
        """Initialize all conversion categories."""
        self._setup_length()
        self._setup_area()
        self._setup_volume()
        self._setup_mass()
        self._setup_temperature()
        self._setup_speed()
        self._setup_time()
        self._setup_pressure()
        self._setup_energy()
        self._setup_power()
        self._setup_data()
        self._setup_angle()

    def _setup_length(self) -> None:
        """Length conversions (base: meter)."""
        meters = {
            'nm': Unit('Nanometer', 'nm', 1e-9),
            'um': Unit('Micrometer', 'μm', 1e-6),
            'mm': Unit('Millimeter', 'mm', 0.001),
            'cm': Unit('Centimeter', 'cm', 0.01),
            'm': Unit('Meter', 'm', 1.0),
            'km': Unit('Kilometer', 'km', 1000.0),
            'in': Unit('Inch', 'in', 0.0254),
            'ft': Unit('Foot', 'ft', 0.3048),
            'yd': Unit('Yard', 'yd', 0.9144),
            'mi': Unit('Mile', 'mi', 1609.344),
            'nmi': Unit('Nautical Mile', 'nmi', 1852.0),
            'ly': Unit('Light Year', 'ly', 9.461e15),
        }
        self._conversions[ConversionCategory.LENGTH] = meters

    def _setup_area(self) -> None:
        """Area conversions (base: square meter)."""
        sq_meters = {
            'mm2': Unit('Square Millimeter', 'mm²', 1e-6),
            'cm2': Unit('Square Centimeter', 'cm²', 1e-4),
            'm2': Unit('Square Meter', 'm²', 1.0),
            'ha': Unit('Hectare', 'ha', 10000.0),
            'km2': Unit('Square Kilometer', 'km²', 1e6),
            'in2': Unit('Square Inch', 'in²', 0.00064516),
            'ft2': Unit('Square Foot', 'ft²', 0.092903),
            'ac': Unit('Acre', 'ac', 4046.86),
            'mi2': Unit('Square Mile', 'mi²', 2.59e6),
        }
        self._conversions[ConversionCategory.AREA] = sq_meters

    def _setup_volume(self) -> None:
        """Volume conversions (base: liter)."""
        liters = {
            'ml': Unit('Milliliter', 'ml', 0.001),
            'cl': Unit('Centiliter', 'cl', 0.01),
            'dl': Unit('Deciliter', 'dl', 0.1),
            'l': Unit('Liter', 'L', 1.0),
            'm3': Unit('Cubic Meter', 'm³', 1000.0),
            'tsp': Unit('Teaspoon', 'tsp', 0.00492892),
            'tbsp': Unit('Tablespoon', 'tbsp', 0.0147868),
            'fl_oz': Unit('Fluid Ounce', 'fl oz', 0.0295735),
            'cup': Unit('Cup', 'cup', 0.24),
            'pt': Unit('Pint', 'pt', 0.473176),
            'qt': Unit('Quart', 'qt', 0.946353),
            'gal': Unit('Gallon', 'gal', 3.78541),
        }
        self._conversions[ConversionCategory.VOLUME] = liters

    def _setup_mass(self) -> None:
        """Mass conversions (base: kilogram)."""
        kg = {
            'mg': Unit('Milligram', 'mg', 1e-6),
            'g': Unit('Gram', 'g', 0.001),
            'kg': Unit('Kilogram', 'kg', 1.0),
            'oz': Unit('Ounce', 'oz', 0.0283495),
            'lb': Unit('Pound', 'lb', 0.453592),
            'st': Unit('Stone', 'st', 6.35029),
            't': Unit('Metric Ton', 't', 1000.0),
        }
        self._conversions[ConversionCategory.MASS] = kg

    def _setup_temperature(self) -> None:
        """Temperature conversions (special handling needed)."""
        def c_to_f(c: float) -> float:
            return c * 9/5 + 32

        def f_to_c(f: float) -> float:
            return (f - 32) * 5/9

        def c_to_k(c: float) -> float:
            return c + 273.15

        def k_to_c(k: float) -> float:
            return k - 273.15

        temp = {
            'c': Unit('Celsius', '°C', 1.0, from_base=lambda x: x, to_base_func=lambda x: x),
            'f': Unit('Fahrenheit', '°F', 1.0, from_base=c_to_f, to_base_func=f_to_c),
            'k': Unit('Kelvin', 'K', 1.0, from_base=c_to_k, to_base_func=k_to_c),
            'r': Unit('Rankine', '°R', 1.0, from_base=lambda c: (c + 273.15) * 9/5, to_base_func=lambda r: r * 5/9 - 273.15),
        }
        self._conversions[ConversionCategory.TEMPERATURE] = temp

    def _setup_speed(self) -> None:
        """Speed conversions (base: m/s)."""
        mps = {
            'mps': Unit('Meters per Second', 'm/s', 1.0),
            'kph': Unit('Kilometers per Hour', 'km/h', 0.277778),
            'mph': Unit('Miles per Hour', 'mph', 0.44704),
            'knot': Unit('Knot', 'kn', 0.514444),
            'fps': Unit('Feet per Second', 'ft/s', 0.3048),
            'mach': Unit('Mach', 'Ma', 343.0),
        }
        self._conversions[ConversionCategory.SPEED] = mps

    def _setup_time(self) -> None:
        """Time conversions (base: second)."""
        seconds = {
            'ms': Unit('Millisecond', 'ms', 0.001),
            's': Unit('Second', 's', 1.0),
            'min': Unit('Minute', 'min', 60.0),
            'h': Unit('Hour', 'h', 3600.0),
            'd': Unit('Day', 'd', 86400.0),
            'wk': Unit('Week', 'wk', 604800.0),
            'mo': Unit('Month (avg)', 'mo', 2.628e6),
            'y': Unit('Year', 'y', 3.154e7),
        }
        self._conversions[ConversionCategory.TIME] = seconds

    def _setup_pressure(self) -> None:
        """Pressure conversions (base: pascal)."""
        pascal = {
            'pa': Unit('Pascal', 'Pa', 1.0),
            'kpa': Unit('Kilopascal', 'kPa', 1000.0),
            'mpa': Unit('Megapascal', 'MPa', 1e6),
            'bar': Unit('Bar', 'bar', 1e5),
            'mbar': Unit('Millibar', 'mbar', 100.0),
            'psi': Unit('PSI', 'psi', 6894.76),
            'atm': Unit('Atmosphere', 'atm', 101325.0),
            'torr': Unit('Torr', 'Torr', 133.322),
            'mmhg': Unit('mmHg', 'mmHg', 133.322),
        }
        self._conversions[ConversionCategory.PRESSURE] = pascal

    def _setup_energy(self) -> None:
        """Energy conversions (base: joule)."""
        joule = {
            'j': Unit('Joule', 'J', 1.0),
            'kj': Unit('Kilojoule', 'kJ', 1000.0),
            'cal': Unit('Calorie', 'cal', 4.184),
            'kcal': Unit('Kilocalorie', 'kcal', 4184.0),
            'wh': Unit('Watt-hour', 'Wh', 3600.0),
            'kwh': Unit('Kilowatt-hour', 'kWh', 3.6e6),
            'btu': Unit('BTU', 'BTU', 1055.06),
            'ev': Unit('Electronvolt', 'eV', 1.602e-19),
            'ftlb': Unit('Foot-pound', 'ft⋅lb', 1.35582),
        }
        self._conversions[ConversionCategory.ENERGY] = joule

    def _setup_power(self) -> None:
        """Power conversions (base: watt)."""
        watt = {
            'w': Unit('Watt', 'W', 1.0),
            'kw': Unit('Kilowatt', 'kW', 1000.0),
            'mw': Unit('Megawatt', 'MW', 1e6),
            'hp': Unit('Horsepower (mech)', 'hp', 745.7),
            'hp_elec': Unit('Horsepower (elec)', 'hp', 746.0),
            'btu_h': Unit('BTU/hour', 'BTU/h', 0.293071),
            'ftlb_s': Unit('ft⋅lb/s', 'ft⋅lb/s', 1.35582),
        }
        self._conversions[ConversionCategory.POWER] = watt

    def _setup_data(self) -> None:
        """Data storage conversions (base: byte)."""
        byte = {
            'b': Unit('Bit', 'b', 0.125),
            'B': Unit('Byte', 'B', 1.0),
            'KB': Unit('Kilobyte', 'KB', 1024.0),
            'MB': Unit('Megabyte', 'MB', 1048576.0),
            'GB': Unit('Gigabyte', 'GB', 1073741824.0),
            'TB': Unit('Terabyte', 'TB', 1099511627776.0),
            'PB': Unit('Petabyte', 'PB', 1.126e15),
        }
        self._conversions[ConversionCategory.DATA] = byte

    def _setup_angle(self) -> None:
        """Angle conversions (base: degree)."""
        degree = {
            'deg': Unit('Degree', '°', 1.0),
            'rad': Unit('Radian', 'rad', 57.2958),
            'grad': Unit('Gradian', 'grad', 0.9),
            'arcmin': Unit('Arcminute', '′', 1/60),
            'arcsec': Unit('Arcsecond', '″', 1/3600),
        }
        self._conversions[ConversionCategory.ANGLE] = degree

    @staticmethod
    def get_categories() -> List[Tuple[ConversionCategory, str]]:
        """Get list of available categories with display names."""
        names = {
            ConversionCategory.LENGTH: 'Length',
            ConversionCategory.AREA: 'Area',
            ConversionCategory.VOLUME: 'Volume',
            ConversionCategory.MASS: 'Mass',
            ConversionCategory.TEMPERATURE: 'Temperature',
            ConversionCategory.SPEED: 'Speed',
            ConversionCategory.TIME: 'Time',
            ConversionCategory.PRESSURE: 'Pressure',
            ConversionCategory.ENERGY: 'Energy',
            ConversionCategory.POWER: 'Power',
            ConversionCategory.DATA: 'Data Storage',
            ConversionCategory.ANGLE: 'Angle',
        }
        return [(cat, names[cat]) for cat in ConversionCategory]

    def get_units(self, category: ConversionCategory) -> List[Tuple[str, str, str]]:
        """Get list of units for a category. Returns (key, name, symbol)."""
        if category not in self._conversions:
            return []
        units = self._conversions[category]
        return [(key, unit.name, unit.symbol) for key, unit in units.items()]

    def convert(self, category: ConversionCategory, from_unit: str, to_unit: str,
                value: float) -> float:
        """
        Convert value from one unit to another.

        Args:
            category: The conversion category
            from_unit: Source unit key
            to_unit: Target unit key
            value: Value to convert

        Returns:
            Converted value
        """
        if category not in self._conversions:
            raise ValueError(f"Unknown category: {category}")

        units = self._conversions[category]

        if from_unit not in units:
            raise ValueError(f"Unknown source unit: {from_unit}")
        if to_unit not in units:
            raise ValueError(f"Unknown target unit: {to_unit}")

        from_u = units[from_unit]
        to_u = units[to_unit]

        # Special handling for temperature
        if category == ConversionCategory.TEMPERATURE:
            if from_u.to_base_func:
                base_value = from_u.to_base_func(value)
            else:
                base_value = value

            if to_u.from_base:
                return to_u.from_base(base_value)
            return base_value

        # Standard conversion: to base then to target
        base_value = value * from_u.to_base
        return base_value / to_u.to_base

    @staticmethod
    def format_result(value: float, precision: int = 6) -> str:
        """Format conversion result nicely."""
        if value == 0:
            return "0"

        # Use scientific notation for very large or small numbers
        if abs(value) >= 1e10 or (abs(value) < 1e-6 and value != 0):
            return f"{value:.{precision}e}"

        # Format with appropriate precision, removing trailing zeros
        formatted = f"{value:.{precision}f}".rstrip('0').rstrip('.')
        return formatted if formatted else "0"


# Global instance
_manager: Optional[ConversionManager] = None


def get_manager() -> ConversionManager:
    """Get or create the global conversion manager."""
    global _manager
    if _manager is None:
        _manager = ConversionManager()
    return cast(ConversionManager, _manager)


def convert(category: ConversionCategory, from_unit: str, to_unit: str,
            value: float) -> float:
    """Convenience function for direct conversion."""
    return get_manager().convert(category, from_unit, to_unit, value)
