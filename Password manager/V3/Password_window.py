from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QDialog, QScrollArea, QGroupBox, QFormLayout, QMessageBox,
    QHBoxLayout, QApplication
)

from Password_constants import ICON_PATH
from Password_helpers import apply_global_theme, show_info_dialog


class PasswordWindow(QDialog):
    def __init__(self, parent, passwords):
        super().__init__(parent)
        self.passwords = passwords
        self.setWindowTitle("Stored Passwords")
        self.setFixedSize(600, 400)
        self.setWindowIcon(QIcon(ICON_PATH))

        # Apply theme on creation
        self.apply_theme()

        layout = QVBoxLayout()

        # Scroll area for passwords
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        for site, info in self.passwords.items():
            if site == "master_pwd_hash":
                continue

            group = QGroupBox(site)
            group_layout = QFormLayout()

            username_label = QLabel(f"Username: {info['username']}")
            group_layout.addRow(username_label)

            email_label = QLabel(f"Email: {info['email']}")
            group_layout.addRow(email_label)

            password_label = QLabel(f"Password: {info['password']}")
            password_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            group_layout.addRow(password_label)

            # Button layout for Copy and Remove
            button_layout = QHBoxLayout()

            copy_btn = QPushButton("Copy Password")
            copy_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px;")
            copy_btn.clicked.connect(lambda checked, s=site, p=info['password']: self.copy_password(s, p))
            button_layout.addWidget(copy_btn)

            remove_btn = QPushButton("Remove")
            remove_btn.setStyleSheet("background-color: #f44336; color: white; padding: 5px;")
            remove_btn.clicked.connect(lambda checked, s=site: self.remove_password(s))
            button_layout.addWidget(remove_btn)

            group_layout.addRow(button_layout)

            group.setLayout(group_layout)
            scroll_layout.addWidget(group)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px;")
        layout.addWidget(close_btn)

        self.setLayout(layout)

        # Apply theme after UI setup
        self.apply_theme()

    def copy_password(self, site, password):
        """Copy password to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(password)
        show_info_dialog(self, "Success", f"Password for {site} copied to clipboard!")

    def remove_password(self, site):
        """Remove password entry"""
        reply = QMessageBox.question(
            self, 'Remove Password',
            f'Are you sure you want to remove the password for {site}?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Remove from passwords dictionary
            if site in self.passwords:
                del self.passwords[site]

                # Update parent's passwords if available
                parent = self.parent()
                if parent and hasattr(parent, 'passwords'):
                    parent.passwords = self.passwords
                    if hasattr(parent, 'save_passwords'):
                        parent.save_passwords()

                # Refresh the password window
                self.refresh_password_list()
                show_info_dialog(self, "Success", f"Password for {site} has been removed.")

    def refresh_password_list(self):
        """Refresh the password list display"""
        # Clear current layout
        layout = self.layout()
        if layout:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        # Recreate password entries
        self._create_password_entries()

    def _create_password_entries(self):
        """Create password entries in the layout"""
        layout = self.layout()

        # Scroll area for passwords
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        for site, info in self.passwords.items():
            if site == "master_pwd_hash":
                continue

            group = QGroupBox(site)
            group_layout = QFormLayout()

            username_label = QLabel(f"Username: {info['username']}")
            group_layout.addRow(username_label)

            email_label = QLabel(f"Email: {info['email']}")
            group_layout.addRow(email_label)

            password_label = QLabel(f"Password: {info['password']}")
            password_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            group_layout.addRow(password_label)

            # Button layout for Copy and Remove
            button_layout = QHBoxLayout()

            copy_btn = QPushButton("Copy Password")
            copy_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px;")
            copy_btn.clicked.connect(lambda checked, s=site, p=info['password']: self.copy_password(s, p))
            button_layout.addWidget(copy_btn)

            remove_btn = QPushButton("Remove")
            remove_btn.setStyleSheet("background-color: #f44336; color: white; padding: 5px;")
            remove_btn.clicked.connect(lambda checked, s=site: self.remove_password(s))
            button_layout.addWidget(remove_btn)

            group_layout.addRow(button_layout)

            group.setLayout(group_layout)
            scroll_layout.addWidget(group)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px;")
        layout.addWidget(close_btn)

    def apply_theme(self):
        """Apply theme to password window"""
        parent = self.parent()
        parent_theme = getattr(parent, 'current_theme', 'light') if parent else "light"
        apply_global_theme(parent_theme, self)
