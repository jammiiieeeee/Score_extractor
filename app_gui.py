import os
import sys
import time
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
QDoubleSpinBox:focus, QSpinBox:focus {{
    border-color: {BRASS};
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
    height: 22px;
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
            overlay = QColor(212, 168, 67, 25)
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
        self.groove.setMinimumHeight(24)
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
        self.groove.mouseReleaseEvent = lambda e: setattr(self, '_dragging', None)

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

        # Start handle
        if self._start_enabled:
            painter.setBrush(QColor(BRASS))
            painter.setPen(QPen(QColor(BG), 2))
            painter.drawEllipse(x1 - 7, mid - 7, 14, 14)

        # End handle
        if self._end_enabled:
            painter.setBrush(QColor(BRASS))
            painter.setPen(QPen(QColor(BG), 2))
            painter.drawEllipse(x2 - 7, mid - 7, 14, 14)

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

        if d_start < 16 and d_start <= d_end:
            self._dragging = 'start'
        elif d_end < 16:
            self._dragging = 'end'
        else:
            self._dragging = None

    def _groove_move(self, event):
        if not self._dragging or self._duration <= 0:
            return
        pos = event.position()
        w = self.groove.width()
        margin = 16
        track_w = max(w - margin * 2, 1)
        frac = max(0.0, min(1.0, (pos.x() - margin) / track_w))

        if self._dragging == 'start':
            self._start = min(frac, self._end)
        else:
            self._end = max(frac, self._start)
        self.groove.update()
        self._update_labels()
        ts = frac * self._duration
        self.seek_changed.emit(ts)


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
        layout.setSpacing(12)

        title = QLabel("Settings")
        title.setObjectName("title")
        layout.addWidget(title)

        desc = QLabel("Adjust extraction behavior. These apply to the next extraction.")
        desc.setObjectName("muted")
        layout.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(18)

        self.crop_ratio = self._spin_float(0.0, 1.0, 0.01, 0.35)
        self.sensitivity = self._spin_float(0.0, 1.0, 0.01, 0.96)
        self.min_interval = self._spin_float(0.0, 60.0, 0.5, 3.0)
        self.ocr_conf = self._spin_int(0, 100, 40)

        self.ocr_enabled = QCheckBox("Enable OCR")
        self.ocr_enabled.setChecked(False)

        form.addRow("Crop ratio:", self.crop_ratio)
        form.addRow("Page change sensitivity:", self.sensitivity)
        form.addRow("Min seconds between captures:", self.min_interval)
        form.addRow("", self.ocr_enabled)
        form.addRow("OCR confidence:", self.ocr_conf)

        layout.addLayout(form)

        # Advanced group
        self.advanced = QGroupBox("Advanced Settings")
        self.advanced.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        adv_grid = QGridLayout(self.advanced)
        adv_grid.setVerticalSpacing(10)
        adv_grid.setHorizontalSpacing(12)

        adv_fields = [
            ("Frame check interval (s):", self._spin_float(0.05, 5.0, 0.05, 0.2)),
            ("Top analysis ratio:", self._spin_float(0.05, 1.0, 0.01, 0.34)),
            ("A-capture delay (s):", self._spin_float(0.0, 5.0, 0.1, 0.3)),
            ("B-capture delay (s):", self._spin_float(0.0, 10.0, 0.1, 3.0)),
            ("B overlay width ratio:", self._spin_float(0.0, 1.0, 0.01, 0.5)),
            ("Duplicate top ratio:", self._spin_float(0.0, 1.0, 0.01, 0.27)),
            ("Pixel similarity threshold:", self._spin_float(0.0, 1.0, 0.01, 0.95)),
            ("Row similarity threshold:", self._spin_float(0.0, 1.0, 0.01, 0.98)),
            ("Row coverage threshold:", self._spin_float(0.0, 1.0, 0.01, 0.94)),
            ("OCR horizontal ratio:", self._spin_float(0.0, 1.0, 0.01, 0.30)),
            ("Crop top offset:", self._spin_float(0.0, 1.0, 0.01, 0.0)),
            ("Blank content std threshold:", self._spin_float(0.0, 50.0, 0.5, 3.0)),
            ("Bar min diff threshold:", self._spin_float(0.0, 50000.0, 100.0, 500.0)),
            ("Bar overlay offset (px):", self._spin_int(-200, 200, -15)),
        ]

        for r, (label_text, spinbox) in enumerate(adv_fields):
            lbl = QLabel(label_text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            adv_grid.addWidget(lbl, r, 0)
            adv_grid.addWidget(spinbox, r, 1)

        adv_grid.setColumnStretch(0, 0)
        adv_grid.setColumnStretch(1, 1)

        self.adv_frame_check = adv_fields[0][1]
        self.adv_top_ratio = adv_fields[1][1]
        self.adv_a_delay = adv_fields[2][1]
        self.adv_b_delay = adv_fields[3][1]
        self.adv_overlay = adv_fields[4][1]
        self.adv_dup_top = adv_fields[5][1]
        self.adv_pixel_sim = adv_fields[6][1]
        self.adv_row_sim = adv_fields[7][1]
        self.adv_row_cov = adv_fields[8][1]
        self.adv_ocr_horiz = adv_fields[9][1]
        self.adv_crop_offset = adv_fields[10][1]
        self.adv_blank_std = adv_fields[11][1]
        self.adv_bar_diff = adv_fields[12][1]
        self.adv_bar_pad = adv_fields[13][1]

        # Debug mode checkbox
        r = len(adv_fields)
        self.debug_cb = QCheckBox("Debug mode (open temp folder on completion)")
        adv_grid.addWidget(self.debug_cb, r, 0, 1, 2)

        layout.addWidget(self.advanced)

        # Connect all signals
        for widget in self._all_spins():
            if isinstance(widget, QDoubleSpinBox):
                widget.valueChanged.connect(self._on_change)
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self._on_change)
        self.ocr_enabled.toggled.connect(self._on_change)
        self.debug_cb.toggled.connect(self._on_debug_toggled)

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _spin_float(self, min_v: float, max_v: float, step: float, default: float) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(min_v, max_v)
        s.setSingleStep(step)
        s.setValue(default)
        s.setDecimals(2)
        s.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return s

    def _spin_int(self, min_v: int, max_v: int, default: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(min_v, max_v)
        s.setValue(default)
        s.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return s

    def _all_spins(self):
        return [
            self.crop_ratio, self.sensitivity, self.min_interval, self.ocr_conf,
            self.adv_frame_check, self.adv_top_ratio, self.adv_a_delay, self.adv_b_delay,
            self.adv_overlay, self.adv_dup_top, self.adv_pixel_sim, self.adv_row_sim,
            self.adv_row_cov, self.adv_ocr_horiz, self.adv_crop_offset, self.adv_blank_std,
            self.adv_bar_diff,
            self.adv_bar_pad,
        ]

    def apply_to_api(self):
        self._updating = True
        try:
            updates = {
                "default_crop_ratio": self.crop_ratio.value(),
                "change_detection_threshold": self.sensitivity.value(),
                "min_screenshot_interval": self.min_interval.value(),
                "ocr_confidence_threshold": self.ocr_conf.value() if self.ocr_enabled.isChecked() else 0,
                "frame_check_interval": self.adv_frame_check.value(),
                "top_analysis_ratio": self.adv_top_ratio.value(),
                "a_capture_delay": self.adv_a_delay.value(),
                "b_capture_delay": self.adv_b_delay.value(),
                "b_overlay_width_ratio": self.adv_overlay.value(),
                "duplicate_top_ratio": self.adv_dup_top.value(),
                "pixel_similarity_threshold": self.adv_pixel_sim.value(),
                "row_similarity_threshold": self.adv_row_sim.value(),
                "row_coverage_threshold": self.adv_row_cov.value(),
                "ocr_horizontal_ratio": self.adv_ocr_horiz.value(),
                "crop_top_offset": self.adv_crop_offset.value(),
                "blank_content_std_threshold": self.adv_blank_std.value(),
                "bar_min_diff_threshold": self.adv_bar_diff.value(),
                "bar_padding_px": self.adv_bar_pad.value(),
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
            self.crop_ratio.setValue(cfg.get("default_crop_ratio", 0.35))
            self.sensitivity.setValue(cfg.get("change_detection_threshold", 0.96))
            self.min_interval.setValue(cfg.get("min_screenshot_interval", 3.0))
            ocr_conf = cfg.get("ocr_confidence_threshold", 40)
            self.ocr_enabled.setChecked(ocr_conf > 0)
            self.ocr_conf.setValue(ocr_conf if ocr_conf > 0 else 40)
            self.adv_frame_check.setValue(cfg.get("frame_check_interval", 0.8))
            self.adv_top_ratio.setValue(cfg.get("top_analysis_ratio", 0.34))
            self.adv_a_delay.setValue(cfg.get("a_capture_delay", 0.3))
            self.adv_b_delay.setValue(cfg.get("b_capture_delay", 3.0))
            self.adv_overlay.setValue(cfg.get("b_overlay_width_ratio", 0.2))
            self.adv_dup_top.setValue(cfg.get("duplicate_top_ratio", 0.27))
            self.adv_pixel_sim.setValue(cfg.get("pixel_similarity_threshold", 0.95))
            self.adv_row_sim.setValue(cfg.get("row_similarity_threshold", 0.98))
            self.adv_row_cov.setValue(cfg.get("row_coverage_threshold", 0.94))
            self.adv_ocr_horiz.setValue(cfg.get("ocr_horizontal_ratio", 0.30))
            self.adv_crop_offset.setValue(cfg.get("crop_top_offset", 0.0))
            self.adv_blank_std.setValue(cfg.get("blank_content_std_threshold", 3.0))
            self.adv_bar_diff.setValue(cfg.get("bar_min_diff_threshold", 500.0))
            self.adv_bar_pad.setValue(cfg.get("bar_padding_px", -15))
            self.debug_cb.setChecked(self._api.is_debug_mode())
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
    seek_requested = pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        self._cap = None
        self._path: Optional[str] = None
        self._fps = 1.0
        self._width = 0
        self._height = 0
        self._seek_seq = 0
        self._ffmpeg = self._find_ffmpeg()
        self._use_ffmpeg = self._ffmpeg is not None
        self.seek_requested.connect(self._do_seek)

    def open(self, path: str):
        self.close()
        self._path = path
        self._cap = cv2.VideoCapture(path)
        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 1.0
        self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def close(self):
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

        self._settings = QSettings("ScoreExtractor", "App")
        self._parent_dir = self._settings.value("parent_dir", str(Path(__file__).resolve().parent / "output"))

        layout = QVBoxLayout(self)

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
        input_grid.setColumnMinimumWidth(2, 210)

        # Local mode
        self._local_label = QLabel("Video file:")
        self._local_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.video_path_edit = QLineEdit()
        self.video_path_edit.setPlaceholderText("Select a video file (*.mp4, *.avi, *.mkv, *.mov)")
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.setObjectName("secondary")
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
        self.download_btn.setObjectName("secondary")
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

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("hline")
        layout.addWidget(sep)

        # ── Project field ──
        project_label = QLabel("Project:")

        self.project_edit = QLineEdit()
        self.project_edit.setPlaceholderText("Score name — type to search existing, or enter a new name")
        self._completer_model = QStringListModel()
        self._completer = QCompleter(self._completer_model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.project_edit.setCompleter(self._completer)

        self.project_browse_btn = QPushButton("Browse…")
        self.project_browse_btn.setObjectName("secondary")

        project_row = QHBoxLayout()
        project_row.addWidget(project_label)
        project_row.addWidget(self.project_edit, 1)
        project_row.addWidget(self.project_browse_btn)
        layout.addLayout(project_row)

        # ── Status line ──
        self.status_label = QLabel("Select a video source above to begin")
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # ── Crop preview ──
        self.crop_widget = CropPreviewWidget()
        layout.addWidget(self.crop_widget, 1)

        self.seek_bar = DualHandleSeekBar()
        self.seek_bar.setMaximumHeight(80)
        self.seek_bar.setMinimumHeight(60)
        layout.addWidget(self.seek_bar)
        layout.addSpacing(4)

        # ── Crop ratio row ──
        crop_row = QHBoxLayout()
        crop_label = QLabel("Crop ratio:")
        crop_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.crop_spin = QDoubleSpinBox()
        self.crop_spin.setRange(0.0, 1.0)
        self.crop_spin.setSingleStep(0.01)
        self.crop_spin.setDecimals(2)
        self.crop_spin.setValue(self._api.get_config().get("default_crop_ratio", 0.35))
        self.crop_spin.setFixedWidth(100)
        self.crop_original_label = QLabel("")
        self.crop_original_label.setObjectName("muted")
        self.set_default_btn = QPushButton("Set as Default")
        self.set_default_btn.setObjectName("secondary")
        self.set_default_btn.setFixedWidth(120)

        crop_row.addWidget(crop_label)
        crop_row.addWidget(self.crop_spin)
        crop_row.addWidget(self.crop_original_label)
        crop_row.addStretch()
        crop_row.addWidget(self.set_default_btn)
        layout.addLayout(crop_row)

        # ── Output PDF name ──
        pdf_row = QHBoxLayout()
        pdf_label = QLabel("Output PDF:")
        pdf_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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
        self.action_btn = QPushButton("Start Extraction")
        self.action_btn.setEnabled(False)
        self.action_btn.setFixedWidth(200)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setFixedWidth(90)
        action_row.addWidget(self.action_btn)
        action_row.addWidget(self.cancel_btn)
        layout.addLayout(action_row)

        # ── Connections ──
        self.project_edit.returnPressed.connect(self._on_project_entered)
        self._completer.activated.connect(self._on_project_selected)
        self.project_browse_btn.clicked.connect(self._browse_project)
        self.browse_btn.clicked.connect(self._browse_video)
        self.video_path_edit.textChanged.connect(self._on_path_changed)
        self.action_btn.clicked.connect(self._on_action)
        self.cancel_btn.clicked.connect(self._cancel)
        self.local_radio.toggled.connect(self._on_source_toggled)
        self.yt_radio.toggled.connect(self._on_source_toggled)
        self._on_source_toggled()
        self.download_btn.clicked.connect(self._on_yt_download)
        self.yt_url_edit.textChanged.connect(self._on_yt_url_changed)
        self.quality_combo.currentIndexChanged.connect(self._on_quality_changed)
        self.seek_bar.seek_changed.connect(self._on_seek)
        self.crop_spin.valueChanged.connect(self._on_crop_spin_changed)
        self.set_default_btn.clicked.connect(self._set_crop_default)
        self.crop_widget.crop_ratio_changed.connect(self.crop_spin.setValue)

        self._refresh_completer()
        self._update_state()

    # ── Public accessors ──

    def get_project_dir(self) -> str:
        project = self.project_edit.text().strip()
        if not project:
            return ""
        return str(Path(self._parent_dir) / project)

    def get_output_path(self) -> str:
        project_dir = self.get_project_dir()
        if not project_dir:
            return ""
        pdf_name = self.pdf_name_edit.text().strip()
        if not pdf_name:
            pdf_name = Path(project_dir).name
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
        self._log(f"Loading score: {score_path}")
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
            self._set_video_controls_enabled(False)
            # Show first page in preview
            first = self._api.get_first_page_image()
            if first is not None:
                self.crop_widget.set_frame(self._img_to_pixmap(first))
            self.status_label.setText(f"Loaded {count} pages from \"{p.name}\"")
            self._log(f"Loaded {count} pages (original crop: {int(self._loaded_original_ratio * 100)}%)")
            self._refresh_completer()
            self._update_state()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load score:\n{e}")

    def _switch_to_new_project(self):
        self._api.clear_pages()
        self._has_existing_score = False
        self._loaded_original_ratio = None
        self._completed_pdf_path = None
        self._project_dir = ""
        self.crop_original_label.setText("")
        self.crop_spin.setValue(self._api.get_config().get("default_crop_ratio", 0.35))
        if not self.pdf_name_edit.text():
            self.pdf_name_edit.setText(self.project_edit.text())
        self._set_video_controls_enabled(True)
        self.status_label.setText("Select a video source above to begin")
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
        self._log(f"Video downloaded: {path}")
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

            self._preview_seeker.open(path)
            self._log("Video loaded: " + path)
            self._log(f"Duration: {info.duration:.1f}s, FPS: {info.fps:.2f}, "
                      f"Resolution: {info.width}x{info.height}")
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
        self.crop_widget.set_ratio(val)
        if self._has_existing_score:
            self._api.reapply_crop(val)
            first = self._api.get_first_page_image()
            if first is not None:
                self.crop_widget.set_frame(self._img_to_pixmap(first))
            self.crop_original_label.setText(
                f"(was {int(self._loaded_original_ratio * 100)}%)" if self._loaded_original_ratio else "")

    def _set_crop_default(self):
        ratio = self.crop_spin.value()
        try:
            self._api.update_config({"default_crop_ratio": ratio})
            self._log(f"Crop default set to {int(ratio * 100)}%")
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))

    # ── State management ──

    def _update_state(self):
        has_project = bool(self.project_edit.text().strip())
        has_video = bool(self._video_path and os.path.exists(self._video_path))
        has_pages = self._api.get_page_count() > 0
        can_act = not self._busy

        if self._busy:
            pass  # button text set by _on_action
        elif self._has_existing_score and has_pages:
            self.action_btn.setText("Regenerate PDF")
            self.action_btn.setEnabled(can_act)
            self.status_label.setText(
                f"Loaded {self._api.get_page_count()} pages — adjust crop ratio and regenerate")
        elif has_project and has_video:
            self.action_btn.setText("Start Extraction")
            self.action_btn.setEnabled(can_act)
            self.status_label.setText("Ready — click Start Extraction to begin")
        else:
            self.action_btn.setText("Start Extraction")
            self.action_btn.setEnabled(False)
            if not has_video:
                self.status_label.setText("Select a video source above to begin")
            elif not has_project:
                self.status_label.setText("Enter a score name to continue")
            else:
                self.status_label.setText("Ready")

    # ── Action button ──

    def _on_action(self):
        if self._busy:
            return
        if self._completed_pdf_path:
            self._open_pdf()
        elif self._has_existing_score and self._api.get_page_count() > 0:
            self._regenerate_pdf()
        else:
            self._start_extraction()

    def _start_extraction(self):
        video_path = self._video_path
        if not video_path or not os.path.exists(video_path):
            QMessageBox.warning(self, "Error", "Please select a valid video file.")
            return

        project = self.project_edit.text().strip()
        if not project:
            QMessageBox.warning(self, "Error", "Please enter a project name.")
            return

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
        self.action_btn.setText("Extracting…")
        self.action_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_edit.clear()
        self.status_label.setText("Extracting pages from video…")

        self._api.start_extraction(
            video_path=video_path,
            no_ocr=no_ocr,
            start_time=start_time,
            end_offset=end_offset,
            output_folder=self._parent_dir,
            score_name=project,
        )

    def _regenerate_pdf(self):
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
        self.action_btn.setText("Generating PDF…")
        self.action_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_edit.clear()
        self.status_label.setText("Generating PDF from loaded pages…")

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
            self._api.cancel_extraction()
            self._log("Cancelling…")

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
        self._log(f"Operation complete: {page_count} pages")
        if page_count == 0:
            self._log("No pages resulted. Skipping PDF.")
            self._reset_ui()
            return

        if not self._has_existing_score:
            output_path = self.get_output_path()
            self._log(f"Generating PDF: {output_path}")
            title = self.pdf_name_edit.text().strip() or None
            try:
                self._api.generate_pdf(output_path, title=title)
            except RuntimeError as e:
                QMessageBox.warning(self, "Error", str(e))
                self._reset_ui()

    def on_pdf_completed(self, page_count: int):
        output_path = self.get_output_path()
        self._completed_pdf_path = output_path
        self._log(f"PDF saved to: {output_path}")
        self.status_label.setText(f"✓ PDF saved — {output_path}")
        self.action_btn.setText("Open PDF")
        self.action_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._busy = False

    def on_cancelled(self):
        self._log("Cancelled by user.")
        self._reset_ui()

    def on_error(self, message: str):
        self._log(f"[Error] {message}")
        if not self._busy:
            QMessageBox.critical(self, "Error", message)
        self._reset_ui()

    def on_page_detected(self, _idx: int, _png_bytes: bytes):
        pass

    def on_progress(self, phase: str, percent: float, _detail: str):
        self.progress_bar.setValue(int(percent))
        if phase == "extracting":
            self.action_btn.setText(f"Extracting… {int(percent)}%")
        elif phase == "generating_pdf":
            self.action_btn.setText(f"Generating PDF… {int(percent)}%")

    def _reset_ui(self):
        self._busy = False
        self.cancel_btn.setEnabled(False)
        self.action_btn.setText("Start Extraction")
        self.download_btn.setEnabled(True)
        self.download_btn.setText("Download")
        self.yt_url_edit.setEnabled(True)
        self.quality_combo.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self._update_state()

    def _log(self, msg: str):
        self.log_edit.append(msg)








# ── Piano-key motif divider ──────────────────────────────────────────

class PianoKeyDivider(QWidget):
    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor, QPen
        painter = QPainter(self)
        w = self.width()
        h = self.height()
        key_w = 18
        key_h = 18
        black_h = 12
        black_w = 10
        offset = 12

        # Brushed brass line across the rest
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(212, 168, 67))
        painter.drawRect(offset + 8 * key_w, h // 2 - 1, w - offset - 8 * key_w, 2)

        # Draw 8 white keys
        for i in range(8):
            x = offset + i * key_w
            painter.setPen(QPen(QColor(51, 51, 51), 1))
            painter.setBrush(QColor(232, 232, 232))
            painter.drawRect(x, h // 2 - key_h // 2, key_w - 1, key_h)

        # Draw 6 black keys (skip positions where there's no black key)
        black_positions = [0, 1, 3, 4, 5, 7]
        for i in black_positions:
            bx = offset + (i + 1) * key_w - black_w // 2
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(22, 22, 22))
            painter.drawRect(bx, h // 2 - key_h // 2, black_w, black_h)

        painter.end()


# ── Main Window ──────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Score Extractor")
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

        header = QLabel("Score Extractor")
        header.setObjectName("title")
        header.setStyleSheet(f"""
            font-size: 26px; font-weight: 700;
            color: {INK}; padding: 4px 0 4px 0;
        """)
        main_layout.addWidget(header)

        # Piano-key motif divider
        piano_div = PianoKeyDivider()
        piano_div.setFixedHeight(28)
        main_layout.addWidget(piano_div)

        # Tabs
        self.tabs = QTabWidget()
        self.extract_tab = ExtractTab(self.api)
        self.config_tab = ConfigTab(self.api)

        self.tabs.addTab(self.extract_tab, "Extract")
        self.tabs.addTab(self.config_tab, "Config")

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
        self.extract_tab._preview_seeker.close()
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
