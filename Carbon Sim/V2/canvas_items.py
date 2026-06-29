"""QGraphicsItem subclasses for atoms and bonds."""

import logging
import math

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QBrush, QPen, QColor, QFont, QFontMetrics, QRadialGradient, QPolygonF
from PyQt6.QtWidgets import QGraphicsItem

from config import COLORS, RADIUS, BOND_ORDER_VALUE
from models import Atom, Bond, Molecule

logger = logging.getLogger(__name__)


def _brightness(rgb: tuple) -> float:
    return (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000


def _lighten(c: QColor, amount: int = 40) -> QColor:
    return QColor(min(255, c.red() + amount), min(255, c.green() + amount), min(255, c.blue() + amount))


def _darken(c: QColor, amount: int = 30) -> QColor:
    return QColor(max(0, c.red() - amount), max(0, c.green() - amount), max(0, c.blue() - amount))


class AtomItem(QGraphicsItem):
    def __init__(self, atom: Atom, zoom: float = 1.0, parent=None):
        super().__init__(parent)
        self.atom = atom
        self.zoom = zoom
        self._base_radius = RADIUS.get(atom.element, 12)
        self._selected = False
        self.setPos(atom.x, atom.y)
        self.setZValue(10)

    def boundingRect(self) -> QRectF:
        try:
            r = self._radius() + 8
            return QRectF(-r, -r, r * 2, r * 2)
        except Exception as e:
            logger.exception(f"AtomItem boundingRect error: {e}")
            return QRectF(-12, -12, 24, 24)

    def _radius(self) -> int:
        try:
            if self.atom.element == 'H':
                return max(int(self._base_radius * self.zoom), 2)
            else:
                return max(int(self._base_radius * self.zoom * 0.75), 2)
        except Exception as e:
            logger.exception(f"AtomItem _radius error: {e}")
            return 12

    def set_selected(self, selected: bool):
        try:
            self._selected = selected
            self.update()
        except Exception as e:
            logger.exception(f"AtomItem set_selected error: {e}")

    def set_zoom(self, zoom: float):
        try:
            self.prepareGeometryChange()
            self.zoom = zoom
            self.update()
        except Exception as e:
            logger.exception(f"AtomItem set_zoom error: {e}")

    def update_position(self):
        try:
            self.setPos(self.atom.x, self.atom.y)
        except Exception as e:
            logger.exception(f"AtomItem update_position error: {e}")

    def paint(self, painter, option, widget=None):
        try:
            r = self._radius()
            if self._selected:
                halo_r = r + max(4, int(5 * self.zoom))
                painter.setPen(QPen(QColor(255, 220, 130), 3))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(0, 0), halo_r, halo_r)
            base_color = QColor(*COLORS.get(self.atom.element, (200, 200, 200)))
            grad = QRadialGradient(QPointF(-r * 0.35, -r * 0.35), r * 1.6)
            grad.setColorAt(0.0, _lighten(base_color, 50))
            grad.setColorAt(0.5, base_color)
            grad.setColorAt(1.0, _darken(base_color, 40))
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(QColor(8, 14, 20), max(1, int(1.5 * self.zoom))))
            painter.drawEllipse(QPointF(0, 0), r, r)
            draw_text = r > 8
            if draw_text:
                font_size = max(8, int(13 * self.zoom))
                font = QFont('Arial', font_size)
                font.setBold(True)
                painter.setFont(font)
                text = self.atom.element
                bright = _brightness(COLORS.get(self.atom.element, (128, 128, 128)))
                text_color = QColor(8, 14, 20) if bright > 170 else QColor(230, 240, 255)
                painter.setPen(QPen(text_color))
                text_rect = QRectF(-r, -r, r * 2, r * 2)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
                if self.atom.formal_charge != 0:
                    sign = '+' if self.atom.formal_charge > 0 else ''
                    charge_text = f'{sign}{self.atom.formal_charge}'
                    cfont = QFont('Arial', max(7, int(9 * self.zoom)))
                    cfont.setBold(True)
                    painter.setFont(cfont)
                    cmetrics = QFontMetrics(cfont)
                    cw = cmetrics.horizontalAdvance(charge_text)
                    painter.setPen(QPen(QColor(230, 240, 255)))
                    painter.drawText(int(-cw / 2), int(-r - 4), charge_text)
        except Exception as e:
            logger.exception(f'Error painting atom {self.atom.id}: {e}')


class BondItem(QGraphicsItem):
    def __init__(self, bond: Bond, mol: Molecule, zoom: float = 1.0, parent=None):
        super().__init__(parent)
        self.bond = bond
        self.mol = mol
        self.zoom = zoom
        self._selected = False
        self.setZValue(5)

    def boundingRect(self) -> QRectF:
        try:
            a1 = self.mol.get_atom(self.bond.a1)
            a2 = self.mol.get_atom(self.bond.a2)
            if not a1 or not a2:
                return QRectF()
            order = BOND_ORDER_VALUE.get(self.bond.type, 1)
            if self.bond.type == 'A':
                line_count = 2
            elif self.bond.type == 'DA':
                line_count = 1
            else:
                line_count = max(int(order), 1)
            spacing = 6 * self.zoom
            margin = 10 + (line_count - 1) * spacing / 2 + 4
            left = min(a1.x, a2.x) - margin
            top = min(a1.y, a2.y) - margin
            right = max(a1.x, a2.x) + margin
            bottom = max(a1.y, a2.y) + margin
            return QRectF(left, top, right - left, bottom - top)
        except Exception as e:
            logger.exception(f"BondItem boundingRect error: {e}")
            return QRectF()

    def set_selected(self, selected: bool):
        try:
            self._selected = selected
            self.update()
        except Exception as e:
            logger.exception(f"BondItem set_selected error: {e}")

    def set_zoom(self, zoom: float):
        try:
            self.zoom = zoom
            self.update()
        except Exception as e:
            logger.exception(f"BondItem set_zoom error: {e}")

    def paint(self, painter, option, widget=None):
        try:
            a1 = self.mol.get_atom(self.bond.a1)
            a2 = self.mol.get_atom(self.bond.a2)
            if not a1 or not a2:
                return
            ax, ay = a1.x, a1.y
            bx, by = a2.x, a2.y
            dx, dy = bx - ax, by - ay
            d = math.hypot(dx, dy)
            if d == 0:
                return
            nx, ny = -dy / d, dx / d
            ux, uy = dx / d, dy / d
            color = QColor(255, 240, 120) if self._selected else QColor(220, 235, 255)
            width = max(2, int(3 * self.zoom))
            if self._selected:
                width = max(3, int(5 * self.zoom))
            pen = QPen(color, width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            spacing = 6 * self.zoom

            if self.bond.type == 'A':
                painter.drawLine(int(ax), int(ay), int(bx), int(by))
                inset = min(10 * self.zoom, d * 0.4)
                ix1, iy1 = ax + ux * inset, ay + uy * inset
                ix2, iy2 = bx - ux * inset, by - uy * inset
                offset = spacing * 0.9
                ox1, oy1 = ix1 + nx * offset, iy1 + ny * offset
                ox2, oy2 = ix2 + nx * offset, iy2 + ny * offset
                dash_pen = QPen(pen)
                dash_pen.setStyle(Qt.PenStyle.DashLine)
                dash_pen.setWidth(max(1, int(width * 0.8)))
                painter.setPen(dash_pen)
                painter.drawLine(int(ox1), int(oy1), int(ox2), int(oy2))
                return

            if self.bond.type == 'DA':
                a2_r = RADIUS.get(a2.element, 12) * self.zoom * (1.0 if a2.element == 'H' else 0.75)
                tip_x, tip_y = bx - ux * a2_r, by - uy * a2_r
                head_len = max(6.0, 9 * self.zoom)
                head_w = head_len * 0.55
                shaft_end = max(0.0, (d - a2_r) - head_len)
                sx, sy = ax + ux * shaft_end, ay + uy * shaft_end
                painter.drawLine(int(ax), int(ay), int(sx), int(sy))
                tip = QPointF(tip_x, tip_y)
                base_l = QPointF(sx + nx * head_w, sy + ny * head_w)
                base_r = QPointF(sx - nx * head_w, sy - ny * head_w)
                painter.setBrush(QBrush(color))
                painter.drawPolygon(QPolygonF([tip, base_l, base_r]))
                return

            order = BOND_ORDER_VALUE.get(self.bond.type, 1)
            line_count = max(int(order), 1)
            for i in range(line_count):
                offset = (i - (line_count - 1) / 2) * spacing
                x1 = ax + nx * offset
                y1 = ay + ny * offset
                x2 = bx + nx * offset
                y2 = by + ny * offset
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        except Exception as e:
            logger.exception(f'Error painting bond {self.bond.a1}-{self.bond.a2}: {e}')

    def hit_test(self, px: float, py: float, threshold: float = 8) -> bool:
        a1 = self.mol.get_atom(self.bond.a1)
        a2 = self.mol.get_atom(self.bond.a2)
        if not a1 or not a2:
            return False
        ax, ay = a1.x, a1.y
        bx, by = a2.x, a2.y
        dx, dy = bx - ax, by - ay
        d = math.hypot(dx, dy) or 1
        nx, ny = -dy / d, dx / d
        order = BOND_ORDER_VALUE.get(self.bond.type, 1)
        if self.bond.type == 'A':
            line_count = 2
        elif self.bond.type == 'DA':
            line_count = 1
        else:
            line_count = max(int(order), 1)
        spacing = 6
        for o in range(line_count):
            off = (o - (line_count - 1) / 2) * spacing
            x1 = ax + nx * off
            y1 = ay + ny * off
            x2 = bx + nx * off
            y2 = by + ny * off
            vx, vy = x2 - x1, y2 - y1
            wx, wy = px - x1, py - y1
            vlen2 = vx * vx + vy * vy
            if vlen2 == 0:
                dist = math.hypot(px - x1, py - y1)
                if dist <= threshold:
                    return True
                continue
            t = max(0.0, min(1.0, (wx * vx + wy * vy) / vlen2))
            projx = x1 + t * vx
            projy = y1 + t * vy
            dist = math.hypot(px - projx, py - projy)
            if dist <= threshold:
                return True
        return False
