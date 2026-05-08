FONT = "Segoe UI"

# Colors
COLOR_INACTIVE = "color: #a0a0a0;"

# Tab titles
TITLE_STANDARD_CALC = "Standard Calculator"
TITLE_SCIENTIFIC_CALC = "Scientific Calculator"

OPERATORS = "+-×÷^/*"

LABEL_STYLESHEET = """
            QLabel {
                color: #888888;
                background: transparent;
                padding: 5px 15px;
                min-height: 28px;
            }
        """

REFRESH_BTN_TEXT = "🔄 Refresh"

# Data storage
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
RATES_CACHE_FILE = os.path.join(DATA_DIR, "currency_rates.json")
