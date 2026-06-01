import secrets
import string

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QDialog,
    QMessageBox, QCheckBox, QSpinBox,
)

from Password_constants import ICON_PATH
from Password_helpers import apply_global_theme, PasswordValidator, get_password_strength_indicator


class PasswordGeneratorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Password Generator")
        self.setFixedSize(350, 300)
        self.setWindowIcon(QIcon(ICON_PATH))
        self.length_spin = None
        self.use_upper = None
        self.use_digits = None
        self.use_symbols = None
        self.word_input = None

        layout = QVBoxLayout()

        # Length input
        length_layout = QHBoxLayout()
        length_layout.addWidget(QLabel("Password Length:"))
        self.length_spin = QSpinBox()
        self.length_spin.setRange(4, 32)
        self.length_spin.setValue(12)
        length_layout.addWidget(self.length_spin)
        layout.addLayout(length_layout)

        # Options
        self.use_upper = QCheckBox("Include Uppercase")
        self.use_upper.setChecked(True)
        layout.addWidget(self.use_upper)

        self.use_digits = QCheckBox("Include Digits")
        self.use_digits.setChecked(True)
        layout.addWidget(self.use_digits)

        self.use_symbols = QCheckBox("Include Symbols")
        self.use_symbols.setChecked(True)
        layout.addWidget(self.use_symbols)

        # Word input
        word_layout = QHBoxLayout()
        word_layout.addWidget(QLabel("Word to include (optional):"))
        self.word_input = QLineEdit()
        word_layout.addWidget(self.word_input)
        layout.addLayout(word_layout)

        # Buttons
        button_layout = QHBoxLayout()
        generate_btn = QPushButton("Generate")
        generate_btn.clicked.connect(self.generate_password)
        generate_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")
        button_layout.addWidget(generate_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("background-color: #f44336; color: white; padding: 8px;")
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Apply theme after UI setup
        self.apply_theme()

    def generate_password(self):
        alphabet = string.ascii_lowercase
        if self.use_upper.isChecked():
            alphabet += string.ascii_uppercase
        if self.use_digits.isChecked():
            alphabet += string.digits
        if self.use_symbols.isChecked():
            alphabet += string.punctuation

        length = self.length_spin.value()
        word = self.word_input.text()

        if word and len(word) < length:
            chars_needed = length - len(word)
            password = [secrets.choice(alphabet) for _ in range(chars_needed)]
            insert_at = secrets.randbelow(chars_needed + 1)
            password = password[:insert_at] + list(word) + password[insert_at:]
            password = ''.join(password)
        else:
            password = ''.join(secrets.choice(alphabet) for _ in range(length))

        # Validate generated password
        validator = PasswordValidator(is_master_password=False)
        is_valid, message = validator.validate(password)
        if not is_valid:
            # Show warning but still allow the password
            QMessageBox.warning(self, "Password Strength",
                                f"Generated password doesn't meet security requirements:\n{message}\n\n"
                                "You can still use this password, but consider regenerating with different options.")

        # Show password strength
        strength_text, _ = get_password_strength_indicator(password)

        # Set password in main window
        parent = self.parent()
        if parent and hasattr(parent, 'set_generated_password'):
            parent.set_generated_password(password)

        # Show detailed message
        QMessageBox.information(self, "Generated Password",
                                f"Password generated successfully!\n\n"
                                f"Password: {password}\n"
                                f"Strength: {strength_text}\n\n"
                                f"Password has been copied to the main window.")
        self.accept()

    def apply_theme(self):
        """Apply theme to password generator"""
        parent_theme = getattr(self.parent(), 'current_theme', 'light') if self.parent() else "light"
        apply_global_theme(parent_theme, self)
