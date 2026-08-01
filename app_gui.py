import os
import sys
import time
import threading
import subprocess
import shutil
import glob as _glob
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import cv2
import numpy as np
from PyQt6.QtCore import Qt, QSize, QTimer, QSettings, pyqtSignal, QStringListModel, QObject, QThread
from PyQt6.QtGui import QAction, QFont, QIcon, QImage, QPixmap
from PyQt6.QtWidgets import QCompleter
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QLineEdit, QFileDialog,
    QMessageBox, QProgressBar, QTextEdit, QGroupBox, QFormLayout,
    QDoubleSpinBox, QSpinBox, QCheckBox, QSlider, QScrollArea,
    QListWidget, QListWidgetItem, QDialog, QComboBox,
    QRadioButton, QButtonGroup,
    QFrame, QSizePolicy, QSplitter, QGridLayout, QMenu,
)

from gui_bridge import ExtractionSignals
from src.api.gui_api import GuiApi, ScoreInfo
from src.infrastructure.file_service import FileService


# ── Debug logging ──────────────────────────────────────────────────────
DEBUG_GUI = os.environ.get("DEBUG_GUI", "0") == "1"

def dbg(msg: str):
    if DEBUG_GUI:
        print(f"[GUI DEBUG] {msg}", flush=True)


# ── Palette (piano ebony-and-brass) ───────────────────────────────────

BG        = "#161616"
SURFACE   = "#1e1e1e"
SURFACE2  = "#282828"
INK       = "#e8e8e8"
MUTED     = "#888888"
BRASS     = "#d4a843"
BRASS_H   = "#e0b85a"
WOOD      = "#6d4c2a"
GREEN     = "#5aaa5a"
DANGER    = "#cc4444"
BORDER    = "#333333"
BORDER2   = "#444444"

# ── Spacing scale (4px base) ──────────────────────────────────────────

SPACE_XXS = 2
SPACE_XS  = 4
SPACE_SM  = 8
SPACE_MD  = 12
SPACE_LG  = 16
SPACE_XL  = 24

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG};
    color: {INK};
    font-family: "Segoe UI", "Noto Sans SC", "Noto Sans JP", "Noto Sans", sans-serif;
    font-size: 13px;
    letter-spacing: 0.3px;
}}
QWidget#roundedWidget {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QTabWidget::pane {{
    background: transparent;
    border: none;
}}
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 20px;
    margin-right: 4px;
    font-weight: 600;
    font-size: 14px;
}}
QTabBar::tab:hover {{
    color: {INK};
}}
QTabBar::tab:selected {{
    color: {BRASS};
    border-bottom: 2px solid {BRASS};
}}
QPushButton {{
    background: {BRASS};
    color: {BG};
    border: 2px solid transparent;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 700;
    font-size: 13px;
}}
QPushButton:hover {{
    background: {BRASS_H};
}}
QPushButton:pressed {{
    background: #b89230;
}}
QPushButton:disabled {{
    background: {SURFACE2};
    color: {MUTED};
}}
QPushButton.secondary {{
    background: transparent;
    color: {INK};
    border: 2px solid {BORDER2};
    padding: 8px 14px;
}}
QPushButton.secondary:hover {{
    background: {SURFACE2};
    border-color: {BRASS};
}}
QPushButton.danger {{
    background: transparent;
    color: {DANGER};
    border: 2px solid {DANGER};
}}
QPushButton.danger:hover {{
    background: {DANGER};
    color: white;
}}
QPushButton:focus {{
    border: 2px solid {BRASS};
}}
QPushButton.secondary:focus {{
    border: 2px solid {BRASS};
}}
QPushButton.danger:focus {{
    border: 2px solid {BRASS};
}}
QPushButton:focus:disabled {{
    border: 2px solid {BORDER};
}}
QLineEdit {{
    background: #0d0d0d;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 12px;
    color: {INK};
    selection-background-color: {BRASS};
    selection-color: {BG};
}}
QLineEdit:focus {{
    border-color: {BRASS};
}}
QDoubleSpinBox, QSpinBox {{
    background: #0d0d0d;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 12px;
    color: {INK};
    min-height: 28px;
    font-size: 14px;
    selection-background-color: {BRASS};
    selection-color: {BG};
}}
QDoubleSpinBox:hover, QSpinBox:hover {{
    border-color: {BORDER2};
}}
QDoubleSpinBox:focus, QSpinBox:focus {{
    border-color: {BRASS};
}}
QDoubleSpinBox:disabled, QSpinBox:disabled {{
    background: {SURFACE2};
    color: {MUTED};
}}
QDoubleSpinBox::up-button, QSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    border: none;
    background: transparent;
}}
QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
    image: url(__SPIN_UP_PLACEHOLDER__);
    width: 10px;
    height: 10px;
}}
QDoubleSpinBox::down-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    border: none;
    background: transparent;
}}
QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
    image: url(__SPIN_DOWN_PLACEHOLDER__);
    width: 10px;
    height: 10px;
}}
QGroupBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 20px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: {BRASS};
    font-weight: 600;
    letter-spacing: 0.5px;
}}
QCheckBox {{
    spacing: 8px;
    color: {INK};
    background: transparent;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {BORDER2};
    background: #0d0d0d;
}}
QCheckBox::indicator:checked {{
    background: {BRASS};
    border-color: {BRASS};
    image: url(__CHECK_PLACEHOLDER__);
}}
QCheckBox::indicator:hover {{
    border-color: {BRASS};
}}
QSlider::groove:horizontal {{
    background: {SURFACE2};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {BRASS};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: {BRASS_H};
}}
QSlider::sub-page:horizontal {{
    background: {BRASS};
    border-radius: 2px;
}}
QProgressBar {{
    background: #0d0d0d;
    border: 1px solid {BORDER};
    border-radius: 6px;
    text-align: center;
    height: 28px;
    font-weight: 600;
    color: {INK};
}}
QProgressBar::chunk {{
    background: {BRASS};
    border-radius: 5px;
}}
QTextEdit {{
    background: #0d0d0d;
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {INK};
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    padding: 6px;
}}
QTextEdit:focus {{
    border-color: {BRASS};
}}
QListWidget {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {INK};
}}
QListWidget::item:selected {{
    background: {SURFACE2};
    border: 1px solid {BRASS};
    border-radius: 6px;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QLabel {{
    color: {INK};
    background: transparent;
}}
QLabel.muted, QLabel#muted {{
    color: {MUTED};
    font-size: 12px;
    font-weight: 400;
    letter-spacing: 0.4px;
}}
QLabel.param, QLabel#param {{
    color: #9a9a9a;
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.3px;
}}
QLabel.title, QLabel#title {{
    font-size: 22px;
    font-weight: 700;
    color: {INK};
    letter-spacing: 0.5px;
}}
QLabel.count, QLabel#count {{
    font-size: 14px;
    font-weight: 600;
    color: {BRASS};
    letter-spacing: 0.4px;
}}
QComboBox {{
    background: #0d0d0d;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 12px;
    color: {INK};
    min-height: 24px;
}}
QComboBox:focus {{
    border-color: {BRASS};
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
    subcontrol-position: center right;
}}
QComboBox::down-arrow {{
    image: url(__CHEVRON_PLACEHOLDER__);
    width: 12px;
    height: 12px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {BORDER2};
    border-radius: 4px;
    outline: none;
    padding: 4px 0px;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 12px;
    min-height: 24px;
    color: {INK};
    border: none;
}}
QComboBox QAbstractItemView::item:selected {{
    background: {SURFACE2};
    color: {BRASS};
}}
QComboBox QAbstractItemView::item:hover {{
    background: {SURFACE2};
    color: {INK};
}}
QSplitter::handle {{
    background: {BORDER};
    width: 1px;
}}
QFrame#hline {{
    color: {BORDER};
}}
QScrollBar:vertical {{
    background: {BG};
    width: 8px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {SURFACE2};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {BORDER2};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {BG};
    height: 8px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {SURFACE2};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {BORDER2};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QRadioButton {{
    color: {INK};
    spacing: 8px;
    background: transparent;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 1px solid {BORDER2};
    background: #0d0d0d;
}}
QRadioButton::indicator:checked {{
    background: {BRASS};
    border-color: {BRASS};
}}
QRadioButton::indicator:hover {{
    border-color: {BRASS};
}}
"""


CHECK_INDICATOR_PATH: str = ""
CHEVRON_PATH: str = ""
SPIN_UP_PATH: str = ""
SPIN_DOWN_PATH: str = ""


def _generate_check_pixmap() -> str:
    from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
    import tempfile
    path = os.path.join(tempfile.gettempdir(), f"score_extractor_check_{os.getpid()}.png")
    pm = QPixmap(36, 36)
    pm.setDevicePixelRatio(2)
    pm.fill(QColor(Qt.GlobalColor.transparent))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("white"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawLine(8, 22, 16, 28)
    p.drawLine(16, 28, 28, 10)
    p.end()
    pm.save(path)
    return path.replace("\\", "/")


def _generate_chevron_pixmap() -> str:
    from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
    import tempfile
    path = os.path.join(tempfile.gettempdir(), f"score_extractor_chevron_{os.getpid()}.png")
    pm = QPixmap(24, 24)
    pm.setDevicePixelRatio(2)
    pm.fill(QColor(Qt.GlobalColor.transparent))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(BRASS), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawLine(4, 8, 12, 16)
    p.drawLine(12, 16, 20, 8)
    p.end()
    pm.save(path)
    return path.replace("\\", "/")


def _generate_spin_arrow_pixmap(up: bool) -> str:
    from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
    import tempfile
    name = "up" if up else "down"
    path = os.path.join(tempfile.gettempdir(), f"score_extractor_spin_{name}_{os.getpid()}.png")
    pm = QPixmap(24, 24)
    pm.setDevicePixelRatio(2)
    pm.fill(QColor(Qt.GlobalColor.transparent))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(BRASS), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if up:
        p.drawLine(4, 16, 12, 8)
        p.drawLine(12, 8, 20, 16)
    else:
        p.drawLine(4, 8, 12, 16)
        p.drawLine(12, 16, 20, 8)
    p.end()
    pm.save(path)
    return path.replace("\\", "/")


def _set_widget_class(widget, cls: str):
    widget.setProperty("class", cls)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _fit_button_width(button, padding: int = 40):
    metrics = button.fontMetrics()
    text_width = metrics.horizontalAdvance(button.text())
    button.setMinimumWidth(text_width + padding)


# ── Crop Preview Widget ──────────────────────────────────────────────

class CropPreviewWidget(QWidget):
    crop_ratio_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._ratio = 0.35
        self._drag_active = False
        self._image_rect = None
        self.setMinimumSize(320, 120)
        self.setMouseTracking(True)
        self._cursor_over_line = False

    def set_frame(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.update()

    def set_ratio(self, ratio: float):
        self._ratio = max(0.05, min(0.95, ratio))
        self.update()

    def get_ratio(self) -> float:
        return self._ratio

    def paintEvent(self, event):
        super().paintEvent(event)
        from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = self.width()
        h = self.height()

        if self._pixmap and not self._pixmap.isNull():
            # Scale pixmap to fit
            scaled = self._pixmap.scaled(w, h - 30,
                                          Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
            pw = scaled.width()
            ph = scaled.height()
            ox = (w - pw) // 2
            oy = (h - 30 - ph) // 2
            self._image_rect = (ox, oy, pw, ph)
            painter.drawPixmap(ox, oy, scaled)

            # Overlay: transparent red band from top to crop line
            line_y = oy + int(ph * self._ratio)
            overlay = QColor(212, 168, 67, 40)
            painter.fillRect(ox, oy, pw, line_y - oy, overlay)

            # Crop line
            pen = QPen(QColor(212, 168, 67), 2)
            painter.setPen(pen)
            painter.drawLine(ox, line_y, ox + pw, line_y)

            # Grip ridges at center (indicates draggable)
            pen_grip = QPen(QColor(212, 168, 67), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_grip)
            cx = ox + pw // 2
            half = 8
            for dy in (-4, 0, 4):
                painter.drawLine(cx - half, line_y + dy, cx + half, line_y + dy)

            # Label
            painter.setPen(QColor(212, 168, 67))
            font = QFont("Segoe UI")
            font.setPixelSize(14)
            font.setWeight(QFont.Weight.DemiBold)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.4)
            painter.setFont(font)
            label = f"Crop: {int(self._ratio * 100)}%"
            painter.drawText(ox, line_y - 16, label)
        else:
            painter.setPen(QColor(136, 136, 136))
            font = QFont("Segoe UI")
            font.setPixelSize(13)
            font.setWeight(QFont.Weight.Normal)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Open a video to preview the crop overlay")

    def mousePressEvent(self, event):
        if self._image_rect and self._pixmap:
            ox, oy, pw, ph = self._image_rect
            line_y = oy + int(ph * self._ratio)
            if abs(event.position().y() - line_y) < 12:
                self._drag_active = True

    def mouseMoveEvent(self, event):
        if self._drag_active and self._image_rect:
            ox, oy, pw, ph = self._image_rect
            rel_y = event.position().y() - oy
            ratio = max(0.05, min(0.95, rel_y / ph))
            if ratio != self._ratio:
                self._ratio = ratio
                self.crop_ratio_changed.emit(self._ratio)
                self.update()
        elif self._image_rect:
            ox, oy, pw, ph = self._image_rect
            line_y = oy + int(ph * self._ratio)
            near = abs(event.position().y() - line_y) < 12
            if near != self._cursor_over_line:
                self._cursor_over_line = near
                self.setCursor(Qt.CursorShape.SizeVerCursor if near
                               else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self._drag_active = False


# ── Dual-Handle Seek Bar (start time + end duration in one widget) ────

class DualHandleSeekBar(QWidget):
    seek_changed = pyqtSignal(float)  # emits active handle timestamp

    def __init__(self, parent=None):
        super().__init__(parent)
        self._duration = 0.0
        self._start = 0.0       # fraction 0..1
        self._end = 1.0         # fraction 0..1
        self._start_enabled = True
        self._end_enabled = False
        self._dragging: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        # Groove surface
        self.groove = QWidget()
        self.groove.setMinimumHeight(32)
        self.groove.setMouseTracking(True)
        self.groove.setToolTip(
            "Drag the brass handles to set where extraction begins and ends."
        )
        layout.addWidget(self.groove)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.setSpacing(4)
        self.start_cb = QCheckBox("Trim start")
        self.start_cb.setChecked(True)
        self.start_cb.setToolTip(
            "Extraction skips the start of the video.\n"
            "The first 2 seconds are skipped by default so the\n"
            "camera settling isn't captured. Uncheck to start\n"
            "from the very beginning."
        )
        self.start_label = QLabel("")
        _set_widget_class(self.start_label, "muted")
        self.start_label.setFixedWidth(88)
        ctrl.addWidget(self.start_cb)
        ctrl.addWidget(self.start_label)

        self.end_cb = QCheckBox("Trim end")
        self.end_cb.setChecked(False)
        self.end_cb.setToolTip(
            "Extraction stops before the end of the video,\n"
            "skipping the closing tail (e.g. the camera being put down)."
        )
        self.end_label = QLabel("")
        _set_widget_class(self.end_label, "muted")
        self.end_label.setFixedWidth(88)
        self.dur_label = QLabel("")
        _set_widget_class(self.dur_label, "muted")
        self.dur_label.setFixedWidth(80)
        ctrl.addStretch()
        ctrl.addWidget(self.end_cb)
        ctrl.addWidget(self.end_label)
        ctrl.addWidget(self.dur_label)
        layout.addLayout(ctrl)

        # Connections
        self.start_cb.toggled.connect(self._on_start_toggled)
        self.end_cb.toggled.connect(self._on_end_toggled)
        self.groove.paintEvent = lambda e: self._paint_groove(e)
        self.groove.mousePressEvent = self._groove_press
        self.groove.mouseMoveEvent = self._groove_move
        self.groove.mouseReleaseEvent = lambda e: self._groove_release(e)

    # ── Public API ──

    def set_duration(self, secs: float):
        self._duration = secs
        self._update_labels()
        self.groove.update()

    def set_start(self, ts: float):
        if self._duration > 0:
            self._start = max(0.0, min(ts / self._duration, self._end))
            self.groove.update()
            self._update_labels()

    def set_end(self, ts: float):
        if self._duration > 0:
            self._end = max(self._start, min(ts / self._duration, 1.0))
            self.groove.update()
            self._update_labels()

    def get_start(self) -> float:
        return -1.0 if not self._start_enabled else self._start * self._duration

    def get_end(self) -> float:
        if not self._end_enabled:
            return self._duration if self._duration > 0 else 0.0
        return self._end * self._duration

    # ── Internals ──

    def _on_start_toggled(self, checked: bool):
        self._start_enabled = checked
        self.groove.update()
        self._update_labels()

    def _on_end_toggled(self, checked: bool):
        self._end_enabled = checked
        self.groove.update()
        self._update_labels()

    @staticmethod
    def _fmt_time(secs: float) -> str:
        """Format seconds as m:ss.t (or h:mm:ss.t for long videos)."""
        tenths = max(0, int(round(secs * 10)))
        total_secs = tenths / 10
        minutes, s = divmod(total_secs, 60)
        minutes = int(minutes)
        if minutes >= 60:
            hours, minutes = divmod(minutes, 60)
            return f"{hours}:{minutes:02d}:{s:04.1f}"
        return f"{minutes}:{s:04.1f}"

    def _update_labels(self):
        if self._duration > 0:
            start_skip = self._start * self._duration if self._start_enabled else 0.0
            end_skip = (1.0 - self._end) * self._duration if self._end_enabled else 0.0
            self.start_label.setText(
                f"Skip {self._fmt_time(start_skip)}" if self._start_enabled else "No skip")
            self.end_label.setText(
                f"Skip {self._fmt_time(end_skip)}" if self._end_enabled else "No skip")
            self.dur_label.setText(f"/ {self._fmt_time(self._duration)}")
        else:
            self.start_label.setText("")
            self.end_label.setText("")
            self.dur_label.setText("")

    def _paint_groove(self, event):
        from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
        painter = QPainter(self.groove)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.groove.width()
        h = self.groove.height()
        mid = h // 2
        margin = 16
        track_w = w - margin * 2
        x1 = int(margin + track_w * self._start)
        x2 = int(margin + track_w * self._end)

        # Groove background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(SURFACE2))
        painter.drawRoundedRect(margin, mid - 3, track_w, 6, 3, 3)

        # Highlighted range when both enabled
        if self._start_enabled and self._end_enabled and x2 > x1:
            painter.setBrush(QColor(BRASS))
            painter.drawRoundedRect(x1, mid - 3, x2 - x1, 6, 3, 3)

        # Start handle (24px diameter for 44pt hit target)
        if self._start_enabled:
            painter.setBrush(QColor(BRASS))
            painter.setPen(QPen(QColor(BG), 2))
            painter.drawEllipse(x1 - 12, mid - 12, 24, 24)

        # End handle (24px diameter)
        if self._end_enabled:
            painter.setBrush(QColor(BRASS))
            painter.setPen(QPen(QColor(BG), 2))
            painter.drawEllipse(x2 - 12, mid - 12, 24, 24)

        painter.end()

    def _groove_press(self, event):
        if self._duration <= 0:
            return
        from PyQt6.QtCore import QPointF
        pos: QPointF = event.position()
        w = self.groove.width()
        margin = 16
        track_w = w - margin * 2
        mx = pos.x()
        my = pos.y()
        mid = self.groove.height() // 2

        def dist_to(x):
            return ((mx - x) ** 2 + (my - mid) ** 2) ** 0.5

        x_start = margin + track_w * self._start
        x_end = margin + track_w * self._end
        d_start = dist_to(x_start) if self._start_enabled else 999
        d_end = dist_to(x_end) if self._end_enabled else 999

        if d_start < 22 and d_start <= d_end:
            self._dragging = 'start'
        elif d_end < 22:
            self._dragging = 'end'
        else:
            self._dragging = None

    def _groove_move(self, event):
        if self._duration <= 0:
            return
        pos = event.position()
        w = self.groove.width()
        margin = 16
        track_w = max(w - margin * 2, 1)
        mx = pos.x()
        my = pos.y()
        mid = self.groove.height() // 2

        if self._dragging:
            frac = max(0.0, min(1.0, (mx - margin) / track_w))
            if self._dragging == 'start':
                self._start = min(frac, self._end)
            else:
                self._end = max(frac, self._start)
            self.groove.update()
            self._update_labels()
            ts = frac * self._duration
            self.seek_changed.emit(ts)
        else:
            # Cursor hover
            x_start = margin + track_w * self._start
            x_end = margin + track_w * self._end
            def dist_to(x):
                return ((mx - x) ** 2 + (my - mid) ** 2) ** 0.5
            near_start = self._start_enabled and dist_to(x_start) < 22
            near_end = self._end_enabled and dist_to(x_end) < 22
            self.groove.setCursor(Qt.CursorShape.SizeHorCursor if (near_start or near_end)
                                  else Qt.CursorShape.ArrowCursor)

    def _groove_release(self, event):
        self._dragging = None
        self.groove.setCursor(Qt.CursorShape.ArrowCursor)


# ── Welcome / Onboarding Widget ─────────────────────────────────────

class WelcomeWidget(QWidget):
    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("roundedWidget")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {SURFACE}; border-radius: 8px; }}")

        inner = QWidget()
        inner.setStyleSheet(f"background: {SURFACE};")
        layout = QVBoxLayout(inner)
        layout.setSpacing(SPACE_LG)
        layout.setContentsMargins(SPACE_XL, SPACE_XL, SPACE_XL, SPACE_XL)

        title = QLabel("Welcome to Score Extractor")
        _set_widget_class(title, "title")
        layout.addWidget(title)

        accent = QFrame()
        accent.setFrameShape(QFrame.Shape.HLine)
        accent.setFixedHeight(1)
        accent.setFixedWidth(60)
        accent.setStyleSheet(f"background: {BRASS}; border: none;")
        layout.addWidget(accent)

        subtitle = QLabel(
            "Turn your sheet music videos into a clean, printable PDF "
            "\u2014 no screenshots, no manual cropping."
        )
        _set_widget_class(subtitle, "muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        steps = QVBoxLayout()
        steps.setSpacing(SPACE_MD)
        steps.setContentsMargins(0, 0, 0, 0)
        steps.addWidget(self._step_card(
            "1", "Choose your video",
            "Load a local file or paste a YouTube URL. "
            "Film from directly above the music stand with the score filling the frame."
        ))
        steps.addWidget(self._step_card(
            "2", "Name your score",
            "The name appears in the PDF title and helps you find it later. "
            "Start typing to pick up an existing score."
        ))
        steps.addWidget(self._step_card(
            "3", "Extract and review",
            "The tool finds every page turn automatically. "
            "Review the captured pages and your PDF is ready."
        ))
        layout.addLayout(steps)

        layout.addSpacing(SPACE_SM)

        footer = QHBoxLayout()
        self._dont_show = QCheckBox("Do not show on next launch")
        self._dont_show.setStyleSheet("background: transparent;")
        footer.addWidget(self._dont_show)
        footer.addStretch()
        dismiss_btn = QPushButton("Start using Score Extractor")
        dismiss_btn.clicked.connect(self._on_dismiss)
        footer.addWidget(dismiss_btn)
        layout.addLayout(footer)

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def _step_card(self, number: str, heading: str, description: str) -> QWidget:
        card = QWidget()
        card.setStyleSheet(f"""
            background: {SURFACE2};
            border-radius: 8px;
            border: 1px solid {BORDER};
        """)
        hbox = QHBoxLayout(card)
        hbox.setContentsMargins(SPACE_MD, SPACE_MD, SPACE_MD, SPACE_MD)
        hbox.setSpacing(SPACE_MD)

        badge = QLabel(number)
        badge.setFixedSize(32, 32)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"""
            background: {BRASS};
            color: {BG};
            border-radius: 16px;
            font-size: 16px;
            font-weight: 700;
            border: none;
        """)
        hbox.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(SPACE_XXS)
        head = QLabel(heading)
        head.setStyleSheet(
            f"font-weight: 600; font-size: 14px; color: {INK}; "
            "border: none; background: transparent;"
        )
        text_col.addWidget(head)
        desc = QLabel(description)
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {MUTED}; font-size: 12px; "
            "font-weight: 400; border: none; background: transparent;"
        )
        text_col.addWidget(desc)
        hbox.addLayout(text_col, 1)

        return card

    def _on_dismiss(self):
        settings = QSettings("ScoreExtractor", "App")
        if self._dont_show.isChecked():
            settings.setValue("onboarding_welcome_seen", True)
        self.dismissed.emit()


class GettingStartedDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Getting Started \u2014 Score Extractor")
        self.resize(580, 520)

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACE_MD)
        layout.setContentsMargins(SPACE_XL, SPACE_XL, SPACE_XL, SPACE_LG)

        title = QLabel("Getting Started")
        _set_widget_class(title, "title")
        layout.addWidget(title)

        accent = QFrame()
        accent.setFrameShape(QFrame.Shape.HLine)
        accent.setFixedHeight(1)
        accent.setFixedWidth(60)
        accent.setStyleSheet(f"background: {BRASS}; border: none;")
        layout.addWidget(accent)

        sections = [
            ("1. Choose your video",
             "Score Extractor works with local video files (.mp4, .avi, .mkv, "
             ".mov) and YouTube URLs. The video should show a piano score with "
             "pages being turned \u2014 ideally filmed from directly above the "
             "music stand in steady lighting."),
            ("2. Adjust the crop",
             "Drag the brass overlay line on the video preview to select which "
             "portion of the frame contains sheet music. Everything above the "
             "line is considered content; below is ignored."),
            ("3. Set trim points",
             "Drag the brass handles on the seek bar to skip unwanted sections "
             "at the start or end of your video. The first 2\u00a0seconds are "
             "skipped by default so camera-settling frames are not captured."),
            ("4. Extract pages",
             "Click Start Extraction. The tool automatically finds page turns "
             "and captures each page. You will see pages appear in real time "
             "in the log area."),
            ("5. Review and export",
             "After extraction, review the captured pages \u2014 uncheck any "
             "you do not want. When you are satisfied, your PDF is saved "
             "automatically."),
        ]

        for heading, body in sections:
            head = QLabel(heading)
            head.setStyleSheet(
                f"font-weight: 600; color: {BRASS}; font-size: 13px; "
                "border: none; background: transparent;"
            )
            layout.addWidget(head)
            body_label = QLabel(body)
            body_label.setWordWrap(True)
            body_label.setStyleSheet(
                f"color: {MUTED}; font-size: 12px; font-weight: 400; "
                "border: none; background: transparent;"
            )
            layout.addWidget(body_label)
            layout.addSpacing(SPACE_XS)

        tips_head = QLabel("Tips for best results")
        tips_head.setStyleSheet(
            f"font-weight: 600; color: {INK}; font-size: 13px; "
            "margin-top: 8px; border: none; background: transparent;"
        )
        layout.addWidget(tips_head)
        tips = QLabel(
            "\u2022  Film in landscape orientation with the score filling the frame\n"
            "\u2022  Keep the camera steady \u2014 a tripod or phone stand works best\n"
            "\u2022  Ensure even lighting without glare on the pages\n"
            "\u2022  Turn pages cleanly without blocking the camera\n"
            "\u2022  If pages go undetected, lower the sensitivity in Settings"
        )
        tips.setWordWrap(True)
        tips.setStyleSheet(
            f"color: {MUTED}; font-size: 12px; font-weight: 400; "
            "border: none; background: transparent;"
        )
        layout.addWidget(tips)

        layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)


# ── Page Preview Dialog ──────────────────────────────────────────────

class PagePreviewDialog(QDialog):
    def __init__(self, pixmap: QPixmap, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Page Preview — {title}")
        self.resize(900, 700)

        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        label = QLabel()
        label.setPixmap(pixmap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setWidget(label)
        layout.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)


# ── Review Pages Dialog ──────────────────────────────────────────────

class ReviewPagesDialog(QDialog):
    """Inspect captured pages before the PDF is saved.

    Each page shows a thumbnail and a "Keep" checkbox. Clicking a
    thumbnail opens the full page for close inspection. When accepted,
    kept_mask() reports which pages survive (in capture order).
    """

    def __init__(self, api: GuiApi, parent=None):
        super().__init__(parent)
        self._api = api
        self._count = api.get_page_count()
        self._kept = [True] * self._count

        self.setWindowTitle(f"Review Pages \u2014 {self._count} captured")
        self.resize(1100, 750)
        self.setStyleSheet(
            STYLESHEET.replace("__CHECK_PLACEHOLDER__", CHECK_INDICATOR_PATH)
            .replace("__CHEVRON_PLACEHOLDER__", CHEVRON_PATH)
            .replace("__SPIN_UP_PLACEHOLDER__", SPIN_UP_PATH)
            .replace("__SPIN_DOWN_PLACEHOLDER__", SPIN_DOWN_PATH)
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        root.setSpacing(SPACE_MD)

        header = QHBoxLayout()
        title = QLabel("Review before saving")
        _set_widget_class(title, "title")
        header.addWidget(title)
        header.addStretch()
        select_all = QPushButton("Select All")
        _set_widget_class(select_all, "secondary")
        select_all.clicked.connect(self._select_all)
        deselect_all = QPushButton("Deselect All")
        _set_widget_class(deselect_all, "secondary")
        deselect_all.clicked.connect(self._deselect_all)
        header.addWidget(select_all)
        header.addWidget(deselect_all)
        root.addLayout(header)

        hint = QLabel(
            "Uncheck any page to keep it out of the PDF. "
            "Click a thumbnail to inspect it up close. "
            "Arrow keys to navigate, Space to toggle.")
        _set_widget_class(hint, "muted")
        root.addWidget(hint)

        tiles = QWidget()
        grid = QGridLayout(tiles)
        grid.setSpacing(SPACE_MD)
        cols = 2
        self._checks: list[QCheckBox] = []
        self._thumbs: list[QLabel] = []
        thumb_w = 400
        for i in range(self._count):
            tile = QWidget()
            tile.setObjectName("roundedWidget")
            box = QVBoxLayout(tile)
            box.setSpacing(SPACE_XS)

            thumb = QLabel()
            thumb.setFixedWidth(thumb_w)
            thumb.setMinimumHeight(260)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setCursor(Qt.CursorShape.PointingHandCursor)
            thumb.setScaledContents(False)
            png = api.get_page_thumbnail(i)
            pix = QPixmap()
            if png and pix.loadFromData(png):
                scaled = pix.scaledToWidth(
                    thumb_w - 10, Qt.TransformationMode.SmoothTransformation)
                if scaled.height() > 300:
                    scaled = scaled.copy(0, 0, scaled.width(), min(scaled.height(), 300))
                thumb.setPixmap(scaled)
            thumb.mousePressEvent = (lambda _e, idx=i: self._preview_page(idx))
            self._thumbs.append(thumb)

            check = QCheckBox(f"Page {i + 1}")
            check.setChecked(True)
            check.toggled.connect(lambda _on, idx=i: self._on_toggled(idx))

            box.addWidget(thumb, 0, Qt.AlignmentFlag.AlignHCenter)
            box.addWidget(check, 0, Qt.AlignmentFlag.AlignHCenter)
            self._checks.append(check)
            grid.addWidget(tile, i // cols, i % cols)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tiles)
        scroll.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        root.addWidget(scroll, 1)

        self._summary = QLabel("")
        root.addWidget(self._summary)

        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("Cancel")
        _set_widget_class(close_btn, "secondary")
        close_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save changes")
        save_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        footer.addWidget(save_btn)
        root.addLayout(footer)

        self._update_summary()
        scroll.setFocus()

    def _select_all(self):
        for c in self._checks:
            c.setChecked(True)

    def _deselect_all(self):
        for c in self._checks:
            c.setChecked(False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key.Key_Space:
            focused = self.focusWidget()
            if isinstance(focused, QCheckBox):
                focused.toggle()
        else:
            super().keyPressEvent(event)

    def _update_summary(self):
        kept = sum(self._kept)
        if kept == self._count:
            self._summary.setText("All pages will be in the PDF.")
        else:
            self._summary.setText(f"{kept} of {self._count} pages will be in the PDF.")

    def _on_toggled(self, idx: int):
        self._kept[idx] = self._checks[idx].isChecked()
        self._update_summary()

    def _preview_page(self, idx: int):
        png = self._api.get_page_full(idx)
        pix = QPixmap()
        if png and pix.loadFromData(png):
            PagePreviewDialog(pix, f"Page {idx + 1}", self).exec()

    def kept_mask(self) -> list[bool]:
        return list(self._kept)


# ── Config Tab ───────────────────────────────────────────────────────

class ConfigTab(QWidget):
    def __init__(self, api: GuiApi, parent=None):
        super().__init__(parent)
        self._api = api
        self._updating = False
        self._param_labels: list[QLabel] = []

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(SPACE_MD)

        title = QLabel("Settings")
        _set_widget_class(title, "title")
        layout.addWidget(title)

        accent = QFrame()
        accent.setFrameShape(QFrame.Shape.HLine)
        accent.setFixedHeight(1)
        accent.setFixedWidth(60)
        accent.setStyleSheet(f"background: {BRASS}; border: none;")
        layout.addWidget(accent)

        layout.addSpacing(SPACE_SM)

        desc = QLabel("Adjust extraction behavior. These apply to the next extraction.")
        _set_widget_class(desc, "muted")
        layout.addWidget(desc)

        layout.addSpacing(SPACE_SM)

        # ── Basic / Advanced toggle ──
        self._settings = QSettings("ScoreExtractor", "App")
        self._config_mode = self._settings.value("config_mode", "basic")
        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)
        self._basic_toggle = QPushButton("Basic")
        self._basic_toggle.setCheckable(True)
        self._basic_toggle.setFlat(True)
        self._basic_toggle.setStyleSheet(self._toggle_style(True, True))
        self._advanced_toggle = QPushButton("Advanced")
        self._advanced_toggle.setCheckable(True)
        self._advanced_toggle.setFlat(True)
        self._advanced_toggle.setStyleSheet(self._toggle_style(False, True))
        self._basic_toggle.clicked.connect(lambda: self._set_mode("basic"))
        self._advanced_toggle.clicked.connect(lambda: self._set_mode("advanced"))
        mode_row.addWidget(self._basic_toggle)
        mode_row.addWidget(self._advanced_toggle)
        mode_row.addStretch()
        if self._config_mode == "advanced":
            self._advanced_toggle.setChecked(True)
            self._advanced_toggle.setStyleSheet(self._toggle_style(False, True))
            self._basic_toggle.setStyleSheet(self._toggle_style(True, False))
        layout.addLayout(mode_row)

        # ── Basic settings widget ──
        self.basic_widget = QWidget()
        basic_layout = QVBoxLayout(self.basic_widget)
        basic_layout.setSpacing(SPACE_MD)
        basic_layout.setContentsMargins(0, SPACE_SM, 0, 0)

        basic_group = QGroupBox("Quick Tuning")
        basic_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        basic_form = QFormLayout(basic_group)
        basic_form.setSpacing(SPACE_MD)

        self.basic_sensitivity = self._spin_float(0.0, 1.0, 0.01, 0.96)
        self.basic_sensitivity.setToolTip("Higher values detect only clearer page turns.\nLower to 0.90 if pages are missed.")
        basic_form.addRow(self._form_label("Detection sensitivity:"), self.basic_sensitivity)

        self.basic_speed = QComboBox()
        self.basic_speed.addItem("Slow turner (~5 s pause)", 5.0)
        self.basic_speed.addItem("Medium (~3 s pause)", 3.0)
        self.basic_speed.addItem("Fast turner (~1 s pause)", 1.0)
        self.basic_speed.setToolTip("How quickly pages are turned in your video.\nChoose Slow for deliberate page-turns; Fast for quick flips.")
        basic_form.addRow(self._form_label("Page-turn speed:"), self.basic_speed)

        self.basic_ocr = QCheckBox("Enable text recognition for better dedup")
        self.basic_ocr.setToolTip("Compares the text on each page to catch duplicates.\nRequires PaddleOCR (slightly longer startup).")
        basic_form.addRow("", self.basic_ocr)

        basic_layout.addWidget(basic_group)

        basic_layout.addStretch()
        self.basic_widget.setVisible(self._config_mode == "basic")
        layout.addWidget(self.basic_widget)

        # ── Advanced groups wrapper ──
        self.advanced_widget = QWidget()
        adv_outer = QVBoxLayout(self.advanced_widget)
        adv_outer.setSpacing(SPACE_MD)
        adv_outer.setContentsMargins(0, SPACE_SM, 0, 0)

        # Presets row
        preset_row = QHBoxLayout()
        preset_label = QLabel("Preset:")
        _set_widget_class(preset_label, "param")
        self._preset_combo = QComboBox()
        self._preset_combo.addItem("Custom", None)
        self._preset_combo.addItem("Standard", "standard")
        self._preset_combo.addItem("Concert recording", "concert")
        self._preset_combo.addItem("Phone video", "phone")
        self._preset_combo.setToolTip(
            "Standard: balanced defaults for well-lit tripod recordings.\n"
            "Concert recording: higher sensitivity for dim lighting and slower turns.\n"
            "Phone video: faster detection for hand-held phone footage."
        )
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_row.addWidget(preset_label)
        preset_row.addWidget(self._preset_combo, 1)
        adv_outer.addLayout(preset_row)

        adv_outer.addSpacing(SPACE_SM)

        # ── Detection group ──
        det_group = QGroupBox("Detection")
        det_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        det_form = QFormLayout(det_group)
        det_form.setSpacing(SPACE_MD)

        self.sensitivity = self._spin_float(0.0, 1.0, 0.01, 0.96)
        self.sensitivity.setToolTip(
            "How similar two consecutive frames must be to count as 'unchanged'.\n"
            "Higher values = fewer false triggers but may miss subtle page turns.\n"
            "Safe range: 0.90–0.99. Raise toward 0.99 if the tool triggers on lighting flickers."
        )
        self.min_interval = self._spin_float(0.0, 60.0, 0.5, 3.0)
        self.min_interval.setToolTip(
            "Minimum seconds between page captures, even if changes are detected.\n"
            "Prevents duplicate captures during slow page turns or hand movements.\n"
            "Safe range: 1.0–10.0. Raise to 5+ for slow page-turners."
        )
        self.frame_check = self._spin_float(0.05, 5.0, 0.05, 0.8)
        self.frame_check.setToolTip(
            "How often (in seconds) the video is sampled for page changes.\n"
            "Lower = faster detection but higher CPU usage.\n"
            "Safe range: 0.05–1.0. Use 0.1 for quick extraction, 0.5 to save CPU."
        )
        self.top_ratio = self._spin_float(0.05, 1.0, 0.01, 0.34)
        self.top_ratio.setToolTip(
            "How much of the frame's top portion is compared between frames.\n"
            "Only this region is checked for page changes, ignoring the bottom\n"
            "(typically the piano keyboard or a player UI).\n"
            "Safe range: 0.20\u20130.50."
        )
        self.blank_std = self._spin_float(0.0, 50.0, 0.5, 3.0)
        self.blank_std.setToolTip(
            "Pixel variation below which a frame is considered blank\n"
            "(white/black screen, no sheet music visible). Blank pages are skipped.\n"
            "Safe range: 1.0\u20138.0. Raise above 10 if real pages are being rejected."
        )

        det_form.addRow(self._form_label("Page change sensitivity:"), self.sensitivity)
        det_form.addRow(self._form_label("Pause after page turn (s):"), self.min_interval)
        det_form.addRow(self._form_label("Frame check interval (s):"), self.frame_check)
        det_form.addRow(self._form_label("Content detection region:"), self.top_ratio)
        det_form.addRow(self._form_label("Blank page threshold:"), self.blank_std)
        layout.addWidget(det_group)

        # ── Capture group ──
        cap_group = QGroupBox("Capture Timing")
        cap_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        cap_form = QFormLayout(cap_group)
        cap_form.setSpacing(SPACE_MD)

        self.a_delay = self._spin_float(0.0, 5.0, 0.1, 0.3)
        self.a_delay.setToolTip(
            "Seconds to wait after detecting a page turn before capturing\n"
            "the clean page image. Gives the page time to settle flat.\n"
            "Safe range: 0.0\u20131.0. Increase if captures show a partial turn."
        )
        self.b_delay = self._spin_float(0.0, 10.0, 0.1, 3.0)
        self.b_delay.setToolTip(
            "Seconds to wait after the clean capture before capturing the\n"
            "new page with its turn-line still visible. Longer reveals more\n"
            "of the incoming page for better merge results.\n"
            "Safe range: 1.0\u20136.0. Increase if the turn-line overlaps content."
        )
        self.overlay_width = self._spin_float(0.0, 1.0, 0.01, 0.5)
        self.overlay_width.setToolTip(
            "Width of the vertical turn-line on the second capture,\n"
            "as a fraction of the image width. Marks where the page\n"
            "transition occurred during the turn.\n"
            "Safe range: 0.3\u20130.7."
        )

        cap_form.addRow(self._form_label("Page settle time (s):"), self.a_delay)
        cap_form.addRow(self._form_label("New page reveal (s):"), self.b_delay)
        cap_form.addRow(self._form_label("Turn-line width:"), self.overlay_width)
        layout.addWidget(cap_group)

        # ── Deduplication group ──
        dedup_group = QGroupBox("Deduplication")
        dedup_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        dedup_form = QFormLayout(dedup_group)
        dedup_form.setSpacing(SPACE_MD)

        self.dup_top = self._spin_float(0.0, 1.0, 0.01, 0.27)
        self.dup_top.setToolTip(
            "How much of the top area is compared when checking\n"
            "for duplicate pages. Only this portion is examined\n"
            "for visual similarity between captures.\n"
            "Safe range: 0.15\u20130.40."
        )
        self.pixel_sim = self._spin_float(0.0, 1.0, 0.01, 0.95)
        self.pixel_sim.setToolTip(
            "Minimum visual similarity (0\u20131) for two pages to\n"
            "be considered the same. Higher values mean stricter matching.\n"
            "Safe range: 0.90\u20130.99. Lower toward 0.90 if duplicate pages slip through."
        )
        self.row_sim = self._spin_float(0.0, 1.0, 0.01, 0.98)
        self.row_sim.setToolTip(
            "Minimum row-by-row similarity to treat two pages as\n"
            "duplicates. Checks each horizontal strip independently.\n"
            "Safe range: 0.95\u20130.99."
        )
        self.row_cov = self._spin_float(0.0, 1.0, 0.01, 0.94)
        self.row_cov.setToolTip(
            "Fraction of rows that must match for two pages to be\n"
            "counted as duplicates. Allows minor differences like\n"
            "page numbers while catching identical content.\n"
            "Safe range: 0.85\u20130.98."
        )

        dedup_form.addRow(self._form_label("Similarity check region:"), self.dup_top)
        dedup_form.addRow(self._form_label("Visual match threshold:"), self.pixel_sim)
        dedup_form.addRow(self._form_label("Row match threshold:"), self.row_sim)
        dedup_form.addRow(self._form_label("Row coverage required:"), self.row_cov)
        layout.addWidget(dedup_group)

        # ── OCR group ──
        ocr_group = QGroupBox("OCR")
        ocr_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        ocr_form = QFormLayout(ocr_group)
        ocr_form.setSpacing(SPACE_MD)

        self.ocr_enabled = QCheckBox("Enable OCR")
        self.ocr_enabled.setChecked(False)
        self.ocr_enabled.setToolTip(
            "Compare page text to help catch duplicate pages that\n"
            "look visually similar but have different content.\n"
            "Requires PaddleOCR (slightly slower startup).\n"
            "Recommended when visual-only matching misses duplicates."
        )
        self.ocr_conf = self._spin_int(0, 100, 40)
        self.ocr_conf.setToolTip(
            "Minimum confidence (0\u2013100) a recognized word must have\n"
            "to be used for page comparison.\n"
            "Safe range: 30\u201370. Set to 0 to skip OCR entirely."
        )
        self.ocr_horiz = self._spin_float(0.0, 1.0, 0.01, 0.30)
        self.ocr_horiz.setToolTip(
            "How far across the page (from the left) text is read.\n"
            "Useful for scores where the title sits on the left.\n"
            "Safe range: 0.20\u20130.50. Set to 1.0 for full-width."
        )

        ocr_form.addRow("", self.ocr_enabled)
        ocr_form.addRow(self._form_label("OCR confidence:"), self.ocr_conf)
        ocr_form.addRow(self._form_label("OCR scan width:"), self.ocr_horiz)
        layout.addWidget(ocr_group)

        # ── Advanced group ──
        self.advanced = QGroupBox("Advanced")
        self.advanced.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        adv_form = QFormLayout(self.advanced)
        adv_form.setSpacing(SPACE_MD)

        self.bar_diff = self._spin_float(0.0, 50000.0, 100.0, 500.0)
        self.bar_diff.setToolTip(
            "Minimum intensity difference needed to detect the turn-line\n"
            "on the captured frame. Higher = less sensitive.\n"
            "Safe range: 200\u20132000. Raise if the turn-line is not being found."
        )
        self.bar_pad = self._spin_int(-200, 200, -15)
        self.bar_pad.setToolTip(
            "Pixel offset for the turn-line detection position.\n"
            "Negative shifts left, positive shifts right.\n"
            "Safe range: -50 to +50. Fine-tune when the turn-line\n"
            "appears slightly off from the actual page boundary."
        )

        adv_form.addRow(self._form_label("Turn-line sensitivity:"), self.bar_diff)
        adv_form.addRow(self._form_label("Turn-line position (px):"), self.bar_pad)

        self.debug_cb = QCheckBox("Debug mode (open temp folder on completion)")
        self.debug_cb.setToolTip(
            "When enabled, opens the output folder automatically after extraction\n"
            "so you can inspect intermediate files (cropped frames, debug images).\n"
            "Enable this when diagnosing extraction issues."
        )
        adv_form.addRow(self.debug_cb)

        adv_outer.addWidget(self.advanced)

        if self._param_labels:
            label_w = max(lbl.sizeHint().width() for lbl in self._param_labels) + 12
            for lbl in self._param_labels:
                lbl.setFixedWidth(label_w)

        self.reset_btn = QPushButton("Reset to Defaults")
        _set_widget_class(self.reset_btn, "secondary")
        self.reset_btn.setToolTip("Restore all parameters to their factory defaults")
        self.reset_btn.clicked.connect(self._reset_defaults)
        adv_outer.addWidget(self.reset_btn)

        self.advanced_widget.setVisible(self._config_mode == "advanced")
        layout.addWidget(self.advanced_widget)

        layout.addStretch()

        # Connect signals
        for widget in self._all_spins():
            if isinstance(widget, QDoubleSpinBox):
                widget.valueChanged.connect(self._on_change)
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self._on_change)
        self.ocr_enabled.toggled.connect(self._on_change)
        self.debug_cb.toggled.connect(self._on_debug_toggled)
        self.basic_sensitivity.valueChanged.connect(self._on_basic_sensitivity_changed)
        self.basic_speed.currentIndexChanged.connect(self._on_basic_speed_changed)
        self.basic_ocr.toggled.connect(self._on_basic_ocr_toggled)

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _form_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        _set_widget_class(lbl, "param")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._param_labels.append(lbl)
        return lbl

    @staticmethod
    def _toggle_style(left: bool, selected: bool) -> str:
        if not selected:
            return (f"background: transparent; color: {MUTED}; border: 1px solid {BORDER}; "
                    f"border-radius: {6 if left else 6}px {0 if left else 6}px {0 if left else 6}px {6 if left else 6}px; "
                    "padding: 4px 14px; font-weight: 600; font-size: 13px;")
        return (f"background: {SURFACE2}; color: {BRASS}; border: 1px solid {BRASS}; "
                f"border-radius: {6 if left else 6}px {0 if left else 6}px {0 if left else 6}px {6 if left else 6}px; "
                "padding: 4px 14px; font-weight: 600; font-size: 13px;")

    def _set_mode(self, mode: str):
        self._config_mode = mode
        self._settings.setValue("config_mode", mode)
        self._basic_toggle.setChecked(mode == "basic")
        self._advanced_toggle.setChecked(mode == "advanced")
        self._basic_toggle.setStyleSheet(self._toggle_style(True, mode == "basic"))
        self._advanced_toggle.setStyleSheet(self._toggle_style(False, mode == "advanced"))
        self.basic_widget.setVisible(mode == "basic")
        self.advanced_widget.setVisible(mode == "advanced")
        if mode == "basic":
            self._sync_basic_from_advanced()

    def _sync_basic_from_advanced(self):
        self._updating = True
        try:
            self.basic_sensitivity.setValue(self.sensitivity.value())
            v = self.min_interval.value()
            idx = 0
            if v <= 2.0:
                idx = 2
            elif v <= 4.0:
                idx = 1
            self.basic_speed.setCurrentIndex(idx)
            self.basic_ocr.setChecked(self.ocr_enabled.isChecked())
        finally:
            self._updating = False

    def _on_basic_sensitivity_changed(self, val: float):
        if not self._updating:
            self.sensitivity.setValue(val)
            self.apply_to_api()

    def _on_basic_speed_changed(self, _idx: int):
        if not self._updating:
            self.min_interval.setValue(self.basic_speed.currentData())
            self.apply_to_api()

    def _on_basic_ocr_toggled(self, checked: bool):
        if not self._updating:
            self.ocr_enabled.setChecked(checked)
            self.apply_to_api()

    def _on_preset_changed(self, idx: int):
        data = self._preset_combo.itemData(idx)
        if data is None:
            return
        self._updating = True
        try:
            if data == "standard":
                self.sensitivity.setValue(0.96)
                self.min_interval.setValue(3.0)
                self.frame_check.setValue(0.8)
                self.top_ratio.setValue(0.34)
                self.blank_std.setValue(3.0)
                self.a_delay.setValue(0.3)
                self.b_delay.setValue(3.0)
                self.overlay_width.setValue(0.5)
                self.dup_top.setValue(0.27)
                self.pixel_sim.setValue(0.95)
                self.row_sim.setValue(0.98)
                self.row_cov.setValue(0.94)
                self.bar_diff.setValue(500.0)
                self.bar_pad.setValue(-15)
            elif data == "concert":
                self.sensitivity.setValue(0.94)
                self.min_interval.setValue(5.0)
                self.frame_check.setValue(1.0)
                self.top_ratio.setValue(0.40)
                self.blank_std.setValue(5.0)
                self.a_delay.setValue(0.5)
                self.b_delay.setValue(4.0)
                self.overlay_width.setValue(0.55)
                self.dup_top.setValue(0.30)
                self.pixel_sim.setValue(0.93)
                self.row_sim.setValue(0.97)
                self.row_cov.setValue(0.92)
                self.bar_diff.setValue(800.0)
                self.bar_pad.setValue(-10)
            elif data == "phone":
                self.sensitivity.setValue(0.90)
                self.min_interval.setValue(2.0)
                self.frame_check.setValue(0.5)
                self.top_ratio.setValue(0.30)
                self.blank_std.setValue(2.0)
                self.a_delay.setValue(0.2)
                self.b_delay.setValue(2.5)
                self.overlay_width.setValue(0.45)
                self.dup_top.setValue(0.25)
                self.pixel_sim.setValue(0.92)
                self.row_sim.setValue(0.96)
                self.row_cov.setValue(0.90)
                self.bar_diff.setValue(400.0)
                self.bar_pad.setValue(-20)
            self.apply_to_api()
            self._preset_combo.blockSignals(True)
            self._preset_combo.setCurrentIndex(0)
            self._preset_combo.blockSignals(False)
        finally:
            self._updating = False

    def _spin_float(self, min_v: float, max_v: float, step: float, default: float) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(min_v, max_v)
        s.setSingleStep(step)
        s.setValue(default)
        s.setDecimals(2)
        s.setFixedWidth(132)
        return s

    def _spin_int(self, min_v: int, max_v: int, default: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(min_v, max_v)
        s.setValue(default)
        s.setFixedWidth(132)
        return s

    def _all_spins(self):
        return [
            self.sensitivity, self.min_interval, self.frame_check,
            self.top_ratio, self.blank_std, self.a_delay, self.b_delay,
            self.overlay_width, self.dup_top, self.pixel_sim,
            self.row_sim, self.row_cov, self.ocr_conf, self.ocr_horiz,
            self.bar_diff, self.bar_pad,
        ]

    def apply_to_api(self):
        self._updating = True
        try:
            updates = {
                "change_detection_threshold": self.sensitivity.value(),
                "min_screenshot_interval": self.min_interval.value(),
                "frame_check_interval": self.frame_check.value(),
                "top_analysis_ratio": self.top_ratio.value(),
                "blank_content_std_threshold": self.blank_std.value(),
                "a_capture_delay": self.a_delay.value(),
                "b_capture_delay": self.b_delay.value(),
                "b_overlay_width_ratio": self.overlay_width.value(),
                "duplicate_top_ratio": self.dup_top.value(),
                "pixel_similarity_threshold": self.pixel_sim.value(),
                "row_similarity_threshold": self.row_sim.value(),
                "row_coverage_threshold": self.row_cov.value(),
                "ocr_confidence_threshold": self.ocr_conf.value() if self.ocr_enabled.isChecked() else 0,
                "ocr_horizontal_ratio": self.ocr_horiz.value(),
                "bar_min_diff_threshold": self.bar_diff.value(),
                "bar_padding_px": self.bar_pad.value(),
            }
            self._api.update_config(updates)
            self._api.set_debug_mode(self.debug_cb.isChecked())
        except ValueError as e:
            QMessageBox.warning(self, "Invalid setting", str(e))
        finally:
            self._updating = False

    def refresh_from_api(self):
        self._updating = True
        try:
            cfg = self._api.get_config()
            self.sensitivity.setValue(cfg.get("change_detection_threshold", 0.96))
            self.min_interval.setValue(cfg.get("min_screenshot_interval", 3.0))
            self.frame_check.setValue(cfg.get("frame_check_interval", 0.8))
            self.top_ratio.setValue(cfg.get("top_analysis_ratio", 0.34))
            self.blank_std.setValue(cfg.get("blank_content_std_threshold", 3.0))
            self.a_delay.setValue(cfg.get("a_capture_delay", 0.3))
            self.b_delay.setValue(cfg.get("b_capture_delay", 3.0))
            self.overlay_width.setValue(cfg.get("b_overlay_width_ratio", 0.5))
            self.dup_top.setValue(cfg.get("duplicate_top_ratio", 0.27))
            self.pixel_sim.setValue(cfg.get("pixel_similarity_threshold", 0.95))
            self.row_sim.setValue(cfg.get("row_similarity_threshold", 0.98))
            self.row_cov.setValue(cfg.get("row_coverage_threshold", 0.94))
            ocr_conf = cfg.get("ocr_confidence_threshold", 40)
            self.ocr_conf.setValue(ocr_conf if ocr_conf > 0 else 40)
            self.ocr_horiz.setValue(cfg.get("ocr_horizontal_ratio", 0.30))
            self.bar_diff.setValue(cfg.get("bar_min_diff_threshold", 500.0))
            self.bar_pad.setValue(cfg.get("bar_padding_px", -15))
            self.debug_cb.setChecked(self._api.is_debug_mode())
        finally:
            self._updating = False

    def _reset_defaults(self):
        reply = QMessageBox.question(
            self, "Reset to Defaults",
            "This will restore all extraction parameters to their factory defaults.\n\n"
            "Your current video, project, and extracted pages will not be affected.\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._updating = True
        try:
            self.sensitivity.setValue(0.96)
            self.min_interval.setValue(3.0)
            self.frame_check.setValue(0.8)
            self.top_ratio.setValue(0.34)
            self.blank_std.setValue(3.0)
            self.a_delay.setValue(0.3)
            self.b_delay.setValue(3.0)
            self.overlay_width.setValue(0.5)
            self.dup_top.setValue(0.27)
            self.pixel_sim.setValue(0.95)
            self.row_sim.setValue(0.98)
            self.row_cov.setValue(0.94)
            self.ocr_enabled.setChecked(False)
            self.ocr_conf.setValue(40)
            self.ocr_horiz.setValue(0.30)
            self.bar_diff.setValue(500.0)
            self.bar_pad.setValue(-15)
            self.debug_cb.setChecked(False)
            self.apply_to_api()
        finally:
            self._updating = False

    def _on_debug_toggled(self, checked: bool):
        if not self._updating:
            self._api.set_debug_mode(checked)

    def _on_change(self):
        if not self._updating:
            self.apply_to_api()


# ── Extract Tab ──────────────────────────────────────────────────────

class PreviewSeeker(QObject):
    """Background frame reader using FFmpeg subprocess (or OpenCV fallback) for seeking."""
    frame_ready = pyqtSignal(object)  # QImage, safe cross-thread
    open_requested = pyqtSignal(str)
    close_requested = pyqtSignal()
    seek_requested = pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        self._cap = None
        self._cap_lock = threading.Lock()
        self._path: Optional[str] = None
        self._fps = 1.0
        self._width = 0
        self._height = 0
        self._seek_seq = 0
        self._closing = False
        self._ffmpeg = self._find_ffmpeg()
        self._use_ffmpeg = False
        self.open_requested.connect(self.open)
        self.close_requested.connect(self.close)
        self.seek_requested.connect(self._do_seek)

    def open(self, path: str):
        self.close()
        self._closing = False
        self._path = path
        with self._cap_lock:
            self._cap = cv2.VideoCapture(path)
            self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 1.0
            self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def close(self):
        self._closing = True
        self._seek_seq += 1
        with self._cap_lock:
            if self._cap:
                self._cap.release()
                self._cap = None
        self._path = None

    @staticmethod
    def _find_ffmpeg() -> Optional[str]:
        path = shutil.which("ffmpeg")
        if path:
            return path
        pattern = r"C:\Users\*\AppData\Local\Microsoft\WinGet\Packages\*ffmpeg*\bin\ffmpeg.exe"
        matches = _glob.glob(pattern)
        return matches[0] if matches else None

    def _read_frame_ffmpeg(self, ts: float) -> Optional[np.ndarray]:
        if not self._path:
            return None
        cmd = [
            self._ffmpeg,
            "-hide_banner", "-loglevel", "error",
            "-hwaccel", "auto",
            "-ss", f"{ts:.3f}",
            "-i", self._path,
            "-frames:v", "1",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "pipe:1",
        ]
        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=5,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None
        if proc.returncode != 0 or not proc.stdout:
            return None
        data = proc.stdout
        if len(data) < 9:
            return None
        out_w = self._width
        out_h = len(data) // (out_w * 3)
        if out_h == 0:
            return None
        return np.frombuffer(data[:out_w * out_h * 3], dtype=np.uint8).reshape(out_h, out_w, 3)

    def _read_frame_opencv(self, ts: float) -> Optional[np.ndarray]:
        with self._cap_lock:
            if self._cap is None or not self._cap.isOpened():
                return None
            self._cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            ret, frame = self._cap.read()
        if not ret or frame is None:
            return None
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def _do_seek(self, ts: float, fps_hint: float):
        if self._path is None or self._closing:
            return
        self._seek_seq += 1
        seq = self._seek_seq
        t0 = time.time()
        try:
            if self._use_ffmpeg:
                rgb = self._read_frame_ffmpeg(ts)
            else:
                rgb = self._read_frame_opencv(ts)
            elapsed = (time.time() - t0) * 1000
            if self._closing or seq != self._seek_seq:
                return
            if rgb is None:
                print(f"[PreviewSeeker] frame miss ts={ts:.2f}ms={elapsed:.0f}")
                return
            h, w = rgb.shape[:2]
            qt_img = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
            self.frame_ready.emit(qt_img.copy())
            backend = "ffmpeg" if self._use_ffmpeg else "opencv"
            print(f"[PreviewSeeker] frame ok ts={ts:.2f}ms={elapsed:.0f} [{backend}]")
        except RuntimeError:
            pass


class ExtractTab(QWidget):
    extraction_completed = pyqtSignal(int)
    config_requested = pyqtSignal()

    def __init__(self, api: GuiApi, parent=None):
        super().__init__(parent)
        self._api = api
        self._video_path: Optional[str] = None
        self._video_duration = 0.0
        self._busy = False
        self._completed_pdf_path: Optional[str] = None
        self._loaded_original_ratio: Optional[float] = None
        self._project_dir: str = ""
        self._has_existing_score = False
        self._reextract_mode = False
        self._yt_video_paths: list[str] = []
        self._peak_style = False

        # Background preview seeker thread
        self._preview_thread = QThread(self)
        self._preview_seeker = PreviewSeeker()
        self._preview_seeker.moveToThread(self._preview_thread)
        self._preview_seeker.frame_ready.connect(self._on_preview_frame)
        self._preview_thread.start()

        self._seek_coalesce = QTimer(self)
        self._seek_coalesce.setSingleShot(True)
        self._seek_coalesce.setTimerType(Qt.TimerType.PreciseTimer)
        self._seek_coalesce.timeout.connect(self._emit_pending_seek)
        self._pending_seek_ts: Optional[float] = None

        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.setTimerType(Qt.TimerType.CoarseTimer)
        self._watchdog.timeout.connect(self._on_watchdog_timeout)

        self._settings = QSettings("ScoreExtractor", "App")
        self._parent_dir = self._settings.value("parent_dir", str(Path(__file__).resolve().parent / "output"))
        self._welcome_seen = bool(self._settings.value("onboarding_welcome_seen", False))

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACE_SM)

        # ── Source toggle ──
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(16)
        self.yt_radio = QRadioButton("YouTube URL")
        self.local_radio = QRadioButton("Local file")
        self.yt_radio.setChecked(True)
        self._source_group = QButtonGroup(self)
        self._source_group.addButton(self.local_radio)
        self._source_group.addButton(self.yt_radio)
        toggle_row.addWidget(self.local_radio)
        toggle_row.addWidget(self.yt_radio)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        # ── Input grid ──
        input_grid = QGridLayout()
        input_grid.setColumnMinimumWidth(0, 115)
        input_grid.setColumnStretch(1, 1)
        input_grid.setColumnMinimumWidth(2, 130)

        # Local mode
        self._local_label = QLabel("Video file:")
        self._local_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.video_path_edit = QLineEdit()
        self.video_path_edit.setPlaceholderText("Location of your sheet-music video (*.mp4, *.avi, *.mkv, *.mov)")
        self.browse_btn = QPushButton("Browse…")
        _set_widget_class(self.browse_btn, "secondary")
        input_grid.addWidget(self._local_label, 0, 0)
        input_grid.addWidget(self.video_path_edit, 0, 1)
        input_grid.addWidget(self.browse_btn, 0, 2)

        # YouTube mode
        self._yt_label = QLabel("YouTube URL:")
        self._yt_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.yt_url_edit = QLineEdit()
        self.yt_url_edit.setPlaceholderText("Paste YouTube video URL")

        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Best (≤1080p)", "bestvideo[height<=1080]")
        self.quality_combo.addItem("720p", "bestvideo[height<=720]")
        self.quality_combo.addItem("480p", "bestvideo[height<=480]")
        self.quality_combo.addItem("360p", "best[height<=360]")
        self.quality_combo.addItem("Best available", "best")
        saved_qi = self._api.get_config().get("yt_quality_index", 0)
        self.quality_combo.setCurrentIndex(min(saved_qi, self.quality_combo.count() - 1))
        self.quality_combo.setFixedWidth(130)

        self.download_btn = QPushButton("Download")
        _set_widget_class(self.download_btn, "secondary")
        self.download_btn.setEnabled(False)

        yt_action = QHBoxLayout()
        yt_action.setSpacing(4)
        yt_action.addWidget(self.quality_combo)
        yt_action.addWidget(self.download_btn)

        input_grid.addWidget(self._yt_label, 0, 0)
        input_grid.addWidget(self.yt_url_edit, 0, 1)
        input_grid.addLayout(yt_action, 0, 2)
        self._yt_label.hide()
        self.yt_url_edit.hide()
        self.quality_combo.hide()
        self.download_btn.hide()

        layout.addLayout(input_grid)

        # ── Project field ──
        project_label = QLabel("Project:")
        project_label.setFixedWidth(115)

        self.project_edit = QLineEdit()
        self.project_edit.setPlaceholderText("Score name \u2014 type to find an existing score, or enter a new name")
        self.project_edit.setMaxLength(100)
        self._completer_model = QStringListModel()
        self._completer = QCompleter(self._completer_model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.project_edit.setCompleter(self._completer)

        self.project_browse_btn = QPushButton("Browse…")
        _set_widget_class(self.project_browse_btn, "secondary")

        project_row = QHBoxLayout()
        project_row.addWidget(project_label)
        project_row.addWidget(self.project_edit, 1)
        project_row.addWidget(self.project_browse_btn)
        layout.addLayout(project_row)

        # ── Status line ──
        self.status_label = QLabel("Choose a video to extract your score")
        _set_widget_class(self.status_label, "muted")
        self.status_label.setWordWrap(True)
        self.status_label.setAccessibleName("Status")
        layout.addWidget(self.status_label)

        # ── Crop preview ──
        self.crop_widget = CropPreviewWidget()
        self.crop_widget.setMinimumHeight(240)
        self.crop_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.crop_widget.setAccessibleName("Crop preview")
        layout.addWidget(self.crop_widget)

        self.seek_bar = DualHandleSeekBar()
        self.seek_bar.setMinimumHeight(64)
        self.seek_bar.setAccessibleName("Video seek bar with start and end handles")
        layout.addWidget(self.seek_bar)

        self.welcome_widget = WelcomeWidget()
        self.welcome_widget.setVisible(not self._welcome_seen and not self._has_existing_score)
        self.welcome_widget.dismissed.connect(self._on_welcome_dismissed)
        layout.addWidget(self.welcome_widget)

        # ── Crop ratio row ──
        crop_row = QHBoxLayout()
        crop_label = QLabel("Crop ratio:")
        crop_label.setFixedWidth(115)
        crop_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.crop_spin = QDoubleSpinBox()
        self.crop_spin.setRange(0.0, 1.0)
        self.crop_spin.setSingleStep(0.01)
        self.crop_spin.setDecimals(2)
        self.crop_spin.setValue(self._api.get_config().get("default_crop_ratio", 0.35))
        self.crop_spin.setFixedWidth(100)
        self.crop_original_label = QLabel("")
        _set_widget_class(self.crop_original_label, "muted")

        crop_row.addWidget(crop_label)
        crop_row.addWidget(self.crop_spin)
        crop_row.addWidget(self.crop_original_label)
        crop_row.addStretch()
        self.config_btn = QPushButton("Settings")
        _set_widget_class(self.config_btn, "secondary")
        self.config_btn.setMinimumWidth(100)
        self.config_btn.setToolTip("Open extraction settings")
        self.config_btn.clicked.connect(self.config_requested.emit)

        crop_row.addWidget(self.config_btn)
        layout.addLayout(crop_row)

        # ── Output PDF name ──
        pdf_row = QHBoxLayout()
        pdf_label = QLabel("Output PDF:")
        pdf_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pdf_label.setFixedWidth(115)
        self.pdf_name_edit = QLineEdit()
        self.pdf_name_edit.setPlaceholderText("Auto-filled from project name")
        self.pdf_name_edit.setMaxLength(100)
        pdf_row.addWidget(pdf_label)
        pdf_row.addWidget(self.pdf_name_edit, 1)
        layout.addLayout(pdf_row)

        # ── Progress & Log ──
        progress_row = QHBoxLayout()
        progress_row.setSpacing(SPACE_SM)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.page_badge = QLabel("")
        _set_widget_class(self.page_badge, "count")
        self.page_badge.setMinimumWidth(150)
        self.page_badge.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.page_badge)
        self._elapsed_label = QLabel("")
        _set_widget_class(self._elapsed_label, "muted")
        self._elapsed_label.setFixedWidth(100)
        self._elapsed_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._elapsed_label.setVisible(False)
        progress_row.addWidget(self._elapsed_label)
        layout.addLayout(progress_row)

        log_header = QHBoxLayout()
        log_header.setSpacing(SPACE_SM)
        log_header.setContentsMargins(0, 0, 0, 0)
        log_label = QLabel("Log")
        _set_widget_class(log_label, "muted")
        log_label.setMinimumWidth(40)
        log_header.addWidget(log_label)
        log_header.addStretch()
        clear_log_btn = QPushButton("Clear")
        _set_widget_class(clear_log_btn, "secondary")
        clear_log_btn.setMinimumWidth(60)
        log_header.addWidget(clear_log_btn)
        layout.addLayout(log_header)

        self.log_edit = QTextEdit()
        clear_log_btn.clicked.connect(self.log_edit.clear)
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(140)
        self.log_edit.document().setMaximumBlockCount(2000)
        layout.addWidget(self.log_edit)

        # ── Action bar ──
        action_row = QHBoxLayout()
        action_row.setSpacing(SPACE_SM)
        action_row.addStretch()
        self.reextract_btn = QPushButton("Re-extract")
        _set_widget_class(self.reextract_btn, "secondary")
        self.reextract_btn.setVisible(False)
        self.reextract_btn.clicked.connect(self._on_reextract)
        _fit_button_width(self.reextract_btn)
        self.extract_btn = QPushButton("Start Extraction")
        self.extract_btn.setEnabled(False)
        _fit_button_width(self.extract_btn)
        self.regenerate_btn = QPushButton("Regenerate PDF")
        self.regenerate_btn.setEnabled(False)
        self.regenerate_btn.setVisible(False)
        self.regenerate_btn.clicked.connect(self._regenerate_pdf)
        _fit_button_width(self.regenerate_btn)
        self.review_btn = QPushButton("Review Pages")
        _set_widget_class(self.review_btn, "secondary")
        self.review_btn.setVisible(False)
        self.review_btn.clicked.connect(self._on_review_pages)
        _fit_button_width(self.review_btn)
        self.open_pdf_btn = QPushButton("Open PDF")
        self.open_pdf_btn.setEnabled(False)
        self.open_pdf_btn.setVisible(False)
        self.open_pdf_btn.clicked.connect(self._open_pdf)
        _fit_button_width(self.open_pdf_btn)
        self.cancel_btn = QPushButton("Cancel")
        _set_widget_class(self.cancel_btn, "danger")
        self.cancel_btn.setEnabled(False)
        _fit_button_width(self.cancel_btn)
        action_row.addWidget(self.reextract_btn)
        action_row.addWidget(self.extract_btn)
        action_row.addWidget(self.regenerate_btn)
        action_row.addWidget(self.review_btn)
        action_row.addWidget(self.open_pdf_btn)
        action_row.addWidget(self.cancel_btn)
        layout.addLayout(action_row)

        # ── Connections ──
        self.project_edit.returnPressed.connect(self._on_project_entered)
        self._completer.activated.connect(self._on_project_selected)
        self.project_browse_btn.clicked.connect(self._browse_project)
        self.browse_btn.clicked.connect(self._browse_video)
        self.video_path_edit.textChanged.connect(self._on_path_changed)
        self.extract_btn.clicked.connect(self._start_extraction)
        self.cancel_btn.clicked.connect(self._cancel)
        self.local_radio.toggled.connect(self._on_source_toggled)
        self.yt_radio.toggled.connect(self._on_source_toggled)
        self._on_source_toggled()
        self.download_btn.clicked.connect(self._on_yt_download)
        self.yt_url_edit.textChanged.connect(self._on_yt_url_changed)
        self.quality_combo.currentIndexChanged.connect(self._on_quality_changed)
        self.seek_bar.seek_changed.connect(self._on_seek)
        self.crop_spin.valueChanged.connect(self._on_crop_spin_changed)
        self.crop_widget.crop_ratio_changed.connect(self.crop_spin.setValue)

        self._refresh_completer()
        self._update_state()

        self.setAcceptDrops(True)

    # ── Drag-and-drop ──

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isfile(path):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                self.local_radio.setChecked(True)
                self.video_path_edit.setText(path)
                break

    # ── Public accessors ──

    @staticmethod
    def _sanitize(name: str) -> str:
        return FileService._sanitize_path_name(name)

    def get_project_dir(self) -> str:
        project = self.project_edit.text().strip()
        if not project:
            return ""
        return str(Path(self._parent_dir) / self._sanitize(project))

    def get_output_path(self) -> str:
        project_dir = self.get_project_dir()
        if not project_dir:
            return ""
        pdf_name = self.pdf_name_edit.text().strip()
        if not pdf_name:
            pdf_name = Path(project_dir).name
        pdf_name = self._sanitize(pdf_name)
        if not pdf_name.endswith(".pdf"):
            pdf_name += ".pdf"
        return str(Path(project_dir) / pdf_name)

    def get_project_name(self) -> str:
        return self.project_edit.text().strip()

    # ── Project field ──

    def _refresh_completer(self):
        try:
            scores = self._api.list_saved_scores(self._parent_dir)
            names = sorted(set(s.score_name for s in scores))
            self._completer_model.setStringList(names)
        except Exception:
            self._completer_model.setStringList([])

    def _on_project_entered(self):
        name = self.project_edit.text().strip()
        if not name:
            return
        # Check if it matches an existing score
        try:
            scores = self._api.list_saved_scores(self._parent_dir)
            for s in scores:
                if s.score_name == name:
                    self._load_existing_score(s.path)
                    return
        except Exception:
            pass
        # New project
        self._switch_to_new_project()

    def _on_project_selected(self, text: str):
        try:
            scores = self._api.list_saved_scores(self._parent_dir)
            for s in scores:
                if s.score_name == text:
                    self._load_existing_score(s.path)
                    return
        except Exception:
            pass

    def _browse_project(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Project Directory", self._parent_dir)
        if not path:
            return
        p = Path(path)
        # Check if this is an existing score dir
        if (p / "photos").is_dir():
            self._load_existing_score(str(p))
            return
        # Otherwise treat as parent dir for new projects
        self._parent_dir = str(p.parent)
        self._settings.setValue("parent_dir", self._parent_dir)
        self.project_edit.setText(p.name)
        self._refresh_completer()
        self._switch_to_new_project()

    def _set_video_controls_enabled(self, enabled: bool):
        self._local_label.setEnabled(enabled)
        self.video_path_edit.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
        self._yt_label.setEnabled(enabled)
        self.yt_url_edit.setEnabled(enabled)
        self.quality_combo.setEnabled(enabled)
        self.download_btn.setEnabled(enabled)
        self.local_radio.setEnabled(enabled)
        self.yt_radio.setEnabled(enabled)
        self.seek_bar.setEnabled(enabled)

    def _load_existing_score(self, score_path: str):
        self._log(f"Loading {score_path}")
        dbg(f"_load_existing_score: {score_path}")
        try:
            count = self._api.load_saved_score(score_path)
            meta = self._api.get_loaded_score_metadata()
            self._loaded_original_ratio = meta.get("crop_ratio", 0.35)
            self._has_existing_score = True
            self._project_dir = score_path
            p = Path(score_path)
            self.project_edit.setText(p.name)
            self.pdf_name_edit.setText(p.name)
            self.crop_spin.setValue(self._loaded_original_ratio)
            self.crop_original_label.setText(f"(was {int(self._loaded_original_ratio * 100)}%)")

            # Load associated video for preview if available
            video_path = meta.get("video_path", "")
            if video_path and os.path.exists(video_path):
                self._set_video_controls_enabled(True)
                self.video_path_edit.setText(video_path)
                self._load_preview()
                self.status_label.setText(f"Loaded {count} pages — {p.name} (preview active)")
            else:
                self._set_video_controls_enabled(False)
                self.status_label.setText(f"Loaded {count} pages — {p.name}")
                if video_path and not os.path.exists(video_path):
                    self._log(f"Video missing: {video_path}")

            self._log(f"Loaded {count} pages (crop {int(self._loaded_original_ratio * 100)}%)")
            self._refresh_completer()
            self._update_state()
        except Exception as e:
            QMessageBox.warning(self, "Error", "Could not load score:\n{e}")

    def _switch_to_new_project(self):
        dbg("_switch_to_new_project")
        self._api.clear_pages()
        self._has_existing_score = False
        self._reextract_mode = False
        self._loaded_original_ratio = None
        self._completed_pdf_path = None
        self._project_dir = ""
        self.crop_original_label.setText("")
        self.crop_spin.setValue(self._api.get_config().get("default_crop_ratio", 0.35))
        if not self.pdf_name_edit.text():
            self.pdf_name_edit.setText(self.project_edit.text())
        self._set_video_controls_enabled(True)
        self.status_label.setText("Choose a video to extract your score")
        self._update_state()

    # ── Source toggle ──

    def _on_source_toggled(self):
        local = self.local_radio.isChecked()
        self._local_label.setVisible(local)
        self.video_path_edit.setVisible(local)
        self.browse_btn.setVisible(local)
        self._yt_label.setVisible(not local)
        self.yt_url_edit.setVisible(not local)
        self.quality_combo.setVisible(not local)
        self.download_btn.setVisible(not local)
        if local:
            self._on_path_changed(self.video_path_edit.text())
        else:
            self._on_yt_url_changed()

    # ── Video / YouTube ──

    def _on_yt_url_changed(self):
        url = self.yt_url_edit.text().strip()
        try:
            parsed = urlparse(url)
            valid = bool(url) and parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except ValueError:
            valid = False
        self.download_btn.setEnabled(valid and not self._busy)

    def _on_quality_changed(self, index: int):
        self._api.update_config({"yt_quality_index": index})

    def _on_yt_download(self):
        if self._busy:
            return
        url = self.yt_url_edit.text().strip()
        if not url:
            return
        if not url.startswith("http"):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid YouTube URL starting with http")
            return
        try:
            parsed = urlparse(url)
        except ValueError:
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid YouTube URL.")
            return
        if not parsed.scheme or not parsed.netloc:
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid YouTube URL.")
            return
        params = parse_qs(parsed.query)
        if 'list' in params:
            reply = QMessageBox.question(
                self, "Playlist Detected",
                "Only the first video will be downloaded. Do you want to proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._busy = True
        self.download_btn.setEnabled(False)
        self.download_btn.setText("Downloading…")
        self.yt_url_edit.setEnabled(False)
        self.quality_combo.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_edit.clear()
        self.status_label.setText("Downloading…")
        self._update_state()
        try:
            fmt = self.quality_combo.currentData()
            self._api.download_youtube(url, fmt)
        except RuntimeError as e:
            QMessageBox.warning(self, "Error", str(e))
            self._reset_download_ui()

    def _on_yt_download_completed(self, path: str):
        if self._api._original_video_path is not None:
            preview_path = self._api._video_info.path if self._api._video_info else path
        else:
            preview_path = path
        self._video_path = preview_path
        self.video_path_edit.setText(preview_path)
        title = self._api._last_download_title or Path(path).stem
        prev_title = self._api._prev_download_title
        cur_name = self.project_edit.text().strip()
        if not cur_name or cur_name == prev_title:
            self.project_edit.setText(title)

        self._log(f"Video saved: {preview_path}")
        self._load_preview()

        # Remember downloaded videos (scan + full-res original) so they can be
        # moved into the score folder once the final score name is known on extract.
        self._yt_video_paths = []
        if self._api._original_video_path and os.path.exists(self._api._original_video_path):
            self._yt_video_paths.append(self._api._original_video_path)
        if self._api._video_info and self._api._video_info.path and os.path.exists(self._api._video_info.path):
            p = self._api._video_info.path
            if p not in self._yt_video_paths:
                self._yt_video_paths.append(p)

        self._busy = False
        self.download_btn.setEnabled(True)
        self.download_btn.setText("Download")
        self.yt_url_edit.setEnabled(True)
        self.quality_combo.setEnabled(True)
        self._update_state()

    def _reset_download_ui(self):
        self._busy = False
        self.download_btn.setEnabled(True)
        self.download_btn.setText("Download")
        self.yt_url_edit.setEnabled(True)
        self.quality_combo.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(False)

    def _browse_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video", "",
            "Video files (*.mp4 *.avi *.mkv *.mov);;All files (*.*)")
        if path:
            self.video_path_edit.setText(path)

    def _on_path_changed(self, path: str):
        valid = bool(path) and os.path.exists(path)
        if valid and path != self._video_path:
            self._load_preview()
        self._update_state()

    def _load_preview(self):
        path = self.video_path_edit.text().strip()
        self._yt_video_paths = []
        if not path or not os.path.exists(path):
            return
        try:
            if self._api.get_video_info() is not None:
                self._api.close_video()
            info = self._api.open_video(path)
            self._video_path = path
            self._video_duration = info.duration
            self.seek_bar.set_duration(info.duration)
            self.seek_bar.set_start(2.0)
            self.seek_bar.set_end(info.duration)

            if not self.project_edit.text():
                self.project_edit.setText(Path(path).stem)
                if not self.pdf_name_edit.text():
                    self.pdf_name_edit.setText(Path(path).stem)

            ratio = self.crop_spin.value()
            self.crop_widget.set_ratio(ratio)
            img = self._api.read_frame_at(0.0)
            if img is not None:
                self.crop_widget.set_frame(self._img_to_pixmap(img))

            self._preview_seeker.open_requested.emit(path)
            self._log(f"Video loaded: {info.duration:.1f}s  {info.width}x{info.height}  {info.fps:.2f}fps")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open video:\n{e}\n\nMake sure the file is a supported video format and is not corrupted.")

    @staticmethod
    def _img_to_pixmap(img: np.ndarray) -> QPixmap:
        h, w = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        qt_img = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qt_img.copy())

    def _on_seek(self, ts: float):
        if ts < 0 or self._api.get_video_info() is None:
            return
        self._pending_seek_ts = ts
        if not self._seek_coalesce.isActive():
            self._seek_coalesce.start(16)  # ~60 fps dispatch

    def _emit_pending_seek(self):
        if self._pending_seek_ts is None:
            return
        ts = self._pending_seek_ts
        self._pending_seek_ts = None
        info = self._api.get_video_info()
        self._preview_seeker.seek_requested.emit(ts, info.fps if info else 30.0)
        if self._pending_seek_ts is not None:
            self._seek_coalesce.start()

    def _on_preview_frame(self, qt_img: QImage):
        self.crop_widget.set_frame(QPixmap.fromImage(qt_img))

    def _on_crop_spin_changed(self, val: float):
        dbg(f"_on_crop_spin_changed: val={val}")
        self._api.update_config({"default_crop_ratio": val})
        self.crop_widget.set_ratio(val)
        if self._has_existing_score:
            self.crop_original_label.setText(
                f"(was {int(self._loaded_original_ratio * 100)}%)" if self._loaded_original_ratio else "")

    def _on_reextract(self):
        dbg("_on_reextract")
        if self._busy:
            return
        page_count = self._api.get_page_count()
        reply = QMessageBox.question(
            self, "Re-extract",
            f"This will re-run extraction to replace all {page_count} existing pages.\n\n"
            "The current PDF will not be affected until you regenerate it.\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._reextract_mode = True
        self._start_extraction()

    # ── State management ──

    def _on_welcome_dismissed(self):
        self._welcome_seen = True
        self.welcome_widget.setVisible(False)
        self.crop_widget.setVisible(True)
        self.seek_bar.setVisible(True)

    def _set_status(self, text: str, peak: bool = False):
        self.status_label.setText(text)
        if peak != self._peak_style:
            _set_widget_class(self.status_label, "count" if peak else "muted")
            self._peak_style = peak

    def _update_state(self):
        has_project = bool(self.project_edit.text().strip())
        has_video = bool(self._video_path and os.path.exists(self._video_path))
        has_pages = self._api.get_page_count() > 0
        can_act = not self._busy

        show_welcome = (not self._welcome_seen
                        and not has_video
                        and not self._has_existing_score
                        and not has_pages)
        self.welcome_widget.setVisible(show_welcome)
        self.crop_widget.setVisible(not show_welcome)
        self.seek_bar.setVisible(not show_welcome)

        dbg(f"_update_state: busy={self._busy}, reextract={self._reextract_mode}, has_existing={self._has_existing_score}, has_pages={has_pages}, has_project={has_project}, has_video={has_video}")

        self.cancel_btn.setVisible(self._busy)
        self.extract_btn.setVisible(False)
        self.regenerate_btn.setVisible(False)
        self.review_btn.setVisible(False)
        self.open_pdf_btn.setVisible(False)
        self.reextract_btn.setVisible(False)

        if self._busy:
            self.cancel_btn.setEnabled(True)
        elif self._reextract_mode:
            self.extract_btn.setVisible(True)
            self.extract_btn.setEnabled(can_act and has_video)
            self.extract_btn.setText("Start Extraction")
            self._set_status(
                f"Re-extract: will replace {self._api.get_page_count()} pages")
        elif self._has_existing_score and has_pages:
            self.regenerate_btn.setVisible(True)
            self.regenerate_btn.setEnabled(can_act)
            self.review_btn.setVisible(True)
            self.review_btn.setEnabled(can_act and self._api.get_page_count() > 0)
            self.reextract_btn.setVisible(True)
            self._set_status(
                f"Loaded {self._api.get_page_count()} pages — review, regenerate PDF, or re-extract")
        elif has_project and has_video:
            self.extract_btn.setVisible(True)
            self.extract_btn.setEnabled(can_act)
            self.extract_btn.setText("Start Extraction")
            self._set_status("Ready \u2014 start extraction")
        else:
            self.extract_btn.setVisible(True)
            self.extract_btn.setEnabled(False)
            self.extract_btn.setText("Start Extraction")
            if not has_video:
                self._set_status("Choose a video to extract your score")
            elif not has_project:
                self._set_status("Enter a score name")
            else:
                self._set_status("Ready")

    def _start_extraction(self):
        dbg("_start_extraction")
        if self._busy:
            return
        video_path = self._video_path
        if not video_path or not os.path.exists(video_path):
            QMessageBox.warning(self, "Error", "Please select a valid video file.")
            return

        project = self.project_edit.text().strip()
        if not project:
            QMessageBox.warning(self, "Error", "Please enter a score name.")
            return

        project_dir = self.get_project_dir()
        if project_dir and len(project_dir) > 220:
            QMessageBox.warning(
                self, "Path Too Long",
                "The score path is too long for Windows (near the 260-character "
                "limit).\n\nUse a shorter score name or move the output folder to a "
                "shorter location.\n\n"
                f"Score path:\n{project_dir}",
            )
            return

        project_dir = self.get_project_dir()
        photos_dir = Path(project_dir) / "photos"
        if photos_dir.is_dir() and not self._reextract_mode:
            existing = sorted(photos_dir.glob("page_*_merged.png"))
            if existing:
                reply = QMessageBox.question(
                    self,
                    "Score Already Exists",
                    f"\"{project}\" already has {len(existing)} pages saved.\n\n"
                    f"Extracting again will overwrite them. Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

        # Clear old pages before re-extraction
        if photos_dir.is_dir():
            for f in photos_dir.glob("page_*_merged.png"):
                f.unlink(missing_ok=True)

        main_win = self.window()
        if hasattr(main_win, 'config_tab'):
            main_win.config_tab.apply_to_api()
        self._api.update_config({"default_crop_ratio": self.crop_spin.value()})

        start_time = self.seek_bar.get_start()
        end_time = self.seek_bar.get_end()
        video_duration = self._video_duration if hasattr(self, '_video_duration') else 0.0
        end_offset = max(0.0, video_duration - end_time) if video_duration > 0 else 0.0
        no_ocr = (self._api.get_config().get("ocr_confidence_threshold", 40) == 0)

        self._busy = True
        self.extract_btn.setText("Extracting…")
        self.extract_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_edit.clear()
        self.page_badge.setText("")
        self._set_status("Extracting…")
        self._watchdog.start(300000)  # 5 min safety timeout

        try:
            self._api.start_extraction(
            video_path=video_path,
            no_ocr=no_ocr,
            start_time=start_time,
            end_offset=end_offset,
            output_folder=self._parent_dir,
            score_name=project,
        )
        except RuntimeError as e:
            QMessageBox.warning(self, "Error", str(e))
            self._reset_ui()

    def _regenerate_pdf(self):
        dbg("_regenerate_pdf")
        if self._busy:
            return
        output_path = self.get_output_path()
        if not output_path:
            QMessageBox.warning(self, "Error", "Please enter a score name.")
            return

        main_win = self.window()
        if hasattr(main_win, 'config_tab'):
            main_win.config_tab.apply_to_api()

        self._api.update_config({"default_crop_ratio": self.crop_spin.value()})

        pdf_name = self.pdf_name_edit.text().strip()
        title = pdf_name if pdf_name else None

        self._busy = True
        self.extract_btn.setVisible(False)
        self.regenerate_btn.setVisible(False)
        self.regenerate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_edit.clear()
        self._set_status("Generating PDF…")

        if hasattr(main_win, '_generating_pdf'):
            main_win._generating_pdf = True

        try:
            self._api.generate_pdf(output_path, title=title)
        except RuntimeError as e:
            if hasattr(main_win, '_generating_pdf'):
                main_win._generating_pdf = False
            QMessageBox.warning(self, "Error", str(e))
            self._reset_ui()

    def _cancel(self):
        if self._busy:
            self._watchdog.stop()
            self._api.cancel_extraction()
            self._log("Cancelling…")

    def _on_watchdog_timeout(self):
        self._log("[Timeout] Extraction stalled — forcing reset")
        self._api.cancel_extraction()
        self._reset_ui()

    def _open_pdf(self):
        if self._completed_pdf_path and os.path.exists(self._completed_pdf_path):
            try:
                os.startfile(self._completed_pdf_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open PDF:\n{e}")
        self._completed_pdf_path = None
        self._update_state()

    # ── Callbacks from MainWindow ──

    def _move_downloaded_videos(self):
        """Move downloaded videos into the score folder once the final name is known."""
        if not self._yt_video_paths:
            return
        project_dir = self.get_project_dir()
        if not project_dir:
            return
        try:
            # Release open capture handles so Windows allows the files to be moved
            self._preview_seeker.close()
            svc = self._api._video_service
            if svc is not None:
                svc.close()
            video_dir = Path(project_dir) / "video"
            video_dir.mkdir(parents=True, exist_ok=True)
            moved: dict[str, str] = {}
            for src in self._yt_video_paths:
                if not os.path.exists(src):
                    continue
                dst = video_dir / Path(src).name
                if not dst.exists():
                    shutil.move(src, str(dst))
                moved[src] = str(dst)
            if not moved:
                return
            # Point API + GUI paths at the moved files
            if self._api._original_video_path in moved:
                self._api._original_video_path = moved[self._api._original_video_path]
            info = self._api._video_info
            if info and info.path in moved:
                info.path = moved[info.path]
                self._video_path = info.path
                self._api._video_path = info.path
                self.video_path_edit.setText(info.path)
            self._yt_video_paths = []
            self._log(f"Video saved: {video_dir}")
        except Exception as e:
            self._log(f"  [Warn] Could not move downloaded video into project: {e}")

    def on_completed(self, page_count: int) -> bool:
        """Finish extraction. Returns True if PDF generation was started."""
        dbg(f"on_completed: page_count={page_count}")
        if page_count == 0:
            self._log("No pages captured \u2014 check that the video contains visible sheet music and the crop region covers the score. Try lowering sensitivity in Settings.")
            self._reset_ui()
            return False

        self._move_downloaded_videos()

        self._review_before_save()

        if self._api.get_page_count() == 0:
            self._log("All pages removed in review — no PDF generated")
            self._busy = False
            self._update_state()
            self._set_status("No pages kept — re-extract to try again")
            return False

        output_path = self.get_output_path()
        title = self.pdf_name_edit.text().strip() or None
        self._watchdog.start(300000)
        try:
            self._api.generate_pdf(output_path, title=title)
            return True
        except (RuntimeError, ValueError, PermissionError) as e:
            QMessageBox.warning(self, "Error", str(e))
            self._reset_ui()
            return False

    def _review_before_save(self):
        """Show the review dialog so pages can be dropped before the PDF is made."""
        dlg = ReviewPagesDialog(self._api, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            removed = [i for i, keep in enumerate(dlg.kept_mask()) if not keep]
            if removed:
                self._apply_page_removals(removed)
        kept = self._api.get_page_count()
        self.page_badge.setText(f"Pages: {kept}")
        self._log(f"Review: {kept} pages kept")

    def _apply_page_removals(self, removed: list[int]):
        """Drop pages from the in-memory store and their files on disk.

        Disk files are numbered by extraction attempt (gaps when duplicates
        were skipped), so store indices map to the sorted file list, not to
        the numbers in the filenames.
        """
        photos = Path(self.get_project_dir()) / "photos"
        files = sorted(
            photos.glob("page_*_merged.png"),
            key=lambda f: int(f.stem.split("_")[1]),
        )
        for idx in sorted(removed, reverse=True):
            if 0 <= idx < len(files):
                files[idx].unlink(missing_ok=True)
            try:
                self._api.remove_page(idx)
            except IndexError:
                pass
        self._log(f"Removed {len(removed)} page(s) — keeping {self._api.get_page_count()}")

    def _on_review_pages(self):
        if self._api.get_page_count() == 0:
            return
        dlg = ReviewPagesDialog(self._api, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            removed = [i for i, keep in enumerate(dlg.kept_mask()) if not keep]
            if removed:
                self._apply_page_removals(removed)
            self.page_badge.setText(f"Pages: {self._api.get_page_count()}")
            self._update_state()
            if removed:
                self._log("Regenerate the PDF to apply the change")

    def on_pdf_completed(self, page_count: int):
        output_path = self.get_output_path()
        dbg(f"on_pdf_completed: page_count={page_count}, path={output_path}")
        self._completed_pdf_path = output_path
        self._has_existing_score = True
        self._reextract_mode = False
        self._busy = False
        self.cancel_btn.setEnabled(False)
        self.extract_btn.setVisible(False)
        self.regenerate_btn.setVisible(False)
        self.open_pdf_btn.setVisible(True)
        self.open_pdf_btn.setEnabled(True)
        self.review_btn.setVisible(True)
        self.review_btn.setEnabled(True)
        self.page_badge.setText(f"Pages: {page_count}")
        self._set_status(f"Score ready — {page_count} pages in the PDF", peak=True)
        self._log(f"PDF saved: {output_path}")
        self._refresh_completer()

    def on_cancelled(self):
        dbg("on_cancelled")
        self._log("Cancelled — no pages were captured")
        self._reset_ui()

    def on_cancelled_with_pages(self, page_count: int):
        dbg(f"on_cancelled_with_pages: {page_count}")
        self._busy = False
        self._watchdog.stop()
        self.cancel_btn.setEnabled(False)
        self.page_badge.setText(f"Pages: {page_count}")

        reply = QMessageBox.question(
            self, "Extraction Cancelled",
            f"Extraction was stopped with {page_count} page(s) captured.\n\n"
            "Would you like to keep these pages and review them, "
            "or discard them and start over?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._move_downloaded_videos()
            self._review_before_save()
            if self._api.get_page_count() == 0:
                self._log("All pages removed in review — no PDF generated")
                self._busy = False
                self._update_state()
                self._set_status("No pages kept — extract again to try")
                return
            output_path = self.get_output_path()
            title = self.pdf_name_edit.text().strip() or None
            try:
                self._api.generate_pdf(output_path, title=title)
                main_win = self.window()
                if hasattr(main_win, '_generating_pdf'):
                    main_win._generating_pdf = True
            except (RuntimeError, ValueError, PermissionError) as e:
                QMessageBox.warning(self, "Error", str(e))
                self._reset_ui()
        else:
            self._api.clear_pages()
            self._reset_ui()
            self._set_status("Pages discarded — start over")

    def on_error(self, message: str):
        dbg(f"on_error: {message}")
        self._log(f"[Error] {message}")
        if not self._busy:
            QMessageBox.critical(self, "Error", message)
        self._reset_ui()
        self._set_status(f"Failed — {message}")

    def on_page_detected(self, idx: int, png_bytes: bytes):
        dbg(f"on_page_detected: idx={idx}")
        self.page_badge.setText(f"Pages: {idx + 1}")

    def on_progress(self, phase: str, percent: float, detail: str):
        dbg(f"on_progress: phase={phase}, percent={percent:.0f}%, detail={detail}")
        self.progress_bar.setValue(int(percent))
        self._watchdog.start(300000)
        self._elapsed_label.setVisible(True)
        elapsed = self._api.get_extraction_state().elapsed_seconds
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        self._elapsed_label.setText(f"{mins}:{secs:02d}")
        phase_text = phase.replace("_", " ").title()
        if detail:
            self._set_status(f"{phase_text}: {detail}")
        else:
            self._set_status(phase_text)

    def _reset_ui(self):
        dbg("_reset_ui")
        self._busy = False
        self._reextract_mode = False
        self._watchdog.stop()
        self.cancel_btn.setEnabled(False)
        self.open_pdf_btn.setVisible(False)
        self.page_badge.setText("")
        self.download_btn.setEnabled(True)
        self.download_btn.setText("Download")
        self.yt_url_edit.setEnabled(True)
        self.quality_combo.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self._update_state()

    def _log(self, msg: str):
        self.log_edit.append(msg)








# ── Main Window ──────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Score Extractor — Piano Score Video to PDF")
        self.setMinimumSize(1040, 760)
        self.resize(1100, 780)
        self.setStyleSheet(
            STYLESHEET.replace("__CHECK_PLACEHOLDER__", CHECK_INDICATOR_PATH)
            .replace("__CHEVRON_PLACEHOLDER__", CHEVRON_PATH)
            .replace("__SPIN_UP_PLACEHOLDER__", SPIN_UP_PATH)
            .replace("__SPIN_DOWN_PLACEHOLDER__", SPIN_DOWN_PATH)
        )

        # Core API
        self.api = GuiApi()
        self.signals = ExtractionSignals()
        self.signals.wire(self.api)
        self._generating_pdf = False

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Tabs
        self.tabs = QTabWidget()
        self.extract_tab = ExtractTab(self.api)
        self.config_tab = ConfigTab(self.api)

        self.tabs.addTab(self.extract_tab, "Extract")
        self.tabs.addTab(self.config_tab, "Settings")

        main_layout.addWidget(self.tabs, 1)

        # ── Menu bar ──
        menu = self.menuBar()
        menu.setStyleSheet(f"""
            QMenuBar {{
                background: {BG};
                color: {INK};
                border-bottom: 1px solid {BORDER};
                padding: 2px 0;
                font-size: 13px;
            }}
            QMenuBar::item {{
                padding: 4px 10px;
                background: transparent;
            }}
            QMenuBar::item:selected {{
                background: {SURFACE2};
                border-radius: 4px;
            }}
            QMenu {{
                background: {SURFACE};
                border: 1px solid {BORDER2};
                border-radius: 4px;
                padding: 4px 0;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 20px;
                color: {INK};
            }}
            QMenu::item:selected {{
                background: {SURFACE2};
            }}
            QMenu::item:disabled {{
                color: {MUTED};
            }}
            QMenu::separator {{
                height: 1px;
                background: {BORDER};
                margin: 4px 8px;
            }}
        """)

        file_menu = menu.addMenu("&File")
        open_video_action = QAction("&Open Video...\tCtrl+O", self)
        open_video_action.triggered.connect(self.extract_tab._browse_video)
        file_menu.addAction(open_video_action)

        open_project_action = QAction("Open &Project...\tCtrl+Shift+O", self)
        open_project_action.triggered.connect(self.extract_tab._browse_project)
        file_menu.addAction(open_project_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit\tAlt+F4", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        extraction_menu = menu.addMenu("E&xtraction")
        start_action = QAction("&Start Extraction\tCtrl+E", self)
        start_action.triggered.connect(self.extract_tab._start_extraction)
        extraction_menu.addAction(start_action)

        cancel_action = QAction("&Cancel\tEscape", self)
        cancel_action.triggered.connect(self.extract_tab._cancel)
        extraction_menu.addAction(cancel_action)

        settings_action = QAction("&Settings...\tCtrl+,", self)
        settings_action.triggered.connect(lambda: self.tabs.setCurrentIndex(1))
        extraction_menu.addAction(settings_action)

        help_menu = menu.addMenu("&Help")
        getting_started_action = QAction("&Getting Started\tF1", self)
        getting_started_action.triggered.connect(self._show_getting_started)
        help_menu.addAction(getting_started_action)

        shortcuts_action = QAction("&Keyboard Shortcuts", self)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()

        about_action = QAction("&About Score Extractor", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        # ── Keyboard shortcuts (window-level) ──
        open_video_action.setShortcut("Ctrl+O")
        open_project_action.setShortcut("Ctrl+Shift+O")
        start_action.setShortcut("Ctrl+E")
        cancel_action.setShortcut("Escape")
        settings_action.setShortcut("Ctrl+,")
        getting_started_action.setShortcut("F1")

        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        self.status_bar.showMessage("Ready")

        # ── Connect signals ──
        self.signals.progress.connect(self._on_progress)
        self.signals.page_detected.connect(self._on_page_detected)
        self.signals.log.connect(self._on_log)
        self.signals.error.connect(self._on_error)
        self.signals.completed.connect(self._on_completed)
        self.signals.cancelled.connect(self._on_cancelled)
        self.signals.cancelled_with_pages.connect(self._on_cancelled_with_pages)
        self.signals.download_done.connect(self._on_yt_downloaded)

        self.extract_tab.config_requested.connect(lambda: self.tabs.setCurrentIndex(1))
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_progress(self, phase: str, percent: float, detail: str):
        self.extract_tab.on_progress(phase, percent, detail)
        self.status_bar.showMessage(detail)

    def _on_page_detected(self, idx: int, png_bytes: bytes):
        self.extract_tab.on_page_detected(idx, png_bytes)

    def _on_log(self, message: str):
        self.extract_tab._log(message)

    def _on_error(self, message: str):
        self.extract_tab.on_error(message)

    def _on_completed(self, page_count: int):
        if self._generating_pdf:
            self._generating_pdf = False
            self.extract_tab.on_pdf_completed(page_count)
        else:
            started_pdf = self.extract_tab.on_completed(page_count)
            score_dir = self.extract_tab.get_project_dir()
            self.api.open_debug_folder(score_dir)
            if started_pdf:
                self._generating_pdf = True
            elif page_count == 0:
                self.extract_tab._reset_ui()

    def _on_cancelled(self):
        self.extract_tab.on_cancelled()

    def _on_cancelled_with_pages(self, page_count: int):
        self.extract_tab.on_cancelled_with_pages(page_count)

    def _on_yt_downloaded(self, path: str):
        self.extract_tab._on_yt_download_completed(path)

    def _on_tab_changed(self, index: int):
        if index == 1:
            self.config_tab.refresh_from_api()

    def _show_getting_started(self):
        dlg = GettingStartedDialog(self)
        dlg.setStyleSheet(
            STYLESHEET.replace("__CHECK_PLACEHOLDER__", CHECK_INDICATOR_PATH)
            .replace("__CHEVRON_PLACEHOLDER__", CHEVRON_PATH)
            .replace("__SPIN_UP_PLACEHOLDER__", SPIN_UP_PATH)
            .replace("__SPIN_DOWN_PLACEHOLDER__", SPIN_DOWN_PATH)
        )
        dlg.exec()

    def _show_shortcuts(self):
        text = (
            "Ctrl+O          Open video file\n"
            "Ctrl+Shift+O    Open existing project\n"
            "Ctrl+E          Start extraction\n"
            "Ctrl+,          Open Settings\n"
            "Escape          Cancel extraction\n"
            "F1              Getting Started guide\n"
            "Ctrl+Tab        Switch tab\n"
            "Alt+F4          Exit"
        )
        QMessageBox.information(self, "Keyboard Shortcuts", text)

    def _show_about(self):
        QMessageBox.about(
            self, "About Score Extractor",
            "<h3>Score Extractor</h3>"
            "<p>Convert videos of page-turning sheet music into clean, "
            "printable PDFs.</p>"
            "<p>Built with PyQt6, OpenCV, and PaddleOCR.</p>"
            "<p><a href='https://github.com/anomalyco/Score_extractor'>"
            "github.com/anomalyco/Score_extractor</a></p>"
        )

    def closeEvent(self, event):
        seeker = self.extract_tab._preview_seeker
        thread = self.extract_tab._preview_thread
        seeker.close_requested.emit()
        thread.quit()
        if not thread.wait(6000):
            thread.terminate()
            thread.wait(1000)
        super().closeEvent(event)


# ── Entrypoint ───────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Score Extractor")

    global CHECK_INDICATOR_PATH
    global CHEVRON_PATH
    global SPIN_UP_PATH
    global SPIN_DOWN_PATH
    CHECK_INDICATOR_PATH = _generate_check_pixmap()
    CHEVRON_PATH = _generate_chevron_pixmap()
    SPIN_UP_PATH = _generate_spin_arrow_pixmap(up=True)
    SPIN_DOWN_PATH = _generate_spin_arrow_pixmap(up=False)

    # Set app-wide font
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
