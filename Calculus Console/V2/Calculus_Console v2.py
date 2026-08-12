#!/usr/bin/env python3
"""
Calculus Console v2 — Formula Knowledge Manager

A desktop application for organizing, searching, and managing mathematical,
scientific, and engineering formulas with an integrated SQLite database.

Core Features
-------------
- Formula CRUD: Create, read, update, and delete formulas with rich metadata
  (subject, topic, sub-topic, notes, tags, and variable definitions).
- Hierarchical Filtering: Real-time search with cascading subject → topic →
  sub-topic filters and tag-based discovery.
- Smart Suggestions: SymbolLearner engine suggests variable names and units
  based on historical usage patterns.
- Math Symbol Keypad: Floating non-modal keypad with Greek letters, operators,
  superscripts/subscripts, and user-defined macros.
- Export Suite: Export formulas to HTML, PDF, CSV, JSON, Markdown, or plain
  text with hierarchical selection.
- Statistics Dashboard: Visual breakdown of formula distribution across
  subjects and topics with progress indicators.
- Achievement System: Tiered awards (Common → Cosmic) and secret unlocks
  based on usage patterns and hidden criteria.
- Milestone Narrative: Progressive narrative system with entity reflection
  sequence triggered at formula count thresholds.

Architecture
------------
- Frontend: PyQt6 widgets with custom stylesheets (dark theme).
- Backend: SQLite via DatabaseManager with automatic backup rotation.
- State: JSON-based config (user_env.sys) and tip state
  (runtime_log.bin).
- Data Model: master_data dict mapping formula IDs to dicts with
  main_info (list), variables (list), and tags (list).

Key Classes
-----------
- CalculusConsoleV2: Main window, menubar, table, filters, pagination.
- FormulaDialog: Modal dialog for formula entry/edit with ghost suggestions.
- FormulaDetailsDialog: Frameless overlay showing formula analysis.
- ReflectionOverlay: Cinematic narrative overlay for the 150-formula entity.
- MilestoneBanner: Animated slide-in toast for milestone notifications.
- FormulaRenderWidget: Custom QWidget for math formula rendering.

Entry Point
-----------
Run python Calculus_Console_v2.py to launch the application.

Author
------
Avyaya Goel · Class 11
"""

import logging
import os
import shutil
import sys
from typing import Dict, List, Optional

from PyQt6.QtCore import (
    Qt, QTimer
)
from PyQt6.QtGui import (
    QAction, QKeySequence, QColor, QPalette, QIntValidator,
    QShortcut, QIcon
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMenu, QStatusBar, QMessageBox, QFrame,
    QDialog, QTextEdit, QSizePolicy
)

from aux_widgets import FormulaDetailsDialog, ReflectionOverlay, MilestoneBanner
from award_panel import AwardPanel
# ---------------------------------------------------------------------------
# Local imports – all pre-converted PyQt6 modules
# ---------------------------------------------------------------------------
from constants import (
    DB_NAME, CONFIG_NAME, TIP_NAME, BACKUP_NAMES,
    DEFAULT_SUBJECT_COLORS,
    SYSTEM_LOCKED_MSG, SYSTEM_LOCKED_TRY_AGAIN_MSG,
    SYSTEM_LOCKED_NOTHING_SAVES_MSG, SYSTEM_LOCKED_NICE_TRY_MSG,
    NO_FORMULA_SELECTED, ALL_SUBJECTS, ALL_TOPICS, ALL_SUB_TOPICS,
    ICON_PATH
)
from database_manager import DatabaseManager
from export_dialog import ExportDialog
from formula_dialog import FormulaDialog
from formula_entry import FormulaEntry, FormulaCollection
from formula_utils import FormulaUtils
from keypad_manager import KeypadManager
from macro_manager_window import MacroManagerWindow
from milestone_manager import MilestoneManager
from notification_manager import manage_notifications, show_notification
from settings_window import SettingsWindow
from stats_dashboard import StatsDashboard
from symbol_learner import SymbolLearner
from trash_dialog import TrashDialog

logging.basicConfig(
    filename="calculus_console_v2.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# =============================================================================
# Main Window
# =============================================================================

class CalculusConsoleV2(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Calculus Console v2")
        self.setMinimumSize(800, 700)
        self.resize(1000, 800)
        self.setWindowIcon(QIcon(ICON_PATH))
        self._setup_paths()

        self.master_data = FormulaCollection()
        self.display_to_db_id_map: Dict[int, int] = {}
        self.subject_colors = DEFAULT_SUBJECT_COLORS.copy()
        self.user_macros: List[dict] = []
        self.tip_state = FormulaUtils.load_tip_state(self.tip_file)

        self.enable_backups = True
        self.enable_suggestions = True
        self.suggestion_strictness = "Balanced"
        self.max_suggestions = 3
        self.always_on_top = False

        self.windows: Dict[str, Optional[QWidget]] = {
            "macro": None, "keypad": None, "stats": None,
            "settings": None, "awards": None, "admin": None,  # Add this
        }
        self.in_reflection_mode = False
        self._active_banner: Optional[MilestoneBanner] = None
        self.current_page = 1
        self.items_per_page = 10

        self._setup_managers()
        self._build_menubar()
        self._build_central_ui()
        self._build_statusbar()
        self._apply_global_styles()
        self._load_data()
        self._finalize_startup()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_paths(self):
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        self.primary_dir = os.path.join(appdata, "Microsoft", "CLR", "Metadata")
        self.fallback_dir = os.path.join(appdata, "CalculusConsole")
        self.data_dir = self.primary_dir if os.path.exists(self.primary_dir) else self.fallback_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self.db_file = os.path.join(self.data_dir, DB_NAME)
        self.config_file = os.path.join(self.data_dir, CONFIG_NAME)
        self.tip_file = os.path.join(self.data_dir, TIP_NAME)
        self.backup_slots = [os.path.join(self.data_dir, b) for b in BACKUP_NAMES]
        self.all_data_dirs = [self.primary_dir, self.fallback_dir]

    def _setup_managers(self):
        self.db_manager = DatabaseManager(self.db_file)
        self.symbol_learner = SymbolLearner()
        self.milestone_manager = MilestoneManager(self.tip_state, parent=self)
        self._connect_milestone_signals()
        self.keypad_manager = KeypadManager(insert_text_callback=self.insert_text, user_macros=self.user_macros)
        manage_notifications(self)

    def _connect_milestone_signals(self):
        mm = self.milestone_manager
        mm.banner_requested.connect(self._on_milestone_banner)
        mm.toast_requested.connect(lambda msg, bs: show_notification(msg, bs, 4000))
        mm.glitch_requested.connect(lambda txt: show_notification(txt, "warning", 2500))
        mm.award_unlocked.connect(lambda t, d: show_notification(f"🏆 {t}\\n{d}", "success", 5000))
        mm.secret_unlocked.connect(lambda: show_notification("🏆 SECRET AWARD\\nSTABILITY MAINTAINED", "danger", 6000))
        mm.state_modified.connect(self.save_tip_state)
        mm.ui_lock_changed.connect(self._set_reflection_lock)
        mm.entity_banner_show.connect(self._show_entity_banner)
        mm.entity_banner_hide.connect(self._hide_entity_banner)
        mm.entity_prompt_show.connect(self._show_entity_prompt)
        mm.entity_prompt_hide.connect(self._hide_entity_prompt)
        mm.entity_options_ready.connect(self._show_entity_options)
        mm.entity_bottom_bar_show.connect(self._show_entity_bottom_bar)
        mm.entity_bottom_bar_hide.connect(self._hide_entity_bottom_bar)

    # ------------------------------------------------------------------
    # Menubar
    # ------------------------------------------------------------------

    def _build_menubar(self):
        menubar = self.menuBar()
        if menubar:
            menubar.setNativeMenuBar(False)

            file_menu = menubar.addMenu("File")
            if file_menu:
                file_menu.addAction(self._action("📄 Export…", self.open_export, "Ctrl+Shift+E"))

            formula_menu = menubar.addMenu("Formula")
            if formula_menu:
                formula_menu.addAction(self._action("➕ New Formula", self.add_formula, "Ctrl+N"))
                formula_menu.addAction(self._action("✎ Edit Formula", self.edit_formula, "Ctrl+E"))
                formula_menu.addAction(self._action("🗑 Delete Formula", self.delete_formula, "Delete"))
                formula_menu.addAction(self._action("↩ Restore Deleted", self.open_trash, "Ctrl+Shift+D"))
                formula_menu.addSeparator()
                formula_menu.addAction(self._action("🔍 View Details", self.view_details, "Ctrl+Return"))

            view_menu = menubar.addMenu("View")
            if view_menu:
                view_menu.addAction(self._action("📊 Statistics", self.open_stats, "Ctrl+Shift+S"))
                view_menu.addAction(self._action("🏅 Awards", self.open_awards, "Ctrl+Shift+A"))
                view_menu.addSeparator()
                view_menu.addAction(self._action("⌨ Toggle Keypad", self.toggle_keypad, "Ctrl+K", True))
                view_menu.addAction(self._action("📌 Always on Top", self.toggle_always_on_top))

            tools_menu = menubar.addMenu("Tools")
            if tools_menu:
                tools_menu.addAction(self._action("⛭ Settings", self.open_settings, "Ctrl+,"))
                tools_menu.addAction(self._action("⌨ Manage Macros", self.open_macros, "Ctrl+M"))

            help_menu = menubar.addMenu("Help")
            if help_menu:
                help_menu.addAction(self._action("About", self.show_about))

    def _action(self, text: str, slot, shortcut: str | None = None, _global: bool = False) -> QAction:
        act = QAction(text, self)
        act.triggered.connect(slot)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        if _global:
            act.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        return act

    # ------------------------------------------------------------------
    # Central UI
    # ------------------------------------------------------------------

    def _build_central_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Filter Bar
        filter_bar = QFrame()
        filter_bar.setObjectName("filterBar")
        fl = QHBoxLayout(filter_bar)
        fl.setContentsMargins(12, 10, 12, 10)
        fl.setSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Search formulas, subjects, topics…")
        self.search_edit.setMinimumWidth(280)
        self.search_edit.textChanged.connect(self._apply_filters_and_pagination)
        fl.addWidget(self.search_edit, stretch=2)

        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self._focus_search_bar)

        self.slash_shortcut = QShortcut(QKeySequence("/"), self)
        self.slash_shortcut.activated.connect(self._focus_search_bar)

        self.filter_subject = QComboBox()
        self.filter_subject.setPlaceholderText(ALL_SUBJECTS)
        self.filter_subject.setMinimumWidth(100)
        self.filter_subject.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.filter_subject.currentTextChanged.connect(self._on_filter_subject_changed)
        fl.addWidget(self.filter_subject, stretch=1)

        self.filter_topic = QComboBox()
        self.filter_topic.setPlaceholderText(ALL_TOPICS)
        self.filter_topic.setMinimumWidth(100)
        self.filter_topic.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.filter_topic.currentTextChanged.connect(self._on_filter_topic_changed)
        fl.addWidget(self.filter_topic, stretch=1)

        self.filter_subtopic = QComboBox()
        self.filter_subtopic.setPlaceholderText(ALL_SUB_TOPICS)
        self.filter_topic.setMinimumWidth(100)
        self.filter_topic.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.filter_subtopic.currentTextChanged.connect(self._apply_filters_and_pagination)
        fl.addWidget(self.filter_subtopic, stretch=1)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("secondaryBtn")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_filters)
        fl.addWidget(clear_btn)

        layout.addWidget(filter_bar)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        for icon, tip, cb in [
            ("➕", "New Formula (Ctrl+N)", self.add_formula),
            ("✎", "Edit Formula (Ctrl+E)", self.edit_formula),
            ("🗑", "Delete Formula (Del)", self.delete_formula),
            ("🔍", "View Details (Ctrl+Enter)", self.view_details)
        ]:
            btn = QPushButton(icon)
            btn.setToolTip(tip)
            btn.setFixedSize(36, 36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("toolBtn")
            btn.clicked.connect(cb)
            toolbar.addWidget(btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # -- Table --
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["#", "Formula", "Subject", "Topic", "Sub-Topic", "Vars"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 160)
        self.table.setColumnWidth(4, 160)
        self.table.setColumnWidth(5, 50)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_context_menu)
        self.table.doubleClicked.connect(self.edit_formula)
        layout.addWidget(self.table, stretch=1)

        # -- Pagination Bar --
        pag_bar = QFrame()
        pag_bar.setObjectName("pagBar")
        pl = QHBoxLayout(pag_bar)
        pl.setContentsMargins(8, 8, 8, 8)
        pl.setSpacing(6)

        self.first_page_btn = QPushButton("«")
        self.first_page_btn.setFixedWidth(40)
        self.first_page_btn.setToolTip("First page")
        self.first_page_btn.clicked.connect(self.go_to_first_page)
        pl.addWidget(self.first_page_btn)

        self.prev_page_btn = QPushButton("‹")
        self.prev_page_btn.setFixedWidth(36)
        self.prev_page_btn.setToolTip("Previous page")
        self.prev_page_btn.clicked.connect(self.go_to_prev_page)
        pl.addWidget(self.prev_page_btn)

        self.page_entry = QLineEdit()
        self.page_entry.setFixedWidth(50)
        self.page_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_entry.setText("1")
        self.page_entry.returnPressed.connect(self.on_page_entry_changed)
        pl.addWidget(self.page_entry)

        self.page_label = QLabel("of 1")
        pl.addWidget(self.page_label)

        self.next_page_btn = QPushButton("›")
        self.next_page_btn.setFixedWidth(36)
        self.next_page_btn.setToolTip("Next page")
        self.next_page_btn.clicked.connect(self.go_to_next_page)
        pl.addWidget(self.next_page_btn)

        self.last_page_btn = QPushButton("»")
        self.last_page_btn.setFixedWidth(40)
        self.last_page_btn.setToolTip("Last page")
        self.last_page_btn.clicked.connect(self.go_to_last_page)
        pl.addWidget(self.last_page_btn)

        pl.addSpacing(16)

        pl.addStretch()

        self.result_count_lbl = QLabel("0 formulas")
        self.result_count_lbl.setStyleSheet("color: #888;")
        pl.addWidget(self.result_count_lbl)

        layout.addWidget(pag_bar)

        # Reflection Overlay
        self.reflection_overlay = ReflectionOverlay(
            parent=central,
            main_window=self
        )
        self.reflection_overlay.setGeometry(100, 120, self.width() - 200, 300)

    def _build_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.status_filter = QLabel("")
        self.statusbar.addPermanentWidget(self.status_filter)

    def _apply_global_styles(self):
        self.setStyleSheet("""
            /* ---------------- Main Window ---------------- */
            QMainWindow {
                background-color: #121212;
            }

            QWidget {
                font-family: "Segoe UI", "Inter", Arial;
                font-size: 13px;
                color: #ECECEC;
            }

            /* ---------------- Containers ---------------- */
            #filterBar, #pagBar {
                background-color: #1C1C1C;
                border: 1px solid #2A2A2A;
                border-radius: 10px;
            }

            /* ---------------- Input Fields ---------------- */
            QLineEdit {
                background-color: #181818;
                color: #F5F5F5;
                border: 1px solid #303030;
                border-radius: 8px;
                padding: 8px 10px;
                selection-background-color: #3B82F6;
            }

            QLineEdit:focus {
                border: 1px solid #3B82F6;
                background-color: #1E1E1E;
            }

            /* ---------------- Combo Boxes ---------------- */
            QComboBox {
                background-color: #181818;
                color: #F5F5F5;
                border: 1px solid #303030;
                border-radius: 8px;
                padding: 6px 8px;
            }

            QComboBox:hover {
                border: 1px solid #3B82F6;
            }

            QComboBox::drop-down {
                border: none;
                width: 24px;
            }

            QComboBox QAbstractItemView {
                background-color: #1C1C1C;
                color: white;
                border: 1px solid #303030;
                selection-background-color: #3B82F6;
            }

            /* ---------------- Table ---------------- */
            QTableWidget {
                background-color: #161616;
                border: 1px solid #2A2A2A;
                border-radius: 10px;
                gridline-color: #202020;
                selection-background-color: #2563EB;
                alternate-background-color: #1B1B1B;
                padding: 4px;
            }

            QTableWidget::item {
                padding: 10px;
                border: none;
            }

            QTableWidget::item:selected {
                background-color: #2563EB;
                color: white;
            }

            QTableWidget::item:hover:!selected {
                background-color: #222222;
            }

            /* ---------------- Table Headers ---------------- */
            QHeaderView::section {
                background-color: #1E1E1E;
                color: #B0B0B0;
                padding: 10px;
                border: none;
                border-bottom: 1px solid #2A2A2A;
                font-weight: bold;
            }

            /* ---------------- Toolbar Buttons ---------------- */
            #toolBtn {
                background-color: #1F1F1F;
                color: white;
                border: 1px solid #2F2F2F;
                border-radius: 8px;
                font-size: 16px;
            }

            #toolBtn:hover {
                background-color: #2A2A2A;
                border: 1px solid #3B82F6;
            }

            #toolBtn:pressed {
                background-color: #2563EB;
            }

            /* ---------------- Secondary Buttons ---------------- */
            #secondaryBtn {
                background-color: #222222;
                color: white;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 8px 16px;
            }

            #secondaryBtn:hover {
                background-color: #2D2D2D;
                border: 1px solid #3B82F6;
            }

            /* ---------------- Pagination Buttons ---------------- */
            QPushButton {
                background-color: #1F1F1F;
                border: 1px solid #303030;
                border-radius: 6px;
                padding: 6px;
            }

            QPushButton:hover {
                background-color: #2B2B2B;
            }

            QPushButton:pressed {
                background-color: #2563EB;
            }

            /* ---------------- Menu Bar ---------------- */
            QMenuBar {
                background-color: #181818;
                color: white;
                border-bottom: 1px solid #2A2A2A;
            }

            QMenuBar::item {
                padding: 8px 14px;
                background: transparent;
            }

            QMenuBar::item:selected {
                background-color: #2563EB;
                border-radius: 4px;
            }

            /* ---------------- Dropdown Menus ---------------- */
            QMenu {
                background-color: #1C1C1C;
                color: white;
                border: 1px solid #2A2A2A;
            }

            QMenu::item {
                padding: 8px 20px;
            }

            QMenu::item:selected {
                background-color: #2563EB;
            }

            /* ---------------- Status Bar ---------------- */
            QStatusBar {
                background-color: #181818;
                color: #9A9A9A;
                border-top: 1px solid #2A2A2A;
            }

            /* ---------------- Scrollbars ---------------- */
            QScrollBar:vertical {
                background: #181818;
                width: 10px;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical {
                background: #404040;
                border-radius: 5px;
                min-height: 25px;
            }

            QScrollBar::handle:vertical:hover {
                background: #5A5A5A;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar:horizontal {
                background: #181818;
                height: 10px;
            }

            QScrollBar::handle:horizontal {
                background: #404040;
                border-radius: 5px;
            }

            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def _load_data(self):
        self._load_from_db()
        self.load_config()
        self.refresh_table()
        self._refresh_filter_combos()
        self.symbol_learner.learn(self.master_data)
        self.current_page = 1
        self._apply_filters_and_pagination()

    def _finalize_startup(self):
        count = len(self.master_data)
        self.create_backup()
        self._run_startup_garbage_collection()
        QTimer.singleShot(100, lambda: self.milestone_manager.process_count(count, self.master_data))

    def _run_startup_garbage_collection(self):
        """Permanently delete formulas that have been soft-deleted for over 30 days."""
        try:
            deleted_count = self.db_manager.garbage_collect_deleted()
            if deleted_count > 0:
                logging.info(f"Garbage collected {deleted_count} old deleted formulas")
        except Exception as e:
            logging.exception(f"Startup garbage collection failed: {e}")

    def _load_from_db(self):
        self.master_data.clear()
        try:
            formulas = self.db_manager.get_all_formulas()
            for f in formulas:
                db_id = f["db_id"]
                tags = self.db_manager.get_formula_tags(db_id)
                entry = FormulaEntry.from_db_row(f, db_id, tags)
                self.master_data.add(entry)
        except Exception as e:
            logging.exception(f"DB load failed: {e}")
            self._recover_from_backup()

    def _recover_from_backup(self):
        newest = None
        latest = -1
        for slot in self.backup_slots:
            if os.path.exists(slot) and os.path.getmtime(slot) > latest:
                latest = os.path.getmtime(slot)
                newest = slot
        if newest:
            try:
                if os.path.exists(self.db_file):
                    os.remove(self.db_file)
                shutil.copy2(newest, self.db_file)
                self.db_manager = DatabaseManager(self.db_file)
                self._load_from_db()
                show_notification("Recovered from backup", "warning")
            except Exception as e:
                logging.critical(f"Recovery failed: {e}")

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    def apply_settings_live(self):
        """
        Apply updated settings immediately without restart.
        """

        # Always on top
        self.setWindowFlag(
            Qt.WindowType.WindowStaysOnTopHint,
            self.always_on_top
        )
        self.show()

        # Update child windows
        self.update_child_windows_topmost()

        # Update keypad macros
        self.keypad_manager.update_macros(self.user_macros)

        # Refresh table colors if subject colors changed
        self.apply_row_colors()

        # Refresh UI if suggestion settings changed
        self.symbol_learner.learn(self.master_data)

    def load_config(self):
        """Load configuration from file, apply settings to local state, and update UI components."""
        cfg = FormulaUtils.load_config(self.config_file)
        self.enable_backups = cfg.get("backups", True)
        self.enable_suggestions = cfg.get("suggestions", True)
        self.suggestion_strictness = cfg.get("suggestion_strictness", "Balanced")
        self.max_suggestions = cfg.get("max_suggestions", 3)
        self.user_macros = cfg.get("macros", [])
        self.always_on_top = cfg.get("always_on_top", False)
        self.subject_colors = cfg.get("subject_colors", DEFAULT_SUBJECT_COLORS.copy())
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.always_on_top)
        self.show()
        self.keypad_manager.update_macros(self.user_macros)

    def save_config(self):
        """Serialize and write the current application settings to the configuration file."""
        FormulaUtils.save_config(
            self.config_file, self.enable_backups,
            self.enable_suggestions, self.suggestion_strictness,
            self.max_suggestions, self.user_macros, self.always_on_top,
            self.subject_colors
        )

    def save_tip_state(self):
        FormulaUtils.save_tip_state(self.tip_file, self.tip_state)

    # ------------------------------------------------------------------
    # Table & Filtering
    # ------------------------------------------------------------------
    def _adjust_table_row_layout(self):
        """
        Always make exactly 10 rows fill the visible table area.
        Rows auto-resize when window size changes.
        """

        visible_rows = self.items_per_page  # always 10

        viewport_height = self.table.viewport().height()

        if viewport_height <= 0:
            return

        # Divide available space evenly across rows
        row_height = max(30, viewport_height // visible_rows)

        # Tell table header to use this fixed size automatically
        self.table.verticalHeader().setDefaultSectionSize(row_height)

        # Optional font scaling
        font_size = max(10, min(16, int(row_height * 0.35)))

        font = self.table.font()
        font.setPointSize(font_size)
        self.table.setFont(font)

    def refresh_table(self):
        self._apply_filters_and_pagination()

    def _add_table_row(self, db_id: int, entry: FormulaEntry):
        row = self.table.rowCount()
        self.table.insertRow(row)
        items = [
            QTableWidgetItem(str(db_id)),
            QTableWidgetItem(entry.formula_text),
            QTableWidgetItem(entry.subject),
            QTableWidgetItem(entry.topic),
            QTableWidgetItem(entry.display_sub_topic),
            QTableWidgetItem(str(entry.var_count)),
        ]
        for col, it in enumerate(items):
            it.setData(Qt.ItemDataRole.UserRole, db_id)
            self.table.setItem(row, col, it)

    def apply_row_colors(self):
        for row in range(self.table.rowCount()):
            subj_item = self.table.item(row, 2)
            if not subj_item:
                continue
            color = self.subject_colors.get(subj_item.text().strip(), "#cccccc")
            for col in range(self.table.columnCount()):
                it = self.table.item(row, col)
                if it:
                    it.setForeground(QColor(color))

    def _refresh_filter_combos(self) -> None:
        """Populate filter dropdowns from current master_data."""
        subjects = self.master_data.subjects()
        self._topics_by_subject = self.master_data.topics_by_subject()
        self._subs_by_topic = self.master_data.subtopics_by_topic()

        current_sub = self.filter_subject.currentText()
        self.filter_subject.blockSignals(True)
        self.filter_subject.clear()
        self.filter_subject.addItem(ALL_SUBJECTS)
        self.filter_subject.addItems(sorted(subjects | {"Physics", "Chemistry", "Maths"}))
        if current_sub:
            self.filter_subject.setCurrentText(current_sub)
        self.filter_subject.blockSignals(False)

    def _on_filter_subject_changed(self, text: str):
        self.filter_topic.blockSignals(True)
        self.filter_topic.clear()
        self.filter_topic.addItem(ALL_TOPICS)
        if text and text != ALL_SUBJECTS:
            self.filter_topic.addItems(sorted(self._topics_by_subject.get(text, set())))
        self.filter_topic.blockSignals(False)
        self.filter_subtopic.blockSignals(True)
        self.filter_subtopic.clear()
        self.filter_subtopic.addItem(ALL_SUB_TOPICS)
        self.filter_subtopic.blockSignals(False)
        self._apply_filters_and_pagination()

    def _on_filter_topic_changed(self, text: str):
        subj = self.filter_subject.currentText()
        self.filter_subtopic.blockSignals(True)
        self.filter_subtopic.clear()
        self.filter_subtopic.addItem(ALL_SUB_TOPICS)
        if subj and subj != ALL_SUBJECTS and text and text != ALL_TOPICS:
            self.filter_subtopic.addItems(sorted(self._subs_by_topic.get((subj, text), set())))
        self.filter_subtopic.blockSignals(False)
        self._apply_filters_and_pagination()

    def _apply_filters_and_pagination(self):
        self.filtered_formulas = self._get_filtered_ids()
        self.current_page = self._clamp_page(self.current_page)

        self._populate_table()
        self._update_pagination_controls()
        self._update_status_labels()

    def _focus_search_bar(self):
        focused = QApplication.focusWidget()
        if focused is self.search_edit:
            return
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _get_filtered_ids(self) -> List[int]:
        search = self.search_edit.text().strip().lower()
        f_subj = self.filter_subject.currentText()
        f_topic = self.filter_topic.currentText()
        f_sub = self.filter_subtopic.currentText()
        return self.master_data.filter(search, f_subj, f_topic, f_sub)

    def _clamp_page(self, page: int) -> int:
        """Ensure page number is within valid range."""
        total = self.get_total_pages()
        return max(1, min(page, total))

    def _populate_table(self):
        start = (self.current_page - 1) * self.items_per_page
        page_ids = self.filtered_formulas[start:start + self.items_per_page]
        self.table.setRowCount(0)
        self.display_to_db_id_map.clear()
        for db_id in page_ids:
            self.display_to_db_id_map[db_id] = db_id
            self._add_table_row(db_id, self.master_data[db_id])
        self.apply_row_colors()

    def _update_pagination_controls(self):
        """Update page buttons and entry field."""
        total_pages = self.get_total_pages()

        self.page_entry.setText(str(self.current_page))
        self.page_label.setText(f"of {total_pages}")
        self.page_entry.setValidator(QIntValidator(1, max(1, total_pages), self))

        has_prev = self.current_page > 1
        has_next = self.current_page < total_pages
        self.first_page_btn.setEnabled(has_prev)
        self.prev_page_btn.setEnabled(has_prev)
        self.next_page_btn.setEnabled(has_next)
        self.last_page_btn.setEnabled(has_next)

    def _update_status_labels(self):
        """Update status bar and result count labels."""
        total = len(self.master_data)
        filtered = len(self.filtered_formulas)
        self.status_filter.setText(f"Showing {filtered} of {total}")
        self.result_count_lbl.setText(f"{filtered} results")
        self._adjust_table_row_layout()

    def _clear_filters(self):
        self.search_edit.clear()
        self.filter_subject.setCurrentIndex(0)
        self.filter_topic.clear()
        self.filter_subtopic.clear()
        self._apply_filters_and_pagination()

    def _table_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        col = self.table.columnAt(pos.x())
        if col < 0:
            return

        self.table.selectRow(row)
        menu = QMenu(self)

        menu.addAction("Edit", self.edit_formula)
        menu.addAction("View Details", self.view_details)
        menu.addSeparator()

        if col in (2, 3, 4):
            item = self.table.item(row, col)
            if item:
                value = item.text().strip()
                if value:
                    col_names = {2: "Subject", 3: "Topic", 4: "Sub-Topic"}
                    action_text = f"Filter by {col_names[col]} → '{value}'"
                    # Capture current row and col in lambda
                    menu.addAction(action_text, lambda r=row, c=col: self._filter_by_column(r, c))
                    menu.addSeparator()

        menu.addAction("Delete", self.delete_formula)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _filter_by_column(self, row: int, col: int):
        """Set filters based on clicked cell, cascading correctly."""
        item = self.table.item(row, col)
        if not item:
            return

        # Retrieve the formula entry
        display_id = item.data(Qt.ItemDataRole.UserRole)
        if display_id is None or display_id not in self.master_data:
            return
        entry = self.master_data[display_id]

        # Block signals to prevent multiple refreshes
        self.filter_subject.blockSignals(True)
        self.filter_topic.blockSignals(True)
        self.filter_subtopic.blockSignals(True)

        # 1. Set Subject
        self.filter_subject.setCurrentText(entry.subject)
        # Manually populate Topic list based on Subject
        self.filter_topic.clear()
        self.filter_topic.addItem(ALL_TOPICS)
        topics = self._topics_by_subject.get(entry.subject, set())
        self.filter_topic.addItems(sorted(topics))

        # 2. If filtering by Topic or Sub‑Topic, set Topic
        if col in (3, 4):
            self.filter_topic.setCurrentText(entry.topic)
            # Manually populate Sub‑Topic list based on (Subject, Topic)
            self.filter_subtopic.clear()
            self.filter_subtopic.addItem(ALL_SUB_TOPICS)
            subs = self._subs_by_topic.get((entry.subject, entry.topic), set())
            self.filter_subtopic.addItems(sorted(subs))
            if col == 4:
                self.filter_subtopic.setCurrentText(entry.sub_topic)
            else:
                # Topic filter only – clear sub‑topic selection
                self.filter_subtopic.setCurrentText(ALL_SUB_TOPICS)
        else:
            # Subject only – clear Topic and Sub‑Topic
            self.filter_topic.setCurrentText(ALL_TOPICS)
            self.filter_subtopic.clear()
            self.filter_subtopic.addItem(ALL_SUB_TOPICS)
            self.filter_subtopic.setCurrentText(ALL_SUB_TOPICS)

        # Unblock signals
        self.filter_subject.blockSignals(False)
        self.filter_topic.blockSignals(False)
        self.filter_subtopic.blockSignals(False)

        # Apply filters once
        self._apply_filters_and_pagination()

    def selected_db_id(self) -> Optional[int]:
        items = self.table.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.ItemDataRole.UserRole)

    def get_total_pages(self):
        return max(1, (len(self.filtered_formulas) + self.items_per_page - 1) // self.items_per_page)

    # --- Pagination navigation ---

    def go_to_first_page(self):
        self.current_page = 1
        self._apply_filters_and_pagination()

    def go_to_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._apply_filters_and_pagination()

    def go_to_next_page(self):
        total = self.get_total_pages()
        if self.current_page < total:
            self.current_page += 1
            self._apply_filters_and_pagination()

    def go_to_last_page(self):
        self.current_page = self.get_total_pages()
        self._apply_filters_and_pagination()

    def on_page_entry_changed(self):
        try:
            page = int(self.page_entry.text().strip())
            total = self.get_total_pages()
            if page < 1:
                page = 1
            elif page > total:
                page = total
            self.current_page = page
            self._apply_filters_and_pagination()
        except ValueError:
            self.page_entry.setText(str(self.current_page))

    def _jump_to_formula_page(self, db_id: int):
        """After save/delete, jump to the page containing this formula."""
        for idx, fid in enumerate(self.filtered_formulas):
            if fid == db_id:
                self.current_page = (idx // self.items_per_page) + 1
                return
        self.current_page = 1

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------

    def add_formula(self):
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_NOTHING_SAVES_MSG, "danger")
            return
        dialog = FormulaDialog(
            parent=self, edit_data=None, master_data=self.master_data,
            symbol_learner=self.symbol_learner, max_suggestions=self.max_suggestions
        )
        dialog.finished.connect(lambda result: self._on_dialog_finished(result, dialog, is_edit=False))
        dialog.open()

    def _on_dialog_finished(self, result_code, dialog, is_edit):
        if result_code == QDialog.DialogCode.Accepted:
            result = dialog.get_result()
            if result:
                self._save_formula_result(result, is_edit=is_edit)

    def edit_formula(self):
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_TRY_AGAIN_MSG, "danger")
            return
        db_id = self.selected_db_id()
        if db_id is None or db_id not in self.master_data:
            show_notification(NO_FORMULA_SELECTED, "warning")
            return
        dialog = FormulaDialog(
            parent=self, edit_data=self.master_data[db_id],
            master_data=self.master_data, symbol_learner=self.symbol_learner,
            max_suggestions=self.max_suggestions
        )
        dialog.finished.connect(lambda result: self._on_dialog_finished(result, dialog, is_edit=True))
        dialog.open()

    def _save_formula_result(self, result: dict, is_edit: bool):
        """Save or update a formula result."""
        if not is_edit and self.milestone_manager.check_secret_code(result["field"], result["topic"]):
            show_notification("…", "warning")
            return

        try:
            if is_edit and result["id"] is not None:
                self._update_existing_formula(result)
            else:
                self._add_new_formula(result)
            self._post_data_change()
        except Exception as e:
            logging.exception(f"Save error: {e}")
            show_notification("Failed to save formula", "danger")

    def _update_existing_formula(self, result: dict):
        """Update an existing formula in the database and master_data."""
        display_id = result["id"]
        entry = self.master_data.get(display_id)
        if not entry:
            show_notification("Formula not found", "danger")
            return

        db_id = entry.db_id
        if db_id is None or not isinstance(db_id, int):
            show_notification("Formula database ID missing or invalid", "danger")
            return

        success = self.db_manager.update_formula(
            db_id,
            result["formula"], result["field"],
            result["topic"], result["sub_topic"], result["notes"], result["variables"]
        )

        if not success:
            show_notification("Failed to update formula", "danger")
            return

        self.db_manager.replace_formula_tags(db_id, result.get("tags", []))
        self._update_master_data_entry(display_id, db_id, result)
        show_notification(f"Formula updated: {result['formula']}", "success")

    def _add_new_formula(self, result: dict):
        """Add a new formula to the database and master_data."""
        db_id = self.db_manager.add_formula(
            result["formula"], result["field"], result["topic"],
            result["sub_topic"], result["notes"], result["variables"],
        )
        if not db_id:
            show_notification("Failed to save formula", "danger")
            return

        self.db_manager.add_formula_tags(db_id, result.get("tags", []))

        new_formula = self.db_manager.get_formula(db_id)
        display_id = new_formula["id"] if new_formula else db_id

        self._update_master_data_entry(display_id, db_id, result)
        show_notification(f"Formula saved: #{display_id}", "success")
        self.milestone_manager.record_movement("save_formula")

    def _update_master_data_entry(self, display_id, db_id: int, result: dict):
        entry = FormulaEntry.from_dialog_result(result, display_id, db_id)
        self.master_data.add(entry)

    def _post_data_change(self):
        self.symbol_learner.learn(self.master_data)
        self._load_from_db()
        self.refresh_table()
        self._refresh_filter_combos()
        count = len(self.master_data)
        self.milestone_manager.process_count(count, self.master_data)

    def delete_formula(self):
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_TRY_AGAIN_MSG, "danger")
            return

        display_id = self.selected_db_id()
        if display_id is None or display_id not in self.master_data:
            show_notification(NO_FORMULA_SELECTED, "warning")
            return

        entry = self.master_data[display_id]
        db_id = entry.db_id
        if db_id is None or not isinstance(db_id, int):
            show_notification("Invalid formula database ID", "danger")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete", f"Delete formula #{display_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            success = self.db_manager.soft_delete_formula(db_id)
            if success:
                # Remove from master_data immediately for UI
                self.master_data.remove(display_id)

                # Rebuild display IDs since numbering may have shifted
                self._load_from_db()

                self.refresh_table()
                self._refresh_filter_combos()
                count = len(self.master_data)
                self.milestone_manager.process_count(count, self.master_data)

                # Show undo-capable notification
                show_notification(
                    f"Formula #{display_id} deleted.",
                    "warning",
                    5000
                )
            else:
                show_notification("Failed to delete formula", "danger")
        except Exception as e:
            logging.exception(f"Delete error: {e}")
            show_notification("Error deleting formula", "danger")

    def view_details(self):
        db_id = self.selected_db_id()
        if db_id is None or db_id not in self.master_data:
            show_notification(NO_FORMULA_SELECTED, "warning")
            return
        dlg = FormulaDetailsDialog(self, self.master_data[db_id], self.subject_colors)
        dlg.exec()

    # ------------------------------------------------------------------
    # Dialog Launchers
    # ------------------------------------------------------------------

    def open_export(self):
        if not self.master_data:
            show_notification("No formulas to export", "warning")
            return
        dlg = ExportDialog(self, self.master_data)
        dlg.exec()

    def open_stats(self):
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_MSG, "danger")
            return
        if self.windows["stats"] and self.windows["stats"].isVisible():
            self.windows["stats"].raise_()
            self.windows["stats"].activateWindow()
            return
        self.windows["stats"] = StatsDashboard(self, self.master_data)
        self.windows["stats"].show()
        self.milestone_manager.record_movement("open_stats")

    def open_awards(self):
        if self.windows["awards"] and self.windows["awards"].isVisible():
            self.windows["awards"].raise_()
            self.windows["awards"].activateWindow()
            return

        formula_count = len(self.master_data)
        if formula_count < 30:
            QMessageBox.warning(
                self,
                "ACCESS DENIED",
                (
                    "You are not worthy enough to access the Award Panel.\n\n"
                    f"Formulas Discovered: {formula_count}/30\n\n"
                    "Continue extracting knowledge until the threshold is reached."
                )
            )
            return

        self.windows["awards"] = AwardPanel(self)
        self.windows["awards"].show()

    def open_settings(self):
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_NOTHING_SAVES_MSG, "danger")
            return
        if self.windows["settings"] and self.windows["settings"].isVisible():
            self.windows["settings"].raise_()
            self.windows["settings"].activateWindow()
            return
        self.windows["settings"] = SettingsWindow(self)
        self.windows["settings"].show()

    def open_trash(self):
        """Open Recently Deleted dialog for restoring or permanently deleting formulas."""
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_MSG, "danger")
            return

        deleted = self.db_manager.get_deleted_formulas(limit=50)
        if not deleted:
            show_notification("No recently deleted formulas", "info")
            return

        dlg = TrashDialog(self, deleted, self._handle_restore, self._handle_perma_delete)
        dlg.exec()

    def _handle_restore(self, db_ids: list[int]) -> bool:
        """Restore soft-deleted formulas and refresh UI."""
        success = self._bulk_db_operation(db_ids, self.db_manager.restore_formula)
        if success:
            self._refresh_after_data_change()
            show_notification(f"Restored {len(db_ids)} formula(s)", "success")
        else:
            show_notification("Some formulas failed to restore", "warning")
        return success

    def _handle_perma_delete(self, db_ids: list[int]) -> bool:
        """Permanently delete formulas."""
        success = self._bulk_db_operation(db_ids, self.db_manager.hard_delete_formula)
        if success:
            show_notification(f"Deleted {len(db_ids)} formula(s) permanently", "success")
        else:
            show_notification("Some formulas failed to delete", "warning")
        return success

    @staticmethod
    def _bulk_db_operation(db_ids: list[int], operation) -> bool:
        """Execute a database operation on multiple IDs. Returns True if all succeed."""
        success = True
        for db_id in db_ids:
            if not operation(db_id):
                success = False
        return success

    def _refresh_after_data_change(self):
        """Reload data, refresh table, update filters, and process milestones."""
        self._load_from_db()
        self.refresh_table()
        self._refresh_filter_combos()
        count = len(self.master_data)
        self.milestone_manager.process_count(count, self.master_data)

    def open_macros(self):
        if self.windows["macro"] and self.windows["macro"].isVisible():
            self.windows["macro"].raise_()
            self.windows["macro"].activateWindow()
            return
        self.windows["macro"] = MacroManagerWindow(self)
        self.windows["macro"].show()

    def toggle_keypad(self):
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_MSG, "danger")
            return
        opened = self.keypad_manager.toggle(parent_widget=self)
        self.windows["keypad"] = getattr(self.keypad_manager, "_window") if opened else None

    def toggle_always_on_top(self):
        self.always_on_top = not self.always_on_top
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.always_on_top)
        self.show()
        self.save_config()
        self.update_child_windows_topmost()
        state = "enabled" if self.always_on_top else "disabled"
        show_notification(f"Always on top {state}", "info")

    def show_about(self):
        QMessageBox.about(
            self, "About",
            "<h2>Calculus Console v2</h2>"
            "<p><b>Save. Organize. Discover.</b></p>"
            "<p>· Smart symbol suggestions<br>"
            "· Hierarchical filtering &amp; tagging<br>"
            "· Export to HTML, PDF, JSON &amp; more</p>"
            "<p style='color:#888;font-style:italic;'>This app is deeper than it looks.<br>"
            "The deeper you go, the deeper it gets.</p>"
            "<p><b>Created by Avyaya Goel</b> · Class 11</p>"
        )

    # ------------------------------------------------------------------
    # Keypad Insertion (works globally across all windows)
    # ------------------------------------------------------------------

    @staticmethod
    def insert_text(text: str, warp: int = 0):
        focused = QApplication.focusWidget()
        if isinstance(focused, QLineEdit):
            cursor = focused.cursorPosition()
            focused.insert(text)
            if warp > 0:
                focused.setCursorPosition(cursor + len(text) - warp)
        elif isinstance(focused, QTextEdit):
            tc = focused.textCursor()
            tc.insertText(text)
            focused.setTextCursor(tc)

    # ------------------------------------------------------------------
    # Milestone & Reflection Delegation
    # ------------------------------------------------------------------

    def _on_milestone_banner(self, text: str, tier: str):
        banner = MilestoneBanner(self, text, tier)
        banner.show()

    def _set_reflection_lock(self, locked: bool):
        self.in_reflection_mode = locked
        self.table.setEnabled(not locked)
        for w in [self.search_edit, self.filter_subject, self.filter_topic, self.filter_subtopic]:
            w.setEnabled(not locked)
        if locked:
            self.reflection_overlay.setGeometry(
                80, 100, self.width() - 160, self.height() - 200
            )
            self.reflection_overlay.show()
            self.reflection_overlay.raise_()
        else:
            self.reflection_overlay.hide()
            self.reflection_overlay.clear()

    def _show_entity_banner(self, text: str, corrupted: bool = False):
        self.reflection_overlay.set_banner(text, corrupted)

    def _hide_entity_banner(self):
        self.reflection_overlay.hide_banner()

    def _show_entity_prompt(self, text: str):
        self.reflection_overlay.set_prompt(text)

    def _show_entity_options(self, options: List[str]):
        self.reflection_overlay.set_options(options)

    def _hide_entity_prompt(self):
        self.reflection_overlay.hide_prompt()

    def _show_entity_bottom_bar(self):
        self.reflection_overlay.show_bottom_bar()

    def _hide_entity_bottom_bar(self):
        self.reflection_overlay.hide_bottom_bar()

    # ------------------------------------------------------------------
    # Secret Award Delegation
    # ------------------------------------------------------------------

    def get_secret_award_state(self) -> dict:
        return self.milestone_manager.get_secret_award_state()

    def milestone_seen(self, key: str) -> bool:
        return self.tip_state.setdefault("shown", {}).get(key, False)

    def secret_movement(self, action: str):
        self.milestone_manager.record_movement(action)

    # ------------------------------------------------------------------
    # Child Window Sync
    # ------------------------------------------------------------------

    def update_child_windows_topmost(self):
        flag = self.always_on_top
        for key in ["stats", "awards", "settings", "macro"]:
            win = self.windows.get(key)
            if win and win.isVisible():
                win.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, flag)
                win.show()

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def create_backup(self):
        if not self.enable_backups or not os.path.exists(self.db_file):
            return
        oldest = FormulaUtils.find_oldest_backup_slot(self.backup_slots)
        try:
            self.db_manager.backup_database(oldest)
        except Exception as e:
            logging.exception(f"Backup failed: {e}")

    # ------------------------------------------------------------------
    # Window Events
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_NICE_TRY_MSG, "danger")
            event.ignore()
            return
        self.save_config()
        self.save_tip_state()
        self.db_manager.close()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)

        self._adjust_table_row_layout()

        if self.reflection_overlay.isVisible():
            self.reflection_overlay.setGeometry(
                80, 100, self.width() - 160, self.height() - 200
            )


# =============================================================================
# Entry Point
# =============================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#1e1e1e"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#e0e0e0"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#252525"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#2a2a2a"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2d2d2d"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#e0e0e0"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#e0e0e0"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#3a3a3a"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#e0e0e0"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#2980b9"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)

    window = CalculusConsoleV2()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
