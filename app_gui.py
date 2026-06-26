import os
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import cv2
import numpy as np
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QIcon, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QLineEdit, QFileDialog,
    QMessageBox, QProgressBar, QTextEdit, QGroupBox, QFormLayout,
    QDoubleSpinBox, QSpinBox, QCheckBox, QSlider, QScrollArea,
    QListWidget, QListView, QListWidgetItem, QDialog, QComboBox,
    QRadioButton, QButtonGroup,
    QFrame, QSizePolicy, QSplitter, QGridLayout,
)

from gui_bridge import ExtractionSignals
from src.api.gui_api import GuiApi, SandboxInfo


# ── Palette (ink-on-cream-paper) ──────────────────────────────────────

PAPER      = "#f5f0e8"
CARD       = "#ffffff"
INK        = "#1a1a2e"
MUTED      = "#6b6b8d"
ACCENT     = "#c0392b"
ACCENT_H   = "#e74c3c"
GREEN      = "#27ae60"
BORDER     = "#ddd8cd"
CREAM_DARK = "#e8e0d0"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {PAPER};
    color: {INK};
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 13px;
}}
QTabWidget::pane {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}
QTabBar::tab {{
    background: {CREAM_DARK};
    color: {INK};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 20px;
    margin-right: 2px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background: {CARD};
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QPushButton {{
    background: {ACCENT};
    color: white;
    border: none;
    border-radius: 5px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton:hover {{
    background: {ACCENT_H};
}}
QPushButton:pressed {{
    background: #992d22;
}}
QPushButton:disabled {{
    background: {BORDER};
    color: {MUTED};
}}
QPushButton.secondary {{
    background: {CARD};
    color: {INK};
    border: 1px solid {BORDER};
    padding: 8px 14px;
}}
QPushButton.secondary:hover {{
    background: {CREAM_DARK};
}}
QPushButton.danger {{
    background: {MUTED};
}}
QPushButton.danger:hover {{
    background: {ACCENT};
}}
QLineEdit {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 10px;
    color: {INK};
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}
QDoubleSpinBox, QSpinBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 10px;
    color: {INK};
    min-height: 26px;
    font-size: 14px;
}}
QGroupBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 18px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: {INK};
}}
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {BORDER};
}}
QSlider::groove:horizontal {{
    background: {BORDER};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 3px;
}}
QProgressBar {{
    background: {CREAM_DARK};
    border: 1px solid {BORDER};
    border-radius: 6px;
    text-align: center;
    height: 22px;
    font-weight: 600;
    color: {INK};
}}
QProgressBar::chunk {{
    background: {GREEN};
    border-radius: 5px;
}}
QTextEdit {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {INK};
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
}}
QListWidget {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {INK};
}}
QListWidget::item:selected {{
    background: {CREAM_DARK};
    border: 2px solid {ACCENT};
    border-radius: 6px;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QLabel {{
    color: {INK};
}}
QLabel.muted {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel.title {{
    font-size: 22px;
    font-weight: 700;
    color: {INK};
}}
QLabel.count {{
    font-size: 14px;
    font-weight: 600;
    color: {ACCENT};
}}
QComboBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 10px;
    color: {INK};
}}
QFormLayout {{
    font-size: 14px;
}}
QSplitter::handle {{
    background: {BORDER};
    width: 2px;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: url(__CHECK_PLACEHOLDER__);
}}
"""


CHECK_INDICATOR_PATH: str = ""


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


# ── Crop Preview Widget ──────────────────────────────────────────────

class CropPreviewWidget(QWidget):
    crop_ratio_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._ratio = 0.35
        self._drag_active = False
        self._image_rect = None
        self.setMinimumSize(320, 240)
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
            overlay = QColor(192, 57, 43, 40)
            painter.fillRect(ox, oy, pw, line_y - oy, overlay)

            # Crop line
            pen = QPen(QColor(192, 57, 43), 3)
            painter.setPen(pen)
            painter.drawLine(ox, line_y, ox + pw, line_y)

            # Grip ridges at center (indicates draggable)
            pen_grip = QPen(QColor(192, 57, 43), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_grip)
            cx = ox + pw // 2
            half = 8
            for dy in (-4, 0, 4):
                painter.drawLine(cx - half, line_y + dy, cx + half, line_y + dy)

            # Label
            painter.setPen(QColor(192, 57, 43))
            font = QFont("Segoe UI", 11, QFont.Weight.Bold)
            painter.setFont(font)
            label = f"Crop: {int(self._ratio * 100)}%"
            painter.drawText(ox, line_y - 16, label)
        else:
            painter.setPen(QColor(107, 107, 141))
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
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(2)

        # Groove surface
        self.groove = QWidget()
        self.groove.setMinimumHeight(36)
        self.groove.setMouseTracking(True)
        layout.addWidget(self.groove)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)
        self.start_cb = QCheckBox("Start-time capture")
        self.start_cb.setChecked(True)
        self.start_label = QLabel("00:00.0")
        self.start_label.setObjectName("muted")
        self.start_label.setFixedWidth(70)
        ctrl.addWidget(self.start_cb)
        ctrl.addWidget(self.start_label)

        self.end_cb = QCheckBox("End duration")
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
        return 0.0 if not self._end_enabled else self._end * self._duration

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
        painter.setBrush(QColor(BORDER))
        painter.drawRoundedRect(margin, mid - 3, track_w, 6, 3, 3)

        # Highlighted range when both enabled
        if self._start_enabled and self._end_enabled and x2 > x1:
            painter.setBrush(QColor(ACCENT))
            painter.drawRoundedRect(x1, mid - 3, x2 - x1, 6, 3, 3)

        # Start handle
        if self._start_enabled:
            painter.setBrush(QColor(ACCENT))
            painter.setPen(QPen(QColor("white"), 2))
            painter.drawEllipse(x1 - 9, mid - 9, 18, 18)

        # End handle
        if self._end_enabled:
            painter.setBrush(QColor(ACCENT))
            painter.setPen(QPen(QColor("white"), 2))
            painter.drawEllipse(x2 - 9, mid - 9, 18, 18)

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

        if d_start < 20 and d_start <= d_end:
            self._dragging = 'start'
        elif d_end < 20:
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
        self.strips = self._spin_int(1, 20, 7)
        self.sensitivity = self._spin_float(0.0, 1.0, 0.01, 0.96)
        self.min_interval = self._spin_float(0.0, 60.0, 0.5, 3.0)
        self.ocr_conf = self._spin_int(0, 100, 40)

        form.addRow("Crop ratio:", self.crop_ratio)
        form.addRow("Strips per page:", self.strips)
        form.addRow("Page change sensitivity:", self.sensitivity)
        form.addRow("Min seconds between captures:", self.min_interval)
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
            self.crop_ratio, self.strips, self.sensitivity, self.min_interval, self.ocr_conf,
            self.adv_frame_check, self.adv_top_ratio, self.adv_a_delay, self.adv_b_delay,
            self.adv_overlay, self.adv_dup_top, self.adv_pixel_sim, self.adv_row_sim,
            self.adv_row_cov, self.adv_ocr_horiz, self.adv_crop_offset, self.adv_blank_std,
            self.adv_bar_diff,
        ]

    def apply_to_api(self):
        self._updating = True
        try:
            updates = {
                "default_crop_ratio": self.crop_ratio.value(),
                "default_strips_per_page": self.strips.value(),
                "change_detection_threshold": self.sensitivity.value(),
                "min_screenshot_interval": self.min_interval.value(),
                "ocr_confidence_threshold": self.ocr_conf.value(),
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
            self.strips.setValue(cfg.get("default_strips_per_page", 7))
            self.sensitivity.setValue(cfg.get("change_detection_threshold", 0.96))
            self.min_interval.setValue(cfg.get("min_screenshot_interval", 3.0))
            self.ocr_conf.setValue(cfg.get("ocr_confidence_threshold", 40))
            self.adv_frame_check.setValue(cfg.get("frame_check_interval", 0.2))
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

class ExtractTab(QWidget):
    extraction_completed = pyqtSignal(int)

    def __init__(self, api: GuiApi, parent=None):
        super().__init__(parent)
        self._api = api
        self._video_path: Optional[str] = None
        self._video_duration = 0.0
        self._extracting = False

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Source toggle ──
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(16)
        self.local_radio = QRadioButton("Local file")
        self.yt_radio = QRadioButton("YouTube URL")
        self.yt_radio.setChecked(True)
        toggle_row.addWidget(self.local_radio)
        toggle_row.addWidget(self.yt_radio)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        # ── Input grid (shared column alignment) ──
        input_grid = QGridLayout()
        input_grid.setColumnMinimumWidth(0, 115)
        input_grid.setColumnStretch(1, 1)
        input_grid.setColumnMinimumWidth(2, 210)

        # Row 0 — Local file mode
        self._local_label = QLabel("Video file:")
        self._local_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.video_path_edit = QLineEdit()
        self.video_path_edit.setPlaceholderText("Select a video file (*.mp4, *.avi, *.mkv, *.mov)")
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.setObjectName("secondary")
        input_grid.addWidget(self._local_label, 0, 0)
        input_grid.addWidget(self.video_path_edit, 0, 1)
        input_grid.addWidget(self.browse_btn, 0, 2)

        # Row 0 — YouTube URL mode (same cells, hidden initially)
        self._yt_label = QLabel("YouTube URL:")
        self._yt_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.yt_url_edit = QLineEdit()
        self.yt_url_edit.setPlaceholderText("Paste YouTube video URL")

        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Best (≤1080p)", "best[height<=1080]")
        self.quality_combo.addItem("720p", "best[height<=720]")
        self.quality_combo.addItem("480p", "best[height<=480]")
        self.quality_combo.addItem("360p", "best[height<=360]")
        self.quality_combo.addItem("Best available", "best")
        self.quality_combo.setCurrentIndex(0)
        self.quality_combo.setFixedWidth(100)

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
        # YT widgets visible by default (radio checked above); hide local ones
        self._local_label.hide()
        self.video_path_edit.hide()
        self.browse_btn.hide()

        # Row 1 — PDF title
        title_label = QLabel("PDF title:")
        title_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.custom_title_edit = QLineEdit()
        input_grid.addWidget(title_label, 1, 0)
        input_grid.addWidget(self.custom_title_edit, 1, 1)

        # Row 2 — Output path
        out_label = QLabel("Save PDF to:")
        out_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("output.pdf")
        self.output_browse_btn = QPushButton("Browse…")
        self.output_browse_btn.setObjectName("secondary")
        input_grid.addWidget(out_label, 2, 0)
        input_grid.addWidget(self.output_path_edit, 2, 1)
        input_grid.addWidget(self.output_browse_btn, 2, 2)

        layout.addLayout(input_grid)

        # ── Unified preview (crop + dual seekbar) ──
        self.crop_widget = CropPreviewWidget()
        layout.addWidget(self.crop_widget, 1)

        self.seek_bar = DualHandleSeekBar()
        layout.addWidget(self.seek_bar)

        # Crop bar
        crop_bar = QHBoxLayout()
        self.crop_default_label = QLabel(f"Default: {int(self._api.get_config().get('default_crop_ratio', 0.35) * 100)}%")
        self.crop_default_label.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {MUTED};")
        self.crop_default_btn = QPushButton("Set as Default")
        self.crop_default_btn.setObjectName("secondary")
        self.crop_default_btn.setFixedWidth(120)
        crop_bar.addWidget(self.crop_default_label)
        crop_bar.addStretch()
        crop_bar.addWidget(self.crop_default_btn)
        layout.addLayout(crop_bar)

        self.crop_default_btn.clicked.connect(self._set_crop_default)

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
        self.start_btn = QPushButton("Start Extraction")
        self.start_btn.setEnabled(False)
        self.start_btn.setFixedWidth(160)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setFixedWidth(90)
        action_row.addWidget(self.start_btn)
        action_row.addWidget(self.cancel_btn)
        layout.addLayout(action_row)

        # ── Connections ──
        self.browse_btn.clicked.connect(self._browse_video)
        self.video_path_edit.textChanged.connect(self._on_path_changed)
        self.output_browse_btn.clicked.connect(self._browse_output)
        self.start_btn.clicked.connect(self._start_extraction)
        self.cancel_btn.clicked.connect(self._cancel_extraction)
        self.local_radio.toggled.connect(self._on_source_toggled)
        self.yt_radio.toggled.connect(self._on_source_toggled)
        self._on_source_toggled()
        self.download_btn.clicked.connect(self._on_yt_download)
        self.yt_url_edit.textChanged.connect(self._on_yt_url_changed)

        # Seek bar connection
        self.seek_bar.seek_changed.connect(self._on_seek)

    def get_output_path(self) -> str:
        path = self.output_path_edit.text().strip()
        if not path and self._video_path:
            path = str(Path(self._video_path).with_suffix('.pdf'))
            self.output_path_edit.setText(path)
        return path

    def set_output_path(self, path: str):
        self.output_path_edit.setText(path)

    def _browse_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video", "",
            "Video files (*.mp4 *.avi *.mkv *.mov);;All files (*.*)")
        if path:
            self.video_path_edit.setText(path)

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF As", "",
            "PDF files (*.pdf);;All files (*.*)")
        if path:
            self.output_path_edit.setText(path)

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

    def _on_yt_url_changed(self):
        valid = bool(self.yt_url_edit.text().strip())
        self.download_btn.setEnabled(valid and not self._extracting)

    def _on_yt_download(self):
        url = self.yt_url_edit.text().strip()
        if not url:
            return
        if not url.startswith("http"):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid YouTube URL starting with http")
            return
        # Warn if playlist URL
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

        self._extracting = True
        self.download_btn.setEnabled(False)
        self.download_btn.setText("Downloading…")
        self.yt_url_edit.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_edit.clear()
        try:
            fmt = self.quality_combo.currentData()
            self._api.download_youtube(url, fmt)
        except RuntimeError as e:
            QMessageBox.warning(self, "Error", str(e))
            self._reset_download_ui()

    def _on_yt_download_completed(self, path: str):
        self._video_path = path
        self.video_path_edit.setText(path)
        self.custom_title_edit.setText(Path(path).stem)
        self._log(f"Video downloaded: {path}")
        self._load_preview()
        self._extracting = False
        self.download_btn.setEnabled(True)
        self.download_btn.setText("Download")
        self.yt_url_edit.setEnabled(True)
        self.start_btn.setEnabled(True)

    def _reset_download_ui(self):
        self._extracting = False
        self.download_btn.setEnabled(True)
        self.download_btn.setText("Download")
        self.yt_url_edit.setEnabled(True)

    def _on_path_changed(self, path: str):
        valid = bool(path) and os.path.exists(path)
        self.start_btn.setEnabled(valid and not self._extracting)
        if valid and path != self._video_path:
            self._load_preview()

    def _load_preview(self):
        path = self.video_path_edit.text().strip()
        if not path or not os.path.exists(path):
            return
        try:
            # Close previous video if already open
            if self._api.get_video_info() is not None:
                self._api.close_video()
            info = self._api.open_video(path)
            self._video_path = path
            self._video_duration = info.duration
            self.seek_bar.set_duration(info.duration)
            self.seek_bar.set_start(0.0)
            self.seek_bar.set_end(info.duration)

            # Default output path
            if not self.output_path_edit.text().strip():
                default_pdf = str(Path(path).with_suffix('.pdf'))
                self.output_path_edit.setText(default_pdf)

            # Auto-populate PDF title from video filename
            if not self.custom_title_edit.text():
                self.custom_title_edit.setText(Path(path).stem)

            # Show frame 0 in crop tab, sync crop ratio from config
            default_ratio = self._api.get_config().get("default_crop_ratio", 0.35)
            self.crop_widget.set_ratio(default_ratio)
            self.crop_default_label.setText(f"Default: {int(default_ratio * 100)}%")
            png_bytes = self._api.read_frame_at(0.0)
            if png_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(png_bytes)
                self.crop_widget.set_frame(pixmap)

            self._log("Video loaded: " + path)
            self._log(f"Duration: {info.duration:.1f}s, FPS: {info.fps:.2f}, "
                      f"Resolution: {info.width}x{info.height}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open video:\n{e}")

    def _on_seek(self, ts: float):
        if ts < 0 or self._api.get_video_info() is None:
            return
        png_bytes = self._api.read_frame_at(ts)
        if png_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(png_bytes)
            self.crop_widget.set_frame(pixmap)

    def _start_extraction(self):
        video_path = self._video_path
        if not video_path or not os.path.exists(video_path):
            QMessageBox.warning(self, "Error", "Please select a valid video file.")
            return

        output_path = self.get_output_path()
        if not output_path:
            QMessageBox.warning(self, "Error", "Please set an output PDF path.")
            return

        # Apply config from ConfigTab (parent's sibling)
        main_win = self.window()
        if hasattr(main_win, 'config_tab'):
            main_win.config_tab.apply_to_api()

        # Get parameters from seek controls
        start_time = self.seek_bar.get_start()
        duration = self.seek_bar.get_end()
        no_ocr = (self._api.get_config().get("ocr_confidence_threshold", 40) == 0)

        self._extracting = True
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Extracting…")
        self.cancel_btn.setEnabled(True)
        self.browse_btn.setEnabled(False)
        self.yt_url_edit.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_edit.clear()

        self._api.start_extraction(
            video_path=video_path,
            no_ocr=no_ocr,
            start_time=start_time,
            duration=duration,
        )

    def _cancel_extraction(self):
        if self._extracting:
            self._api.cancel_extraction()

    def _set_crop_default(self):
        ratio = self.crop_widget.get_ratio()
        try:
            self._api.update_config({"default_crop_ratio": ratio})
            self.crop_default_label.setText(f"Default: {int(ratio * 100)}%")
            self._log(f"Crop default set to {int(ratio * 100)}%")
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))

    def on_completed(self, page_count: int):
        self._log(f"Extraction complete: {page_count} pages found")
        if page_count == 0:
            self._log("No pages detected. Skipping PDF generation.")
            self._reset_ui()
            return

        # Auto-generate PDF
        output_path = self.get_output_path()
        self._log(f"Generating PDF: {output_path}")
        title = self.custom_title_edit.text().strip() or None
        try:
            self._api.generate_pdf(output_path, title=title)
        except RuntimeError as e:
            QMessageBox.warning(self, "Error", str(e))
            self._reset_ui()

    def on_pdf_completed(self, page_count: int):
        output_path = self.get_output_path()
        self._log(f"PDF saved to: {output_path}")
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Success")
        msg.setText(f"PDF generated successfully!\n\n{output_path}")
        open_btn = msg.addButton("Open PDF", QMessageBox.ButtonRole.ActionRole)
        msg.addButton(QMessageBox.StandardButton.Ok)
        msg.exec()
        if msg.clickedButton() == open_btn:
            try:
                os.startfile(output_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open PDF:\n{e}")
        self._reset_ui()

    def on_cancelled(self):
        self._log("Extraction cancelled by user.")
        self._reset_ui()

    def on_error(self, message: str):
        self._log(f"[Error] {message}")
        if not self._extracting:
            QMessageBox.critical(self, "Error", message)
        self._reset_ui()

    def on_page_detected(self, _idx: int, _png_bytes: bytes):
        pass

    def on_progress(self, phase: str, percent: float, _detail: str):
        self.progress_bar.setValue(int(percent))

    def _reset_ui(self):
        self._extracting = False
        self.start_btn.setText("Start Extraction")
        self.start_btn.setEnabled(bool(self._video_path and os.path.exists(self._video_path)))
        self.cancel_btn.setEnabled(False)
        self.browse_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.download_btn.setText("Download")
        self.yt_url_edit.setEnabled(True)

    def _log(self, msg: str):
        self.log_edit.append(msg)


# ── Gallery Tab ──────────────────────────────────────────────────────

class GalleryTab(QWidget):
    def __init__(self, api: GuiApi, parent=None):
        super().__init__(parent)
        self._api = api

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.count_label = QLabel("Pages: 0")
        self.count_label.setObjectName("count")
        header.addWidget(self.count_label)
        header.addStretch()
        layout.addLayout(header)

        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListView.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(160, 120))
        self.list_widget.setGridSize(QSize(180, 150))
        self.list_widget.setWordWrap(True)
        self.list_widget.setSpacing(6)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list_widget.itemDoubleClicked.connect(self._show_preview)
        layout.addWidget(self.list_widget, 1)

        btn_row = QHBoxLayout()
        self.move_up_btn = QPushButton("▲ Move Up")
        self.move_up_btn.setObjectName("secondary")
        self.move_down_btn = QPushButton("▼ Move Down")
        self.move_down_btn.setObjectName("secondary")
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("danger")
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setObjectName("danger")
        btn_row.addWidget(self.move_up_btn)
        btn_row.addWidget(self.move_down_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.move_up_btn.clicked.connect(self._move_up)
        self.move_down_btn.clicked.connect(self._move_down)
        self.delete_btn.clicked.connect(self._delete)
        self.clear_btn.clicked.connect(self._clear_all)

        self.setEnabled(False)

    def refresh(self):
        self.list_widget.clear()
        count = self._api.get_page_count()
        self.count_label.setText(f"Pages: {count}")
        self.setEnabled(count > 0)

        for i in range(count):
            thumb_bytes = self._api.get_page_thumbnail(i)
            if thumb_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(thumb_bytes)
                icon = QIcon(pixmap)
                item = QListWidgetItem(icon, f"Page {i + 1}")
                item.setData(Qt.ItemDataRole.UserRole, i)
                item.setSizeHint(QSize(170, 140))
                self.list_widget.addItem(item)

    def _get_selected_index(self) -> Optional[int]:
        items = self.list_widget.selectedItems()
        if not items:
            QMessageBox.information(self, "Select a page",
                                    "Please select a page first.")
            return None
        return self.list_widget.row(items[0])

    def _move_up(self):
        idx = self._get_selected_index()
        if idx is None or idx == 0:
            return
        new_order = list(range(self._api.get_page_count()))
        new_order[idx], new_order[idx - 1] = new_order[idx - 1], new_order[idx]
        self._api.reorder_pages(new_order)
        self.refresh()
        self.list_widget.setCurrentRow(idx - 1)

    def _move_down(self):
        idx = self._get_selected_index()
        if idx is None or idx >= self._api.get_page_count() - 1:
            return
        new_order = list(range(self._api.get_page_count()))
        new_order[idx], new_order[idx + 1] = new_order[idx + 1], new_order[idx]
        self._api.reorder_pages(new_order)
        self.refresh()
        self.list_widget.setCurrentRow(idx + 1)

    def _delete(self):
        idx = self._get_selected_index()
        if idx is None:
            return
        self._api.remove_page(idx)
        self.refresh()

    def _clear_all(self):
        if self._api.get_page_count() == 0:
            return
        reply = QMessageBox.question(self, "Clear All Pages",
                                     "Remove all detected pages?",
                                     QMessageBox.StandardButton.Yes |
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._api.clear_pages()
            self.refresh()

    def _show_preview(self, item: QListWidgetItem):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None:
            return
        full_bytes = self._api.get_page_full(idx)
        if full_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(full_bytes)
            dialog = PagePreviewDialog(pixmap, f"Page {idx + 1}", self)
            dialog.exec()


# ── Export Tab ───────────────────────────────────────────────────────

class ExportTab(QWidget):
    def __init__(self, api: GuiApi, parent=None):
        super().__init__(parent)
        self._api = api

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Export")
        title.setObjectName("title")
        layout.addWidget(title)

        # Output path (read-only display; set via Extract tab)
        out_row = QHBoxLayout()
        out_label = QLabel("Output PDF:")
        out_label.setFixedWidth(80)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("output.pdf")
        self.output_edit.setReadOnly(True)
        out_row.addWidget(out_label)
        out_row.addWidget(self.output_edit, 1)
        layout.addLayout(out_row)

        self.regenerate_btn = QPushButton("Regenerate PDF")
        self.regenerate_btn.setEnabled(False)
        layout.addWidget(self.regenerate_btn)

        # Sandbox section
        layout.addWidget(QLabel(""))
        sandbox_label = QLabel("Previous Sessions")
        sandbox_label.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {INK};")
        layout.addWidget(sandbox_label)

        self.sandbox_combo = QComboBox()
        self.sandbox_combo.setMinimumHeight(32)
        layout.addWidget(self.sandbox_combo)

        sb_btn_row = QHBoxLayout()
        self.load_sb_btn = QPushButton("Load Pages")
        self.load_sb_btn.setObjectName("secondary")
        self.delete_sb_btn = QPushButton("Delete Sandbox")
        self.delete_sb_btn.setObjectName("danger")
        self.refresh_sb_btn = QPushButton("Refresh")
        self.refresh_sb_btn.setObjectName("secondary")
        sb_btn_row.addWidget(self.load_sb_btn)
        sb_btn_row.addWidget(self.delete_sb_btn)
        sb_btn_row.addWidget(self.refresh_sb_btn)
        sb_btn_row.addStretch()
        layout.addLayout(sb_btn_row)

        # Status
        self.status_label = QLabel("")
        self.status_label.setObjectName("muted")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Connections
        self.regenerate_btn.clicked.connect(self._regenerate)
        self.load_sb_btn.clicked.connect(self._load_sandbox)
        self.delete_sb_btn.clicked.connect(self._delete_sandbox)
        self.refresh_sb_btn.clicked.connect(self.refresh_sandboxes)

    def refresh_sandboxes(self):
        self.sandbox_combo.clear()
        try:
            sandboxes = self._api.list_sandboxes()
            for sb in sandboxes:
                label = f"{sb.video_name} ({sb.page_count} pages, {sb.created.strftime('%Y-%m-%d')})"
                self.sandbox_combo.addItem(label, sb.path)
            self._set_status(f"Found {len(sandboxes)} previous sessions.")
        except Exception as e:
            self._set_status(f"Error listing sandboxes: {e}")

    def set_output_path(self, path: str):
        self.output_edit.setText(path)

    def get_output_path(self) -> str:
        path = self.output_edit.text().strip()
        if not path:
            path = "score.pdf"
            self.output_edit.setText(path)
        return path

    def _regenerate(self):
        output = self.get_output_path()
        if self._api.get_page_count() == 0:
            QMessageBox.warning(self, "No Pages",
                                "No pages loaded. Load a sandbox or run extraction first.")
            return
        self.regenerate_btn.setEnabled(False)
        self.regenerate_btn.setText("Generating…")
        self._set_status(f"Generating PDF: {output}")
        try:
            self._api.generate_pdf(output)
        except RuntimeError as e:
            QMessageBox.warning(self, "Error", str(e))
            self.regenerate_btn.setEnabled(True)
            self.regenerate_btn.setText("Regenerate PDF")

    def _load_sandbox(self):
        path = self.sandbox_combo.currentData()
        if not path:
            QMessageBox.information(self, "Select Session",
                                    "Select a previous session from the list.")
            return
        try:
            count = self._api.load_sandbox(path)
            self._set_status(f"Loaded {count} pages from session.")
            self.regenerate_btn.setEnabled(True)

            # Switch parent's gallery tab to show loaded pages
            main_win = self.window()
            if hasattr(main_win, 'gallery_tab'):
                main_win.gallery_tab.refresh()
                main_win.tabs.setCurrentWidget(main_win.gallery_tab)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load sandbox:\n{e}")

    def _delete_sandbox(self):
        path = self.sandbox_combo.currentData()
        if not path:
            QMessageBox.information(self, "Select Session",
                                    "Select a previous session from the list.")
            return
        reply = QMessageBox.question(self, "Delete Sandbox",
                                     f"Delete this session permanently?\n\n{path}",
                                     QMessageBox.StandardButton.Yes |
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._api.delete_sandbox(path)
                self.refresh_sandboxes()
                self._set_status("Sandbox deleted.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not delete:\n{e}")

    def _set_status(self, msg: str):
        self.status_label.setText(msg)


# ── Main Window ──────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Score Extractor")
        self.setMinimumSize(960, 700)
        self.resize(1100, 780)
        self.setStyleSheet(STYLESHEET.replace("__CHECK_PLACEHOLDER__", CHECK_INDICATOR_PATH))

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

        # Header
        header = QLabel("Score Extractor")
        header.setObjectName("title")
        header.setStyleSheet(f"""
            font-size: 26px; font-weight: 700;
            color: {INK}; padding: 4px 0 8px 0;
            border-bottom: 2px solid {ACCENT};
        """)
        main_layout.addWidget(header)

        # Tabs (Config is last — Extract opens by default)
        self.tabs = QTabWidget()
        self.extract_tab = ExtractTab(self.api)
        self.gallery_tab = GalleryTab(self.api)
        self.export_tab = ExportTab(self.api)
        self.config_tab = ConfigTab(self.api)

        self.tabs.addTab(self.extract_tab, "Extract")
        self.tabs.addTab(self.gallery_tab, "Gallery")
        self.tabs.addTab(self.export_tab, "Export")
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

        # Refresh sandboxes and config when the respective tabs become visible
        QTimer.singleShot(200, self.export_tab.refresh_sandboxes)

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
            self.gallery_tab.refresh()
            self.export_tab.refresh_sandboxes()
        else:
            self.extract_tab.on_completed(page_count)
            self.gallery_tab.refresh()
            self.api.open_sandbox_folder()
            # Auto-generate PDF after extraction
            if page_count > 0:
                self._generating_pdf = True
            else:
                self.extract_tab._reset_ui()

    def _on_cancelled(self):
        self.extract_tab.on_cancelled()

    def _on_yt_downloaded(self, path: str):
        self.extract_tab._on_yt_download_completed(path)

    def _on_tab_changed(self, index: int):
        if index == 1:  # Gallery tab
            self.gallery_tab.refresh()
        elif index == 2:  # Export tab
            self.export_tab.set_output_path(self.extract_tab.get_output_path())
            self.export_tab.refresh_sandboxes()
        elif index == 3:  # Config tab
            self.config_tab.refresh_from_api()


# ── Entrypoint ───────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Score Extractor")

    global CHECK_INDICATOR_PATH
    CHECK_INDICATOR_PATH = _generate_check_pixmap()

    # Set app-wide font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
