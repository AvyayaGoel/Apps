import os
import sys

if sys.platform == "win32":
    APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", ""), "PasswordManager")
else:
    APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".local", "PasswordManager")

DATA_FILE = os.path.join(APP_DATA_DIR, "passwords.json")
KEY_FILE = os.path.join(APP_DATA_DIR, "key.key")
CONFIG_FILE = os.path.join(APP_DATA_DIR, "settings.json")

# Password validation constants
PASSWORD_CONSTANTS = {
    'min_length': 8,
    'max_length': 128,
    'min_uppercase': 1,
    'min_lowercase': 1,
    'min_digits': 1,
    'min_special': 1
}

MASTER_PASSWORD_CONSTANTS = {
    'min_length': 12,
    'max_length': 128,
    'min_uppercase': 2,
    'min_lowercase': 2,
    'min_digits': 2,
    'min_special': 2
}

# Weak password lists
WEAK_PASSWORDS = [
    'password', '12345678', 'qwerty123', 'admin123', 'password123',
    'letmein', 'welcome', 'monkey', 'dragon', 'football',
    'iloveyou', '123456789', 'abc123', 'password1'
]

# noinspection SpellCheckingInspection
WEAK_MASTER_PASSWORDS = [
    'masterpassword', 'adminpassword', 'rootpassword', 'password1234',
    'master123', 'admin1234', 'root123', 'superpassword',
    'mypassword123', 'passwordmaster', 'securepassword', 'strongpassword'
]

# Common words to avoid in master passwords
COMMON_WORDS = ['password', 'master', 'admin', 'user', 'login', 'secure']

# UI Constants
ICON_NAME = "icon.png"
MISSING_INF = "Missing Information"
INCORRECT_M_P = "Current master password is incorrect!"
CLOSE_BTN_STYLE = "background-color: #f44336; color: white; padding: 8px;"
SAVE_BTN_STYLE = "background-color: #4CAF50; color: white; padding: 8px;"
CHANGE_MASTER_PWD = "Change Master Password"
SETUP_MASTER_PWD = "Setup Master Password"
PASSWORD_EMPTY = "Password is empty"
