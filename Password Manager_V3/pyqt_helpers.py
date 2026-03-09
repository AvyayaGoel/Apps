import hashlib
import re

from PyQt6.QtWidgets import QLineEdit, QPushButton, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, \
    QWidget

from pyqt_constants import PASSWORD_CONSTANTS, MASTER_PASSWORD_CONSTANTS, WEAK_PASSWORDS, WEAK_MASTER_PASSWORDS, \
    COMMON_WORDS, SAVE_BTN_STYLE, CLOSE_BTN_STYLE, PASSWORD_EMPTY


def hash_password(password):
    """Hash password for verification"""
    return hashlib.sha256(password.encode()).hexdigest()


class PasswordValidator:
    """Enhanced password validator with real-time criteria checking"""

    def __init__(self, is_master_password=False, requirements=None):
        self.is_master_password = is_master_password
        self.constants = MASTER_PASSWORD_CONSTANTS if is_master_password else PASSWORD_CONSTANTS
        self.weak_passwords = WEAK_MASTER_PASSWORDS if is_master_password else WEAK_PASSWORDS

        # Configurable requirements override
        self.requirements = requirements if requirements is not None else {}

    def check_criteria(self, password):
        """Check individual criteria and return results"""
        criteria = {}

        # If password is empty, all criteria should fail
        if not password:
            # Length check (always enabled)
            min_length = self.requirements.get('length', self.constants['min_length'])
            criteria['length'] = {
                'passed': False,
                'requirement': f"At least {min_length} characters",
                'current': "Current: 0 characters"
            }

            # Uppercase check
            min_upper = self.requirements.get('uppercase', self.constants['min_uppercase'])
            criteria['uppercase'] = {
                'passed': False,
                'requirement': f"At least {min_upper} uppercase letter(s)",
                'current': "Current: 0 uppercase letter(s)"
            }

            # Lowercase check
            min_lower = self.requirements.get('lowercase', self.constants['min_lowercase'])
            criteria['lowercase'] = {
                'passed': False,
                'requirement': f"At least {min_lower} lowercase letter(s)",
                'current': "Current: 0 lowercase letter(s)"
            }

            # Digits check
            min_digits = self.requirements.get('digits', self.constants['min_digits'])
            criteria['digits'] = {
                'passed': False,
                'requirement': f"At least {min_digits} digit(s)",
                'current': "Current: 0 digit(s)"
            }

            # Special characters check
            min_special = self.requirements.get('special', self.constants['min_special'])
            criteria['special'] = {
                'passed': False,
                'requirement': f"At least {min_special} special character(s)",
                'current': "Current: 0 special character(s)"
            }

            # No sequential characters
            criteria['no_sequential'] = {
                'passed': False,
                'requirement': "No 3+ identical characters in a row",
                'current': PASSWORD_EMPTY
            }

            # No common patterns
            criteria['no_patterns'] = {
                'passed': False,
                'requirement': "No common sequential patterns (123, abc, qwe)",
                'current': PASSWORD_EMPTY
            }

            # Not in weak passwords list
            criteria['not_weak'] = {
                'passed': False,
                'requirement': "Not a common weak password",
                'current': PASSWORD_EMPTY
            }

            criteria['no_common_words'] = {
                'passed': False,
                'requirement': "No common words (password, master, admin, etc.)",
                'current': PASSWORD_EMPTY
            }

            return criteria

        # Length check (always enabled)
        min_length = self.requirements.get('length', self.constants['min_length'])
        if min_length > 0:
            criteria['length'] = {
                'passed': len(password) >= min_length,
                'requirement': f"At least {min_length} characters",
                'current': f"Current: {len(password)} characters"
            }

        # Uppercase check
        min_upper = self.requirements.get('uppercase', self.constants['min_uppercase'])
        if min_upper > 0:
            uppercase_count = len(re.findall(r'[A-Z]', password))
            criteria['uppercase'] = {
                'passed': uppercase_count >= min_upper,
                'requirement': f"At least {min_upper} uppercase letter(s)",
                'current': f"Current: {uppercase_count} uppercase letter(s)"
            }

        # Lowercase check
        min_lower = self.requirements.get('lowercase', self.constants['min_lowercase'])
        if min_lower > 0:
            lowercase_count = len(re.findall(r'[a-z]', password))
            criteria['lowercase'] = {
                'passed': lowercase_count >= min_lower,
                'requirement': f"At least {min_lower} lowercase letter(s)",
                'current': f"Current: {lowercase_count} lowercase letter(s)"
            }

        # Digit check
        min_digits = self.requirements.get('digits', self.constants['min_digits'])
        if min_digits > 0:
            digit_count = len(re.findall(r'\d', password))
            criteria['digits'] = {
                'passed': digit_count >= min_digits,
                'requirement': f"At least {min_digits} number(s)",
                'current': f"Current: {digit_count} number(s)"
            }

        # Special character check
        min_special = self.requirements.get('special', self.constants['min_special'])
        if min_special > 0:
            special_count = len(re.findall(r'[!@#$%^&*(),.?":{}|<>]', password))
            criteria['special'] = {
                'passed': special_count >= min_special,
                'requirement': f"At least {min_special} special character(s)",
                'current': f"Current: {special_count} special character(s)"
            }

        # No sequential characters
        criteria['no_sequential'] = {
            'passed': not re.search(r'(.)\1{2,}', password),
            'requirement': "No 3+ identical characters in a row",
            'current': "OK" if not re.search(r'(.)\1{2,}', password) else "Found sequential characters"
        }

        # No common patterns
        criteria['no_patterns'] = {
            'passed': not re.search(r'(123|abc|qwe)', password.lower()),
            'requirement': "No common sequential patterns (123, abc, qwe)",
            'current': "OK" if not re.search(r'(123|abc|qwe)', password.lower()) else "Found common patterns"
        }

        # Not in weak passwords list
        criteria['not_weak'] = {
            'passed': password.lower() not in self.weak_passwords,
            'requirement': "Not a common weak password",
            'current': "OK" if password.lower() not in self.weak_passwords else "Common weak password"
        }

        # For master passwords, check for common words
        if self.is_master_password:
            criteria['no_common_words'] = {
                'passed': not any(word in password.lower() for word in COMMON_WORDS),
                'requirement': "No common words (password, master, admin, etc.)",
                'current': "OK" if not any(
                    word in password.lower() for word in COMMON_WORDS) else "Contains common words"
            }

        return criteria

    def validate(self, password):
        """Validate password and return overall result"""
        if not password:
            return False, "Password cannot be empty"

        if len(password) > self.constants['max_length']:
            return False, f"Password cannot be more than {self.constants['max_length']} characters long"

        criteria = self.check_criteria(password)
        failed_criteria = [key for key, check in criteria.items() if not check['passed']]

        # Check for disabled requirements and add warnings
        disabled_requirements = []
        if self.requirements.get('uppercase', 1) == 0:
            disabled_requirements.append("Uppercase letters are not required")
        if self.requirements.get('lowercase', 1) == 0:
            disabled_requirements.append("Lowercase letters are not required")
        if self.requirements.get('digits', 1) == 0:
            disabled_requirements.append("Numbers are not required")
        if self.requirements.get('special', 1) == 0:
            disabled_requirements.append("Special characters are not required")

        if failed_criteria:
            if self.is_master_password and 'no_common_words' in failed_criteria:
                found_words = [word for word in COMMON_WORDS if word in password.lower()]
                return False, f"Master password should not contain common words like: {', '.join(found_words)}"

            error_msg = "Password does not meet the following requirements:\n"
            error_msg += "\n".join(f"- {criteria[key]['requirement']}" for key in failed_criteria)

            if disabled_requirements:
                error_msg += f"\n\nNote: {', '.join(disabled_requirements)}"

            return False, error_msg

        return True, "Password meets all security requirements"


def get_password_strength_indicator(password):
    """Get password strength as text and color"""
    if not password:
        return "Enter a password", "#666666"

    score = 0

    # Length scoring
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if len(password) >= 16:
        score += 1

    # Character variety scoring
    if re.search(r'[a-z]', password):
        score += 1
    if re.search(r'[A-Z]', password):
        score += 1
    if re.search(r'\d', password):
        score += 1
    if re.search(r'[!@#$%^&*(),.?\":{}|<>]', password):
        score += 1

    # Complexity scoring
    if len(set(password)) >= len(password) * 0.7:  # Good character variety
        score += 1

    if score <= 2:
        return "Very Weak", "#ff4444"
    elif score <= 4:
        return "Weak", "#ff8800"
    elif score <= 6:
        return "Medium", "#ffaa00"
    elif score <= 8:
        return "Strong", "#44ff44"
    else:
        return "Very Strong", "#00aa00"


def show_info_dialog(parent, title, message):
    """Show information dialog"""
    QMessageBox.information(parent, title, message)


def show_error_dialog(parent, title, message):
    """Show error dialog"""
    QMessageBox.warning(parent, title, message)


def show_warning_dialog(parent, title, message):
    """Show warning dialog"""
    QMessageBox.warning(parent, title, message)


def create_styled_button(text, callback, color="#2196F3", width=120):
    """Create a styled button"""
    button = QPushButton(text)
    button.clicked.connect(callback)
    button.setStyleSheet(f"""
        QPushButton {{
            background-color: {color};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            min-width: {width}px;
        }}
        QPushButton:hover {{
            background-color: {color}DD;
        }}
    """)
    return button


def create_styled_input(placeholder=""):
    """Create a styled input field"""
    input_field = QLineEdit()
    input_field.setPlaceholderText(placeholder)
    input_field.setStyleSheet("""
        QLineEdit {
            border: 2px solid #ddd;
            border-radius: 4px;
            padding: 8px;
            font-size: 12px;
        }
        QLineEdit:focus {
            border-color: #2196F3;
        }
    """)
    return input_field


def apply_global_theme(theme_type, widget):
    """Apply simple theme to widget"""
    if not hasattr(widget, 'setStyleSheet'):
        return

    try:
        if theme_type == "dark":
            widget.setStyleSheet("""
                QMainWindow, QDialog, QWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QLabel {
                    color: #ffffff;
                    background-color: transparent;
                }
                QLineEdit {
                    background-color: #3c3c3c;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton {
                    background-color: #3c3c3c;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 8px;
                    border-radius: 3px;
                }
                QCheckBox {
                    color: #ffffff;
                }
                QGroupBox {
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    color: #ffffff;
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QSpinBox {
                    background-color: #3c3c3c;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 5px;
                    border-radius: 3px;
                }
                QToolBar {
                    background-color: #3c3c3c;
                    border: 1px solid #555555;
                }
                QStatusBar {
                    background-color: #3c3c3c;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QScrollArea {
                    background-color: #2b2b2b;
                    border: 1px solid #555555;
                }
            """)
        else:
            widget.setStyleSheet("""
                QMainWindow, QDialog, QWidget {
                    background-color: #ffffff;
                    color: #000000;
                }
                QLabel {
                    color: #000000;
                    background-color: transparent;
                }
                QLineEdit {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #cccccc;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton {
                    background-color: #f0f0f0;
                    color: #000000;
                    border: 1px solid #cccccc;
                    padding: 8px;
                    border-radius: 3px;
                }
                QCheckBox {
                    color: #000000;
                }
                QGroupBox {
                    color: #000000;
                    border: 1px solid #cccccc;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    color: #000000;
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QSpinBox {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #cccccc;
                    padding: 5px;
                    border-radius: 3px;
                }
                QToolBar {
                    background-color: #f8f8f8;
                    border: 1px solid #cccccc;
                }
                QStatusBar {
                    background-color: #f8f8f8;
                    color: #000000;
                    border: 1px solid #cccccc;
                }
                QScrollArea {
                    background-color: #ffffff;
                    border: 1px solid #cccccc;
                }
            """)
    except Exception as e:
        print(f"Theme error: {e}")


def verify_current_master_password(parent, manager):
    """Verify current master password dialog - reusable across windows"""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Verify Current Master Password")
    dialog.setFixedSize(300, 150)

    layout = QVBoxLayout()

    pwd_label = QLabel("Enter Current Master Password:")
    pwd_input = QLineEdit()
    pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
    layout.addWidget(pwd_label)
    layout.addWidget(pwd_input)

    def check_password():
        if manager.master_pwd_hash and hash_password(pwd_input.text()) == manager.master_pwd_hash:
            dialog.accept()
            return True
        else:
            show_error_dialog(parent, "Error", "Current master password is incorrect!")
            return False

    button_layout = QHBoxLayout()
    verify_btn = QPushButton("Verify")
    verify_btn.clicked.connect(check_password)
    verify_btn.setStyleSheet(SAVE_BTN_STYLE)
    button_layout.addWidget(verify_btn)

    layout.addLayout(button_layout)
    dialog.setLayout(layout)
    return dialog.exec() == QDialog.DialogCode.Accepted


def setup_new_master_password(parent, manager):
    """Setup new master password dialog - reusable across windows"""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Setup New Master Password")
    dialog.setFixedSize(400, 300)  # Smaller window size

    layout = QVBoxLayout()

    # Initialize validator for this dialog (backend only)
    master_password_validator = PasswordValidator(is_master_password=True)

    # Password input with show/hide checkbox
    pwd_layout = QHBoxLayout()
    pwd_label = QLabel("New Master Password:")
    pwd_input = QLineEdit()
    pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
    show_pwd_cb = QCheckBox("Show")
    show_pwd_cb.toggled.connect(
        lambda checked: pwd_input.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password))

    pwd_layout.addWidget(pwd_label)
    pwd_layout.addWidget(pwd_input)
    pwd_layout.addWidget(show_pwd_cb)
    layout.addLayout(pwd_layout)

    # Confirm password input with show/hide checkbox
    confirm_layout = QHBoxLayout()
    confirm_label = QLabel("Confirm Master Password:")
    confirm_input = QLineEdit()
    confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
    show_confirm_cb = QCheckBox("Show")
    show_confirm_cb.toggled.connect(lambda checked: confirm_input.setEchoMode(
        QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password))

    confirm_layout.addWidget(confirm_label)
    confirm_layout.addWidget(confirm_input)
    confirm_layout.addWidget(show_confirm_cb)
    layout.addLayout(confirm_layout)

    # Password validation container (initially hidden)
    validation_container = QWidget()
    validation_layout = QVBoxLayout(validation_container)
    validation_layout.setContentsMargins(0, 5, 0, 0)
    validation_container.hide()

    # Create validation labels for master password
    setup_master_password_validation_labels(validation_layout, validation_container, master_password_validator,
                                            pwd_input)

    layout.addWidget(validation_container)

    def save_password():
        password = pwd_input.text()
        confirm_password = confirm_input.text()

        # Validate master password using the validator
        if master_password_validator:
            is_valid, message = master_password_validator.validate(password)
            if not is_valid:
                show_error_dialog(parent, "Invalid Master Password", message)
                return

        if password != confirm_password:
            show_error_dialog(parent, "Password Mismatch", "Master passwords do not match!")
            return

        if not password:
            show_error_dialog(parent, "Empty Password", "Master password cannot be empty!")
            return

        manager.master_pwd_hash = hash_password(password)
        manager.passwords["master_pwd_hash"] = manager.master_pwd_hash

        # Automatically enable master password when set
        manager.disable_master = False

        manager.save_passwords()
        manager.update_lock_button_state()
        show_info_dialog(parent, "Success",
                         "Master password set successfully!\n\nMaster password has been automatically enabled.")
        dialog.accept()

    button_layout = QHBoxLayout()
    save_btn = QPushButton("Save")
    save_btn.clicked.connect(save_password)
    save_btn.setStyleSheet(SAVE_BTN_STYLE)
    button_layout.addWidget(save_btn)

    cancel_btn = QPushButton("Cancel")
    cancel_btn.clicked.connect(dialog.reject)
    cancel_btn.setStyleSheet(CLOSE_BTN_STYLE)
    button_layout.addWidget(cancel_btn)

    layout.addLayout(button_layout)
    dialog.setLayout(layout)
    return dialog.exec() == QDialog.DialogCode.Accepted


def setup_master_password_validation_labels(validation_layout, validation_container, validator, password_input):
    """Setup validation labels for master password with same style as main window"""
    criteria_labels = {
        'length': 'Minimum length (12 chars)',
        'uppercase': 'At least 2 uppercase letters',
        'lowercase': 'At least 2 lowercase letters',
        'digits': 'At least 2 numbers',
        'special': 'At least 2 special characters',
        'no_sequential': 'No 3+ identical characters',
        'no_patterns': 'No common patterns (123, abc)',
        'not_weak': 'Not a common weak password',
        'no_common_words': 'No common words (password, master, admin)'
    }

    validation_labels = _create_validation_labels(criteria_labels, validation_layout)
    _initialize_validation_display(validation_labels, validation_container)

    def on_master_password_changed(text):
        """Handle master password text change for real-time validation"""
        _update_validation_labels(text, validator, validation_labels)

    # Connect password input to validation
    password_input.textChanged.connect(on_master_password_changed)


def _create_validation_labels(criteria_labels, validation_layout):
    """Create and configure validation labels"""
    validation_labels = {}
    for key, label_text in criteria_labels.items():
        label = QLabel(f"❌ {label_text}")
        label.setStyleSheet("color: #666666; font-size: 11px; margin-left: 10px;")
        label.show()  # Show labels immediately for dialogs
        validation_labels[key] = label
        validation_layout.addWidget(label)
    return validation_labels


def _initialize_validation_display(validation_labels, validation_container):
    """Initialize validation display state - always show for dialogs"""
    # Show all labels and container initially for dialogs
    for label in validation_labels.values():
        label.show()
    validation_container.show()


def _update_validation_labels(text, validator, validation_labels):
    """Update validation labels based on password criteria"""
    criteria = validator.check_criteria(text)
    for key, check in criteria.items():
        if key in validation_labels:
            label = validation_labels[key]
            _update_single_label(label, check)


def _update_single_label(label, check):
    """Update a single validation label based on check result"""
    # Get the original text without emoji prefix
    current_text = label.text()
    if current_text.startswith('❌ ') or current_text.startswith('✅ '):
        criteria_text = current_text[2:]
    else:
        criteria_text = current_text

    if check['passed']:
        label.setText(f"✅ {criteria_text}")
        label.setStyleSheet("color: #00aa00; font-size: 11px; margin-left: 10px;")
    else:
        label.setText(f"❌ {criteria_text}")
        label.setStyleSheet("color: #666666; font-size: 11px; margin-left: 10px;")
