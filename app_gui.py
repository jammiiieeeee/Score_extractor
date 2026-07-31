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
    QFrame, QSizePolicy, QSplitter, QGridLayout,
)

from gui_bridge import ExtractionSignals
from src.api.gui_api import GuiApi, ScoreInfo


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
    border: none;
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
    border: 1px solid {BORDER2};
    padding: 8px 14px;
}}
QPushButton.secondary:hover {{
    background: {SURFACE2};
    border-color: {BRASS};
}}
QPushButton.danger {{
    background: transparent;
    color: {DANGER};
    border: 1px solid {DANGER};
}}
QPushButton.danger:hover {{
    background: {DANGER};
    color: white;
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
    padding: 4px 10px;
    color: {INK};
    min-height: 26px;
    font-size: 14px;
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
QGroupBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 20px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: {BRASS};
}}
QCheckBox {{
    spacing: 8px;
    color: {INK};
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
QLabel.muted {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel.title {{
    font-size: 22px;
    font-weight: 700;
    color: {INK};
    letter-spacing: 0.5px;
}}
QLabel.count {{
    font-size: 14px;
    font-weight: 600;
    color: {BRASS};
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
QFormLayout {{
    font-size: 14px;
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


def _generate_check_pixmap() -> str:
    from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
    import tempfile
    path = os.path.join(tempfile.gettempdir(), f"score_extractor_check_{os.getpid()}.png")
    pm = QPixmap(18, 18)
    pm.fill(QColor(Qt.GlobalColor.transparent))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("white"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawLine(4, 10, 7, 13)
    p.drawLine(7, 13, 14, 6)
    p.end()
    pm.save(path)
    return path.replace("\\", "/")


def _generate_chevron_pixmap() -> str:
    from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
    import tempfile
    path = os.path.join(tempfile.gettempdir(), f"score_extractor_chevron_{os.getpid()}.png")
    pm = QPixmap(12, 12)
    pm.fill(QColor(Qt.GlobalColor.transparent))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(BRASS), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawLine(2, 4, 6, 8)
    p.drawLine(6, 8, 10, 4)
    p.end()
    pm.save(path)
    return path.replace("\\", "/")


def _set_widget_class(widget, cls: str):
    widget.setProperty("class", cls)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


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
            font = QFont("Segoe UI", 11, QFont.Weight.Bold)
            painter.setFont(font)
            label = f"Crop: {int(self._ratio * 100)}%"
            painter.drawText(ox, line_y - 16, label)
        else:
            painter.setPen(QColor(136, 136, 136))
            font = QFont("Segoe UI", 12)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Open a video to preview crop")

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
        layout.addWidget(self.groove)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.setSpacing(4)
        self.start_cb = QCheckBox("Start-time capture")
        self.start_cb.setChecked(True)
        self.start_label = QLabel("00:00.0")
        self.start_label.setObjectName("muted")
        self.start_label.setFixedWidth(70)
        ctrl.addWidget(self.start_cb)
        ctrl.addWidget(self.start_label)

        self.end_cb = QCheckBox("End offset (s)")
        self.end_cb.setChecked(False)
        self.end_label = QLabel("00:00.0")
        self.end_label.setObjectName("muted")
        self.end_label.setFixedWidth(70)
        self.dur_label = QLabel("/ 00:00.0")
        self.dur_label.setObjectName("muted")
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

    def _on_end_toggled(self, checked: bool):
        self._end_enabled = checked
        self.groove.update()

    def _update_labels(self):
        def fmt(s):
            m = int(s // 60)
            ss = s % 60
            return f"{m}:{ss:05.2f}"
        self.start_label.setText(fmt(self._start * self._duration))
        self.end_label.setText(fmt(self._end * self._duration))
        self.dur_label.setText(f"/ {fmt(self._duration)}")

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


# ── Config Tab ───────────────────────────────────────────────────────

class ConfigTab(QWidget):
    def __init__(self, api: GuiApi, parent=None):
        super().__init__(parent)
        self._api = api
        self._updating = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(SPACE_MD)

        title = QLabel("Settings")
        title.setObjectName("title")
        layout.addWidget(title)

        accent = QFrame()
        accent.setFrameShape(QFrame.Shape.HLine)
        accent.setFixedHeight(1)
        accent.setFixedWidth(60)
        accent.setStyleSheet(f"background: {BRASS}; border: none;")
        layout.addWidget(accent)

        layout.addSpacing(SPACE_SM)

        desc = QLabel("Adjust extraction behavior. These apply to the next extraction.")
        desc.setObjectName("muted")
        layout.addWidget(desc)

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
            "(typically a static piano keyboard or player UI).\n"
            "Safe range: 0.20–0.50."
        )
        self.blank_std = self._spin_float(0.0, 50.0, 0.5, 3.0)
        self.blank_std.setToolTip(
            "Pixel standard deviation below which a frame is considered blank\n"
            "(white/black screen, no content). Blank frames are skipped.\n"
            "Safe range: 1.0–8.0. Raise to 10+ if real content is being rejected."
        )

        det_form.addRow(self._form_label("Page change sensitivity:"), self.sensitivity)
        det_form.addRow(self._form_label("Min seconds between captures:"), self.min_interval)
        det_form.addRow(self._form_label("Frame check interval (s):"), self.frame_check)
        det_form.addRow(self._form_label("Top analysis ratio:"), self.top_ratio)
        det_form.addRow(self._form_label("Blank content std threshold:"), self.blank_std)
        layout.addWidget(det_group)

        # ── Capture group ──
        cap_group = QGroupBox("Capture Timing")
        cap_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        cap_form = QFormLayout(cap_group)
        cap_form.setSpacing(SPACE_MD)

        self.a_delay = self._spin_float(0.0, 5.0, 0.1, 0.3)
        self.a_delay.setToolTip(
            "Seconds to wait after detecting a change before capturing the\n"
            "'before' frame (clean page). Gives the page time to settle.\n"
            "Safe range: 0.0–1.0. Increase if captures show a partial page turn."
        )
        self.b_delay = self._spin_float(0.0, 10.0, 0.1, 3.0)
        self.b_delay.setToolTip(
            "Seconds to wait after A-capture before capturing the 'after' frame\n"
            "(page with overlay bar). Controls how much of the new page is visible.\n"
            "Safe range: 1.0–6.0. Increase if the bar overlaps content."
        )
        self.overlay_width = self._spin_float(0.0, 1.0, 0.01, 0.5)
        self.overlay_width.setToolTip(
            "Width of the vertical overlay bar on the B-frame, as a fraction\n"
            "of the image width. The bar marks where the page transition occurred.\n"
            "Safe range: 0.3–0.7."
        )

        cap_form.addRow(self._form_label("A-capture delay (s):"), self.a_delay)
        cap_form.addRow(self._form_label("B-capture delay (s):"), self.b_delay)
        cap_form.addRow(self._form_label("B overlay width ratio:"), self.overlay_width)
        layout.addWidget(cap_group)

        # ── Deduplication group ──
        dedup_group = QGroupBox("Deduplication")
        dedup_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        dedup_form = QFormLayout(dedup_group)
        dedup_form.setSpacing(SPACE_MD)

        self.dup_top = self._spin_float(0.0, 1.0, 0.01, 0.27)
        self.dup_top.setToolTip(
            "How much of the top area is compared when deduplicating pages.\n"
            "Only this portion is checked for visual similarity between captures.\n"
            "Safe range: 0.15–0.40."
        )
        self.pixel_sim = self._spin_float(0.0, 1.0, 0.01, 0.95)
        self.pixel_sim.setToolTip(
            "Minimum pixel-level similarity (0–1) for two pages to be\n"
            "considered duplicates. Higher = stricter matching.\n"
            "Safe range: 0.90–0.99. Lower to 0.90 if near-duplicates slip through."
        )
        self.row_sim = self._spin_float(0.0, 1.0, 0.01, 0.98)
        self.row_sim.setToolTip(
            "Minimum row-by-row similarity for deduplication. Checks each\n"
            "horizontal strip independently. Higher = stricter.\n"
            "Safe range: 0.95–0.99."
        )
        self.row_cov = self._spin_float(0.0, 1.0, 0.01, 0.94)
        self.row_cov.setToolTip(
            "Fraction of rows that must be similar for pages to be considered\n"
            "duplicates. Allows minor differences (e.g., page numbers) while\n"
            "catching truly identical content.\n"
            "Safe range: 0.85–0.98."
        )

        dedup_form.addRow(self._form_label("Duplicate top ratio:"), self.dup_top)
        dedup_form.addRow(self._form_label("Pixel similarity threshold:"), self.pixel_sim)
        dedup_form.addRow(self._form_label("Row similarity threshold:"), self.row_sim)
        dedup_form.addRow(self._form_label("Row coverage threshold:"), self.row_cov)
        layout.addWidget(dedup_group)

        # ── OCR group ──
        ocr_group = QGroupBox("OCR")
        ocr_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        ocr_form = QFormLayout(ocr_group)
        ocr_form.setSpacing(SPACE_MD)

        self.ocr_enabled = QCheckBox("Enable OCR")
        self.ocr_enabled.setChecked(False)
        self.ocr_enabled.setToolTip(
            "Use OCR to compare page text for deduplication.\n"
            "Requires PaddleOCR (adds startup time). Recommended for scores\n"
            "where visual similarity alone may confuse similar-looking pages."
        )
        self.ocr_conf = self._spin_int(0, 100, 40)
        self.ocr_conf.setToolTip(
            "Minimum OCR confidence score (0–100) to accept recognized text.\n"
            "Used to deduplicate pages by comparing text content.\n"
            "Safe range: 30–70. Set to 0 to disable OCR entirely."
        )
        self.ocr_horiz = self._spin_float(0.0, 1.0, 0.01, 0.30)
        self.ocr_horiz.setToolTip(
            "How far across the page (from the left) OCR text is extracted.\n"
            "Useful for scores where the title/header sits on the left side.\n"
            "Safe range: 0.20–0.50. Set to 1.0 for full-width OCR."
        )

        ocr_form.addRow("", self.ocr_enabled)
        ocr_form.addRow(self._form_label("OCR confidence:"), self.ocr_conf)
        ocr_form.addRow(self._form_label("OCR horizontal ratio:"), self.ocr_horiz)
        layout.addWidget(ocr_group)

        # ── Advanced group ──
        self.advanced = QGroupBox("Advanced")
        self.advanced.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        adv_form = QFormLayout(self.advanced)
        adv_form.setSpacing(SPACE_MD)

        self.bar_diff = self._spin_float(0.0, 50000.0, 100.0, 500.0)
        self.bar_diff.setToolTip(
            "Minimum pixel intensity difference required to detect the black\n"
            "bar overlay on the B-frame. Higher = less sensitive to the bar.\n"
            "Safe range: 200–2000. Raise if the bar isn't being detected."
        )
        self.bar_pad = self._spin_int(-200, 200, -15)
        self.bar_pad.setToolTip(
            "Pixel offset applied to the bar detection position.\n"
            "Negative = shift left, positive = shift right.\n"
            "Safe range: -50 to +50. Fine-tune when the bar position is slightly off."
        )

        adv_form.addRow(self._form_label("Bar min diff threshold:"), self.bar_diff)
        adv_form.addRow(self._form_label("Bar overlay offset (px):"), self.bar_pad)

        self.debug_cb = QCheckBox("Debug mode (open temp folder on completion)")
        self.debug_cb.setToolTip(
            "When enabled, opens the output folder automatically after extraction\n"
            "so you can inspect intermediate files (cropped frames, debug images).\n"
            "Enable this when diagnosing extraction issues."
        )
        adv_form.addRow(self.debug_cb)

        layout.addWidget(self.advanced)
        layout.addStretch()

        # Connect all signals
        for widget in self._all_spins():
            if isinstance(widget, QDoubleSpinBox):
                widget.valueChanged.connect(self._on_change)
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self._on_change)
        self.ocr_enabled.toggled.connect(self._on_change)
        self.debug_cb.toggled.connect(self._on_debug_toggled)
        self.reset_btn = QPushButton("Reset to Defaults")
        _set_widget_class(self.reset_btn, "secondary")
        self.reset_btn.setToolTip("Restore all parameters to their factory defaults")
        self.reset_btn.clicked.connect(self._reset_defaults)
        layout.addWidget(self.reset_btn)

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    @staticmethod
    def _form_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("muted")
        lbl.setFixedWidth(115)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return lbl

    def _spin_float(self, min_v: float, max_v: float, step: float, default: float) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(min_v, max_v)
        s.setSingleStep(step)
        s.setValue(default)
        s.setDecimals(2)
        s.setFixedWidth(110)
        return s

    def _spin_int(self, min_v: int, max_v: int, default: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(min_v, max_v)
        s.setValue(default)
        s.setFixedWidth(110)
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
        self._ffmpeg = self._find_ffmpeg()
        self._use_ffmpeg = False
        self.open_requested.connect(self.open)
        self.close_requested.connect(self.close)
        self.seek_requested.connect(self._do_seek)

    def open(self, path: str):
        self.close()
        self._path = path
        with self._cap_lock:
            self._cap = cv2.VideoCapture(path)
            self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 1.0
            self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def close(self):
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
        if self._path is None:
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
            if rgb is None:
                print(f"[PreviewSeeker] frame miss ts={ts:.2f}ms={elapsed:.0f}")
                return
            if seq != self._seek_seq:
                print(f"[PreviewSeeker] stale discard ts={ts:.2f}ms={elapsed:.0f}")
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

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACE_SM)

        # ── Source toggle ──
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(16)
        self.yt_radio = QRadioButton("YouTube URL")
        self.local_radio = QRadioButton("Local file")
        self.yt_radio.setChecked(True)
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
        self.video_path_edit.setPlaceholderText("Select a video file (*.mp4, *.avi, *.mkv, *.mov)")
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
        self.quality_combo.addItem("Best (≤1080p)", "bestvideo[height<=1080][fps<=30]")
        self.quality_combo.addItem("720p", "bestvideo[height<=720][fps<=30]")
        self.quality_combo.addItem("480p", "bestvideo[height<=480][fps<=30]")
        self.quality_combo.addItem("360p", "best[height<=360][fps<=30]")
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
        self.project_edit.setPlaceholderText("Score name — type to search existing, or enter a new name")
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
        self.status_label = QLabel("Select a video source")
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # ── Crop preview ──
        self.crop_widget = CropPreviewWidget()
        self.crop_widget.setMinimumHeight(240)
        self.crop_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.crop_widget)

        self.seek_bar = DualHandleSeekBar()
        self.seek_bar.setMinimumHeight(64)
        layout.addWidget(self.seek_bar)

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
        self.crop_original_label.setObjectName("muted")

        crop_row.addWidget(crop_label)
        crop_row.addWidget(self.crop_spin)
        crop_row.addWidget(self.crop_original_label)
        crop_row.addStretch()
        self.config_btn = QPushButton("Settings")
        _set_widget_class(self.config_btn, "secondary")
        self.config_btn.setFixedWidth(80)
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
        pdf_row.addWidget(pdf_label)
        pdf_row.addWidget(self.pdf_name_edit, 1)
        layout.addLayout(pdf_row)

        # ── Progress & Log ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(140)
        layout.addWidget(self.log_edit)

        # ── Action bar ──
        action_row = QHBoxLayout()
        action_row.addStretch()
        self.reextract_btn = QPushButton("Re-extract")
        _set_widget_class(self.reextract_btn, "secondary")
        self.reextract_btn.setFixedWidth(110)
        self.reextract_btn.setVisible(False)
        self.reextract_btn.clicked.connect(self._on_reextract)
        self.extract_btn = QPushButton("Start Extraction")
        self.extract_btn.setEnabled(False)
        self.extract_btn.setFixedWidth(160)
        self.regenerate_btn = QPushButton("Regenerate PDF")
        self.regenerate_btn.setEnabled(False)
        self.regenerate_btn.setFixedWidth(160)
        self.regenerate_btn.setVisible(False)
        self.regenerate_btn.clicked.connect(self._regenerate_pdf)
        self.open_pdf_btn = QPushButton("Open PDF")
        self.open_pdf_btn.setEnabled(False)
        self.open_pdf_btn.setFixedWidth(120)
        self.open_pdf_btn.setVisible(False)
        self.open_pdf_btn.clicked.connect(self._open_pdf)
        self.cancel_btn = QPushButton("Cancel")
        _set_widget_class(self.cancel_btn, "danger")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setFixedWidth(90)
        action_row.addWidget(self.reextract_btn)
        action_row.addWidget(self.extract_btn)
        action_row.addWidget(self.regenerate_btn)
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

    # ── Public accessors ──

    @staticmethod
    def _sanitize(name: str) -> str:
        import re
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        name = name.strip('. ')
        name = re.sub(r'\s+', ' ', name)
        return name[:100] if name else "untitled"

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
            QMessageBox.warning(self, "Error", f"Could not load score:\n{e}")

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
        self.status_label.setText("Select a video source")
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
        valid = bool(self.yt_url_edit.text().strip())
        self.download_btn.setEnabled(valid and not self._busy)

    def _on_quality_changed(self, index: int):
        self._api.update_config({"yt_quality_index": index})

    def _on_yt_download(self):
        url = self.yt_url_edit.text().strip()
        if not url:
            return
        if not url.startswith("http"):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid YouTube URL starting with http")
            return
        parsed = urlparse(url)
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
        try:
            fmt = self.quality_combo.currentData()
            self._api.download_youtube(url, fmt)
        except RuntimeError as e:
            QMessageBox.warning(self, "Error", str(e))
            self._reset_download_ui()

    def _on_yt_download_completed(self, path: str):
        if self._api._original_video_path is not None:
            preview_path = self._api._video_info.path
        else:
            preview_path = path
        self._video_path = preview_path
        self.video_path_edit.setText(preview_path)
        title = self._api._last_download_title or Path(path).stem
        prev_title = self._api._prev_download_title
        cur_name = self.project_edit.text().strip()
        if not cur_name or cur_name == prev_title:
            self.project_edit.setText(title)

        # Move video files into the project's video folder
        project_dir = self.get_project_dir()
        if project_dir:
            video_dir = Path(project_dir) / "video"
            video_dir.mkdir(parents=True, exist_ok=True)
            import shutil
            video_files = [Path(path)]
            orig = self._api._original_video_path
            if orig and os.path.exists(orig) and orig != path:
                video_files.append(Path(orig))
            for src in video_files:
                dst = video_dir / src.name
                if not dst.exists():
                    shutil.move(str(src), str(dst))
            # Update GUI + API paths to the new location
            new_path = str(video_dir / Path(path).name)
            self._video_path = new_path
            self.video_path_edit.setText(new_path)
            if self._api._video_info:
                self._api._video_info.path = new_path
            if orig:
                self._api._original_video_path = str(video_dir / Path(orig).name)

        self._log(f"Video saved: {new_path}")
        self._load_preview()
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
            QMessageBox.warning(self, "Error", f"Could not open video:\n{e}")

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

    def _update_state(self):
        has_project = bool(self.project_edit.text().strip())
        has_video = bool(self._video_path and os.path.exists(self._video_path))
        has_pages = self._api.get_page_count() > 0
        can_act = not self._busy

        dbg(f"_update_state: busy={self._busy}, reextract={self._reextract_mode}, has_existing={self._has_existing_score}, has_pages={has_pages}, has_project={has_project}, has_video={has_video}")

        self.cancel_btn.setVisible(self._busy)
        self.extract_btn.setVisible(False)
        self.regenerate_btn.setVisible(False)
        self.open_pdf_btn.setVisible(False)
        self.reextract_btn.setVisible(False)

        if self._busy:
            self.cancel_btn.setEnabled(True)
        elif self._reextract_mode:
            self.extract_btn.setVisible(True)
            self.extract_btn.setEnabled(can_act and has_video)
            self.extract_btn.setText("Start Extraction")
            self.status_label.setText(
                f"Re-extract: will replace {self._api.get_page_count()} pages")
        elif self._has_existing_score and has_pages:
            self.regenerate_btn.setVisible(True)
            self.regenerate_btn.setEnabled(can_act)
            self.reextract_btn.setVisible(True)
            self.status_label.setText(
                f"Loaded {self._api.get_page_count()} pages — regenerate PDF or re-extract")
        elif has_project and has_video:
            self.extract_btn.setVisible(True)
            self.extract_btn.setEnabled(can_act)
            self.extract_btn.setText("Start Extraction")
            self.status_label.setText("Ready — start extraction")
        else:
            self.extract_btn.setVisible(True)
            self.extract_btn.setEnabled(False)
            self.extract_btn.setText("Start Extraction")
            if not has_video:
                self.status_label.setText("Select a video source")
            elif not has_project:
                self.status_label.setText("Enter a score name")
            else:
                self.status_label.setText("Ready")

    def _start_extraction(self):
        dbg("_start_extraction")
        video_path = self._video_path
        if not video_path or not os.path.exists(video_path):
            QMessageBox.warning(self, "Error", "Please select a valid video file.")
            return

        project = self.project_edit.text().strip()
        if not project:
            QMessageBox.warning(self, "Error", "Please enter a project name.")
            return

        project_dir = self.get_project_dir()
        photos_dir = Path(project_dir) / "photos"
        if photos_dir.is_dir() and not self._reextract_mode:
            existing = sorted(photos_dir.glob("page_*_merged.png"))
            if existing:
                reply = QMessageBox.question(
                    self,
                    "Overwrite Existing Project",
                    f"Project \"{project}\" already exists with {len(existing)} pages.\n\n"
                    f"Extraction will overwrite the existing pages. Continue?",
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
        self.status_label.setText("Extracting…")
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
        output_path = self.get_output_path()
        if not output_path:
            QMessageBox.warning(self, "Error", "Please set a project name.")
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
        self.status_label.setText("Generating PDF…")

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

    def on_completed(self, page_count: int):
        dbg(f"on_completed: page_count={page_count}")
        if page_count == 0:
            self._log("No pages — skipping PDF")
            self._reset_ui()
            return

        output_path = self.get_output_path()
        title = self.pdf_name_edit.text().strip() or None
        self._watchdog.start(300000)
        try:
            self._api.generate_pdf(output_path, title=title)
        except (RuntimeError, ValueError, PermissionError) as e:
            QMessageBox.warning(self, "Error", str(e))
            self._reset_ui()

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
        self.status_label.setText(f"✓ PDF saved — {output_path}")

    def on_cancelled(self):
        dbg("on_cancelled")
        self._log("Cancelled")
        self._reset_ui()

    def on_error(self, message: str):
        dbg(f"on_error: {message}")
        self._log(f"[Error] {message}")
        if not self._busy:
            QMessageBox.critical(self, "Error", message)
        self._reset_ui()

    def on_page_detected(self, idx: int, png_bytes: bytes):
        dbg(f"on_page_detected: idx={idx}")
        pass

    def on_progress(self, phase: str, percent: float, detail: str):
        dbg(f"on_progress: phase={phase}, percent={percent:.0f}%, detail={detail}")
        self.progress_bar.setValue(int(percent))
        self._watchdog.start(300000)
        phase_text = phase.replace("_", " ").title()
        if detail:
            self.status_label.setText(f"{phase_text}: {detail}")
        else:
            self.status_label.setText(phase_text)

    def _reset_ui(self):
        dbg("_reset_ui")
        self._busy = False
        self._reextract_mode = False
        self._watchdog.stop()
        self.cancel_btn.setEnabled(False)
        self.open_pdf_btn.setVisible(False)
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
        self.setMinimumSize(960, 760)
        self.resize(1100, 780)
        self.setStyleSheet(STYLESHEET.replace("__CHECK_PLACEHOLDER__", CHECK_INDICATOR_PATH).replace("__CHEVRON_PLACEHOLDER__", CHEVRON_PATH))

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
            self.extract_tab.on_completed(page_count)
            score_dir = self.extract_tab.get_project_dir()
            self.api.open_debug_folder(score_dir)
            if page_count > 0:
                self._generating_pdf = True
            else:
                self.extract_tab._reset_ui()

    def _on_cancelled(self):
        self.extract_tab.on_cancelled()

    def _on_yt_downloaded(self, path: str):
        self.extract_tab._on_yt_download_completed(path)

    def _on_tab_changed(self, index: int):
        if index == 1:
            self.config_tab.refresh_from_api()

    def closeEvent(self, event):
        self.extract_tab._preview_seeker.close_requested.emit()
        self.extract_tab._preview_thread.quit()
        self.extract_tab._preview_thread.wait(2000)
        super().closeEvent(event)


# ── Entrypoint ───────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Score Extractor")

    global CHECK_INDICATOR_PATH
    global CHEVRON_PATH
    CHECK_INDICATOR_PATH = _generate_check_pixmap()
    CHEVRON_PATH = _generate_chevron_pixmap()

    # Set app-wide font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
