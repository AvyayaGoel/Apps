from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QDialog,
    QCheckBox, QSpinBox,
    QGroupBox, QWidget,
    QMessageBox
)

from Password_constants import ICON_PATH, INCORRECT_M_P, CLOSE_BTN_STYLE, SAVE_BTN_STYLE, SETUP_MASTER_PWD, \
    CHANGE_MASTER_PWD
from Password_helpers import show_info_dialog, show_error_dialog, apply_global_theme, hash_password, PasswordValidator, \
    verify_current_master_password, setup_new_master_password, setup_master_password_validation_labels


class SettingsWindow(QDialog):
    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Settings")
        self.setFixedSize(550, 400)
        self.setWindowIcon(QIcon(ICON_PATH))
        self.disable_master = None
        self.theme_combo = None
        self.auto_lock_enabled = None
        self.auto_lock_minutes = None
        self.require_upper = None
        self.require_lower = None
        self.require_digits = None
        self.require_symbols = None
        self.min_length_label = None
        self.min_length_spin = None

        # Master password validation attributes
        self.master_password_validator = None
        self.master_password_validation_labels = {}
        self.master_password_validation_visible = False
        self.master_validation_height_increment = 140  # Store height increment as variable

        layout = QVBoxLayout()

        # Master password section
        master_group = QGroupBox("Master Password")
        master_layout = QVBoxLayout()

        self.disable_master = QCheckBox("Disable Master Password")
        self.disable_master.setChecked(not bool(manager.master_pwd_hash))
        self.disable_master.toggled.connect(self.on_disable_master_toggled)
        master_layout.addWidget(self.disable_master)

        self.change_master_btn = QPushButton(CHANGE_MASTER_PWD if manager.master_pwd_hash else SETUP_MASTER_PWD)
        self.change_master_btn.clicked.connect(self.handle_master_password_action)
        self.change_master_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 8px;")
        master_layout.addWidget(self.change_master_btn)

        master_group.setLayout(master_layout)
        layout.addWidget(master_group)

        # Theme section
        theme_group = QGroupBox("Appearance")
        theme_layout = QVBoxLayout()

        self.theme_combo = QCheckBox("Dark Theme")
        self.theme_combo.setChecked(manager.current_theme == "dark")
        theme_layout.addWidget(self.theme_combo)

        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        # Auto-lock section
        lock_group = QGroupBox("Auto-Lock")
        lock_layout = QVBoxLayout()

        self.auto_lock_enabled = QCheckBox("Enable Auto-Lock")
        self.auto_lock_enabled.setChecked(manager.auto_lock_enabled)
        lock_layout.addWidget(self.auto_lock_enabled)

        minutes_layout = QHBoxLayout()
        minutes_layout.addWidget(QLabel("Lock after (minutes):"))
        self.auto_lock_minutes = QSpinBox()
        self.auto_lock_minutes.setRange(1, 60)
        self.auto_lock_minutes.setValue(manager.auto_lock_minutes)
        minutes_layout.addWidget(self.auto_lock_minutes)
        lock_layout.addLayout(minutes_layout)

        lock_now_btn = QPushButton("Lock Now")
        lock_now_btn.clicked.connect(self.lock_now)
        lock_now_btn.setStyleSheet("background-color: #FF5722; color: white; padding: 8px;")
        lock_layout.addWidget(lock_now_btn)

        lock_group.setLayout(lock_layout)
        layout.addWidget(lock_group)

        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setStyleSheet(SAVE_BTN_STYLE)
        button_layout.addWidget(save_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(CLOSE_BTN_STYLE)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Apply theme after UI setup
        self.apply_theme()

    def apply_theme(self):
        """Apply theme to settings window"""
        apply_global_theme(self.manager.current_theme, self)

    def handle_master_password_action(self):
        """Handle master password button click - show correct dialog based on existence"""
        if self.manager.master_pwd_hash:
            # Master password exists - show change dialog
            self.change_master_password()
        else:
            # No master password - show setup dialog
            setup_new_master_password(self, self.manager)

    def on_disable_master_toggled(self, checked):
        """Handle disable master password checkbox toggle"""
        if checked:
            self._handle_disable_checked()
        else:
            self._handle_disable_unchecked()

    def _handle_disable_checked(self):
        """Handle when disable checkbox is checked (master password disabled)"""
        if self.manager.master_pwd_hash:
            self._disable_existing_master_password()
        # If no master password exists, just ensure checkbox state is correct

    def _handle_disable_unchecked(self):
        """Handle when disable checkbox is unchecked (master password enabled)"""
        if not self.manager.master_pwd_hash:
            self._setup_master_password()
        # If master password already exists, just update button text
        self._update_button_text_for_existing_master()

    def _disable_existing_master_password(self):
        """Disable existing master password after confirmation"""
        reply = QMessageBox.question(
            self, 'Disable Master Password',
            'Are you sure you want to disable the master password? This will remove all protection.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.manager.master_pwd_hash = None
                self.manager.save_passwords()
                self.disable_master.setChecked(False)
                self.change_master_btn.setText(SETUP_MASTER_PWD)
                show_info_dialog(self, "Success", "Master password has been disabled.")
            except Exception as e:
                print("Debug:", e)

    def _setup_master_password(self):
        """Setup master password when user unchecks disable box"""
        if setup_new_master_password(self, self.manager):
            self.disable_master.setChecked(True)
            self.change_master_btn.setText(CHANGE_MASTER_PWD)
        # If user cancels, keep checkbox unchecked (don't change anything)

    def _update_button_text_for_existing_master(self):
        """Update button text when existing master password is active"""
        self.change_master_btn.setText(CHANGE_MASTER_PWD)

    def change_master_password(self):
        """Change master password dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle(CHANGE_MASTER_PWD)
        dialog.setFixedSize(400, 350)  # Smaller window size

        layout = QVBoxLayout()

        # Initialize validator for this dialog (backend only)
        change_validator = PasswordValidator(is_master_password=True)

        # Current password
        current_label = QLabel("Current Master Password:")
        current_input = QLineEdit()
        current_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(current_label)
        layout.addWidget(current_input)

        # New password with show/hide checkbox
        new_layout = QHBoxLayout()
        new_label = QLabel("New Master Password:")
        new_input = QLineEdit()
        new_input.setEchoMode(QLineEdit.EchoMode.Password)
        show_new_cb = QCheckBox("Show")
        show_new_cb.toggled.connect(lambda checked: new_input.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password))

        new_layout.addWidget(new_label)
        new_layout.addWidget(new_input)
        new_layout.addWidget(show_new_cb)
        layout.addLayout(new_layout)

        # Confirm new password with show/hide checkbox
        confirm_layout = QHBoxLayout()
        confirm_label = QLabel("Confirm New Password:")
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
        validation_container.show()

        # Create validation labels for master password
        setup_master_password_validation_labels(validation_layout, validation_container, change_validator, new_input)

        layout.addWidget(validation_container)

        def save_new_password():
            # Validate current password
            if self.manager.master_pwd_hash and hash_password(current_input.text()) != self.manager.master_pwd_hash:
                show_error_dialog(self, "Error", INCORRECT_M_P)
                return

            # Validate new master password
            new_password = new_input.text()
            confirm_password = confirm_input.text()

            is_valid, message = change_validator.validate(new_password)
            if not is_valid:
                show_error_dialog(self, "Invalid Master Password", message)
                return

            if new_password != confirm_password:
                show_error_dialog(self, "Password Mismatch", "New master passwords do not match!")
                return

            if not new_password:
                show_error_dialog(self, "Empty Password", "Master password cannot be empty!")
                return

            self.manager.master_pwd_hash = hash_password(new_password)
            self.manager.passwords["master_pwd_hash"] = self.manager.master_pwd_hash

            # Automatically enable master password when changed
            self.manager.disable_master = False

            # Save both passwords and settings
            self.manager.save_passwords()
            self.manager.update_lock_button_state()
            show_info_dialog(self, "Success",
                             "Master password changed successfully!\n\nMaster password has been automatically enabled.")
            dialog.accept()

        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(save_new_password)
        save_btn.setStyleSheet(SAVE_BTN_STYLE)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        cancel_btn.setStyleSheet(CLOSE_BTN_STYLE)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()

    def lock_now(self):
        self.manager.lock_application()
        self.accept()

    def save_settings(self):
        self.manager.auto_lock_enabled = self.auto_lock_enabled.isChecked()
        self.manager.auto_lock_minutes = self.auto_lock_minutes.value()

        # Handle master password disable properly
        if self.disable_master.isChecked():
            if self.manager.master_pwd_hash:
                # Ask for current master password before disabling
                if verify_current_master_password(self, self.manager):
                    self.manager.master_pwd_hash = None
                    self.manager.passwords.pop("master_pwd_hash", None)

                    # Automatically disable auto-lock when master password is disabled
                    self.manager.auto_lock_enabled = False
                    self.disable_master.setChecked(False)

                    self.manager.save_passwords()
                    self.manager.update_lock_button_state()
                    show_info_dialog(self, "Success",
                                     "Master password disabled successfully!\n\nAuto-lock has been automatically disabled.")
                else:
                    show_error_dialog(self, "Error", INCORRECT_M_P)
                    return
        else:
            # Enable master password if it was disabled
            if not self.manager.master_pwd_hash:
                setup_new_master_password(self, self.manager)
                return

        # Update theme
        self.manager.current_theme = "dark" if self.theme_combo.isChecked() else "light"
        self.manager.apply_theme()

        # Update lock button state
        self.manager.update_lock_button_state()

        self.manager.save_settings()
        show_info_dialog(self, "Settings", "Settings saved successfully!")
        self.accept()
