"""
Comprehensive Unit Conversion System.
Supports Length, Area, Volume, Mass, Temperature, Speed, Time, Pressure,
Energy, Power, Data Storage, and Angle conversions.
"""

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, getcontext
from enum import Enum, auto
from typing import Dict, Callable, Optional, Tuple, List, cast, Union

import requests

from constants_calculator import RATES_CACHE_FILE


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
    CURRENCY = auto()


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
        self._last_updated_currency: Optional[datetime] = None
        self._is_offline: bool = False
        self._setup_all_conversions()

    def _load_cached_rates(self) -> Optional[Tuple[Dict[str, float], datetime]]:
        """Load cached rates from file. Returns (rates, timestamp) or None."""
        try:
            if os.path.exists(RATES_CACHE_FILE):
                with open(RATES_CACHE_FILE, 'r') as f:
                    data = json.load(f)
                    rates = data.get('rates', {})
                    timestamp_str = data.get('timestamp')
                    if timestamp_str:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        return rates, timestamp
        except Exception as e:
            print(f"Error loading cached rates: {e}")
        return None

    def _save_cached_rates(self, rates: Dict[str, float], timestamp: datetime) -> None:
        """Save rates to cache file."""
        try:
            data = {
                'rates': rates,
                'timestamp': timestamp.isoformat()
            }
            with open(RATES_CACHE_FILE, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving cached rates: {e}")

    def is_offline(self) -> bool:
        """Check if currently using offline/cached rates."""
        return self._is_offline

    def get_last_updated(self) -> Optional[datetime]:
        """Get last update timestamp for currency rates."""
        return self._last_updated_currency

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
        self._setup_currency()

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

    # Currency code to full name mapping
    _CURRENCY_NAMES = {
        "AED": "UAE Dirham", "AFN": "Afghan Afghani", "ALL": "Albanian Lek",
        "AMD": "Armenian Dram", "ANG": "Netherlands Antillian Guilder",
        "AOA": "Angolan Kwanza", "ARS": "Argentine Peso", "AUD": "Australian Dollar",
        "AWG": "Aruban Florin", "AZN": "Azerbaijani Manat",
        "BAM": "Bosnia and Herzegovina Mark", "BBD": "Barbados Dollar",
        "BDT": "Bangladeshi Taka", "BGN": "Bulgarian Lev", "BHD": "Bahraini Dinar",
        "BIF": "Burundian Franc", "BMD": "Bermudian Dollar", "BND": "Brunei Dollar",
        "BOB": "Bolivian Boliviano", "BRL": "Brazilian Real", "BSD": "Bahamian Dollar",
        "BTN": "Bhutanese Ngultrum", "BWP": "Botswana Pula", "BYN": "Belarusian Ruble",
        "BZD": "Belize Dollar", "CAD": "Canadian Dollar", "CDF": "Congolese Franc",
        "CHF": "Swiss Franc", "CLP": "Chilean Peso", "CNY": "Chinese Renminbi",
        "COP": "Colombian Peso", "CRC": "Costa Rican Colon", "CUP": "Cuban Peso",
        "CVE": "Cape Verdean Escudo", "CZK": "Czech Koruna", "DJF": "Djiboutian Franc",
        "DKK": "Danish Krone", "DOP": "Dominican Peso", "DZD": "Algerian Dinar",
        "EGP": "Egyptian Pound", "ERN": "Eritrean Nakfa", "ETB": "Ethiopian Birr",
        "EUR": "Euro", "FJD": "Fiji Dollar", "FKP": "Falkland Islands Pound",
        "FOK": "Faroese Króna", "GBP": "British Pound", "GEL": "Georgian Lari",
        "GGP": "Guernsey Pound", "GHS": "Ghanaian Cedi", "GIP": "Gibraltar Pound",
        "GMD": "Gambian Dalasi", "GNF": "Guinean Franc", "GTQ": "Guatemalan Quetzal",
        "GYD": "Guyanese Dollar", "HKD": "Hong Kong Dollar", "HNL": "Honduran Lempira",
        "HRK": "Croatian Kuna", "HTG": "Haitian Gourde", "HUF": "Hungarian Forint",
        "IDR": "Indonesian Rupiah", "ILS": "Israeli New Shekel", "IMP": "Isle of Man Pound",
        "INR": "Indian Rupee", "IQD": "Iraqi Dinar", "IRR": "Iranian Rial",
        "ISK": "Icelandic Króna", "JEP": "Jersey Pound", "JMD": "Jamaican Dollar",
        "JOD": "Jordanian Dinar", "JPY": "Japanese Yen", "KES": "Kenyan Shilling",
        "KGS": "Kyrgyzstani Som", "KHR": "Cambodian Riel", "KID": "Kiribati Dollar",
        "KMF": "Comorian Franc", "KRW": "South Korean Won", "KWD": "Kuwaiti Dinar",
        "KYD": "Cayman Islands Dollar", "KZT": "Kazakhstani Tenge",
        "LAK": "Lao Kip", "LBP": "Lebanese Pound", "LKR": "Sri Lanka Rupee",
        "LRD": "Liberian Dollar", "LSL": "Lesotho Loti", "LYD": "Libyan Dinar",
        "MAD": "Moroccan Dirham", "MDL": "Moldovan Leu", "MGA": "Malagasy Ariary",
        "MKD": "Macedonian Denar", "MMK": "Myanmar Kyat", "MNT": "Mongolian Tugrik",
        "MOP": "Macanese Pataca", "MRU": "Mauritanian Ouguiya", "MUR": "Mauritian Rupee",
        "MVR": "Maldivian Rufiyaa", "MWK": "Malawian Kwacha", "MXN": "Mexican Peso",
        "MYR": "Malaysian Ringgit", "MZN": "Mozambican Metical", "NAD": "Namibian Dollar",
        "NGN": "Nigerian Naira", "NIO": "Nicaraguan Córdoba", "NOK": "Norwegian Krone",
        "NPR": "Nepalese Rupee", "NZD": "New Zealand Dollar", "OMR": "Omani Rial",
        "PAB": "Panamanian Balboa", "PEN": "Peruvian Sol", "PGK": "Papua New Guinean Kina",
        "PHP": "Philippine Peso", "PKR": "Pakistani Rupee", "PLN": "Polish Zloty",
        "PYG": "Paraguayan Guaraní", "QAR": "Qatari Riyal", "RON": "Romanian Leu",
        "RSD": "Serbian Dinar", "RUB": "Russian Ruble", "RWF": "Rwandan Franc",
        "SAR": "Saudi Riyal", "SBD": "Solomon Islands Dollar", "SCR": "Seychellois Rupee",
        "SDG": "Sudanese Pound", "SEK": "Swedish Krona", "SGD": "Singapore Dollar",
        "SHP": "Saint Helena Pound", "SLE": "Sierra Leonean Leone", "SLL": "Sierra Leonean Leone",
        "SOS": "Somali Shilling", "SRD": "Surinamese Dollar", "SSP": "South Sudanese Pound",
        "STN": "São Tomé and Príncipe Dobra", "SYP": "Syrian Pound", "SZL": "Eswatini Lilangeni",
        "THB": "Thai Baht", "TJS": "Tajikistani Somoni", "TMT": "Turkmenistani Manat",
        "TND": "Tunisian Dinar", "TOP": "Tongan Paʻanga", "TRY": "Turkish Lira",
        "TTD": "Trinidad and Tobago Dollar", "TVD": "Tuvaluan Dollar", "TWD": "New Taiwan Dollar",
        "TZS": "Tanzanian Shilling", "UAH": "Ukrainian Hryvnia", "UGX": "Ugandan Shilling",
        "USD": "United States Dollar", "UYU": "Uruguayan Peso", "UZS": "Uzbekistani Som",
        "VES": "Venezuelan Bolívar", "VND": "Vietnamese Đồng", "VUV": "Vanuatu Vatu",
        "WST": "Samoan Tala", "XAF": "Central African CFA Franc",
        "XCD": "East Caribbean Dollar", "XDR": "Special Drawing Rights",
        "XOF": "West African CFA Franc", "XPF": "CFP Franc", "YER": "Yemeni Rial",
        "ZAR": "South African Rand", "ZMW": "Zambian Kwacha", "ZWL": "Zimbabwean Dollar",
    }

    # Currency symbols for display
    _CURRENCY_SYMBOLS = {
        # Major currencies
        "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥",
        "AUD": "A$", "CAD": "C$", "CHF": "Fr", "HKD": "HK$", "NZD": "NZ$",
        "SEK": "kr", "NOK": "kr", "DKK": "kr", "SGD": "S$", "MXN": "Mex$",
        # Asian currencies
        "INR": "₹", "IDR": "Rp", "PHP": "₱", "MYR": "RM",
        "VND": "₫", "THB": "฿", "PKR": "₨", "BDT": "৳",
        "LKR": "₨", "MMK": "K", "KHR": "៛", "LAK": "₭",
        "KZT": "₸", "UZS": "so'm", "KGS": "с",
        "AFN": "؋", "BND": "B$", "MOP": "MOP$", "FJD": "FJ$", "PGK": "K",
        # Middle Eastern currencies
        "AED": "د.إ", "SAR": "﷼", "QAR": "﷼", "KWD": "د.ك", "BHD": "د.ب",
        "OMR": "ر.ع.", "JOD": "د.ا", "ILS": "₪", "LBP": "ل.ل",
        "YER": "﷼", "IRR": "﷼", "IQD": "ع.د", "SYP": "£S",  # European currencies (non-EUR)
        "RUB": "₽", "PLN": "zł", "TRY": "₺", "CZK": "Kč", "HUF": "Ft",
        "RON": "lei", "BGN": "лв", "HRK": "kn", "UAH": "₴", "GEL": "₾",
        "AMD": "֏", "AZN": "₼", "BYN": "Br", "MDL": "L", "MKD": "ден",
        "RSD": "дин", "ALL": "L", "BAM": "KM", "ISK": "kr", "GIP": "£",
        "FOK": "kr", "GGP": "£", "JEP": "£", "IMP": "£",
        # African currencies
        "ZAR": "R", "NGN": "₦", "KES": "KSh", "GHS": "₵", "MAD": "DH", "TND": "DT", "DZD": "DA", "XOF": "CFA",
        "XAF": "FCFA",
        "ETB": "Br", "TZS": "Sh", "UGX": "Sh", "RWF": "FRw",
        "ZMW": "K", "BWP": "P", "NAD": "N$", "SZL": "L", "LSL": "L",
        "MZN": "MT", "AOA": "Kz", "CVE": "Esc", "SCR": "₨", "MUR": "₨",
        "MGA": "Ar", "MWK": "MK", "ZWL": "Z$", "BIF": "FBu", "CDF": "FC",
        "ERN": "Nfk", "GMD": "D", "GNF": "FG", "SLL": "Le",
        "SOS": "Sh", "SSP": "£", "STD": "Db", "SDG": "£",  # Latin American currencies
        "BRL": "R$", "ARS": "$", "CLP": "$", "COP": "$", "PEN": "S/",
        "UYU": "$U", "PYG": "₲", "BOB": "Bs", "VED": "Bs.", "VEF": "Bs.F",
        "GTQ": "Q", "HNL": "L", "NIO": "C$", "CRC": "₡", "PAB": "B/.",
        "DOP": "RD$", "BBD": "Bds$", "BZD": "BZ$", "KYD": "CI$",
        "TTD": "TT$", "JMD": "J$", "HTG": "G", "SVC": "₡", "ANG": "NAf.",
        "SRD": "$", "GYD": "G$", "BMD": "BD$", "BSD": "B$",
        # Other currencies
    }

    def _setup_currency(self) -> None:
        """Currency conversions (base: USD). Rates fetched from API or loaded from cache."""
        # Try to load from cache first
        cached = self._load_cached_rates()
        if cached:
            rates, timestamp = cached
            self._last_updated_currency = timestamp
            self._is_offline = True  # Start in offline mode until we verify online
        else:
            # Default rates if no cache
            rates = self._default_currency_rates()
            self._last_updated_currency = None
            self._is_offline = True

        # Initialize units from the loaded/default rates
        self._initialize_currency_units(rates)

    def _default_currency_rates(self) -> Dict[str, float]:
        """Default currency rates when offline."""
        return {
            "USD": 1.0, "EUR": 0.92, "GBP": 0.79, "JPY": 150.0,
            "CAD": 1.35, "AUD": 1.52, "CHF": 0.88, "CNY": 7.19,
            "INR": 83.0, "SGD": 1.34, "NZD": 1.61, "MXN": 17.0,
            "BRL": 4.95, "ZAR": 19.0, "KRW": 1330.0, "RUB": 92.0,
        }

    def _initialize_currency_units(self, rates: Dict[str, float]) -> None:
        """Initialize currency units from rates dictionary."""
        self._conversions[ConversionCategory.CURRENCY] = {}
        for currency, rate in rates.items():
            # Get full name from dictionary, fallback to code if not found
            name = self._CURRENCY_NAMES.get(currency, currency)
            # Store as Unit(name=full_name, symbol=currency_code, to_base=rate)
            self._conversions[ConversionCategory.CURRENCY][currency] = Unit(
                name, currency, rate
            )

    @staticmethod
    def _fetch_exchange_rates() -> Dict[str, float]:
        """Fetch exchange rates from API. Returns cached rates if fetch fails."""
        # Fallback rates if API fails
        fallback = {
            "USD": 1.0, "EUR": 0.92, "GBP": 0.79, "JPY": 150.0,
            "CAD": 1.35, "AUD": 1.52, "CHF": 0.88, "CNY": 7.19,
            "INR": 83.0, "SGD": 1.34, "NZD": 1.61, "MXN": 17.0,
            "BRL": 4.95, "ZAR": 19.0, "KRW": 1330.0, "RUB": 92.0,
        }

        try:
            url = "https://api.exchangerate-api.com/v4/latest/USD"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            if "rates" in data:
                # Return all currencies from the API
                return dict(data["rates"])
        except Exception:
            pass

        return fallback

    def refresh_currency_rates(self) -> bool:
        """Refresh currency exchange rates. Returns True if successful."""
        try:
            url = "https://api.exchangerate-api.com/v4/latest/USD"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            if "rates" in data:
                # Update all currencies from the API
                rates = data["rates"]
                currency_units = self._conversions.get(ConversionCategory.CURRENCY, {})
                for currency, rate in rates.items():
                    if currency in currency_units:
                        currency_units[currency].to_base = rate
                    else:
                        # Add new currency if not exists (lookup full name, fallback to code)
                        name = self._CURRENCY_NAMES.get(currency, currency)
                        currency_units[currency] = Unit(name, currency, rate)
                # Save to cache and mark as online
                self._last_updated_currency = datetime.now()
                self._is_offline = False
                self._save_cached_rates(rates, self._last_updated_currency)
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def get_currency_last_updated() -> str:
        """Get last updated time for currency rates."""
        return datetime.now().strftime("%H:%M")

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
            ConversionCategory.CURRENCY: 'Currency',
        }
        return [(cat, names[cat]) for cat in ConversionCategory]

    def get_units(self, category: ConversionCategory) -> List[Tuple[str, str, str]]:
        """Get list of units for a category. Returns (key, name, symbol)."""
        if category not in self._conversions:
            return []
        units = self._conversions[category]
        return [(key, unit.name, unit.symbol) for key, unit in units.items()]

    def convert(self, category: ConversionCategory, from_unit: str, to_unit: str,
                value: Union[float, Decimal]) -> Union[float, Decimal]:
        """
        Convert value from one unit to another.

        Args:
            category: The conversion category
            from_unit: Source unit key
            to_unit: Target unit key
            value: Value to convert

        Returns:
            Converted value (float or Decimal for large numbers)
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
            # Convert Decimal to float for temperature (unlikely to overflow)
            temp_value = float(value) if isinstance(value, Decimal) else value
            if from_u.to_base_func:
                base_value = from_u.to_base_func(temp_value)
            else:
                base_value = temp_value

            if to_u.from_base:
                result = to_u.from_base(base_value)
            else:
                result = base_value
            # Check if result overflowed
            if isinstance(result, float) and math.isinf(result):
                return self._convert_with_decimal(value, from_u, to_u)
            return result

        # Special handling for currency (rates are from base, not to base)
        if category == ConversionCategory.CURRENCY:
            # For currency: value * to_rate / from_rate
            # (e.g., USD->INR: value * 83.5 / 1.0 = 83.5 INR)
            if isinstance(value, Decimal):
                decimal_to = Decimal(str(to_u.to_base))
                decimal_from = Decimal(str(from_u.to_base))
                return value * decimal_to / decimal_from
            result = value * to_u.to_base / from_u.to_base
            if math.isinf(result):
                decimal_to = Decimal(str(to_u.to_base))
                decimal_from = Decimal(str(from_u.to_base))
                return Decimal(str(value)) * decimal_to / decimal_from
            return result

        # Standard conversion: to base then to target
        # If value is Decimal, use Decimal arithmetic to avoid type errors
        if isinstance(value, Decimal):
            decimal_from = Decimal(str(from_u.to_base))
            decimal_to = Decimal(str(to_u.to_base))
            return value * decimal_from / decimal_to

        # Float arithmetic
        result = value * from_u.to_base / to_u.to_base
        # Check for overflow
        if math.isinf(result):
            # Use high precision Decimal
            return self._convert_with_decimal(value, from_u, to_u)
        return result

    @staticmethod
    def _convert_with_decimal(value: Union[float, Decimal], from_u, to_u) -> Decimal:
        """Convert using high-precision Decimal arithmetic."""
        getcontext().prec = 100
        # Handle both float and Decimal input
        if isinstance(value, Decimal):
            decimal_value = value
        else:
            decimal_value = Decimal(str(value))
        decimal_from = Decimal(str(from_u.to_base))
        decimal_to = Decimal(str(to_u.to_base))
        return decimal_value * decimal_from / decimal_to

    @staticmethod
    def _add_thousands_separator(num_str: str) -> str:
        """Add thousands separators to a number string."""
        # Handle negative numbers
        if num_str.startswith('-'):
            prefix = '-'
            num_str = num_str[1:]
        else:
            prefix = ''

        # Split into integer and decimal parts
        if '.' in num_str:
            integer_part, decimal_part = num_str.split('.')
        else:
            integer_part, decimal_part = num_str, ''

        # Add commas to integer part
        integer_part = f"{int(integer_part):,}"

        # Recombine
        if decimal_part:
            return f"{prefix}{integer_part}.{decimal_part}"
        return f"{prefix}{integer_part}"

    @staticmethod
    def format_result(value: Union[float, Decimal], precision: int = 6) -> str:
        """Format conversion result nicely with thousands separators."""

        # Handle Decimal values
        if isinstance(value, Decimal):
            abs_val = abs(value)
            if abs_val >= Decimal('1e10') or (abs_val < Decimal('1e-6') and abs_val != 0):
                return f"{value:.{precision}e}"
            result_str = str(value)
            if '.' in result_str:
                result_str = result_str.rstrip('0').rstrip('.')
            return ConversionManager._add_thousands_separator(result_str) if result_str else "0"

        # Check for infinity in float
        if isinstance(value, float) and math.isinf(value):
            return "∞ (overflow)"

        if value == 0:
            return "0"

        # Use scientific notation for very large or small numbers
        if abs(value) >= 1e10 or (abs(value) < 1e-6 and value != 0):
            return f"{value:.{precision}e}"

        # Format with appropriate precision, removing trailing zeros
        formatted = f"{value:.{precision}f}".rstrip('0').rstrip('.')
        return ConversionManager._add_thousands_separator(formatted) if formatted else "0"


# Global instance
_manager: Optional[ConversionManager] = None


def get_manager() -> ConversionManager:
    """Get or create the global conversion manager."""
    global _manager
    if _manager is None:
        _manager = ConversionManager()
    return cast(ConversionManager, _manager)


def convert(category: ConversionCategory, from_unit: str, to_unit: str,
            value: Union[float, Decimal]) -> Union[float, Decimal]:
    """Convenience function for direct conversion."""
    return get_manager().convert(category, from_unit, to_unit, value)
