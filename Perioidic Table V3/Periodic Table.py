"""
Periodic Table Explorer V3
A modern PyQt6-based periodic table application with comprehensive element data.
"""

import difflib
import json
import math
import os
import sys
from functools import lru_cache
from typing import List, Callable

from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QRadialGradient, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QLineEdit, QFrame, QScrollArea,
    QSplitter, QStatusBar, QSizePolicy,
    QGraphicsDropShadowEffect, QListWidget, QListWidgetItem
)

from Periodic_Table_Data import (elements_data, category_colors, category_names,
                                 STYLESHEET_FRAME_1, COLOR_WHITE, FONT, COLOR_2,
                                 STYLESHEET_FRAME_2)


def get_shell_distribution(atomic_number: int) -> List[int]:
    """Calculate electron shell distribution."""
    capacities = [2, 8, 18, 32, 32, 18, 8]
    shells = []
    temp_z = atomic_number
    for cap in capacities:
        if temp_z <= 0:
            break
        val = min(temp_z, cap)
        shells.append(val)
        temp_z -= val
    return shells


@lru_cache(maxsize=None)
def get_spdf_config(atomic_number: int) -> str:
    """Get electron configuration in SPDF notation."""
    if not isinstance(atomic_number, int):
        return "N/A"
    orbitals = [
        ("1s", 2), ("2s", 2), ("2p", 6), ("3s", 2), ("3p", 6), ("4s", 2),
        ("3d", 10), ("4p", 6), ("5s", 2), ("4d", 10), ("5p", 6), ("6s", 2),
        ("4f", 14), ("5d", 10), ("6p", 6), ("7s", 2), ("5f", 14), ("6d", 10), ("7p", 6)
    ]
    sup = {"0": "", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹"}
    config = []
    remaining = atomic_number
    for name, capacity in orbitals:
        if remaining <= 0:
            break
        fill = min(remaining, capacity)
        fill_str = "".join(sup[digit] for digit in str(fill))
        config.append(f"{name}{fill_str}")
        remaining -= fill
    return " ".join(config)


class ElementButton(QPushButton):
    """Custom button for periodic table elements with rich HTML display."""
    clicked_with_symbol = pyqtSignal(str)

    def __init__(self, element_data: dict, parent=None):
        super().__init__(parent)
        self.element_data = element_data
        self.symbol = element_data.get("symbol", "")
        self.atomic_number = element_data.get("atomic_number")
        self.category = element_data.get("category", "unknown")
        self.name = element_data.get("name", "")
        self.mass = element_data.get("mass_number", "")
        self.setup_ui()
        self.clicked.connect(self.on_clicked)

    def setup_ui(self):
        """Setup button with actual HTML rendering."""

        # Button sizing
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.setMinimumSize(65, 65)
        self.setMaximumSize(90, 90)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Remove default text because QLabel will handle rendering
        self.setText("")

        # Create internal layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # HTML label
        self.content_label = QLabel()
        self.content_label.setTextFormat(Qt.TextFormat.RichText)
        self.content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_label.setWordWrap(False)

        # Prevent label from blocking clicks
        self.content_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )

        # Transparent background
        self.content_label.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
            }
        """)

        # Main element display
        if self.atomic_number:
            html_text = f"""
            <div style="
                text-align:center;
                color:white;
                font-family:Segoe UI;
                line-height:1.0;
            ">

                <div style="
                    font-size:10px;
                    text-align:left;
                    font-weight:bold;
                    color:rgba(255,255,255,0.85);
                    padding-left:2px;
                ">
                    {self.atomic_number}
                </div>

                <div style="
                    font-size:22px;
                    font-weight:bold;
                    margin-top:-2px;
                    margin-bottom:2px;
                ">
                    {self.symbol}
                </div>

                <div style="
                    font-size:8px;
                    color:rgba(255,255,255,0.85);
                ">
                    {self.name[:12]}
                </div>

                <div style="
                    font-size:7px;
                    color:rgba(255,255,255,0.65);
                ">
                    {self.mass}
                </div>

            </div>
            """
        else:
            # For Lanthanides / Actinides labels
            html_text = f"""
            <div style="
                text-align:center;
                font-size:11px;
                font-weight:bold;
                color:white;
            ">
                {self.symbol}
            </div>
            """

        self.content_label.setText(html_text)
        layout.addWidget(self.content_label)

        # Set category color
        color = category_colors.get(self.category, "#95A5A6")
        self.update_style(color)

        # Tooltip
        self._setup_tooltip()

    def _setup_tooltip(self):
        """Setup rich HTML tooltip."""
        atomic_num = self.atomic_number if self.atomic_number else "N/A"
        mass = self.mass if self.mass else "N/A"
        category = self.category
        category_display = category_names.get(category, category.replace("_", " ").title())
        color = category_colors.get(self.category, "#95A5A6")

        tooltip_html = f"""
        <table cellspacing="4" cellpadding="2">
            <tr>
                <td colspan="2" style="font-size: 13px; font-weight: bold; color: #3498DB; padding-bottom: 4px;">
                    {self.name}
                </td>
            </tr>
            <tr>
                <td style="color: #BDC3C7;">Symbol:</td>
                <td style="font-weight: bold; color: #ECF0F1;">{self.symbol}</td>
            </tr>
            <tr>
                <td style="color: #BDC3C7;">Atomic No:</td>
                <td style="font-weight: bold; color: #ECF0F1;">{atomic_num}</td>
            </tr>
            <tr>
                <td style="color: #BDC3C7;">Mass:</td>
                <td style="font-weight: bold; color: #ECF0F1;">{mass}</td>
            </tr>
            <tr>
                <td style="color: #BDC3C7;">Category:</td>
                <td style="font-weight: bold; color: {color};">{category_display}</td>
            </tr>
        </table>
        """
        self.setToolTip(tooltip_html)

    def update_style(self, color: str):
        """Update button stylesheet."""
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: 2px solid {color};
                border-radius: 6px;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: white;
                color: {color};
                border: 2px solid {color};
            }}
            QPushButton:hover div {{
                color: {color} !important;
            }}
            QPushButton:pressed {{
                background-color: {color};
                color: white;
            }}
        """)

    def on_clicked(self):
        """Handle button click."""
        self.clicked_with_symbol.emit(self.symbol)


class BohrModelWidget(QWidget):
    """Widget displaying a realistic 3D-tilted Bohr model with elliptical orbits,
    individual nucleons in the nucleus, and mouse-wheel zoom."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(300)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.atomic_number = 0
        self.mass_number = 0.0
        self.animation_angle = 0.0
        self.zoom_factor = 1.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer_active = False
        self.setMouseTracking(True)

        # Zoom label fade animation
        self._zoom_label_opacity = 0.0
        self._zoom_label_timer = QTimer(self)
        self._zoom_label_timer.setSingleShot(True)
        self._zoom_label_timer.timeout.connect(self._start_zoom_fade)
        self._zoom_fade_timer = QTimer(self)
        self._zoom_fade_timer.timeout.connect(self._fade_zoom_label)

        # Reset zoom button (top-right corner)
        self._reset_btn = QPushButton("⟲", self)
        self._reset_btn.setFixedSize(28, 28)
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.setToolTip("Reset zoom")
        self._reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #34495E;
                color: #ECF0F1;
                border: 1px solid #3498DB;
                border-radius: 14px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3498DB;
                color: white;
            }
            QPushButton:pressed {
                background-color: #2980B9;
            }
        """)
        self._reset_btn.clicked.connect(self._reset_zoom)
        self._reset_btn.hide()

    def _reset_zoom(self):
        """Reset zoom to 100%."""
        self.zoom_factor = 1.0
        self._zoom_label_opacity = 0.0
        self._zoom_fade_timer.stop()
        self._zoom_label_timer.stop()
        self._reset_btn.hide()
        self.update()

    def set_atomic_number(self, z: int, mass: float = 0.0):
        """Set atomic number and mass number, then update display."""
        self.atomic_number = z if isinstance(z, int) else 0
        self.mass_number = mass if isinstance(mass, (int, float)) else 0.0
        if self.atomic_number > 0 and not self.timer_active:
            self.timer.start(16)
            self.timer_active = True
        elif self.atomic_number == 0 and self.timer_active:
            self.timer.stop()
            self.timer_active = False
        self.zoom_factor = 1.0
        self._zoom_label_opacity = 0.0
        self._zoom_fade_timer.stop()
        self._zoom_label_timer.stop()
        self._reset_btn.hide()
        self.update()

    def update_animation(self):
        """Update animation frame."""
        self.animation_angle += 0.35
        self.update()

    def wheelEvent(self, event):
        """Zoom in/out with mouse wheel."""
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_factor = min(self.zoom_factor * 1.15, 4.0)
        else:
            self.zoom_factor = max(self.zoom_factor / 1.15, 0.5)

        # Show/hide reset button based on zoom
        self._reset_btn.setVisible(not math.isclose(self.zoom_factor, 1.0, rel_tol=1e-09, abs_tol=1e-09))

        # Trigger zoom label with fade
        self._zoom_label_opacity = 1.0
        self._zoom_fade_timer.stop()
        self._zoom_label_timer.stop()
        self._zoom_label_timer.start(2000)  # 2s delay before fade starts
        self.update()

    def mouseDoubleClickEvent(self, event):
        """Double-click to reset zoom."""
        self._reset_zoom()

    def resizeEvent(self, event):
        """Keep reset button in top-right corner."""
        super().resizeEvent(event)
        self._reset_btn.move(self.width() - 36, 8)

    def _start_zoom_fade(self):
        """Start the fade-out animation for zoom label."""
        self._zoom_fade_timer.start(50)  # 50ms per frame = smooth 20fps fade

    def _fade_zoom_label(self):
        """Gradually fade out the zoom label."""
        self._zoom_label_opacity -= 0.04  # ~1.25s to fully fade at 50ms intervals
        if self._zoom_label_opacity <= 0:
            self._zoom_label_opacity = 0.0
            self._zoom_fade_timer.stop()
        self.update()

    def paintEvent(self, event):
        """Paint the Bohr model with dynamic sizing based on element complexity."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        avail_radius = min(center_x, center_y) - 20

        if not isinstance(self.atomic_number, int) or self.atomic_number <= 0:
            painter.setPen(QPen(QColor("#7F8C8D"), 1))
            painter.setFont(QFont(FONT, 12, QFont.Weight.Bold))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Select an element")
            return

        shells = get_shell_distribution(self.atomic_number)
        num_shells = len(shells)
        protons = self.atomic_number
        neutrons = max(0, round(self.mass_number) - self.atomic_number) if self.mass_number else 0
        total_nucleons = protons + neutrons

        # ── Dynamic sizing: natural size → scale to fit widget ──
        TARGET_NUCLEON_R = 4.2  # Ideal nucleon radius (px)
        NATURAL_SHELL_GAP = 28  # Ideal gap between electron shells (px)
        NUCLEUS_MARGIN = 22  # Space between nucleus and first orbit

        num_nuc_rings = self._get_nucleon_ring_count(total_nucleons)
        natural_nucleus_r = TARGET_NUCLEON_R * (1 + num_nuc_rings * 1.85)
        natural_atom_r = (natural_nucleus_r + NUCLEUS_MARGIN
                          + max(0, num_shells - 1) * NATURAL_SHELL_GAP
                          + 15)  # outer margin

        # Scale so the whole atom fits; cap at 1.0 so small atoms don't blow up
        base_scale = min(1.0, avail_radius / natural_atom_r) if natural_atom_r > 0 else 1.0

        nucleon_radius = max(1.2, TARGET_NUCLEON_R * base_scale)
        nucleus_radius = natural_nucleus_r * base_scale
        shell_gap = max(8, NATURAL_SHELL_GAP * base_scale)

        # Apply user zoom (view transform only — geometry is pre-scaled)
        painter.save()
        painter.translate(center_x, center_y)
        painter.scale(self.zoom_factor, self.zoom_factor)
        painter.translate(-center_x, -center_y)

        # Atom extent for vignette
        atom_extent = nucleus_radius + NUCLEUS_MARGIN + max(0, num_shells - 1) * shell_gap + 20

        # ── 1. Background vignette ──
        vignette = QRadialGradient(center_x, center_y, atom_extent + 20)
        vignette.setColorAt(0, QColor(52, 73, 94, 80))
        vignette.setColorAt(1, QColor(26, 37, 47, 0))
        painter.setBrush(QBrush(vignette))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())

        # ── 2. Nucleus (individual protons & neutrons) ──
        self._draw_nucleus(painter, center_x, center_y, nucleus_radius,
                           nucleon_radius, protons, neutrons)

        # ── 3. Electron shells (ELLIPTICAL) ──
        for i, count in enumerate(shells):
            rx = nucleus_radius + NUCLEUS_MARGIN + (i * shell_gap)
            ry = rx * 0.55  # Ellipse flattening for 3D tilt effect

            # Orbit soft glow
            painter.setPen(QPen(QColor(100, 200, 255, 30), 4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(
                int(center_x - rx), int(center_y - ry),
                int(rx * 2), int(ry * 2)
            )
            # Main orbit ring
            painter.setPen(QPen(QColor(120, 210, 255, 90), 1))
            painter.drawEllipse(
                int(center_x - rx), int(center_y - ry),
                int(rx * 2), int(ry * 2)
            )

            # Electron calculations on ellipse
            base_e_radius = max(2.0, min(5.5, rx / 14))
            direction = 1 if i % 2 == 0 else -1
            speed = (1.0 / (i + 1.2)) * direction
            base_angle = math.radians(self.animation_angle * speed * 35)

            for j in range(count):
                phase = j * (2 * math.pi / count)
                theta = base_angle + phase

                ex = center_x + rx * math.cos(theta)
                ey = center_y + ry * math.sin(theta)

                depth = math.sin(theta)
                depth_norm = (depth + 1) / 2

                e_radius = base_e_radius * (0.6 + 0.4 * depth_norm)
                alpha = int(70 + 160 * depth_norm)

                # ── Electron outer glow ──
                bloom_r = e_radius * 4.0
                bloom = QRadialGradient(ex, ey, bloom_r)
                bloom.setColorAt(0, QColor(0, 235, 190, int(alpha * 0.4)))
                bloom.setColorAt(1, QColor(0, 235, 190, 0))
                painter.setBrush(QBrush(bloom))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(
                    int(ex - bloom_r), int(ey - bloom_r),
                    int(bloom_r * 2), int(bloom_r * 2)
                )

                # ── Electron inner glow ──
                inner_glow_r = e_radius * 2.0
                inner_glow = QRadialGradient(ex, ey, inner_glow_r)
                inner_glow.setColorAt(0, QColor(180, 255, 240, int(alpha * 0.7)))
                inner_glow.setColorAt(1, QColor(0, 200, 160, 0))
                painter.setBrush(QBrush(inner_glow))
                painter.drawEllipse(
                    int(ex - inner_glow_r), int(ey - inner_glow_r),
                    int(inner_glow_r * 2), int(inner_glow_r * 2)
                )

                # ── Electron core (3D shaded sphere) ──
                core_grad = QRadialGradient(
                    ex - e_radius * 0.35, ey - e_radius * 0.35, e_radius
                )
                core_grad.setColorAt(0, QColor(255, 255, 255, alpha))
                core_grad.setColorAt(0.5, QColor(0, 240, 200, alpha))
                core_grad.setColorAt(1, QColor(0, 100, 80, int(alpha * 0.7)))
                painter.setBrush(QBrush(core_grad))
                painter.setPen(QPen(QColor(255, 255, 255, int(alpha * 0.6)), 0.5))
                painter.drawEllipse(
                    int(ex - e_radius), int(ey - e_radius),
                    int(e_radius * 2), int(e_radius * 2)
                )

        painter.restore()

        # ── Zoom indicator overlay (not affected by zoom) ──
        if not math.isclose(self.zoom_factor, 1.0, rel_tol=1e-09, abs_tol=1e-09):
            painter.setPen(QPen(QColor(255, 255, 255, 180), 1))
            painter.setFont(QFont(FONT, 9))
            painter.drawText(
                self.rect().adjusted(10, 10, -10, -10),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
                f"{int(self.zoom_factor * 100)}%"
            )

    @staticmethod
    def _get_nucleon_ring_count(total: int) -> int:
        """Calculate how many concentric rings beyond center are needed for nucleons."""
        if total <= 1:
            return 0
        count = 1
        ring = 1
        while count < total:
            count += 6 * ring
            ring += 1
        return ring - 1

    def _draw_nucleus(self, painter: QPainter, cx: float, cy: float,
                      nucleus_radius: float, nucleon_radius: float,
                      protons: int, neutrons: int):
        """Draw the nucleus as individual shaded protons and neutrons.
        Draws outer nucleons FIRST, inner nucleons LAST so they appear in front."""
        total = protons + neutrons
        if total == 0:
            return

        # Get positions for ALL nucleons
        positions = self._get_nucleon_positions(total, nucleon_radius)

        # Scale positions to fit within nucleus_radius minus nucleon_radius
        positions = self._scale_positions(positions, nucleon_radius, nucleus_radius)

        # Create mixed distribution: interleave protons and neutrons evenly
        is_proton_flags = self._create_nucleon_distribution(total, protons)

        # Sort nucleons by distance from center (outside first, inside last)
        nucleons = self._sort_nucleons_by_distance(positions, is_proton_flags)

        # Draw nucleons from outside -> inside
        for _, _, ox, oy, is_proton in nucleons:
            x = cx + ox
            y = cy + oy
            self._draw_single_nucleon(painter, x, y, nucleon_radius, is_proton)

    @staticmethod
    def _create_nucleon_distribution(total: int, protons: int) -> list[bool]:
        """Create distribution of protons and neutrons across positions."""
        if protons >= total:
            return [True] * total
        if protons == 0:
            return [False] * total

        # Distribute protons evenly across all positions
        is_proton_flags = [False] * total
        step = total / protons
        placed = 0

        for p in range(protons):
            idx = int(p * step) % total
            # Find nearest available slot
            offset = 0
            while offset < total:
                test_idx = (idx + offset) % total
                if not is_proton_flags[test_idx]:
                    is_proton_flags[test_idx] = True
                    placed += 1
                    break
                offset += 1
            if placed >= protons:
                break

        return is_proton_flags

    @staticmethod
    def _create_glow_gradient(x: float, y: float, radius: float, is_proton: bool) -> QRadialGradient:
        """Create glow gradient for nucleon."""
        glow_r = radius * 2.2
        glow = QRadialGradient(x, y, glow_r)

        if is_proton:
            glow.setColorAt(0, QColor(255, 90, 90, 55))
            glow.setColorAt(1, QColor(255, 90, 90, 0))
        else:
            glow.setColorAt(0, QColor(130, 160, 200, 55))
            glow.setColorAt(1, QColor(130, 160, 200, 0))

        return glow

    @staticmethod
    def _create_sphere_gradient(x: float, y: float, radius: float, is_proton: bool) -> QRadialGradient:
        """Create 3D sphere gradient for nucleon."""
        sphere_grad = QRadialGradient(
            x - radius * 0.35,
            y - radius * 0.35,
            radius
        )

        if is_proton:
            sphere_grad.setColorAt(0, QColor("#FFDDDD"))
            sphere_grad.setColorAt(0.25, QColor("#FF5555"))
            sphere_grad.setColorAt(0.75, QColor("#CC0000"))
            sphere_grad.setColorAt(1, QColor("#880000"))
        else:
            sphere_grad.setColorAt(0, QColor("#E0E0E0"))
            sphere_grad.setColorAt(0.25, QColor("#78909C"))
            sphere_grad.setColorAt(0.75, QColor("#455A64"))
            sphere_grad.setColorAt(1, QColor("#263238"))

        return sphere_grad

    def _draw_single_nucleon(self, painter: QPainter, x: float, y: float, nucleon_radius: float, is_proton: bool):
        """Draw a single nucleon with optional glow and 3D shading."""
        # Draw glow for larger nucleons
        if nucleon_radius > 3:
            glow = self._create_glow_gradient(x, y, nucleon_radius, is_proton)
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            glow_r = nucleon_radius * 2.2
            painter.drawEllipse(
                int(x - glow_r), int(y - glow_r),
                int(glow_r * 2), int(glow_r * 2)
            )

        # Draw 3D shaded sphere
        sphere_grad = self._create_sphere_gradient(x, y, nucleon_radius, is_proton)
        painter.setBrush(QBrush(sphere_grad))
        painter.setPen(QPen(QColor(255, 255, 255, 90), 0.5))
        painter.drawEllipse(
            int(x - nucleon_radius), int(y - nucleon_radius),
            int(nucleon_radius * 2), int(nucleon_radius * 2)
        )

    @staticmethod
    def _scale_positions(positions: list[tuple[float, float]], nucleon_radius: float, nucleus_radius: float) -> list[
        tuple[float, float]]:
        """Scale positions to fit within nucleus boundary."""
        if len(positions) <= 1:
            return positions

        max_dist = max(math.sqrt(x * x + y * y) for x, y in positions)
        if max_dist > 0:
            scale = (nucleus_radius - nucleon_radius) / max_dist
            if scale < 1.0:
                return [(x * scale, y * scale) for x, y in positions]
        return positions

    @staticmethod
    def _sort_nucleons_by_distance(positions: list[tuple[float, float]], is_proton_flags: list[bool]) -> list[tuple]:
        """Sort nucleons by distance from center (outer first, inner last)."""
        nucleons = []
        for i, (ox, oy) in enumerate(positions):
            dist = math.sqrt(ox * ox + oy * oy)
            nucleons.append((dist, i, ox, oy, is_proton_flags[i]))

        # Sort by distance DESCENDING (outer first, inner last)
        nucleons.sort(key=lambda x: x[0], reverse=True)
        return nucleons

    @staticmethod
    def _get_nucleon_positions(count: int, radius: float) -> list[tuple[float, float]]:
        """Generate close-packed hexagonal positions for nucleons in concentric rings."""
        if count <= 0:
            return []
        if count == 1:
            return [(0.0, 0.0)]

        positions = [(0.0, 0.0)]
        ring = 1
        while len(positions) < count:
            # Hexagonal close packing: 6*n positions in ring n
            n_in_ring = min(6 * ring, count - len(positions))
            ring_radius = ring * radius * 1.85  # Tighter packing

            for i in range(n_in_ring):
                angle = 2 * math.pi * i / n_in_ring + (ring * 0.3)  # Stagger rings
                x = ring_radius * math.cos(angle)
                y = ring_radius * math.sin(angle)
                positions.append((x, y))
            ring += 1

        return positions


class ElementInfoPanel(QScrollArea):
    """Panel displaying detailed element information."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)

        self.header_frame = QFrame()
        self.name_label = QLabel("Select an Element")
        self.close_btn = QPushButton("✕")

        self.symbol_frame = QFrame()
        self.symbol_label = QLabel("--")
        self.atomic_num_label = QLabel("Z = --")

        self.bohr_widget = BohrModelWidget()

        self.info_container = QFrame()
        self.info_layout = QVBoxLayout(self.info_container)

        # Info rows — create_info_row adds itself to self.info_layout automatically
        self.mass_value = self.create_info_row("Atomic Mass:", "--")
        self.category_value = self.create_info_row("Category:", "--")
        self.group_value = self.create_info_row("Group:", "--")
        self.period_value = self.create_info_row("Period:", "--")
        self.state_value = self.create_info_row("State at RTP:", "--")
        self.density_value = self.create_info_row("Density:", "--")
        self.melting_value = self.create_info_row("Melting Point:", "--")
        self.boiling_value = self.create_info_row("Boiling Point:", "--")
        self.electronegativity_value = self.create_info_row("Electronegativity:", "--")
        self.valence_value = self.create_info_row("Valence:", "--")
        self.stability_value = self.create_info_row("Stability:", "--")

        self.config_frame = QFrame()
        self.config_label = QLabel("--")

        self.isotopes_frame = QFrame()
        self.isotopes_label = QLabel("--")

        self.desc_frame = QFrame()
        self.desc_label = QLabel("--")

        self.apps_frame = QFrame()
        self.apps_label = QLabel("--")

        self.current_element = None
        self.setup_ui()

    def setup_ui(self):
        """Setup info panel UI."""
        self.setMinimumWidth(300)
        self.setMaximumWidth(450)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.container)

        self.layout.setSpacing(15)
        self.layout.setContentsMargins(15, 15, 15, 15)

        # Header
        self.header_frame.setStyleSheet(STYLESHEET_FRAME_2)
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(15, 10, 15, 10)

        self.name_label.setFont(QFont(FONT, 16, QFont.Weight.Bold))
        self.name_label.setStyleSheet(COLOR_WHITE)
        header_layout.addWidget(self.name_label)

        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
                color: white;
                border-radius: 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #C0392B;
            }
        """)
        header_layout.addWidget(self.close_btn)
        self.layout.addWidget(self.header_frame)

        # Symbol and atomic number
        symbol_layout = QHBoxLayout(self.symbol_frame)
        symbol_layout.setContentsMargins(0, 0, 0, 0)

        self.symbol_label.setFont(QFont(FONT, 32, QFont.Weight.Bold))
        self.symbol_label.setStyleSheet(COLOR_2)
        symbol_layout.addWidget(self.symbol_label)

        symbol_layout.addStretch()

        self.atomic_num_label.setFont(QFont(FONT, 12))
        self.atomic_num_label.setStyleSheet("color: #7F8C8D;")
        symbol_layout.addWidget(self.atomic_num_label)

        self.layout.addWidget(self.symbol_frame)
        self.bohr_widget.setMinimumHeight(320)
        self.bohr_widget.setMaximumHeight(450)

        self.layout.addWidget(self.bohr_widget)
        # Info cards container
        self.info_container.setStyleSheet(STYLESHEET_FRAME_1)
        self.info_layout.setSpacing(8)
        self.info_layout.setContentsMargins(12, 12, 12, 12)
        # NOTE: info rows were already added to self.info_layout inside __init__
        self.layout.addWidget(self.info_container)

        # Electron configuration
        self.config_frame.setStyleSheet(STYLESHEET_FRAME_2)
        config_layout = QVBoxLayout(self.config_frame)
        config_layout.setContentsMargins(12, 10, 12, 10)

        config_title = QLabel("Electron Configuration")
        config_title.setFont(QFont(FONT, 11, QFont.Weight.Bold))
        config_title.setStyleSheet(COLOR_2)
        config_layout.addWidget(config_title)

        self.config_label.setFont(QFont("Consolas", 10))
        self.config_label.setStyleSheet(COLOR_WHITE)
        self.config_label.setWordWrap(True)
        config_layout.addWidget(self.config_label)

        self.layout.addWidget(self.config_frame)

        # Isotopes section
        self.isotopes_frame.setStyleSheet(STYLESHEET_FRAME_2)
        isotopes_layout = QVBoxLayout(self.isotopes_frame)
        isotopes_layout.setContentsMargins(12, 10, 12, 10)

        isotopes_title = QLabel("Isotopes")
        isotopes_title.setFont(QFont(FONT, 11, QFont.Weight.Bold))
        isotopes_title.setStyleSheet(COLOR_2)
        isotopes_layout.addWidget(isotopes_title)

        self.isotopes_label.setFont(QFont("Consolas", 9))
        self.isotopes_label.setStyleSheet(COLOR_WHITE)
        self.isotopes_label.setWordWrap(True)
        isotopes_layout.addWidget(self.isotopes_label)

        self.layout.addWidget(self.isotopes_frame)

        # Description
        self.desc_frame.setStyleSheet(STYLESHEET_FRAME_1)
        desc_layout = QVBoxLayout(self.desc_frame)
        desc_layout.setContentsMargins(12, 10, 12, 10)

        desc_title = QLabel("Description")
        desc_title.setFont(QFont(FONT, 11, QFont.Weight.Bold))
        desc_title.setStyleSheet(COLOR_2)
        desc_layout.addWidget(desc_title)

        self.desc_label.setFont(QFont(FONT, 10))
        self.desc_label.setStyleSheet("color: #ECF0F1;")
        self.desc_label.setWordWrap(True)
        desc_layout.addWidget(self.desc_label)

        self.layout.addWidget(self.desc_frame)

        # Applications
        self.apps_frame.setStyleSheet(STYLESHEET_FRAME_1)
        apps_layout = QVBoxLayout(self.apps_frame)
        apps_layout.setContentsMargins(12, 10, 12, 10)

        apps_title = QLabel("Applications")
        apps_title.setFont(QFont(FONT, 11, QFont.Weight.Bold))
        apps_title.setStyleSheet(COLOR_2)
        apps_layout.addWidget(apps_title)

        self.apps_label.setFont(QFont(FONT, 10))
        self.apps_label.setStyleSheet("color: #ECF0F1;")
        self.apps_label.setWordWrap(True)
        apps_layout.addWidget(self.apps_label)

        self.layout.addWidget(self.apps_frame)

        self.layout.addStretch()

    def create_info_row(self, label_text: str, value_text: str) -> QLabel:
        """Create a label-value info row and add it to the info layout."""
        layout = QHBoxLayout()

        label = QLabel(label_text)
        label.setFont(QFont(FONT, 10))
        label.setStyleSheet("color: #BDC3C7;")
        layout.addWidget(label)

        layout.addStretch()

        value = QLabel(value_text)
        value.setFont(QFont(FONT, 10, QFont.Weight.Bold))
        value.setStyleSheet(COLOR_WHITE)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        value.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(value)

        self.info_layout.addLayout(layout)
        return value

    def update_info(self, element_data: dict):
        """Update panel with element data."""
        self.current_element = element_data
        self._update_basic_info(element_data)
        self._update_atomic_info(element_data)
        self._update_physical_properties(element_data)
        self._update_chemical_properties(element_data)
        self._update_stability_info(element_data)
        self._update_isotopes_info(element_data)
        self._update_description_and_applications(element_data)

    def _update_basic_info(self, element_data: dict):
        """Update basic element information."""
        name = element_data.get("name", "Unknown")
        symbol = element_data.get("symbol", "--")
        self.name_label.setText(name)
        self.symbol_label.setText(symbol)

    def _update_atomic_info(self, element_data: dict):
        """Update atomic number and electron configuration."""
        atomic_num = element_data.get("atomic_number")
        electron_config = element_data.get("electron_configuration", "")

        if isinstance(atomic_num, int):
            self.atomic_num_label.setText(f"Z = {atomic_num}")
            mass = element_data.get("mass_number")
            if isinstance(mass, (int, float)):
                self.bohr_widget.set_atomic_number(atomic_num, mass)
            else:
                self.bohr_widget.set_atomic_number(atomic_num)
            config = electron_config if electron_config else get_spdf_config(atomic_num)
            self.config_label.setText(config)
        else:
            self.atomic_num_label.setText("Z = --")
            self.bohr_widget.set_atomic_number(0)
            self.config_label.setText("--")

    def _update_physical_properties(self, element_data: dict):
        """Update physical properties of the element."""
        mass = element_data.get("mass_number", "N/A")
        group = element_data.get("group", "--")
        period = element_data.get("period", "--")
        state = element_data.get("state_at_room_temp", "unknown")
        density = element_data.get("density", "N/A")
        melting = element_data.get("melting_point", "N/A")
        boiling = element_data.get("boiling_point", "N/A")

        self.mass_value.setText(self._format_value(mass))
        self.group_value.setText(self._format_value(group))
        self.period_value.setText(self._format_value(period))
        self.state_value.setText(self._format_state(state))
        self.density_value.setText(self._format_density(density))
        self.melting_value.setText(self._format_temperature(melting))
        self.boiling_value.setText(self._format_temperature(boiling))

    def _update_chemical_properties(self, element_data: dict):
        """Update chemical properties of the element."""
        category = element_data.get("category", "unknown")
        valence = element_data.get("valence_electrons", "N/A")
        electronegativity = element_data.get("electronegativity", "N/A")

        self.category_value.setText(self._format_category(category))
        self.valence_value.setText(self._format_valence(valence))
        self.electronegativity_value.setText(self._format_value(electronegativity))

    def _update_stability_info(self, element_data: dict):
        """Update stability information with appropriate coloring."""
        stability = element_data.get("stability", "Unknown")

        if stability and stability != "Unknown":
            self.stability_value.setText(stability)
            self.stability_value.setStyleSheet(self._get_stability_color(stability))
        else:
            self.stability_value.setText("--")
            self.stability_value.setStyleSheet(COLOR_WHITE)

    def _update_isotopes_info(self, element_data: dict):
        """Update isotope information."""
        isotopes = element_data.get("isotopes", {})

        if isotopes:
            isotope_lines = []
            for isotope, data in isotopes.items():
                line = self._format_isotope_line(isotope, data)
                isotope_lines.append(line)
            self.isotopes_label.setText("\n".join(isotope_lines))
        else:
            self.isotopes_label.setText("--")

    def _update_description_and_applications(self, element_data: dict):
        """Update description and applications."""
        description = element_data.get("description", "No description available.")
        applications = element_data.get("applications", [])

        self.desc_label.setText(description)

        if applications:
            self.apps_label.setText("\u2022 " + "\n\u2022 ".join(applications))
        else:
            self.apps_label.setText("--")

    # Helper methods for formatting
    @staticmethod
    def _format_value(value) -> str:
        """Format a basic value, returning '--' for empty/invalid values."""
        return f"{value}" if value and value != "N/A" and value != "--" else "--"

    @staticmethod
    def _format_state(state) -> str:
        """Format state with proper capitalization."""
        return str(state).title() if state and state != "unknown" else "--"

    @staticmethod
    def _format_density(density) -> str:
        """Format density with appropriate units."""
        if isinstance(density, (int, float)):
            return f"{density} g/cm³"
        elif density and density != "N/A":
            return str(density)
        else:
            return "--"

    @staticmethod
    def _format_temperature(temp) -> str:
        """Format temperature values."""
        return f"{temp} K" if temp and temp != "N/A" else "--"

    @staticmethod
    def _format_category(category) -> str:
        """Format category name."""
        if not category:
            return "--"
        return category_names.get(category, category.replace("_", " ").title())

    @staticmethod
    def _format_valence(valence) -> str:
        """Format valence electrons value."""
        if valence and valence != "N/A":
            if isinstance(valence, (tuple, list)):
                return ", ".join(str(v) for v in valence)
            else:
                return str(valence)
        else:
            return "--"

    @staticmethod
    def _get_stability_color(stability: str) -> str:
        """Get color based on stability status."""
        if stability == "Stable":
            return "color: #2ECC71;"
        elif stability == "Radioactive":
            return "color: #E74C3C;"
        else:
            return COLOR_WHITE

    @staticmethod
    def _format_isotope_line(isotope: str, data: dict) -> str:
        """Format a single isotope line."""
        mass = data.get('mass', 'N/A')
        abundance = data.get('abundance', 0)
        half_life = data.get('half_life', None)

        if abundance > 0:
            return f"{isotope}: {mass} ({abundance}%)"
        else:
            return f"{isotope}: {mass} (t½={half_life})" if half_life else f"{isotope}: {mass}"

    @staticmethod
    def update_info_row(layout: QHBoxLayout, value: str):
        """Update an info row value."""
        widget = layout.itemAt(2).widget()
        if widget and isinstance(widget, QLabel):
            widget.setText(value)


class SearchResultItem(QWidget):
    """Rich row inside the dropdown list."""

    def __init__(self, symbol, name, atomic_number, query="", is_recent=False, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        if is_recent:
            icon = QLabel("🕐")
            icon.setStyleSheet("font-size: 12px; background: transparent; border: none;")
            layout.addWidget(icon)

        # Highlight matching text
        display = f"{symbol} — {name}"
        if query:
            q = query.lower()
            d_lower = display.lower()
            if q in d_lower:
                start = d_lower.index(q)
                end = start + len(query)
                highlighted = (
                        display[:start] +
                        f'<span style="color: #3498DB; font-weight: bold;">{display[start:end]}</span>' +
                        display[end:]
                )
            else:
                highlighted = display
        else:
            highlighted = display

        text_lbl = QLabel(highlighted)
        text_lbl.setTextFormat(Qt.TextFormat.RichText)
        text_lbl.setStyleSheet("""
            color: #ECF0F1;
            font-family: 'Segoe UI';
            font-size: 11px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(text_lbl, 1)

        z_lbl = QLabel(f"Z={atomic_number}" if atomic_number else "")
        z_lbl.setStyleSheet("""
            color: #7F8C8D;
            font-size: 10px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(z_lbl)

        self.symbol = symbol
        self.setStyleSheet("""
            background: transparent;
            border: none;
        """)


class SearchLineEdit(QLineEdit):
    """Search field with embedded clear button and escape handling."""
    escape_pressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Search by name, symbol, or atomic number…")
        self.setMinimumWidth(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                border: none;
                color: white;
                font-family: 'Segoe UI';
                font-size: 12px;
                padding: 4px 28px 4px 4px;
            }
        """)

        self.clear_btn = QPushButton("✕", self)
        self.clear_btn.setFixedSize(20, 20)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #7F8C8D;
                color: white;
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #E74C3C;
            }
        """)
        self.clear_btn.hide()
        self.clear_btn.clicked.connect(self.clear)

        self.textChanged.connect(self._toggle_clear)

    def _toggle_clear(self, text):
        self.clear_btn.setVisible(bool(text))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.clear_btn.move(self.width() - 26, (self.height() - 20) // 2)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
        super().keyPressEvent(event)


class SearchDropdown(QFrame):
    """Modern dropdown — solid opaque background, rounded border only on the shell."""
    item_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 140))
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)

        # ONLY the outer shell gets border + radius
        self.setStyleSheet("""
            QFrame {
                background-color: #2C3E50;
                border: 1px solid #3498DB;
                border-radius: 10px;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)  # NO gap between border and content
        outer.setSpacing(0)

        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setMaximumHeight(280)
        # Aggressively remove every border and outline
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2C3E50;
                outline: none;
                border: none;
            }
            QListWidget::item {
                border: none;
                background-color: transparent;
                padding: 0px;
                margin: 0px;
            }
            QListWidget::item:hover {
                background-color: #34495E;
                border: none;
            }
            QListWidget::item:selected {
                background-color: #34495E;
                border: none;
            }
            QListWidget::item:focus {
                outline: none;
                border: none;
            }
        """)
        self.list_widget.itemClicked.connect(self._on_click)
        outer.addWidget(self.list_widget)

        self._highlighted_row = -1

    def key_event(self, event) -> bool:
        if not self.isVisible():
            return False

        if event.key() == Qt.Key.Key_Down:
            self._move(1)
            return True
        elif event.key() == Qt.Key.Key_Up:
            self._move(-1)
            return True
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._activate_current()
            return True
        elif event.key() == Qt.Key.Key_Escape:
            self.hide()
            return True
        return False

    def _move(self, delta):
        count = self.list_widget.count()
        if count == 0:
            return
        self._highlighted_row = (self._highlighted_row + delta) % count
        self.list_widget.setCurrentRow(self._highlighted_row)

    def _activate_current(self):
        if self._highlighted_row < 0:
            self._highlighted_row = 0
        item = self.list_widget.item(self._highlighted_row)
        if item:
            self._on_click(item)

    def _on_click(self, item):
        widget = self.list_widget.itemWidget(item)
        if widget and hasattr(widget, "symbol"):
            self.item_selected.emit(widget.symbol)
        self.hide()

    @staticmethod
    def _get_recent_searches(search_memory: dict, elements_dict: dict) -> list:
        """Get recent search elements."""
        if not search_memory:
            return []

        recent = sorted(search_memory.items(), key=lambda x: x[1], reverse=True)
        recent_elements = []

        for symbol, _ in recent[:6]:
            for data in elements_dict.values():
                if data.get("symbol") == symbol and data.get("atomic_number"):
                    recent_elements.append(data)
                    break

        return recent_elements

    @staticmethod
    def _calculate_search_score(query: str, data: dict) -> int:
        """Calculate search relevance score for an element."""
        name = data.get("name", "").lower()
        sym = data.get("symbol", "").lower()
        z = str(data.get("atomic_number", ""))

        if query == sym or query == z:
            return 100
        elif query == name:
            return 90
        elif query in sym:
            return 80
        elif query in name:
            return 70
        elif query in z:
            return 60
        return 0

    def _get_search_matches(self, query: str, elements_dict: dict) -> list:
        """Get and rank search matches for a query."""
        matches = []

        for data in elements_dict.values():
            if not data.get("atomic_number"):
                continue

            score = self._calculate_search_score(query, data)
            if score:
                matches.append((score, data))

        matches.sort(key=lambda x: x[0], reverse=True)
        return matches

    @staticmethod
    def _create_search_item(data: dict, is_recent: bool = False, query: str = "") -> tuple[
        QListWidgetItem, SearchResultItem]:
        """Create a list widget item for search results."""
        item = QListWidgetItem()
        row = SearchResultItem(
            data["symbol"], data["name"],
            data.get("atomic_number"), is_recent=is_recent, query=query
        )
        item.setSizeHint(row.sizeHint())
        return item, row

    @staticmethod
    def _create_no_results_item() -> tuple[QListWidgetItem, QLabel]:
        """Create a 'no results' item."""
        item = QListWidgetItem()
        empty = QLabel("No elements found")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setStyleSheet("""
            color: #7F8C8D;
            padding: 14px;
            font-style: italic;
            background: transparent;
            border: none;
        """)
        item.setSizeHint(empty.sizeHint())
        return item, empty

    def _add_elements_to_list(self, elements: list, is_recent: bool = False, query: str = ""):
        """Add elements to the list widget."""
        for data in elements:
            item, row = self._create_search_item(data, is_recent, query)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)

    def update_list(self, query: str, elements_dict: dict, search_memory: dict = None):
        """Update the search list with results."""
        self.list_widget.clear()
        self._highlighted_row = -1
        query = query.strip().lower()

        if not query:
            recent_elements = self._get_recent_searches(search_memory, elements_dict)
            if recent_elements:
                self._add_elements_to_list(recent_elements, is_recent=True)
            else:
                self.hide()
                return
        else:
            matches = self._get_search_matches(query, elements_dict)

            if not matches:
                item, empty = self._create_no_results_item()
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, empty)
            else:
                matched_elements = [data for _, data in matches[:8]]
                self._add_elements_to_list(matched_elements, query=query)

        self._update_dropdown_size()

    def _update_dropdown_size(self):
        """Update dropdown size to match search input."""
        self.setFixedWidth(self.parent().search_input.width() if self.parent() else 280)
        self.setFixedHeight(min(self.list_widget.count() * 44 + 16, 310))
        self.show()
        self.raise_()


class PeriodicTableApp(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.search_input = QLineEdit()
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.info_panel = ElementInfoPanel()
        self.search_dropdown = SearchDropdown(self)
        self.status_bar = QStatusBar()
        self.setWindowTitle("Periodic Table Explorer V3")
        self.setMinimumSize(1200, 600)
        self.table_layout = None
        self.periodic_buttons: dict[tuple, ElementButton] = {}
        self.symbol_to_pos: dict[str, tuple] = {}
        self.pos_to_symbol: dict[tuple, str] = {}
        self.all_element_buttons: list[ElementButton] = []
        # Load search memory
        self.symbol_index: dict[str, dict] = {}
        self.z_index: dict[str, dict] = {}
        self.name_index: dict[str, dict] = {}

        for data in elements_data.values():
            if not data.get("atomic_number"):
                continue
            sym = data.get("symbol", "")
            z = str(data.get("atomic_number", ""))
            name = data.get("name", "").lower()
            self.symbol_index[sym.lower()] = data
            self.z_index[z] = data
            self.name_index[name] = data

        self.memory_file = self.get_data_path("search_memory.json")
        self.search_memory = self.load_memory()

        # Debounce timer for live search
        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.timeout.connect(self._do_search_update)

        self.setup_ui()
        self.apply_styles()

    @staticmethod
    def get_data_path(filename: str) -> str:
        """Get path for data file."""
        appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        data_dir = os.path.join(appdata, "PeriodicTableV3")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, filename)

    def load_memory(self) -> dict:
        """Load search memory."""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}

    def save_memory(self):
        """Save search memory."""
        try:
            with open(self.memory_file, 'w') as f:
                json.dump(self.search_memory, f)
        except:
            pass

    def setup_ui(self):
        """Setup main UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Header with search
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("Periodic Table Explorer")
        title_label.setFont(QFont(FONT, 20, QFont.Weight.Bold))
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Search box
        search_container = QFrame()
        search_container.setStyleSheet("""
            QFrame {
                background-color: #34495E;
                border-radius: 20px;
                padding: 3px;
            }
        """)
        search_layout = QHBoxLayout(search_container)
        search_layout.setSpacing(5)
        search_layout.setContentsMargins(12, 4, 0, 4)
        search_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Replace the old QLineEdit with SearchLineEdit
        self.search_input = SearchLineEdit()
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_input.returnPressed.connect(self.perform_search)
        self.search_input.escape_pressed.connect(self._hide_search_dropdown)
        search_layout.addWidget(self.search_input)

        header_layout.addWidget(search_container)

        main_layout.addWidget(header_widget)

        # Legend
        legend_widget = self.create_legend()
        main_layout.addWidget(legend_widget)

        # Splitter for table and info panel
        self.splitter.setHandleWidth(8)

        # Table container with scroll area
        table_scroll = QScrollArea()
        table_scroll.setWidgetResizable(True)
        table_scroll.setFrameShape(QFrame.Shape.NoFrame)
        table_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table_scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #2C3E50;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #3498DB;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #2980B9;
            }
            QScrollBar:horizontal {
                background-color: #2C3E50;
                height: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background-color: #3498DB;
                border-radius: 5px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #2980B9;
            }
        """)

        table_container = QWidget()
        self.table_layout = QGridLayout(table_container)
        self.table_layout.setSpacing(3)
        self.table_layout.setContentsMargins(5, 5, 5, 5)

        # Make grid cells expand evenly
        for i in range(18):
            self.table_layout.setColumnStretch(i, 1)
        for i in range(10):
            self.table_layout.setRowStretch(i, 1)

        self.create_periodic_table()

        table_scroll.setWidget(table_container)
        self.splitter.addWidget(table_scroll)

        # Info panel
        self.info_panel.close_btn.clicked.connect(self.hide_info_panel)
        self.splitter.addWidget(self.info_panel)

        # Initial splitter sizes (hide info panel by default)
        self.splitter.setSizes([1000, 0])
        self.splitter.setCollapsible(1, True)

        main_layout.addWidget(self.splitter, 1)

        # Search dropdown (created after main layout to ensure proper parenting)
        self.search_dropdown.item_selected.connect(self.show_element_info)

        # Status bar
        self.status_bar.setStyleSheet("color: #BDC3C7;")
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Click any element to view details")

    def on_search_text_changed(self):
        """Debounced live search."""
        self._search_debounce_timer.stop()
        self._search_debounce_timer.start(120)  # 120 ms feels snappy

    def _do_search_update(self):
        """Actually refresh the dropdown after debounce."""
        text = self.search_input.text()
        # Show recents when empty, results when typing
        if text.strip() or self.search_memory:
            pos = self.search_input.mapToGlobal(
                QPoint(0, self.search_input.height() + 6)
            )
            self.search_dropdown.move(pos)
            self.search_dropdown.update_list(text, elements_data, self.search_memory)
        else:
            self.search_dropdown.hide()

    def _hide_search_dropdown(self):
        self.search_dropdown.hide()
        self.search_input.clearFocus()

    def perform_search(self):
        """Instant search on Enter (bypass debounce)."""
        self._search_debounce_timer.stop()
        query = self.search_input.text().strip().lower()
        if not query:
            return

        data = None
        if query in self.symbol_index:
            data = self.symbol_index[query]
        elif query in self.z_index:
            data = self.z_index[query]
        elif query in self.name_index:
            data = self.name_index[query]
        else:
            matches = difflib.get_close_matches(query, self.name_index.keys(), n=1, cutoff=0.6)
            if matches:
                data = self.name_index[matches[0]]

        if data:
            self.show_element_info(data["symbol"])
            self.search_input.clear()
            self.search_dropdown.hide()
        else:
            self.status_bar.showMessage(f"No element found for '{query}'", 3000)

    @staticmethod
    def create_legend() -> QWidget:
        """Create category color legend."""
        legend_widget = QWidget()
        legend_layout = QHBoxLayout(legend_widget)
        legend_layout.setSpacing(10)
        legend_layout.setContentsMargins(0, 0, 0, 0)

        legend_layout.addStretch()

        for category, color in category_colors.items():
            if category == "unknown":
                continue

            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setSpacing(4)
            item_layout.setContentsMargins(0, 0, 0, 0)

            color_box = QFrame()
            color_box.setFixedSize(16, 16)
            color_box.setStyleSheet(f"""
                background-color: {color};
                border-radius: 3px;
            """)
            item_layout.addWidget(color_box)

            label = QLabel(category_names.get(category, category))
            label.setFont(QFont(FONT, 9))
            item_layout.addWidget(label)

            legend_layout.addWidget(item_widget)

        legend_layout.addStretch()

        return legend_widget

    def create_periodic_table(self):
        """Create the periodic table grid."""
        self._create_main_table()
        self._create_lanthanides_row()
        self._create_actinides_row()

    def _create_main_table(self):
        """Create the main periodic table (periods 1-7)."""
        for row in range(7):
            for col in range(18):
                self._add_element_button(row, col)

    def _add_element_button(self, row, col):
        """Add an element button at the specified position."""
        if (row, col) not in elements_data:
            return

        element = elements_data[(row, col)]
        if not element.get("atomic_number"):
            return

        btn = ElementButton(element)
        btn.clicked_with_symbol.connect(self.show_element_info)
        self.table_layout.addWidget(btn, row, col)
        self._store_element_references(btn, element, row, col)

    def _store_element_references(self, btn, element, row, col):
        """Store element references for filtering and navigation."""
        self.periodic_buttons[(row, col)] = btn
        self.symbol_to_pos[element["symbol"]] = (row, col)
        self.pos_to_symbol[(row, col)] = element["symbol"]
        self.all_element_buttons.append(btn)

    def _create_lanthanides_row(self):
        """Create the lanthanides row (row 7)."""
        self._add_series_label("Lanthanides", "#FF8C69", 7)
        self._add_series_elements(7, "lanthanides")

    def _create_actinides_row(self):
        """Create the actinides row (row 8)."""
        self._add_series_label("Actinides", "#FF69B4", 8)
        self._add_series_elements(8, "actinides")

    def _add_series_label(self, series_name, color, row):
        """Add a series label for lanthanides or actinides."""
        label = QLabel(series_name)
        label.setFont(QFont(FONT, 9, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {color}; padding: 5px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table_layout.addWidget(label, row, 0, 1, 3)

    def _add_series_elements(self, row, series_type):
        """Add elements for lanthanides or actinides series."""
        for col in range(3, 18):
            if (row, col) in elements_data:
                element = elements_data[(row, col)]
                btn = ElementButton(element)
                btn.clicked_with_symbol.connect(self.show_element_info)
                self.table_layout.addWidget(btn, row, col)

    def eventFilter(self, obj, event):
        """Filter events to hide dropdown when clicking outside."""
        if event.type() == event.Type.MouseButtonPress:
            if self.search_dropdown.isVisible():
                if not self.search_dropdown.geometry().contains(event.globalPosition().toPoint()):
                    if obj != self.search_input:
                        self.search_dropdown.hide()
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        # Let dropdown eat navigation keys first
        if self.search_dropdown.key_event(event):
            return

        # Handle Enter to open current element's info panel
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.info_panel.current_element:
                symbol = self.info_panel.current_element.get("symbol")
                if symbol:
                    # Re-show to ensure panel is visible (in case it was closed)
                    self.show_element_info(symbol)
                    return
            # If no current element, fall through to normal behavior
            super().keyPressEvent(event)
            return

        if not self._can_handle_key_event(event):
            super().keyPressEvent(event)
            return

        current_symbol = self.info_panel.current_element.get("symbol")
        row, col = self.symbol_to_pos[current_symbol]
        new_pos = self._find_new_position(event, row, col)

        if new_pos:
            self.show_element_info(self.pos_to_symbol[new_pos])
        else:
            super().keyPressEvent(event)

    def _can_handle_key_event(self, _event):
        """Check if key event can be handled."""
        if not self.info_panel.current_element:
            return False

        current_symbol = self.info_panel.current_element.get("symbol")
        return current_symbol and current_symbol in self.symbol_to_pos

    def _find_new_position(self, event, row: int, col: int) -> tuple[int, int] | None:
        """Find new position based on arrow key direction."""

        key_handlers: dict[int, Callable[[int, int], tuple[int, int] | None]] = {
            Qt.Key.Key_Left: self._find_left_position,
            Qt.Key.Key_Right: self._find_right_position,
            Qt.Key.Key_Up: self._find_up_position,
            Qt.Key.Key_Down: self._find_down_position
        }

        handler = key_handlers.get(event.key())
        if handler:
            return handler(row, col)
        return None

    def _find_left_position(self, row: int, col: int) -> tuple[int, int] | None:
        """Find the next valid position to the left."""
        for c in range(col - 1, -1, -1):
            if (row, c) in self.periodic_buttons:
                return row, c
        return None

    def _find_right_position(self, row: int, col: int) -> tuple[int, int] | None:
        """Find the next valid position to the right."""
        for c in range(col + 1, 18):
            if (row, c) in self.periodic_buttons:
                return row, c
        return None

    def _find_up_position(self, row: int, col: int) -> tuple[int, int] | None:
        """Find the next valid position above."""
        for r in range(row - 1, -1, -1):
            if (r, col) in self.periodic_buttons:
                return r, col
        return None

    def _find_down_position(self, row: int, col: int) -> tuple[int, int] | None:
        """Find the next valid position below."""
        for r in range(row + 1, 10):
            if (r, col) in self.periodic_buttons:
                return r, col
        return None

    def show_element_info(self, symbol: str):
        """Show element info panel."""
        for data in elements_data.values():
            if data.get("symbol") == symbol:
                # Show panel first
                self.info_panel.update_info(data)
                # Set splitter sizes to show panel
                self.splitter.setSizes([700, 350])

                # Update search memory
                if symbol in self.search_memory:
                    self.search_memory[symbol] += 1
                else:
                    self.search_memory[symbol] = 1
                self.save_memory()

                self.status_bar.showMessage(f"Viewing: {data.get('name')} ({symbol})")
                break

    def hide_info_panel(self):
        """Hide the info panel."""
        self.splitter.setSizes([1000, 0])
        self.status_bar.showMessage("Ready - Click any element to view details")

    def apply_styles(self):
        """Apply application styles."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1A252F;
            }
            QWidget {
                background-color: #1A252F;
                color: #ECF0F1;
                font-family: 'Segoe UI';
            }
            QLabel {
                color: #ECF0F1;
            }
            QSplitter::handle {
                background-color: #34495E;
            }
            QSplitter::handle:horizontal {
                width: 8px;
                border-radius: 4px;
            }
            QSplitter::handle:horizontal:hover {
                background-color: #3498DB;
            }
        """)

    def closeEvent(self, event):
        """Handle window close."""
        self.save_memory()
        event.accept()

    def resizeEvent(self, event):
        """Handle window resize."""
        super().resizeEvent(event)
        # Hide dropdown on resize
        if self.search_dropdown:
            self.search_dropdown.hide()


def get_resource_path(filename: str) -> str:
    """Get path to resource file. Works in dev mode and PyInstaller."""
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    # For --onedir, check if we're in _internal folder
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(getattr(sys, '_MEIPASS'), filename)
    # Development mode - file is next to main.py
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    icon_path = get_resource_path("periodic-table.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Set application font
    font = QFont(FONT, 10)
    app.setFont(font)

    window = PeriodicTableApp()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
