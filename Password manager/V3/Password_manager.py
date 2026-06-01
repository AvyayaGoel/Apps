import json
import os
import re
import sys
import time

from PyQt6.QtCore import Qt, QTimer, QEvent, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QGridLayout, QDialog,
    QCheckBox, QToolBar, QStatusBar
)
from cryptography.fernet import Fernet

from Password_constants import DATA_FILE, KEY_FILE, CONFIG_FILE, APP_DATA_DIR, ICON_PATH, MISSING_INF
from Password_generator import PasswordGeneratorDialog
from Password_helpers import create_styled_button, create_styled_input, show_info_dialog, show_error_dialog, \
    show_warning_dialog, hash_password, apply_global_theme, PasswordValidator
from Password_settings_window import SettingsWindow
from Password_window import PasswordWindow


def load_key():
    """Load or generate encryption key"""
    # Create directory if it doesn't exist
    os.makedirs(APP_DATA_DIR, exist_ok=True)

    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as key_file:
            return key_file.read()
    else:
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as key_file:
            key_file.write(key)
        return key


class ResizeWorker(QThread):
    """Worker thread for handling window resizing operations"""
    resize_signal = pyqtSignal(int, int, int, int)

    def __init__(self, x, y, width, height):
        super().__init__()
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def run(self):
        # Small delay to allow UI to remain responsive
        self.msleep(10)
        self.resize_signal.emit(self.x, self.y, self.width, self.height)


class SimplePasswordManager(QMainWindow):
    def __init__(self):
        super().__init__()

        # Window setup
        self.disable_master = None
        self.setWindowTitle("Password Manager")
        self.setGeometry(100, 100, 900, 350)
        self.setMinimumSize(600, 300)

        self.setWindowIcon(QIcon(ICON_PATH))

        # Initialize resize worker
        self.resize_worker = None

        # Initialize variables
        self.passwords = {}
        self.master_pwd_hash = None
        self.verified = False
        self.auto_lock_enabled = True
        self.auto_lock_minutes = 5
        self.current_theme = "light"  # Default theme
        self.last_activity = time.time()
        self.lock_timeout = 300  # 5 minutes

        # Initialize UI attributes
        self.lock_action = None
        self.site_input = None
        self.username_input = None
        self.email_input = None
        self.password_input = None
        self.show_password_cb = None
        self.result_label = None
        self.status_bar = None
        self.activity_timer = None

        # Password validation attributes
        self.password_validator = None
        self.password_validation_labels = {}
        self.password_validation_visible = False
        self.password_validation_container = None
        self.password_validation_layout = None
        self.validation_height_increment = 150  # Store height increment as variable

        # Load encryption
        key = load_key()
        self.cipher = Fernet(key)

        # Load data
        self.load_passwords()
        self.load_settings()

        # Setup UI
        self.setup_ui()

        # Setup timers
        self.setup_timers()

        # Check master password
        if not os.path.exists(DATA_FILE):
            self.setup_master_password()
        else:
            if self.master_pwd_hash and not self.verified:
                self.verify_master_password()

    def setup_ui(self):
        """Setup the main UI"""

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # Create toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)

        # Theme toggle
        theme_action = QAction(QIcon(), "Toggle Theme", self)
        theme_action.triggered.connect(self.toggle_theme)
        toolbar.addAction(theme_action)

        toolbar.addSeparator()

        # Settings action
        settings_action = QAction(QIcon(), "Settings", self)
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)

        # Lock action (disabled if no master password)
        self.lock_action = QAction(QIcon(), "Lock", self)
        self.lock_action.triggered.connect(self.lock_application)
        toolbar.addAction(self.lock_action)

        # Generator action
        generator_action = QAction(QIcon(), "Generator", self)
        generator_action.triggered.connect(self.open_password_generator)
        toolbar.addAction(generator_action)

        # View passwords action
        view_action = QAction(QIcon(), "View All", self)
        view_action.triggered.connect(self.open_password_window)
        toolbar.addAction(view_action)

        self.addToolBar(toolbar)

        # Apply initial theme
        self.apply_theme()

        # Create form layout
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)

        # Site
        form_layout.addWidget(QLabel("Site:"), 0, 0)
        self.site_input = create_styled_input("Enter website name")
        form_layout.addWidget(self.site_input, 0, 1)

        # Username
        form_layout.addWidget(QLabel("Username:"), 1, 0)
        self.username_input = create_styled_input("Enter username")
        form_layout.addWidget(self.username_input, 1, 1)

        # Email
        form_layout.addWidget(QLabel("Email:"), 2, 0)
        self.email_input = create_styled_input("Enter email address")
        form_layout.addWidget(self.email_input, 2, 1)

        # Password
        form_layout.addWidget(QLabel("Password:"), 3, 0)
        self.password_input = create_styled_input("Enter password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.textChanged.connect(self.on_password_changed)
        form_layout.addWidget(self.password_input, 3, 1)

        # Show/Hide password checkbox
        self.show_password_cb = QCheckBox("Show Password")
        self.show_password_cb.toggled.connect(self.toggle_password_visibility)
        form_layout.addWidget(self.show_password_cb, 3, 2)

        # Password validation container (initially hidden)
        self.password_validation_container = QWidget()
        self.password_validation_layout = QVBoxLayout(self.password_validation_container)
        self.password_validation_layout.setContentsMargins(0, 5, 0, 0)
        self.password_validation_container.hide()

        # Create validation labels for all criteria
        self.setup_password_validation_labels()

        # Initialize password validator with default requirements
        self.update_password_requirements()

        form_layout.addWidget(self.password_validation_container, 4, 0, 1, 3)

        main_layout.addWidget(form_widget)

        # Buttons
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)

        add_btn = create_styled_button("Add/Update", self.add_password, "#4CAF50", 140)
        button_layout.addWidget(add_btn)

        search_btn = create_styled_button("Search", self.search_password, "#2196F3", 120)
        button_layout.addWidget(search_btn)

        view_btn = create_styled_button("View All", self.open_password_window, "#FF9800", 120)
        button_layout.addWidget(view_btn)

        generate_btn = create_styled_button("Generate", self.open_password_generator, "#9C27B0", 140)
        button_layout.addWidget(generate_btn)

        remove_btn = create_styled_button("Remove", self.remove_password, "#f44336", 120)
        button_layout.addWidget(remove_btn)

        main_layout.addWidget(button_widget)

        # Result display (using status bar instead of separate label)
        self.result_label = QLabel("Ready")
        self.result_label.setStyleSheet("""
            QLabel {
                background-color: #FFFFFF;
                border: 2px solid #2196F3;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
                color: #000000;
            }
        """)
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.result_label)

        # Status bar (for system messages only)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def apply_theme(self):
        """Apply current theme to main window"""
        apply_global_theme(self.current_theme, self)

    def toggle_theme(self):
        """Toggle between light and dark themes"""
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme()
        self.save_settings()

    def update_lock_button_state(self):
        """Enable/disable lock button based on master password status"""
        if hasattr(self, 'lock_action') and self.lock_action is not None:
            self.lock_action.setEnabled(bool(self.master_pwd_hash))

    def update_password_requirements(self):
        """Update password validator with fixed requirements"""
        requirements = {
            'length': 8,  # Fixed minimum length
            'uppercase': 1,  # Always require at least 1 uppercase
            'lowercase': 1,  # Always require at least 1 lowercase
            'digits': 1,  # Always require at least 1 digit
            'special': 1  # Always require at least 1 special character
        }

        self.password_validator = PasswordValidator(is_master_password=False, requirements=requirements)

        # Create validation labels if not already created
        if not hasattr(self, 'password_validation_labels'):
            self.setup_password_validation_labels()

    def setup_password_validation_labels(self):
        """Setup password validation labels for all criteria"""
        criteria_labels = {
            'length': 'Minimum length (8 chars)',
            'uppercase': 'At least 1 uppercase letter',
            'lowercase': 'At least 1 lowercase letter',
            'digits': 'At least 1 number',
            'special': 'At least 1 special character',
            'no_sequential': 'No 3+ identical characters',
            'no_patterns': 'No common patterns (123, abc)',
            'not_weak': 'Not a common weak password'
        }

        for key, label_text in criteria_labels.items():
            label = QLabel(f"❌ {label_text}")
            label.setStyleSheet("color: #666666; font-size: 11px; margin-left: 10px;")
            label.hide()
            self.password_validation_labels[key] = label
            self.password_validation_layout.addWidget(label)

        # Show all labels initially to prevent lag on first character
        for label in self.password_validation_labels.values():
            label.show()
        self.password_validation_container.hide()

    def on_password_changed(self, text):
        """Handle password text change for real-time validation"""
        if not self.password_validator:
            return

        has_content = len(text) > 0
        self._update_validation_visibility(has_content)

        if has_content:
            self._update_validation_labels(text)

    def _update_validation_visibility(self, has_content):
        """Show/hide validation container and resize window accordingly"""
        if has_content and not self.password_validation_visible:
            self._show_validation_container()
        elif not has_content and self.password_validation_visible:
            self._hide_validation_container()

    def _show_validation_container(self):
        """Show validation container and resize window asynchronously"""
        self.password_validation_container.show()
        self.password_validation_visible = True
        self._resize_window_async(100, 100, 900, 350 + self.validation_height_increment)

    def _hide_validation_container(self):
        """Hide validation container and resize window asynchronously"""
        self.password_validation_container.hide()
        self.password_validation_visible = False
        self._resize_window_async(100, 100, 900, 350)

    def _resize_window_async(self, x, y, width, height):
        """Resize window asynchronously to prevent UI lag"""
        if self.resize_worker and self.resize_worker.isRunning():
            try:
                self.resize_worker.quit()
                self.resize_worker.wait(100)  # Wait up to 100ms
                if self.resize_worker.isRunning():
                    self.resize_worker.terminate()
                    self.resize_worker.wait(50)
            except (RuntimeError, OSError):
                pass

        self.resize_worker = ResizeWorker(x, y, width, height)
        self.resize_worker.resize_signal.connect(self.setGeometry)
        self.resize_worker.start()

    def closeEvent(self, event):
        """Clean up threads when window is closed"""
        if self.resize_worker and self.resize_worker.isRunning():
            try:
                self.resize_worker.quit()
                self.resize_worker.wait(100)
                if self.resize_worker.isRunning():
                    self.resize_worker.terminate()
                    self.resize_worker.wait(50)
            except (RuntimeError, OSError):
                pass
        super().closeEvent(event)

    def _update_validation_labels(self, password_text):
        """Update validation criteria labels based on password"""
        criteria = self.password_validator.check_criteria(password_text)

        for key, check in criteria.items():
            if key in self.password_validation_labels:
                self._update_single_validation_label(key, check)

    def _update_single_validation_label(self, key, check):
        """Update a single validation label"""
        label = self.password_validation_labels[key]

        if check['passed']:
            label.setText(f"✅ {label.text()[2:]}")
            label.setStyleSheet("color: #00aa00; font-size: 11px; margin-left: 10px;")
        else:
            label.setText(f"❌ {label.text()[2:]}")
            label.setStyleSheet("color: #666666; font-size: 11px; margin-left: 10px;")

    def toggle_password_visibility(self, checked):
        """Toggle password visibility"""
        if checked:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

    def set_generated_password(self, password):
        """Set generated password in the main window"""
        self.password_input.setText(password)
        self.result_label.setText("Password generated successfully!")

    def setup_timers(self):
        """Setup activity monitoring timer"""
        self.activity_timer = QTimer()
        self.activity_timer.timeout.connect(self.check_idle_time)
        self.activity_timer.start(1000)  # Check every second

        # Install event filter for activity monitoring
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        """Filter events to monitor user activity"""
        if event.type() in [QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove]:
            self.last_activity = time.time()
        return super().eventFilter(obj, event)

    def check_idle_time(self):
        """Check if application should be locked"""
        if self.verified and self.auto_lock_enabled:
            if time.time() - self.last_activity > self.lock_timeout:
                self.lock_application()

    def load_passwords(self):
        """Load passwords from file"""
        # Create directory if it doesn't exist
        os.makedirs(APP_DATA_DIR, exist_ok=True)

        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as file:
                    loaded = json.load(file)
                    self.passwords = self.decrypt_passwords(loaded)
                    self.master_pwd_hash = self.passwords.pop("master_pwd_hash", None)
            except (json.JSONDecodeError, FileNotFoundError):
                show_warning_dialog(self, "Warning", "Password data file is corrupted. Starting fresh.")
                self.passwords = {}
                self.master_pwd_hash = None

    def save_passwords(self):
        """Save passwords to file"""
        # Create directory if it doesn't exist
        os.makedirs(APP_DATA_DIR, exist_ok=True)

        passwords_to_save = self.passwords.copy()
        if self.master_pwd_hash:
            passwords_to_save["master_pwd_hash"] = self.master_pwd_hash

        encrypted_passwords = self.encrypt_passwords(passwords_to_save)
        with open(DATA_FILE, "w") as file:
            json.dump(encrypted_passwords, file)

    def encrypt_passwords(self, passwords_to_encrypt):
        """Encrypt passwords for storage"""
        encrypted = {}
        for site, info in passwords_to_encrypt.items():
            if site == "master_pwd_hash":
                encrypted[site] = info
                continue
            encrypted[site] = {
                "username": info["username"],
                "email": info["email"],
                "password": self.cipher.encrypt(info["password"].encode()).decode()
            }
        return encrypted

    def decrypt_passwords(self, passwords_to_decrypt):
        """Decrypt passwords from storage"""
        decrypted = {}
        for site, info in passwords_to_decrypt.items():
            if site == "master_pwd_hash":
                decrypted[site] = info
                continue
            pwd = info["password"]
            if isinstance(pwd, str) and pwd.startswith("gAAAA"):
                pwd = self.cipher.decrypt(pwd.encode()).decode()
            decrypted[site] = {
                "username": info["username"],
                "email": info["email"],
                "password": pwd
            }
        return decrypted

    def load_settings(self):
        """Load application settings"""
        # Create directory if it doesn't exist
        os.makedirs(APP_DATA_DIR, exist_ok=True)

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as file:
                    settings = json.load(file)
                    self.auto_lock_enabled = settings.get("auto_lock_enabled", True)
                    self.auto_lock_minutes = settings.get("auto_lock_minutes", 5)
                    self.current_theme = settings.get("theme", "light")
                    self.disable_master = settings.get("disable_master", False)
            except (json.JSONDecodeError, FileNotFoundError):
                pass

        # Update lock button state after loading settings
        self.update_lock_button_state()

    def save_settings(self):
        """Save application settings"""
        # Create directory if it doesn't exist
        os.makedirs(APP_DATA_DIR, exist_ok=True)

        settings = {
            "auto_lock_enabled": self.auto_lock_enabled,
            "auto_lock_minutes": self.auto_lock_minutes,
            "disable_master": self.disable_master,
            "theme": self.current_theme
        }
        try:
            with open(CONFIG_FILE, "w") as file:
                json.dump(settings, file, indent=4)
        except (OSError, TypeError) as e:
            print(f"Warning: Failed to save settings: {e}")

    def setup_master_password(self):
        """Setup master password dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Setup Master Password")
        dialog.setFixedSize(300, 200)

        layout = QVBoxLayout()

        pwd_label = QLabel("Set a New Master Password:")
        pwd_input = QLineEdit()
        pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(pwd_label)
        layout.addWidget(pwd_input)

        confirm_label = QLabel("Confirm Master Password:")
        confirm_input = QLineEdit()
        confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(confirm_label)
        layout.addWidget(confirm_input)

        def save_password():
            password = pwd_input.text()
            confirm_password = confirm_input.text()

            # Validate master password using PasswordValidator
            validator = PasswordValidator(is_master_password=True)
            is_valid, message = validator.validate(password)
            if not is_valid:
                show_error_dialog(self, "Invalid Master Password", message)
                return

            if password != confirm_password:
                show_error_dialog(self, "Password Mismatch", "Master passwords do not match!")
                return

            if not password:
                show_error_dialog(self, "Empty Password", "Master password cannot be empty!")
                return

            self.master_pwd_hash = hash_password(password)
            self.passwords["master_pwd_hash"] = self.master_pwd_hash

            # Automatically enable master password when set
            self.disable_master = False

            self.save_passwords()
            self.update_lock_button_state()  # Update lock button state
            show_info_dialog(self, "Success",
                             "Master password set successfully!\n\nMaster password has been automatically enabled.")
            dialog.accept()

        def skip():
            self.master_pwd_hash = None
            self.passwords.pop("master_pwd_hash", None)

            # Automatically disable auto-lock when master password is skipped
            self.auto_lock_enabled = False
            self.disable_master = True

            self.save_passwords()
            self.update_lock_button_state()  # Update lock button state
            show_info_dialog(self, "Info",
                             "Master password skipped.\n\nAuto-lock has been automatically disabled.\nYou can enable both in Settings later.")
            dialog.accept()

        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(save_password)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")
        button_layout.addWidget(save_btn)

        skip_btn = QPushButton("Skip")
        skip_btn.clicked.connect(skip)
        skip_btn.setStyleSheet("background-color: #f44336; color: white; padding: 8px;")
        button_layout.addWidget(skip_btn)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()

    def verify_master_password(self):
        """Verify master password"""
        if not self.master_pwd_hash:
            return True
        if self.verified:
            return True

        dialog = QDialog(self)
        dialog.setWindowTitle("Verify Master Password")
        dialog.setFixedSize(300, 150)

        layout = QVBoxLayout()

        pwd_label = QLabel("Enter Master Password:")
        pwd_input = QLineEdit()
        pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(pwd_label)
        layout.addWidget(pwd_input)

        def check_password():
            if self.master_pwd_hash and hash_password(pwd_input.text()) == self.master_pwd_hash:
                self.verified = True
                show_info_dialog(self, "Success", "Access granted!")
                dialog.accept()
            else:
                show_error_dialog(self, "Error", "Incorrect password!")

        button_layout = QHBoxLayout()
        verify_btn = QPushButton("Verify")
        verify_btn.clicked.connect(check_password)
        verify_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px;")
        button_layout.addWidget(verify_btn)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()

        return self.verified

    def add_password(self):
        """Add or update a password"""
        if not self.verify_master_password():
            return

        site = self.site_input.text().strip()
        user = self.username_input.text().strip()
        eml = self.email_input.text().strip()
        pwd = self.password_input.text().strip()

        if not self._validate_password_inputs(site, user, eml, pwd):
            return

        self._save_or_update_password(site, user, eml, pwd)

    def _validate_password_inputs(self, site, user, eml, pwd):
        """Validate all password inputs"""
        if not site:
            show_error_dialog(self, MISSING_INF, "Please enter a website name.")
            return False

        if not user:
            show_error_dialog(self, MISSING_INF, "Please enter a username.")
            return False

        if not eml:
            show_error_dialog(self, MISSING_INF, "Please enter an email address.")
            return False

        if not pwd:
            show_error_dialog(self, MISSING_INF, "Please enter a password.")
            return False

        if not self._validate_email_format(eml):
            return False

        if not self._validate_password_strength(pwd):
            return False

        return True

    def _validate_email_format(self, email):
        """Validate email format"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            show_error_dialog(self, "Invalid Email", "Please enter a valid email address.")
            return False
        return True

    def _validate_password_strength(self, password):
        """Validate password strength"""
        if self.password_validator:
            is_valid, message = self.password_validator.validate(password)
            if not is_valid:
                show_error_dialog(self, "Weak Password", message)
                return False
        return True

    def _save_or_update_password(self, site, user, eml, pwd):
        """Save new password or update existing one"""
        if site in self.passwords and (
                self.passwords[site]["username"] == user or self.passwords[site]["email"] == eml):
            self.passwords[site]["password"] = pwd
            self.result_label.setText(f"Updated password for {user} at {site}")
        else:
            self.passwords[site] = {"username": user, "email": eml, "password": pwd}
            self.result_label.setText(f"Saved password for {site}")

        self.save_passwords()
        self.clear_fields()

    def search_password(self):
        """Search for a password"""
        if not self.verify_master_password():
            return

        site = self.site_input.text().strip().lower()
        eml = self.email_input.text().strip().lower()
        user = self.username_input.text().strip().lower()

        if not site:
            self.result_label.setText("Please enter a site to search.")
            return

        if site in self.passwords and (
                self.passwords[site]["username"] == user or self.passwords[site]["email"] == eml):
            info = self.passwords[site]
            self.result_label.setText(
                f"Username: {info['username']}\\nEmail: {info['email']}\\nPassword: {info['password']}")
            self.status_bar.showMessage("Password found", 3000)
        else:
            self.result_label.setText("No password found for this site.")
            self.status_bar.showMessage("No password found", 3000)

    def remove_password(self):
        """Remove a password entry"""
        if not self.verify_master_password():
            return

        site = self.site_input.text().strip()
        user = self.username_input.text().strip()
        eml = self.email_input.text().strip()

        if not site:
            self.result_label.setText("Please enter a site to remove.")
            return

        if site in self.passwords and (
                self.passwords[site]["username"] == user or
                self.passwords[site]["email"] == eml):
            del self.passwords[site]
            self.save_passwords()
            self.clear_fields()
            self.result_label.setText(f"Password for {site} removed successfully!")
        else:
            self.result_label.setText("No matching password found to remove.")

    def clear_fields(self):
        """Clear all input fields"""
        self.site_input.clear()
        self.username_input.clear()
        self.email_input.clear()
        self.password_input.clear()

    def open_password_window(self):
        """Open password window"""
        if not self.verify_master_password():
            return

        window = PasswordWindow(self, self.passwords)
        window.exec()

    def open_settings(self):
        """Open settings window"""
        if not self.verify_master_password():
            return

        window = SettingsWindow(self, self)
        window.exec()

    def open_password_generator(self):
        """Open password generator dialog"""
        if not self.verify_master_password():
            return

        dialog = PasswordGeneratorDialog(self)
        dialog.exec()

    def lock_application(self):
        """Lock the application"""
        if not self.auto_lock_enabled or not self.master_pwd_hash:
            return

        self.verified = False
        show_info_dialog(self, "Locked", "Application locked. Please re-enter master password.")
        if not self.verify_master_password():
            self.close()
        else:
            self.last_activity = time.time()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Modern look
    window = SimplePasswordManager()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
