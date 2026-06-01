"""
Settings Window (PyQt6 version)
Multi-page settings with sidebar navigation. Theme selection reserved for later.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QRadioButton,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget,
    QMessageBox, QColorDialog, QStackedWidget, QCheckBox
)

from macro_manager_window import MacroManagerWindow
from notification_manager import show_notification


class SettingsWindow(QDialog):
    """Application settings dialog with multipage navigation."""

    def __init__(self, parent):
        super().__init__(parent.root if hasattr(parent, 'root') else parent)
        self.parent = parent

        self.setWindowTitle("Settings")
        self.setMinimumSize(700, 520)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self._selected_color = "#ffffff"
        self._pages = {}

        self._build_ui()
        self._apply_styles()
        self._load_settings()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ──
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(180)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 12, 0, 12)
        sidebar_layout.setSpacing(4)

        sidebar_header = QLabel("  Settings")
        sidebar_header.setObjectName("sidebarHeader")
        sidebar_layout.addWidget(sidebar_header)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navList")
        self.nav_list.setFrameShape(QFrame.Shape.NoFrame)
        self.nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav_list.currentRowChanged.connect(self._switch_page)
        sidebar_layout.addWidget(self.nav_list)

        # Add nav items
        for name in ["General", "Symbol Suggestions", "Backups", "Colors"]:
            item = QListWidgetItem(name)
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.nav_list.addItem(item)

        sidebar_layout.addStretch()
        layout.addWidget(sidebar)

        # ── Content Area ──
        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        self.content_layout = QVBoxLayout(content_frame)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(16)

        # Pages container
        self.pages_stack = QStackedWidget()
        self.pages_stack.setObjectName("pagesStack")
        self.content_layout.addWidget(self.pages_stack, stretch=1)

        # Bottom actions
        actions = QHBoxLayout()
        actions.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(cancel_btn)

        save_btn = QPushButton("Apply and Save")
        save_btn.setObjectName("primaryBtn")
        save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_btn.clicked.connect(self._apply_all)
        actions.addWidget(save_btn)

        self.content_layout.addLayout(actions)
        layout.addWidget(content_frame, stretch=1)

        # Build pages
        self._build_general_page()
        self._build_suggestions_page()
        self._build_backups_page()
        self._build_colors_page()

        self.nav_list.setCurrentRow(0)

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QWidget {
                font-family: "Segoe UI", "Arial", sans-serif;
                font-size: 13px;
            }
            #sidebar {
                background-color: #252525;
                border-right: 1px solid #333;
            }
            #sidebarHeader {
                color: #888;
                font-size: 11px;
                font-weight: bold;
                text-transform: uppercase;
                padding-bottom: 8px;
            }
            #navList {
                background: transparent;
                outline: none;
            }
            #navList::item {
                color: #aaa;
                padding: 10px 16px;
                border-left: 3px solid transparent;
            }
            #navList::item:selected {
                background-color: #2a2a2a;
                color: #fff;
                border-left: 3px solid #2980b9;
            }
            #navList::item:hover:!selected {
                background-color: #2d2d2d;
            }
            #contentFrame {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #e0e0e0;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 1px solid #555;
                background: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background: #2980b9;
                border-color: #3498db;
            }
            QRadioButton {
                color: #e0e0e0;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 1px solid #555;
                background: #2d2d2d;
            }
            QRadioButton::indicator:checked {
                background: #2980b9;
                border-color: #3498db;
            }
            QSpinBox {
                background: #2d2d2d;
                color: #f0f0f0;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 4px;
                min-width: 50px;
            }
            QLineEdit {
                background: #2d2d2d;
                color: #f0f0f0;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 6px 8px;
            }
            QLineEdit:focus {
                border-color: #2980b9;
            }
            #primaryBtn {
                background-color: #2980b9;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }
            #primaryBtn:hover {
                background-color: #3498db;
            }
            #secondaryBtn {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 8px 16px;
            }
            #secondaryBtn:hover {
                background-color: #4a4a4a;
            }
            QGroupBox {
                color: #aaa;
                font-weight: bold;
                border: 1px solid #333;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)

    # ── Page Builders ──

    def _make_page(self, name):
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.Shape.NoFrame)

        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        page.setWidget(widget)

        self.pages_stack.addWidget(page)
        self._pages[name] = page

        return layout

    def _show_page(self, name):
        if name in self._pages:
            self.pages_stack.setCurrentWidget(self._pages[name])

    def _switch_page(self, index):
        if index >= 0:
            self.pages_stack.setCurrentIndex(index)

    def _build_general_page(self):
        layout = self._make_page("General")

        # Always on top
        self.topmost_cb = self._make_checkbox("Keep Window Always on Top")
        layout.insertWidget(0, self.topmost_cb)

        # Theme placeholder
        theme_frame = QFrame()
        theme_frame.setObjectName("formArea")
        theme_layout = QHBoxLayout(theme_frame)
        theme_layout.setContentsMargins(12, 12, 12, 12)

        theme_label = QLabel("Theme:")
        theme_label.setStyleSheet("color: #aaa;")
        theme_layout.addWidget(theme_label)

        self.theme_display = QLabel("Dark (themes coming soon)")
        self.theme_display.setStyleSheet("color: #666; font-style: italic;")
        theme_layout.addWidget(self.theme_display)
        theme_layout.addStretch()

        layout.insertWidget(1, theme_frame)

        # Macro manager button
        macro_btn = QPushButton("⌨️ Manage Keypad Buttons")
        macro_btn.setObjectName("primaryBtn")
        macro_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        macro_btn.clicked.connect(self._open_macro_manager)
        layout.insertWidget(2, macro_btn)

    def _build_suggestions_page(self):
        layout = self._make_page("Symbol Suggestions")

        formula_count = len(getattr(self.parent, 'master_data', {}))
        suggestions_enabled = formula_count >= 6

        if not suggestions_enabled:
            warning = QLabel(
                f"⚠️ Smart Suggestions require at least 6 formulas "
                f"(you have {formula_count})"
            )
            warning.setStyleSheet("""
                background-color: #3d2e1e;
                color: #e0a040;
                padding: 12px;
                border-radius: 4px;
            """)
            layout.addWidget(warning)

        # Enable toggle
        self.suggest_cb = self._make_checkbox("Enable Smart Suggestions")
        self.suggest_cb.setEnabled(suggestions_enabled)
        layout.addWidget(self.suggest_cb)

        # Strictness section
        strict_frame = QFrame()
        strict_layout = QVBoxLayout(strict_frame)
        strict_layout.setContentsMargins(0, 0, 0, 0)
        strict_layout.setSpacing(8)

        strict_label = QLabel("Suggestion Strictness")
        strict_label.setStyleSheet("font-weight: bold; color: #aaa;")
        strict_layout.addWidget(strict_label)

        self.strictness_group = []

        for mode, desc in [
            ("Conservative", "Only suggest when meaning is guaranteed"),
            ("Balanced", "Suggest on strong context matches (Default)"),
            ("Aggressive", "Suggest near-context matches for speed")
        ]:
            row = QHBoxLayout()

            radio = QRadioButton(mode)
            radio.setEnabled(suggestions_enabled)
            self.strictness_group.append((mode, radio))
            row.addWidget(radio)

            desc_lbl = QLabel(f"— {desc}")
            desc_lbl.setStyleSheet("color: #888; font-size: 12px;")
            row.addWidget(desc_lbl)

            row.addStretch()
            strict_layout.addLayout(row)

        layout.addWidget(strict_frame)

        # Max suggestions
        count_frame = QHBoxLayout()

        count_label = QLabel("Max Suggestions:")
        count_label.setStyleSheet("color: #aaa;")
        count_frame.addWidget(count_label)

        self.max_suggestions_spin = QSpinBox()
        self.max_suggestions_spin.setRange(1, 5)
        self.max_suggestions_spin.setEnabled(suggestions_enabled)
        count_frame.addWidget(self.max_suggestions_spin)

        count_frame.addStretch()

        layout.addLayout(count_frame)

    def _build_backups_page(self):
        layout = self._make_page("Backups")

        self.backup_cb = self._make_checkbox("Enable backup file creation on launch")
        layout.insertWidget(0, self.backup_cb)

        info = QLabel(
            "Backups are stored as rotating .tmp files in your data directory.\n"
            "The oldest backup is overwritten each time."
        )
        info.setStyleSheet("color: #888; font-size: 12px;")
        layout.insertWidget(1, info)

    def _build_colors_page(self):
        layout = self._make_page("Colors")

        # Add new color
        add_frame = QFrame()
        add_frame.setObjectName("formArea")
        add_layout = QHBoxLayout(add_frame)
        add_layout.setContentsMargins(12, 12, 12, 12)
        add_layout.setSpacing(8)

        self.new_sub_name = QLineEdit()
        self.new_sub_name.setPlaceholderText("Subject name")
        add_layout.addWidget(self.new_sub_name, stretch=1)

        self.color_preview = QFrame()
        self.color_preview.setFixedSize(28, 28)
        self.color_preview.setStyleSheet(
            f"background: {self._selected_color}; border-radius: 4px; border: 1px solid #555;")
        add_layout.addWidget(self.color_preview)

        pick_btn = QPushButton("Pick")
        pick_btn.setObjectName("secondaryBtn")
        pick_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        pick_btn.clicked.connect(self._pick_color)
        add_layout.addWidget(pick_btn)

        add_btn = QPushButton("+ Add")
        add_btn.setObjectName("primaryBtn")
        add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_btn.clicked.connect(self._add_color)
        add_layout.addWidget(add_btn)

        layout.insertWidget(0, add_frame)

        # Color list
        self.color_list = QFrame()
        self.color_list_layout = QVBoxLayout(self.color_list)
        self.color_list_layout.setContentsMargins(0, 0, 0, 0)
        self.color_list_layout.setSpacing(6)
        self.color_list_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.color_list)
        layout.addWidget(scroll, stretch=1)

    # ── Helpers ──

    def _make_checkbox(self, text):
        cb = QCheckBox(text)
        cb.setStyleSheet("""
            QCheckBox {
                color: #e0e0e0;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 1px solid #555;
                background: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background: #2980b9;
                border-color: #3498db;
            }
        """)
        return cb

    def _refresh_color_list(self):
        while self.color_list_layout.count() > 1:
            item = self.color_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        colors = getattr(self.parent, 'subject_colors', {})

        for subject, color in colors.items():
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.setSpacing(10)

            name_lbl = QLabel(subject)
            name_lbl.setStyleSheet("color: #e0e0e0;")
            row_layout.addWidget(name_lbl, stretch=1)

            preview = QFrame()
            preview.setFixedSize(24, 24)
            preview.setStyleSheet(f"background: {color}; border-radius: 4px; border: 1px solid #555;")
            row_layout.addWidget(preview)

            change_btn = QPushButton("Change")
            change_btn.setObjectName("secondaryBtn")
            change_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            change_btn.clicked.connect(lambda checked, s=subject: self._change_color(s))
            row_layout.addWidget(change_btn)

            if subject not in ["Physics", "Chemistry", "Maths"]:
                del_btn = QPushButton("✕")
                del_btn.setObjectName("delBtn")
                del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                del_btn.clicked.connect(lambda checked, s=subject: self._delete_color(s))
                row_layout.addWidget(del_btn)

            row.setStyleSheet("""
                QFrame {
                    background-color: #252525;
                    border-radius: 4px;
                }
                QFrame:hover {
                    background-color: #2a2a2a;
                }
                #delBtn {
                    background: transparent;
                    color: #888;
                    border: none;
                    padding: 2px 8px;
                }
                #delBtn:hover {
                    color: #e74c3c;
                }
            """)

            self.color_list_layout.insertWidget(self.color_list_layout.count() - 1, row)

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self._selected_color), self, "Pick Color")
        if color.isValid():
            self._selected_color = color.name()
            self.color_preview.setStyleSheet(
                f"background: {self._selected_color}; border-radius: 4px; border: 1px solid #555;"
            )

    def _add_color(self):
        name = self.new_sub_name.text().strip()
        if not name:
            return

        self.parent.subject_colors[name] = self._selected_color
        self.new_sub_name.clear()
        self._selected_color = "#ffffff"
        self.color_preview.setStyleSheet(
            f"background: {self._selected_color}; border-radius: 4px; border: 1px solid #555;"
        )
        self._refresh_color_list()

    def _change_color(self, subject):
        current = self.parent.subject_colors.get(subject, "#ffffff")
        color = QColorDialog.getColor(QColor(current), self, f"Change Color for {subject}")
        if color.isValid():
            self.parent.subject_colors[subject] = color.name()
            self._refresh_color_list()

    def _delete_color(self, subject):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Remove color mapping for '{subject}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.parent.subject_colors.pop(subject, None)
            self._refresh_color_list()

    def _open_macro_manager(self):
        if hasattr(self.parent, 'windows') and isinstance(self.parent.windows, dict):
            macro_win = self.parent.windows.get("macro")
            if macro_win and macro_win.isVisible():
                macro_win.raise_()
                macro_win.activateWindow()
                return

        macro_window = MacroManagerWindow(self.parent)
        self.parent.windows["macro"] = macro_window
        macro_window.show()

    # ── Load / Save ──

    def _load_settings(self):
        self.topmost_cb.setChecked(getattr(self.parent, 'always_on_top', False))

        self.suggest_cb.setChecked(getattr(self.parent, 'enable_suggestions', True))

        strictness = getattr(self.parent, 'suggestion_strictness', 'Balanced')
        for mode, radio in self.strictness_group:
            radio.setChecked(mode == strictness)

        self.max_suggestions_spin.setValue(getattr(self.parent, 'max_suggestions', 3))

        self.backup_cb.setChecked(getattr(self.parent, 'enable_backups', True))

        self._refresh_color_list()

    def _apply_all(self):
        self.parent.always_on_top = self.topmost_cb.isChecked()
        self.parent.enable_suggestions = self.suggest_cb.isChecked()

        for mode, radio in self.strictness_group:
            if radio.isChecked():
                self.parent.suggestion_strictness = mode
                break

        self.parent.max_suggestions = self.max_suggestions_spin.value()
        self.parent.enable_backups = self.backup_cb.isChecked()

        self.parent.save_config()
        self.parent.apply_settings_live()

        show_notification("Settings saved!", "success")

        self.accept()

    def closeEvent(self, event):
        if hasattr(self.parent, 'windows') and isinstance(self.parent.windows, dict):
            self.parent.windows["settings"] = None
        event.accept()
