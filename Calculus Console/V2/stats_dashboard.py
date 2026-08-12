"""
Statistics Dashboard v2 (PyQt6)
Knowledge collection overview with subject/topic hierarchy,
AND an Activity chart showing formula entries over time.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple, Callable

from PyQt6.QtCharts import (
    QChartView, QChart, QStackedBarSeries, QBarSet,
    QBarCategoryAxis, QValueAxis, QLegend
)
from PyQt6.QtCore import Qt, pyqtSignal, QMargins
from PyQt6.QtGui import QColor, QPainter, QPen, QCursor, QFont
from PyQt6.QtWidgets import (
    QDialog, QHeaderView, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QHBoxLayout, QPushButton, QFrame,
    QLabel, QProgressBar, QGraphicsDropShadowEffect,
    QSizePolicy, QLineEdit, QWidget, QTabWidget,
    QToolTip, QButtonGroup, QListWidget, QListWidgetItem,
)

from constants import DEFAULT_SUBJECT_COLORS
from formula_entry import FormulaCollection

logger = logging.getLogger(__name__)


# ── Helper Widgets ──────────────────────────────────────────────────

class MicroProgressBar(QProgressBar):
    def __init__(self, value: float, color: str = "#3B82F6", parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(int(value))
        self.setTextVisible(False)
        self.setFixedHeight(10)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"""
            QProgressBar {{
                background-color: #202020;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                min-width: 2px;
            }}
        """)


class MetricChip(QFrame):
    def __init__(self, label: str, value: str, accent_color: str = "#3B82F6", parent=None):
        super().__init__(parent)
        self.setObjectName("metricChip")
        self.setMinimumWidth(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self._label = QLabel(label.upper())
        self._label.setStyleSheet("color: #888; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(self._label)

        self._value = QLabel(value)
        self._value.setStyleSheet(f"color: {accent_color}; font-size: 28px; font-weight: bold;")
        layout.addWidget(self._value)

        self.setStyleSheet(f"""
            #metricChip {{
                background-color: #1C1C1C;
                border-radius: 10px;
                border: 1px solid #2A2A2A;
                border-left: 3px solid {accent_color};
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

    def set_value(self, text: str):
        self._value.setText(text)


class SegmentedControl(QFrame):
    """
    Pill-shaped segmented switcher (Daily / Monthly / Yearly), matching a
    native "iOS style" toggle group. Emits `changed(str)` with the value
    of the newly-active segment whenever the selection changes.
    """

    changed = pyqtSignal(str)

    def __init__(self, options: list[tuple[str, str]], default: str = "", parent=None):
        """
        options: list of (value, label) tuples, e.g. [("day", "Daily"), ...]
        """
        super().__init__(parent)
        self.setObjectName("segmentedControl")
        self._options = options
        self._value = default or options[0][0]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(0)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

        for value, label in options:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setMinimumHeight(30)
            btn.setChecked(value == self._value)
            btn.clicked.connect(lambda checked, v=value: self._select(v))
            self._group.addButton(btn)
            self._buttons[value] = btn
            layout.addWidget(btn)

        self.setStyleSheet("""
            #segmentedControl {
                background-color: #161616;
                border: 1px solid #2A2A2A;
                border-radius: 16px;
            }
            QPushButton {
                background-color: transparent;
                color: #8a8a8a;
                border: none;
                border-radius: 13px;
                padding: 5px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover:!checked {
                color: #c9c9c9;
                background-color: #202020;
            }
            QPushButton:checked {
                background-color: #2563EB;
                color: white;
            }
        """)

    def _select(self, value: str):
        if value == self._value:
            return
        self._value = value
        self.changed.emit(value)

    @property
    def value(self) -> str:
        return self._value

    def set_value(self, value: str, emit: bool = False):
        if value not in self._buttons:
            return
        self._value = value
        self._buttons[value].setChecked(True)
        if emit:
            self.changed.emit(value)


class YearMonthPicker(QWidget):
    """
    A single button that opens a compact "LeetCode style" popup: a year
    column and (optionally) a month column, side by side, both scrollable,
    with the current selection highlighted. Replaces two separate
    dropdowns with one picker so switching months is a single click
    inside one panel instead of hunting through a plain combo box.
    """

    changed = pyqtSignal(int, int)  # (year, month) — month is 0 when not shown

    def __init__(self, months_provider: Callable[[int], List[int]], parent=None):
        super().__init__(parent)
        self._months_provider = months_provider
        self._years: List[int] = []
        self._year: Optional[int] = None
        self._month: Optional[int] = None
        self._show_months = True
        self._popup: Optional[QFrame] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._btn = QPushButton("No data")
        self._btn.setObjectName("datePickerBtn")
        self._btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn.clicked.connect(self._toggle_popup)
        layout.addWidget(self._btn)

    # ── Public API ──

    def set_show_months(self, show_months: bool):
        self._show_months = show_months
        self._update_label()

    def set_years(self, years: List[int], selected_year: Optional[int] = None,
                  selected_month: Optional[int] = None):
        self._years = years
        self._year = selected_year if years else None
        self._month = selected_month if self._show_months else None
        self._update_label()
        self._btn.setEnabled(bool(years))

    def current(self) -> Tuple[Optional[int], Optional[int]]:
        return self._year, self._month

    # ── Internals ──

    def _update_label(self):
        if self._year is None:
            self._btn.setText("No data")
        elif self._show_months and self._month is not None:
            self._btn.setText(f"{self._year}-{self._month}")
        else:
            self._btn.setText(str(self._year))

    def _toggle_popup(self):
        if self._popup is not None:
            try:
                still_open = self._popup.isVisible()
            except RuntimeError:
                still_open = False
            if still_open:
                self._popup.close()
                return
            try:
                self._popup.deleteLater()
            except RuntimeError:
                pass
            self._popup = None
        self._open_popup()

    def _open_popup(self):
        if not self._years:
            return

        popup = QFrame(self, Qt.WindowType.Popup)
        popup.setObjectName("datePickerPopup")
        popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        popup.destroyed.connect(lambda: setattr(self, "_popup", None))

        outer = QHBoxLayout(popup)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        year_list = QListWidget()
        year_list.setObjectName("pickerList")
        year_list.setFixedWidth(76)
        year_list.setFixedHeight(220)
        for y in self._years:
            list_item = QListWidgetItem(str(y))
            list_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            year_list.addItem(list_item)
            if y == self._year:
                list_item.setSelected(True)
                year_list.setCurrentItem(list_item)
        outer.addWidget(year_list)

        month_list = None
        if self._show_months:
            month_list = QListWidget()
            month_list.setObjectName("pickerList")
            month_list.setFixedWidth(58)
            month_list.setFixedHeight(220)
            outer.addWidget(month_list)

            def populate_months(year: int):
                if month_list is None:
                    return
                month_list.clear()
                months = self._months_provider(year) or list(range(1, 13))
                current = self._month if self._month in months else months[-1]
                for m in months:
                    list_item = QListWidgetItem(str(m))
                    list_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    month_list.addItem(list_item)
                    if m == current:
                        list_item.setSelected(True)
                        month_list.setCurrentItem(list_item)
                if month_list.currentItem() is not None:
                    month_list.scrollToItem(month_list.currentItem())

            def on_month_clicked(list_item: QListWidgetItem):
                self._month = int(list_item.text())
                self._update_label()
                self.changed.emit(self._year, self._month)
                popup.close()

            populate_months(self._year if self._year is not None else self._years[-1])
            month_list.itemClicked.connect(on_month_clicked)

            def on_year_clicked(list_item: QListWidgetItem):
                self._year = int(list_item.text())
                populate_months(self._year)
        else:
            def on_year_clicked(list_item: QListWidgetItem):
                self._year = int(list_item.text())
                self._update_label()
                self.changed.emit(self._year, 0)
                popup.close()

        year_list.itemClicked.connect(on_year_clicked)

        popup.setStyleSheet("""
            #datePickerPopup {
                background-color: #1c1c1c;
                border: 1px solid #333;
                border-radius: 10px;
            }
            #pickerList {
                background-color: #1c1c1c;
                border: none;
                outline: none;
                font-size: 13px;
                color: #d5d5d5;
            }
            #pickerList::item {
                padding: 7px 4px;
                border-radius: 6px;
                margin: 1px 2px;
            }
            #pickerList::item:hover:!selected {
                background-color: #2a2a2a;
            }
            #pickerList::item:selected {
                background-color: #2563EB;
                color: white;
            }
        """)

        if year_list.currentItem() is not None:
            year_list.scrollToItem(year_list.currentItem())

        btn_rect = self._btn.rect()
        pos = self._btn.mapToGlobal(btn_rect.bottomLeft())
        popup.move(pos)
        popup.show()
        self._popup = popup


# ── Main Dashboard ──────────────────────────────────────────────────

class StatsDashboard(QDialog):
    METRIC_COLORS = {
        "total": "#3B82F6",
        "subjects": "#10B981",
        "topics": "#F59E0B",
    }

    def __init__(self, parent, master_data: FormulaCollection):
        super().__init__(parent.root if hasattr(parent, 'root') else parent)
        self.parent = parent
        self.master_data = master_data
        self._all_years: List[int] = []
        self._selected_year: Optional[int] = None
        self._selected_month: Optional[int] = None

        self.setWindowTitle("Knowledge Collection")
        self.setMinimumSize(820, 700)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self._build_ui()
        self._apply_styles()
        self._populate_hierarchy()
        self._on_granularity_changed()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # KPI CARDS
        metrics_layout = QHBoxLayout()
        self.metric_total = MetricChip("📚 Formulas", "0", self.METRIC_COLORS["total"])
        self.metric_subjects = MetricChip("🧪 Subjects", "0", self.METRIC_COLORS["subjects"])
        self.metric_topics = MetricChip("🗂 Topics", "0", self.METRIC_COLORS["topics"])
        metrics_layout.addWidget(self.metric_total)
        metrics_layout.addWidget(self.metric_subjects)
        metrics_layout.addWidget(self.metric_topics)
        main_layout.addLayout(metrics_layout)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("statsTabs")
        # ── Expand tabs to full width ──
        self.tabs.tabBar().setExpanding(True)
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #161616; border-radius: 10px; }
            QTabBar::tab {
                background: #1E1E1E;
                color: #888;
                padding: 10px 20px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 8px;
                min-width: 120px;
            }
            QTabBar::tab:selected { background: #2A2A2A; color: #e0e0e0; }
            QTabBar::tab:hover:!selected { background: #262626; }
        """)

        self.hierarchy_tab = self._build_hierarchy_tab()
        self.tabs.addTab(self.hierarchy_tab, "  Hierarchy  ")

        self.activity_tab = self._build_activity_tab()
        self.tabs.addTab(self.activity_tab, "  Activity  ")

        main_layout.addWidget(self.tabs, stretch=1)

    def _build_hierarchy_tab(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        expand_btn = QPushButton("📂 Expand All")
        expand_btn.setObjectName("toolbarBtn")
        expand_btn.clicked.connect(self._tree_expand_all)
        collapse_btn = QPushButton("📁 Collapse All")
        collapse_btn.setObjectName("toolbarBtn")
        collapse_btn.clicked.connect(self._tree_collapse_all)
        toolbar.addWidget(expand_btn)
        toolbar.addWidget(collapse_btn)
        toolbar.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setPlaceholderText("Search subjects or topics...")
        self.search_box.textChanged.connect(self._filter_tree)
        toolbar.addWidget(self.search_box)

        layout.addLayout(toolbar)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels([
            "Rank", "Subject / Topic", "Count", "Subject %", "Total %", "Distribution"
        ])
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(22)
        header = self.tree.header()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(0, 50)
        self.tree.setColumnWidth(2, 80)
        self.tree.setColumnWidth(3, 90)
        self.tree.setColumnWidth(4, 90)
        self.tree.setColumnWidth(5, 200)

        layout.addWidget(self.tree, stretch=1)
        return container

    def _build_activity_tab(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.granularity_switch = SegmentedControl(
            [("day", "Daily"), ("week", "Weekly"), ("month", "Monthly")],
            default="month",
        )
        self.granularity_switch.changed.connect(self._on_granularity_changed)
        controls.addWidget(self.granularity_switch)

        self.drilldown_frame = QFrame()
        drilldown_layout = QHBoxLayout(self.drilldown_frame)
        drilldown_layout.setContentsMargins(0, 0, 0, 0)
        drilldown_layout.setSpacing(6)

        period_lbl = QLabel("Period:")
        period_lbl.setObjectName("drilldownLabel")
        drilldown_layout.addWidget(period_lbl)

        self.date_picker = YearMonthPicker(months_provider=self._get_available_months_for_year)
        self.date_picker.changed.connect(self._on_date_picked)
        drilldown_layout.addWidget(self.date_picker)

        controls.addWidget(self.drilldown_frame)
        controls.addStretch()
        layout.addLayout(controls)

        # Chart card
        chart_card = QFrame()
        chart_card.setObjectName("chartCard")
        chart_card_layout = QVBoxLayout(chart_card)
        chart_card_layout.setContentsMargins(4, 4, 4, 4)

        shadow = QGraphicsDropShadowEffect(chart_card)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 4)
        chart_card.setGraphicsEffect(shadow)

        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setMinimumHeight(400)
        self.chart_view.setMouseTracking(True)
        chart_card_layout.addWidget(self.chart_view)

        layout.addWidget(chart_card, stretch=1)

        return container

    # ─── Hierarchy Population ───────────────────────────────────────

    def _populate_hierarchy(self):
        self.tree.clear()

        data_map: Dict[str, Dict[str, int]] = {}
        for entry in self.master_data.values():
            subj = entry.subject
            topic = entry.topic
            subj_dict = data_map.setdefault(subj, {})
            subj_dict[topic] = subj_dict.get(topic, 0) + 1

        total = len(self.master_data)
        unique_subjects = len(data_map)
        unique_topics = sum(len(x) for x in data_map.values())

        self.metric_total.set_value(str(total))
        self.metric_subjects.set_value(str(unique_subjects))
        self.metric_topics.set_value(str(unique_topics))

        sorted_subjects = sorted(
            data_map.items(),
            key=lambda item: sum(item[1].values()),
            reverse=True
        )
        medals = ["🥇", "🥈", "🥉"]

        for rank, (subj, topics) in enumerate(sorted_subjects):
            total_subj = sum(topics.values())
            subject_pct = (total_subj / total * 100) if total > 0 else 0

            color = "#3B82F6"
            if hasattr(self.parent, "subject_colors"):
                color = self.parent.subject_colors.get(subj, color)

            rank_text = medals[rank] if rank < 3 else f"#{rank + 1}"

            parent_item = QTreeWidgetItem(self.tree)
            parent_item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
            parent_item.setText(0, rank_text)
            parent_item.setText(1, subj)
            parent_item.setText(2, str(total_subj))
            parent_item.setText(3, "100%")
            parent_item.setText(4, f"{subject_pct:.1f}%")
            parent_item.setForeground(1, QColor(color))
            font = parent_item.font(0)
            font.setBold(True)
            parent_item.setFont(0, font)

            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bar = MicroProgressBar(subject_pct, color)
            container_layout.addWidget(bar)
            self.tree.setItemWidget(parent_item, 5, container)

            for topic, count in sorted(topics.items(), key=lambda x: x[1], reverse=True):
                subject_share = (count / total_subj * 100) if total_subj > 0 else 0
                total_share = (count / total * 100) if total > 0 else 0

                child = QTreeWidgetItem(parent_item)
                child.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
                child.setText(0, "")
                child.setText(1, topic)
                child.setText(2, str(count))
                child.setText(3, f"{subject_share:.1f}%")
                child.setText(4, f"{total_share:.1f}%")

                container = QWidget()
                layout = QHBoxLayout(container)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                bar = MicroProgressBar(subject_share, color)
                layout.addWidget(bar)
                self.tree.setItemWidget(child, 5, container)

        self.tree.expandAll()

    # ─── Activity Chart ─────────────────────────────────────────────

    def _get_available_years(self) -> List[int]:
        years = set()
        for entry in self.master_data.values():
            if entry.created_at:
                years.add(entry.created_at.year)
        return sorted(years)

    def _get_available_months_for_year(self, year: int) -> List[int]:
        months = set()
        for entry in self.master_data.values():
            if entry.created_at and entry.created_at.year == year:
                months.add(entry.created_at.month)
        return sorted(months)

    def _refresh_date_picker(self):
        years = self._get_available_years()
        self._all_years = years

        show_months = self.granularity_switch.value in ("day", "week")
        self.date_picker.set_show_months(show_months)

        if not years:
            self.date_picker.set_years([])
            self._selected_year = None
            self._selected_month = None
            return

        year = self._selected_year if self._selected_year in years else years[-1]
        month = None
        if show_months:
            months = self._get_available_months_for_year(year)
            month = self._selected_month if self._selected_month in months else (months[-1] if months else None)

        self._selected_year = year
        self._selected_month = month
        self.date_picker.set_years(years, selected_year=year, selected_month=month)

    def _on_granularity_changed(self):
        self.drilldown_frame.setVisible(True)
        self._refresh_date_picker()
        self._populate_chart()

    def _on_date_picked(self, year: int, month: int):
        self._selected_year = year
        self._selected_month = month if month else None
        self._populate_chart()

    def _get_date_range(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        min_dt = None
        max_dt = None
        for entry in self.master_data.values():
            if entry.created_at:
                dt = entry.created_at
                if min_dt is None or dt < min_dt:
                    min_dt = dt
                if max_dt is None or dt > max_dt:
                    max_dt = dt
        return min_dt, max_dt

    def _generate_periods(self, min_date: datetime, max_date: datetime, granularity: str) -> List[str]:
        periods = []
        if granularity == "month":
            year = self._selected_year
            if year is not None:
                for month in range(1, 13):
                    periods.append(f"{year}-{month:02d}")
            else:
                current = datetime(min_date.year, min_date.month, 1)
                end = datetime(max_date.year, max_date.month, 1)
                while current <= end:
                    periods.append(current.strftime("%Y-%m"))
                    if current.month == 12:
                        current = datetime(current.year + 1, 1, 1)
                    else:
                        current = datetime(current.year, current.month + 1, 1)
        elif granularity == "week":
            year = self._selected_year
            month = self._selected_month
            if year is not None and month is not None:
                if month == 12:
                    next_month = datetime(year + 1, 1, 1)
                else:
                    next_month = datetime(year, month + 1, 1)
                first_day = datetime(year, month, 1)
                last_day = next_month - timedelta(days=1)
                current = first_day
                while current <= last_day:
                    iso_year, iso_week, _ = current.isocalendar()
                    key = f"{iso_year}-W{iso_week:02d}"
                    if not periods or periods[-1] != key:
                        periods.append(key)
                    current += timedelta(days=1)
            else:
                current = min_date
                while current <= max_date:
                    iso_year, iso_week, _ = current.isocalendar()
                    key = f"{iso_year}-W{iso_week:02d}"
                    if not periods or periods[-1] != key:
                        periods.append(key)
                    current += timedelta(days=1)
        else:  # day
            year = self._selected_year
            month = self._selected_month
            if year is not None and month is not None:
                if month == 12:
                    next_month = datetime(year + 1, 1, 1)
                else:
                    next_month = datetime(year, month + 1, 1)
                first_day = datetime(year, month, 1)
                last_day = next_month - timedelta(days=1)
                current = first_day
                while current <= last_day:
                    periods.append(current.strftime("%Y-%m-%d"))
                    current += timedelta(days=1)
            else:
                current = min_date
                while current <= max_date:
                    periods.append(current.strftime("%Y-%m-%d"))
                    current += timedelta(days=1)
        return periods

    @staticmethod
    def _format_period_label(key: str, granularity: str, index: int, total: int) -> str:
        try:
            if granularity == "month":
                dt = datetime.strptime(key, "%Y-%m")
                return dt.strftime("%b '%y")
            elif granularity == "week":
                return f"W{index + 1}"
            else:
                dt = datetime.strptime(key, "%Y-%m-%d")
                return dt.strftime("%d").lstrip("0") or "0"
        except ValueError:
            return key

    @staticmethod
    def _format_period_display(key: str, granularity: str) -> str:
        try:
            if granularity == "month":
                return datetime.strptime(key, "%Y-%m").strftime("%B %Y")
            elif granularity == "week":
                iso_year, iso_week = key.split("-W")
                monday = datetime.fromisocalendar(int(iso_year), int(iso_week), 1)
                sunday = monday + timedelta(days=6)
                if monday.month == sunday.month:
                    return f"{monday.strftime('%b')} {monday.day}–{sunday.day}, {monday.year}"
                return f"{monday.strftime('%b')} {monday.day} – {sunday.strftime('%b')} {sunday.day}, {sunday.year}"
            else:
                return datetime.strptime(key, "%Y-%m-%d").strftime("%d %B %Y")
        except ValueError:
            return key

    def _on_bar_hover(self, status: bool, index: int, bar_set: QBarSet,
                      subject: str, periods: List[str], granularity: str):
        if not status:
            QToolTip.hideText()
            return
        if index < 0 or index >= len(periods):
            return
        value = int(bar_set.at(index))
        if value <= 0:
            QToolTip.hideText()
            return
        period_display = self._format_period_display(periods[index], granularity)
        noun = "formula" if value == 1 else "formulas"
        QToolTip.showText(
            QCursor.pos(),
            f"{subject} — {period_display}\n{value} {noun}",
            self.chart_view,
        )

    # ── Chart building split into smaller functions ──

    def _build_chart_data(self, periods: List[str], granularity: str):
        raw_data: Dict[str, Dict[str, int]] = {}
        for entry in self.master_data.values():
            if not entry.created_at:
                continue
            dt = entry.created_at
            if granularity == "day":
                key = dt.strftime("%Y-%m-%d")
            elif granularity == "month":
                key = dt.strftime("%Y-%m")
            else:  # week
                iso_year, iso_week, _ = dt.isocalendar()
                key = f"{iso_year}-W{iso_week:02d}"
            raw_data.setdefault(key, {})
            subj = entry.subject
            raw_data[key][subj] = raw_data[key].get(subj, 0) + 1

        all_subjects = set()
        for period_data in raw_data.values():
            all_subjects.update(period_data.keys())

        subject_counts = {s: [] for s in sorted(all_subjects)}
        for period in periods:
            counts = raw_data.get(period, {})
            for s in subject_counts:
                subject_counts[s].append(counts.get(s, 0))

        return raw_data, all_subjects, subject_counts

    def _configure_axes(self, periods: List[str], subject_counts: Dict[str, List[int]],
                        granularity: str) -> Tuple[QBarCategoryAxis, QValueAxis, int]:
        period_labels = []
        total = len(periods)
        for i, p in enumerate(periods):
            label = self._format_period_label(p, granularity, i, total)
            period_labels.append(label)

        axis_label_font = QFont("Segoe UI", 9)
        title_font = QFont("Segoe UI", 10)
        title_font.setBold(True)

        categories = QBarCategoryAxis()
        categories.append(period_labels)
        categories.setTitleText(granularity.capitalize())
        categories.setTitleBrush(QColor("#8a8a8a"))
        categories.setTitleFont(title_font)
        categories.setLabelsColor(QColor("#b0b0b0"))
        categories.setLabelsFont(axis_label_font)
        categories.setLinePen(QPen(QColor("#2A2A2A"), 1))
        categories.setGridLineVisible(False)

        y_axis = QValueAxis()
        y_axis.setTitleText("Formulas")
        y_axis.setTitleBrush(QColor("#8a8a8a"))
        y_axis.setTitleFont(title_font)
        y_axis.setLabelsColor(QColor("#b0b0b0"))
        y_axis.setLabelsFont(axis_label_font)
        y_axis.setMin(0)

        if subject_counts:
            period_totals = [
                sum(subject_counts[s][i] for s in subject_counts)
                for i in range(len(periods))
            ]
            max_count = max(period_totals)
        else:
            max_count = 1
        y_axis.setMax(max_count + 1)
        y_axis.applyNiceNumbers()
        y_axis.setGridLineVisible(True)
        y_axis.setGridLinePen(QPen(QColor(255, 255, 255, 18), 1, Qt.PenStyle.DashLine))
        y_axis.setLinePen(QPen(Qt.GlobalColor.transparent))

        return categories, y_axis, max_count

    def _populate_chart(self):
        self.chart_view.setChart(QChart())

        try:
            granularity = self.granularity_switch.value
            min_date, max_date = self._get_date_range()

            if min_date is None or max_date is None:
                chart = QChart()
                chart.setTitle("No formulas with timestamps")
                chart.setTitleBrush(QColor("#e0e0e0"))
                chart.setBackgroundVisible(False)
                self.chart_view.setChart(chart)
                return

            periods = self._generate_periods(min_date, max_date, granularity)
            if not periods:
                chart = QChart()
                chart.setTitle("No periods to display")
                chart.setTitleBrush(QColor("#e0e0e0"))
                chart.setBackgroundVisible(False)
                self.chart_view.setChart(chart)
                return

            _, all_subjects, subject_counts = self._build_chart_data(periods, granularity)

            subject_colors = dict(DEFAULT_SUBJECT_COLORS)
            if hasattr(self.parent, "subject_colors"):
                subject_colors.update(self.parent.subject_colors)
            fallback_palette = ["#e67e22", "#1abc9c", "#e74c3c", "#f1c40f", "#9b59b6", "#2ecc71"]
            fallback_idx = 0

            bar_sets = []
            for subject in sorted(all_subjects):
                bar_set = QBarSet(subject)
                if subject in subject_colors:
                    color = QColor(subject_colors[subject])
                else:
                    color = QColor(fallback_palette[fallback_idx % len(fallback_palette)])
                    fallback_idx += 1
                bar_set.setColor(color)
                no_pen = QPen(Qt.GlobalColor.transparent)
                bar_set.setPen(no_pen)
                for val in subject_counts[subject]:
                    bar_set.append(val)
                bar_set.hovered.connect(
                    lambda status, index, bs=bar_set, subj=subject:
                    self._on_bar_hover(status, index, bs, subj, periods, granularity)
                )
                bar_sets.append(bar_set)

            series = QStackedBarSeries()
            for bs in bar_sets:
                series.append(bs)

            series.setLabelsVisible(False)
            bar_width = {"day": 0.4, "week": 0.65, "month": 0.7}.get(granularity, 0.7)
            series.setBarWidth(bar_width)

            categories, y_axis, _ = self._configure_axes(periods, subject_counts, granularity)

            chart = QChart()
            chart.addSeries(series)
            chart.addAxis(categories, Qt.AlignmentFlag.AlignBottom)
            chart.addAxis(y_axis, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(categories)
            series.attachAxis(y_axis)

            chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
            chart.setDropShadowEnabled(True)
            chart.setTheme(QChart.ChartTheme.ChartThemeLight)
            chart.setBackgroundBrush(QColor(20, 20, 20))
            chart.setBackgroundVisible(True)
            chart.setMargins(QMargins(8, 8, 8, 8))
            chart.setTitle("Formula Activity")
            title_font = QFont("Segoe UI", 12)
            title_font.setBold(True)
            chart.setTitleFont(title_font)
            chart.setTitleBrush(QColor("#e8e8e8"))

            legend = chart.legend()
            legend.setVisible(True)
            legend.setAlignment(Qt.AlignmentFlag.AlignBottom)
            legend.setLabelColor(QColor("#c9c9c9"))
            legend.setFont(QFont("Segoe UI", 9))
            legend.setBackgroundVisible(False)
            legend.setMarkerShape(QLegend.MarkerShape.MarkerShapeCircle)

            chart.setPlotAreaBackgroundVisible(True)
            chart.setPlotAreaBackgroundBrush(QColor(255, 255, 255, 6))
            chart.setPlotAreaBackgroundPen(QPen(Qt.PenStyle.NoPen))

            self.chart_view.setChart(chart)
            self.chart_view.setRubberBand(QChartView.RubberBand.NoRubberBand)

        except Exception as e:
            logger.exception(f"Chart creation failed: {e}")
            chart = QChart()
            chart.setTitle(f"Chart Error: {str(e)}")
            chart.setTitleBrush(QColor("#e74c3c"))
            chart.setBackgroundVisible(False)
            self.chart_view.setChart(chart)

    # ─── Tree Controls ──────────────────────────────────────────────

    def _filter_tree(self):
        text = self.search_box.text().lower()
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            parent_visible = text in parent.text(1).lower()
            child_visible = False
            for j in range(parent.childCount()):
                child = parent.child(j)
                visible = text in child.text(1).lower()
                child.setHidden(not visible)
                child_visible |= visible
            parent.setHidden(not (parent_visible or child_visible))

    def _tree_expand_all(self):
        self.tree.expandAll()

    def _tree_collapse_all(self):
        self.tree.collapseAll()

    # ─── Styles ──────────────────────────────────────────────────────

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #121212; }
            QWidget { font-family: "Segoe UI", "Consolas", sans-serif; font-size: 13px; }
            #toolbarBtn {
                background-color: #1F1F1F;
                color: #888;
                border: 1px solid #2F2F2F;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: bold;
            }
            #toolbarBtn:hover { background-color: #2A2A2A; border-color: #3B82F6; color: #e0e0e0; }
            #toolbarBtn:pressed { background-color: #2563EB; color: white; }
            QTreeWidget {
                background-color: #161616;
                color: #e0e0e0;
                border: 1px solid #2A2A2A;
                border-radius: 10px;
                outline: none;
                padding: 4px;
            }
            QTreeWidget::item {
                padding: 8px 6px;
                border-bottom: 1px solid #202020;
                min-height: 32px;
            }
            QTreeWidget::item:selected { background-color: #2563EB; }
            QTreeWidget::item:hover:!selected { background-color: #1E1E1E; }
            QHeaderView::section {
                background-color: #1E1E1E;
                color: #B0B0B0;
                padding: 10px;
                border: none;
                border-bottom: 1px solid #2A2A2A;
                font-weight: bold;
            }
            #datePickerBtn {
                background-color: #1E1E1E;
                color: #e0e0e0;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 600;
                min-width: 70px;
            }
            #datePickerBtn:hover {
                border-color: #3B82F6;
                background-color: #242424;
            }
            #datePickerBtn:disabled {
                color: #555;
            }
            QLineEdit {
                background-color: #181818;
                color: #F5F5F5;
                border: 1px solid #303030;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QLineEdit:focus { border-color: #3B82F6; }
            QChartView {
                background: transparent;
            }
            #chartCard {
                background-color: #161616;
                border: 1px solid #262626;
                border-radius: 14px;
            }
            #drilldownLabel {
                color: #888;
                font-size: 12px;
            }
            QToolTip {
                background-color: #202020;
                color: #f0f0f0;
                border: none;
                border-radius: 0px;
                padding: 6px 10px;
                font-size: 12px;
            }
        """)

    def closeEvent(self, event):
        if hasattr(self.parent, 'secret_movement'):
            self.parent.secret_movement("close_stats")
        if hasattr(self.parent, 'windows') and isinstance(self.parent.windows, dict):
            self.parent.windows["stats"] = None
        event.accept()
