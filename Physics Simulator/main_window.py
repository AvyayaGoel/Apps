"""
ui/main_window.py – now uses a fixed, collapsible side panel instead of docks.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QMainWindow, QScrollArea, QSplitter, QVBoxLayout, QWidget

from config import SimulationConfig
from gl_widget import SandboxGLWidget
from property_panel import PropertyPanel
from scene import Scene
from toolbar import ToolbarPanel


class MainWindow(QMainWindow):
    def __init__(self, scene: Scene, config: SimulationConfig) -> None:
        super().__init__()
        self.setWindowTitle("3D Physics Sandbox")
        self.resize(1400, 900)
        self.setStyleSheet("""
            QMainWindow, QScrollArea, QWidget#sidePanel {
                background: #20242a;
                color: #eef2f6;
            }
            QToolButton {
                background: #30343b;
                color: #eef2f6;
                border: 1px solid #4a505a;
                border-radius: 4px;
                padding: 6px;
                font-weight: 600;
                text-align: left;
            }
            QFrame#collapsibleContent {
                background: #272c33;
                color: #eef2f6;
                border: 1px solid #454d58;
                border-top: 0;
            }
            QLabel, QCheckBox { color: #eef2f6; }
            QPushButton {
                background: #3a4452;
                color: #f6f8fa;
                border: 1px solid #667386;
                border-radius: 4px;
                padding: 5px 8px;
            }
            QPushButton:hover { background: #465367; }
            QPushButton:checked { background: #2d6cdf; }
            QSlider::groove:horizontal {
                height: 6px;
                background: #15181d;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #7fb0ff;
                border: 1px solid #d6e6ff;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QDoubleSpinBox, QComboBox {
                background: #15181d;
                color: #eef2f6;
                border: 1px solid #596372;
                padding: 3px;
            }
                background: #f3f4f6;
                border: 1px solid #c7ccd4;
                border-top: 0;
            }
        """)

        self.scene = scene
        self.config = config

        # Central widget is a horizontal splitter
        central = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(central)

        # Left panel: collapsible toolbox
        left_widget = QWidget()
        left_widget.setObjectName("sidePanel")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        self.toolbar = ToolbarPanel(scene, config)
        left_layout.addWidget(self.toolbar)
        left_layout.addStretch(1)
        left_scroll = QScrollArea()
        left_scroll.setWidget(left_widget)
        left_scroll.setWidgetResizable(True)
        left_scroll.setMinimumWidth(230)
        left_scroll.setMaximumWidth(360)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        central.addWidget(left_scroll)

        # GL widget
        self.gl_widget = SandboxGLWidget(scene, config, self)
        central.addWidget(self.gl_widget)

        # Right panel: properties with scroll
        right_widget = QWidget()
        right_widget.setObjectName("sidePanel")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self.property_panel = PropertyPanel(scene)
        right_layout.addWidget(self.property_panel)
        right_layout.addStretch(1)
        right_scroll = QScrollArea()
        right_scroll.setWidget(right_widget)
        right_scroll.setWidgetResizable(True)
        right_scroll.setMinimumWidth(250)
        right_scroll.setMaximumWidth(380)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        central.addWidget(right_scroll)

        # Set initial sizes
        central.setSizes([300, 820, 320])
        central.setStretchFactor(0, 0)
        central.setStretchFactor(1, 1)
        central.setStretchFactor(2, 0)

        self._build_status_bar()

        self.gl_widget.fps_updated.connect(self._on_fps_updated)
        self.gl_widget.object_count_changed.connect(self._on_object_count_changed)

        self.scene.reset_default_scene()

    def _build_status_bar(self) -> None:
        self.fps_label = QLabel("FPS: --")
        self.count_label = QLabel("Objects: 0")
        self.speed_label = QLabel("Sim speed: 1.0x")
        bar = self.statusBar()
        bar.addPermanentWidget(self.fps_label)
        bar.addPermanentWidget(self.count_label)
        bar.addPermanentWidget(self.speed_label)

    def _on_fps_updated(self, fps: float) -> None:
        self.fps_label.setText(f"FPS: {fps:0.0f}")

    def _on_object_count_changed(self, count: int) -> None:
        self.count_label.setText(f"Objects: {count}")
