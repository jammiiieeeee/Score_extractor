"""
PROTOTYPE — throwaway UI mockup.
Answer: "What should the Score Extractor main screen look like?"
3 radically different layouts, switch with ← → arrow keys.
Run: python prototype_ui.py
"""

import sys
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QLinearGradient
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit,
    QProgressBar, QFrame, QSizePolicy, QScrollArea, QCheckBox,
    QSlider, QDoubleSpinBox,
)

# ── Shared palette ──
BG      = "#161616"
SURFACE = "#1e1e1e"
SURFACE2= "#282828"
INK     = "#e8e8e8"
MUTED   = "#888888"
BRASS   = "#d4a843"
GREEN   = "#5aaa5a"
DANGER  = "#cc4444"
BORDER  = "#333333"

FONT = QFont("Segoe UI", 10)

STYLESHEET = f"""
QMainWindow, QWidget {{ background-color: {BG}; color: {INK}; font-family: "Segoe UI", sans-serif; font-size: 13px; }}
QLineEdit {{ background: #0d0d0d; border: 1px solid {BORDER}; border-radius: 6px; padding: 7px 12px; color: {INK}; }}
QLineEdit:focus {{ border-color: {BRASS}; }}
QPushButton {{ background: {BRASS}; color: {BG}; border: none; border-radius: 6px; padding: 8px 18px; font-weight: 700; }}
QPushButton:hover {{ background: "#e0b85a"; }}
QPushButton:disabled {{ background: {SURFACE2}; color: {MUTED}; }}
QPushButton#secondary {{ background: transparent; color: {INK}; border: 1px solid #444; }}
QPushButton#secondary:hover {{ background: {SURFACE2}; border-color: {BRASS}; }}
QPushButton#danger {{ background: transparent; color: {DANGER}; border: 1px solid {DANGER}; }}
QPushButton#danger:hover {{ background: {DANGER}; color: white; }}
QComboBox {{ background: #0d0d0d; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 12px; color: {INK}; }}
QProgressBar {{ background: #0d0d0d; border: 1px solid {BORDER}; border-radius: 6px; text-align: center; height: 22px; color: {INK}; }}
QProgressBar::chunk {{ background: {BRASS}; border-radius: 5px; }}
QTextEdit {{ background: #0d0d0d; border: 1px solid {BORDER}; border-radius: 6px; color: {INK}; font-family: Consolas, monospace; font-size: 12px; }}
QSlider::groove:horizontal {{ background: {SURFACE2}; height: 4px; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {BRASS}; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }}
QSlider::sub-page:horizontal {{ background: {BRASS}; border-radius: 2px; }}
"""


# ── Floating variant switcher (bar at bottom) ──

class VariantSwitcher(QWidget):
    def __init__(self, variants, parent=None):
        super().__init__(parent)
        self._variants = variants
        self._current = 0
        self.setFixedHeight(44)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: #222; border: 1px solid #444; border-radius: 22px;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)

        self.left_btn = QPushButton("<")
        self.left_btn.setFixedSize(32, 32)
        self.left_btn.setStyleSheet(f"background: {SURFACE2}; color: {INK}; border: none; border-radius: 16px; font-size: 16px;")
        self.left_btn.clicked.connect(self._prev)

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet(f"color: {BRASS}; font-weight: 600; font-size: 14px; background: transparent;")

        self.right_btn = QPushButton(">")
        self.right_btn.setFixedSize(32, 32)
        self.right_btn.setStyleSheet(f"background: {SURFACE2}; color: {INK}; border: none; border-radius: 16px; font-size: 16px;")
        self.right_btn.clicked.connect(self._next)

        layout.addWidget(self.left_btn)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.right_btn)
        layout.setSpacing(12)
        self._update_label()

    def _prev(self):
        self._current = (self._current - 1) % len(self._variants)
        self._update_label()
        self._emit()

    def _next(self):
        self._current = (self._current + 1) % len(self._variants)
        self._update_label()
        self._emit()

    def _update_label(self):
        k, n = self._variants[self._current]
        self.label.setText(f"{k} — {n}")

    def _emit(self):
        p = self.window()
        if p and hasattr(p, 'switch_variant'):
            p.switch_variant(self._current)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left:
            self._prev()
        elif event.key() == Qt.Key.Key_Right:
            self._next()
        else:
            super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
        QTimer.singleShot(0, self.setFocus)


# ═════════════════════════════════════════════════════════════════════
# VARIANT A — Dashboard
# Two-column: sidebar (video source + settings) + main (preview + controls)
# ═════════════════════════════════════════════════════════════════════

class VariantA(QWidget):
    NAME = "Dashboard"
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Sidebar ──
        sidebar = QWidget()
        sidebar.setFixedWidth(300)
        sidebar.setStyleSheet(f"background: {SURFACE};")
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 20, 16, 20)
        side.setSpacing(14)

        side_title = QLabel("Video Source")
        side_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {BRASS}; background: transparent;")
        side.addWidget(side_title)

        yt_label = QLabel("YouTube URL")
        yt_label.setStyleSheet(f"font-size: 12px; color: {MUTED}; background: transparent;")
        side.addWidget(yt_label)
        side.addWidget(QLineEdit("https://youtube.com/watch?v=..."))
        side.addWidget(QPushButton("Download"))

        side.addWidget(QLabel("or"))
        lbl = QLabel("Browse local video file")
        lbl.setStyleSheet(f"color: {BRASS}; background: transparent; text-decoration: underline; font-size: 12px;")
        side.addWidget(lbl)

        side.addSpacing(16)

        side_title2 = QLabel("Score")
        side_title2.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {BRASS}; background: transparent;")
        side.addWidget(side_title2)

        side.addWidget(QLabel("Name"))
        n = QLineEdit("My Piano Score")
        side.addWidget(n)
        side.addWidget(QLabel("Save to"))
        s = QLineEdit("C:\\Users\\...\\output")
        s.setReadOnly(True)
        side.addWidget(s)

        side.addStretch()

        side_footer = QLabel("v1.0.0")
        side_footer.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
        side.addWidget(side_footer)

        outer.addWidget(sidebar)

        # ── Main area ──
        main = QWidget()
        m = QVBoxLayout(main)
        m.setContentsMargins(20, 20, 20, 20)
        m.setSpacing(12)

        header = QLabel("My Piano Score")
        header.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {INK}; background: transparent;")
        m.addWidget(header)

        # Preview placeholder
        preview = QLabel()
        preview.setMinimumSize(400, 250)
        preview.setStyleSheet(f"background: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 8px;")
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setText("  crop preview  ")
        preview.setStyleSheet(f"background: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 8px; color: {MUTED}; font-size: 14px;")
        m.addWidget(preview, 1)

        # Seek bar
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(0, 100)
        sl.setValue(30)
        m.addWidget(sl)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Crop ratio:"))
        sp = QDoubleSpinBox()
        sp.setValue(0.35)
        sp.setFixedWidth(80)
        ctrl.addWidget(sp)
        ctrl.addStretch()
        ctrl.addWidget(QPushButton("Set as Default"))
        m.addLayout(ctrl)

        # Progress + log
        pb = QProgressBar()
        pb.setValue(0)
        m.addWidget(pb)

        log = QTextEdit()
        log.setMaximumHeight(80)
        log.setPlainText("Ready. Paste a URL or browse a file to start.")
        m.addWidget(log)

        # Action bar
        act = QHBoxLayout()
        act.addStretch()
        start = QPushButton("Start Extraction")
        start.setFixedWidth(180)
        act.addWidget(start)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("danger")
        act.addWidget(cancel)
        m.addLayout(act)

        outer.addWidget(main, 1)


# ═════════════════════════════════════════════════════════════════════
# VARIANT B — Wizard
# Step-by-step: one screen at a time, progress indicator, Back/Next
# ═════════════════════════════════════════════════════════════════════

class VariantB(QWidget):
    NAME = "Wizard"
    STEP_LABELS = ["Video", "Name", "Crop", "Extract"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._step = 0
        self._step_widgets = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 20, 40, 20)
        outer.setSpacing(16)

        # Step indicator
        self.step_bar = QWidget()
        self.step_bar.setFixedHeight(60)
        self.step_bar.setStyleSheet("background: transparent;")
        bar_layout = QHBoxLayout(self.step_bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        self._step_dots = []
        for i, label in enumerate(self.STEP_LABELS):
            dot = QLabel(f"  {i+1}  ")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setFixedSize(40, 40)
            dot.setStyleSheet(
                f"background: {BRASS}; color: {BG}; border-radius: 20px; font-weight: 700; font-size: 16px;"
                if i == 0 else
                f"background: {SURFACE2}; color: {MUTED}; border-radius: 20px; font-weight: 600; font-size: 16px;"
            )
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {BRASS if i == 0 else MUTED}; font-weight: 600; font-size: 13px; background: transparent;")
            col = QVBoxLayout()
            col.setSpacing(4)
            col.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(dot, alignment=Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)
            self._step_dots.append((dot, lbl))
            bar_layout.addLayout(col)
            if i < len(self.STEP_LABELS) - 1:
                line = QLabel("────")
                line.setStyleSheet(f"color: {BORDER}; background: transparent; font-size: 14px;")
                bar_layout.addWidget(line)
        bar_layout.addStretch()
        outer.addWidget(self.step_bar)

        # Step content area
        self.stacked = QWidget()
        self.stacked.setStyleSheet(f"background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;")
        self._build_step(0, self.stacked)
        outer.addWidget(self.stacked, 1)

        # Navigation
        nav = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.setObjectName("secondary")
        self.back_btn.setEnabled(False)
        nav.addWidget(self.back_btn)

        nav.addStretch()
        self.step_title = QLabel("Step 1: Get a video")
        self.step_title.setStyleSheet(f"color: {MUTED}; font-size: 14px; background: transparent;")
        nav.addWidget(self.step_title)
        nav.addStretch()

        self.next_btn = QPushButton("Next")
        self.next_btn.setFixedWidth(120)
        nav.addWidget(self.next_btn)
        outer.addLayout(nav)

        # Connections
        self.back_btn.clicked.connect(self._go_back)
        self.next_btn.clicked.connect(self._go_next)

    def _build_step(self, idx, container):
        old = container.layout()
        if old:
            QWidget().setLayout(old)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(14)

        if idx == 0:
            t = QLabel("Get a Video")
            t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {INK}; background: transparent;")
            layout.addWidget(t)
            d = QLabel("Paste a YouTube URL or browse a local file.")
            d.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
            layout.addWidget(d)
            layout.addSpacing(8)
            layout.addWidget(QLabel("YouTube URL"))
            u = QLineEdit()
            u.setPlaceholderText("https://youtube.com/watch?v=...")
            layout.addWidget(u)
            r = QHBoxLayout()
            d = QPushButton("Download")
            r.addWidget(d)
            r.addWidget(QLabel("or"))
            b = QPushButton("Browse file...")
            b.setObjectName("secondary")
            r.addWidget(b)
            r.addStretch()
            layout.addLayout(r)

        elif idx == 1:
            t = QLabel("Name Your Score")
            t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {INK}; background: transparent;")
            layout.addWidget(t)
            d = QLabel("Give it a name and choose where to save it.")
            d.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
            layout.addWidget(d)
            layout.addSpacing(8)
            layout.addWidget(QLabel("Score name"))
            n = QLineEdit("My Piano Score")
            layout.addWidget(n)
            layout.addWidget(QLabel("Save location"))
            s = QLineEdit()
            s.setText("C:\\Users\\...\\output")
            s.setReadOnly(True)
            layout.addWidget(s)

        elif idx == 2:
            t = QLabel("Adjust Crop")
            t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {INK}; background: transparent;")
            layout.addWidget(t)
            d = QLabel("Drag the crop line to trim the top margin.")
            d.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
            layout.addWidget(d)
            layout.addSpacing(8)

            prev = QLabel()
            prev.setMinimumHeight(200)
            prev.setStyleSheet(f"background: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 8px;")
            prev.setAlignment(Qt.AlignmentFlag.AlignCenter)
            prev.setText("  [preview with adjustable crop line]  ")
            prev.setStyleSheet(f"background: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 8px; color: {MUTED};")
            layout.addWidget(prev, 1)

            cr = QHBoxLayout()
            cr.addWidget(QLabel("Crop ratio:"))
            sp = QDoubleSpinBox()
            sp.setValue(0.35)
            sp.setFixedWidth(80)
            cr.addWidget(sp)
            cr.addStretch()
            cr.addWidget(QPushButton("Set as Default"))
            layout.addLayout(cr)

            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(0, 100)
            sl.setValue(35)
            layout.addWidget(sl)

        elif idx == 3:
            t = QLabel("Extract")
            t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {INK}; background: transparent;")
            layout.addWidget(t)
            d = QLabel("Everything is set. Hit Extract to start.")
            d.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
            layout.addWidget(d)
            layout.addSpacing(8)

            summary = QFrame()
            summary.setStyleSheet(f"background: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 8px;")
            s = QVBoxLayout(summary)
            s.setSpacing(6)
            for row in [("Video", "my_piano_video.mp4"), ("Score name", "My Piano Score"), ("Save to", "C:\\Users\\...\\output\\My Piano Score"), ("Crop ratio", "35%"), ("OCR", "Enabled")]:
                r = QHBoxLayout()
                r.addWidget(QLabel(row[0]))
                r.addStretch()
                v = QLabel(row[1])
                v.setStyleSheet(f"color: {BRASS}; font-weight: 600; background: transparent;")
                r.addWidget(v)
                s.addLayout(r)
            layout.addWidget(summary, 1)

            pb = QProgressBar()
            pb.setValue(0)
            layout.addWidget(pb)

            go = QPushButton("Start Extraction")
            go.setFixedWidth(200)
            layout.addWidget(go, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

    def _go_back(self):
        if self._step > 0:
            self._step -= 1
            self._update()

    def _go_next(self):
        if self._step < len(self.STEP_LABELS) - 1:
            self._step += 1
            self._update()

    def _update(self):
        self._build_step(self._step, self.stacked)
        self.back_btn.setEnabled(self._step > 0)
        self.next_btn.setText("Finish" if self._step == len(self.STEP_LABELS) - 1 else "Next")
        self.step_title.setText(f"Step {self._step + 1}: {self.STEP_LABELS[self._step]}")
        for i, (dot, lbl) in enumerate(self._step_dots):
            active = i == self._step
            done = i < self._step
            if active:
                dot.setStyleSheet(f"background: {BRASS}; color: {BG}; border-radius: 20px; font-weight: 700; font-size: 16px;")
                lbl.setStyleSheet(f"color: {BRASS}; font-weight: 600; font-size: 13px; background: transparent;")
            elif done:
                dot.setStyleSheet(f"background: {GREEN}; color: {BG}; border-radius: 20px; font-weight: 700; font-size: 16px;")
                lbl.setStyleSheet(f"color: {GREEN}; font-weight: 600; font-size: 13px; background: transparent;")
            else:
                dot.setStyleSheet(f"background: {SURFACE2}; color: {MUTED}; border-radius: 20px; font-weight: 600; font-size: 16px;")
                lbl.setStyleSheet(f"color: {MUTED}; font-weight: 600; font-size: 13px; background: transparent;")


# ═════════════════════════════════════════════════════════════════════
# VARIANT C — Terminal / Pro
# Monospace, compact, keyboard-first, maximum preview
# ═════════════════════════════════════════════════════════════════════

class VariantC(QWidget):
    NAME = "Terminal"
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: #0d0d0d;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(6)

        # Title bar — minimal
        title = QLabel("score-extractor  v1.0.0")
        title.setStyleSheet("color: #555; font-family: Consolas; font-size: 11px; background: transparent;")
        outer.addWidget(title)

        # Prompt-style input
        prompt_row = QHBoxLayout()
        dollar = QLabel("$")
        dollar.setStyleSheet("color: #5aaa5a; font-family: Consolas; font-size: 14px; font-weight: 700; background: transparent;")
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("yt https://youtube.com/watch?v=...  or  file path/to/video.mp4")
        self.input_field.setStyleSheet(
            f"background: #0d0d0d; border: none; border-bottom: 1px solid #333; "
            f"color: {INK}; font-family: Consolas; font-size: 14px; padding: 4px 0; "
            f"selection-background-color: {BRASS};"
        )
        prompt_row.addWidget(dollar)
        prompt_row.addWidget(self.input_field, 1)
        outer.addLayout(prompt_row)

        # Score / save — compact inline
        meta = QHBoxLayout()
        meta.setSpacing(16)
        for label, default in [("score", "my_piano_score"), ("save", "~/output")]:
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("color: #555; font-family: Consolas; font-size: 12px; background: transparent;")
            val = QLineEdit(default)
            val.setStyleSheet(
                f"background: transparent; border: none; border-bottom: 1px dotted #333; "
                f"color: {MUTED}; font-family: Consolas; font-size: 12px; padding: 2px 0;"
            )
            meta.addWidget(lbl)
            meta.addWidget(val)
        meta.addStretch()
        outer.addLayout(meta)

        # Large terminal-style preview placeholder
        preview = QLabel()
        preview.setMinimumHeight(300)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setText("  [ crop preview — press arrow keys or drag crop line ]  ")
        preview.setStyleSheet(
            f"background: #0a0a0a; border: 1px solid #222; border-radius: 4px; "
            f"color: #444; font-family: Consolas; font-size: 13px;"
        )
        outer.addWidget(preview, 1)

        # Slider — terminal style
        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel("<"))
        slider_label = QLabel("0:12.5 / 3:24.0")
        slider_label.setStyleSheet("color: #555; font-family: Consolas; font-size: 11px; background: transparent;")
        slider_row.addWidget(slider_label)
        slider_row.addStretch()
        slider_row.addWidget(QLabel(">"))
        outer.addLayout(slider_row)

        # Status bar — terminal-style
        status = QHBoxLayout()
        status.setSpacing(20)
        items = [("crop", "35%"), ("pages", "0"), ("ocr", "ON"), ("ready", "")]
        for k, v in items:
            lbl = QLabel(f"{k}: {v}" if v else k)
            lbl.setStyleSheet(f"color: {'#5aaa5a' if k == 'ready' else '#555'}; font-family: Consolas; font-size: 11px; background: transparent;")
            status.addWidget(lbl)
        status.addStretch()
        outer.addLayout(status)

        # Cmd line
        cmd = QHBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("extract | regenerate | open | config | help")
        self.cmd_input.setStyleSheet(
            f"background: #0d0d0d; border: 1px solid #222; border-radius: 0; "
            f"color: {INK}; font-family: Consolas; font-size: 12px; padding: 4px 8px;"
        )
        cmd.addWidget(QLabel(">"))
        cmd.addWidget(self.cmd_input, 1)
        cmd.addWidget(QPushButton("run"))
        outer.addLayout(cmd)


# ═════════════════════════════════════════════════════════════════════
# VARIANT D — Media Player
# Chrome-less, video fills the window, controls float as overlays
# ═════════════════════════════════════════════════════════════════════

class VariantD(QWidget):
    NAME = "Media Player"
    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Video fills everything
        self.video_area = QWidget()
        self.video_area.setStyleSheet(f"background: #080808;")
        va = QVBoxLayout(self.video_area)
        va.setContentsMargins(0, 0, 0, 0)

        # Center hint
        hint = QLabel("video preview")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"color: #333; font-size: 16px; background: transparent;")
        va.addWidget(hint)

        # Float controls on top via overlay stack
        outer.addWidget(self.video_area, 1)

        # ── Overlay: top bar (score name + save) ──
        top_overlay = QWidget()
        top_overlay.setStyleSheet(f"background: rgba(0,0,0,0.65);")
        top = QHBoxLayout(top_overlay)
        top.setContentsMargins(14, 10, 14, 10)
        n = QLineEdit("My Piano Score")
        n.setStyleSheet(f"background: transparent; border: none; color: white; font-size: 18px; font-weight: 700; padding: 0;")
        top.addWidget(n)
        top.addStretch()
        s_label = QLabel("save: ~/output")
        s_label.setStyleSheet(f"color: rgba(255,255,255,0.5); font-size: 11px; background: transparent;")
        top.addWidget(s_label)
        outer.addWidget(top_overlay)

        # ── Overlay: bottom controls ──
        bottom = QWidget()
        bottom.setStyleSheet(f"background: rgba(0,0,0,0.7);")
        b = QVBoxLayout(bottom)
        b.setContentsMargins(14, 8, 14, 8)
        b.setSpacing(6)

        # Seek bar
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(0, 100)
        sl.setValue(25)
        sl.setStyleSheet("""
            QSlider::groove:horizontal { background: rgba(255,255,255,0.2); height: 3px; border-radius: 1px; }
            QSlider::handle:horizontal { background: #d4a843; width: 12px; height: 12px; margin: -5px 0; border-radius: 6px; }
            QSlider::sub-page:horizontal { background: #d4a843; border-radius: 1px; }
        """)
        b.addWidget(sl)

        # Controls row
        cr = QHBoxLayout()
        cr.setSpacing(12)
        cr.addWidget(QLabel("0:12.5"))
        cr.addStretch()

        crop_lbl = QLabel("crop")
        crop_lbl.setStyleSheet(f"color: rgba(255,255,255,0.6); font-size: 11px; background: transparent;")
        cr.addWidget(crop_lbl)
        sp = QDoubleSpinBox()
        sp.setValue(0.35)
        sp.setFixedWidth(70)
        sp.setStyleSheet(f"background: rgba(255,255,255,0.1); border: none; color: white; border-radius: 4px; padding: 2px 6px;")
        cr.addWidget(sp)
        cr.addStretch()

        dl = QPushButton("Download")
        dl.setObjectName("secondary")
        dl.setStyleSheet(dl.styleSheet() + "QPushButton { color: white; border: 1px solid rgba(255,255,255,0.3); padding: 6px 14px; background: transparent; }")
        cr.addWidget(dl)
        ex = QPushButton("Extract")
        ex.setStyleSheet(f"background: {BRASS}; color: {BG}; border: none; border-radius: 6px; padding: 6px 20px; font-weight: 700;")
        cr.addWidget(ex)
        b.addLayout(cr)

        outer.addWidget(bottom)


# ═════════════════════════════════════════════════════════════════════
# VARIANT E — Project Manager
# Two-panel: sidebar lists scores/videos, right shows details
# ═════════════════════════════════════════════════════════════════════

class VariantE(QWidget):
    NAME = "Project Manager"
    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Left panel ──
        left = QWidget()
        left.setFixedWidth(280)
        left.setStyleSheet(f"background: {SURFACE};")
        l = QVBoxLayout(left)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)

        # Scores header with count
        h1_row = QWidget()
        h1_row.setStyleSheet("background: transparent;")
        h1r = QHBoxLayout(h1_row)
        h1r.setContentsMargins(14, 12, 14, 4)
        h1 = QLabel("Scores")
        h1.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {MUTED}; background: transparent; letter-spacing: 1.5px; text-transform: uppercase;")
        h1r.addWidget(h1)
        h1r.addStretch()
        h1c = QLabel("5")
        h1c.setStyleSheet(f"font-size: 10px; color: {MUTED}; background: {SURFACE2}; border-radius: 8px; padding: 1px 6px;")
        h1r.addWidget(h1c)
        l.addWidget(h1_row)

        # Search
        search = QLineEdit()
        search.setPlaceholderText("Search scores…")
        search.setStyleSheet(
            f"background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; "
            f"color: {MUTED}; font-size: 12px; padding: 6px 10px; margin: 4px 14px 8px;"
        )
        l.addWidget(search)

        score_items = [
            ("Bach_Prelude_1", 14, True, "done"),
            ("Mozart_K545", 8, False, "done"),
            ("My_Own_Composition", 22, False, "progress"),
            ("Chopin_Nocturne", 12, False, "pending"),
            ("Scale_Exercises", 5, False, "done"),
        ]
        state_styles = {
            "done":   f"color: {GREEN}; font-size: 9px; background: transparent;",
            "progress": f"color: {BRASS}; font-size: 9px; background: transparent;",
            "pending": f"color: #555; font-size: 9px; background: transparent;",
        }
        state_icons = {"done": "✔", "progress": "◌", "pending": "○"}
        for name, pages, selected, state in score_items:
            item = QWidget()
            item.setStyleSheet(f"background: {'transparent' if not selected else SURFACE2}; border-left: 2px solid {BRASS if selected else 'transparent'};")
            row = QHBoxLayout(item)
            row.setContentsMargins(14, 8, 14, 8)
            state_lbl = QLabel(state_icons[state])
            state_lbl.setStyleSheet(state_styles[state])
            state_lbl.setFixedWidth(14)
            row.addWidget(state_lbl)
            lbl = QLabel(name)
            lbl.setStyleSheet(f"color: {INK}; font-size: 13px; font-weight: {'700' if selected else '400'}; background: transparent;")
            row.addWidget(lbl)
            row.addStretch()
            pc = QLabel(f"{pages} pp")
            pc.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
            row.addWidget(pc)
            l.addWidget(item)

        sep1 = QWidget()
        sep1.setFixedHeight(1)
        sep1.setStyleSheet(f"background: {BORDER};")
        l.addWidget(sep1)

        # Videos header with count
        h2_row = QWidget()
        h2_row.setStyleSheet("background: transparent;")
        h2r = QHBoxLayout(h2_row)
        h2r.setContentsMargins(14, 12, 14, 4)
        h2 = QLabel("Videos in Bach_Prelude_1")
        h2.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {MUTED}; background: transparent; letter-spacing: 1.5px; text-transform: uppercase;")
        h2r.addWidget(h2)
        h2r.addStretch()
        h2c = QLabel("3")
        h2c.setStyleSheet(f"font-size: 10px; color: {MUTED}; background: {SURFACE2}; border-radius: 8px; padding: 1px 6px;")
        h2r.addWidget(h2c)
        l.addWidget(h2_row)

        video_names = [
            ("recital_2024.mp4", True),
            ("lesson_week3.mkv", False),
            ("practice_session.mov", False),
        ]
        for name, active in video_names:
            item = QWidget()
            item.setStyleSheet(f"background: {SURFACE2 if active else 'transparent'}; border-left: 2px solid {BRASS if active else 'transparent'};")
            row = QHBoxLayout(item)
            row.setContentsMargins(14, 7, 14, 7)
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {BRASS}; font-size: 8px; background: transparent;")
            dot.setFixedWidth(12)
            row.addWidget(dot)
            lbl = QLabel(name)
            lbl.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
            row.addWidget(lbl)
            l.addWidget(item)

        l.addStretch()

        # Bottom: new score button
        new_btn = QPushButton("+ New Score")
        new_btn.setObjectName("secondary")
        new_btn.setStyleSheet(new_btn.styleSheet() + "QPushButton { border: 1px dashed #555; padding: 10px; font-size: 13px; margin: 8px 12px; }")
        l.addWidget(new_btn)

        outer.addWidget(left)

        # ── Right panel (with fixed bottom bar) ──
        right_container = QWidget()
        right_stack = QVBoxLayout(right_container)
        right_stack.setContentsMargins(0, 0, 0, 0)
        right_stack.setSpacing(0)

        # Scrollable content area
        right = QWidget()
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setWidget(right)
        right_scroll.setStyleSheet(f"QScrollArea {{ background: transparent; border: none; }} QScrollBar:vertical {{ width: 6px; background: transparent; }} QScrollBar::handle:vertical {{ background: {SURFACE2}; border-radius: 3px; min-height: 40px; }} QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}")
        right_stack.addWidget(right_scroll, 1)

        r = QVBoxLayout(right)
        r.setContentsMargins(24, 24, 24, 16)
        r.setSpacing(22)

        # Editable score name
        title = QLineEdit("Bach_Prelude_1")
        title.setStyleSheet(
            f"background: transparent; border: none; border-bottom: 2px solid {BRASS}; "
            f"color: {INK}; font-size: 24px; font-weight: 700; padding: 4px 0; max-width: 320px;"
        )
        r.addWidget(title)

        # ── Config card ──
        config_card = QFrame()
        config_card.setStyleSheet(f"background: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 10px;")
        cc = QHBoxLayout(config_card)
        cc.setContentsMargins(18, 14, 18, 14)
        cc.setSpacing(32)

        config_fields = [
            ("Pages", QLabel, "14"),
            ("Crop %", QDoubleSpinBox, 0.35),
            ("OCR", QCheckBox, True),
            ("Created", QLabel, "2024-06-15"),
        ]
        for k, cls, val in config_fields:
            col = QVBoxLayout()
            col.setSpacing(4)
            label = QLabel(k)
            label.setStyleSheet(f"color: {MUTED}; font-size: 9px; text-transform: uppercase; background: transparent; letter-spacing: 1px;")
            col.addWidget(label)
            if cls is QLabel:
                w = QLabel(str(val))
                w.setStyleSheet(f"color: {INK}; font-size: 15px; font-weight: 600; background: transparent;")
            elif cls is QDoubleSpinBox:
                w = QDoubleSpinBox()
                w.setValue(val)
                w.setRange(0.0, 1.0)
                w.setSingleStep(0.05)
                w.setFixedWidth(88)
                w.setStyleSheet(
                    f"background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 5px; "
                    f"color: {INK}; font-size: 14px; font-weight: 600; padding: 3px 6px;"
                )
            elif cls is QCheckBox:
                w = QCheckBox()
                w.setChecked(val)
                w.setStyleSheet(f"color: {INK}; font-size: 15px; background: transparent;")
            col.addWidget(w)
            cc.addLayout(col)
        cc.addStretch()
        r.addWidget(config_card)

        # ── Import section (move up: configure → acquire → extract) ──
        import_card = QFrame()
        import_card.setStyleSheet(f"background: {SURFACE2}; border: 1px dashed {BRASS}80; border-radius: 10px;")
        ic = QVBoxLayout(import_card)
        ic.setContentsMargins(18, 14, 18, 14)
        ic.setSpacing(10)

        ic_top = QHBoxLayout()
        import_title = QLabel("Import from video")
        import_title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {INK}; background: transparent;")
        ic_top.addWidget(import_title)
        ic_top.addStretch()
        ic.addLayout(ic_top)

        import_row = QHBoxLayout()
        import_row.setSpacing(8)
        u = QLineEdit()
        u.setPlaceholderText("YouTube URL or file path...")
        u.setStyleSheet(
            f"background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; "
            f"color: {INK}; font-size: 13px; padding: 8px 12px;"
        )
        import_row.addWidget(u, 1)
        dl_btn = QPushButton("Download")
        dl_btn.setStyleSheet(
            f"background: transparent; color: {BRASS}; border: 1px solid {BRASS}; border-radius: 6px; "
            f"padding: 8px 18px; font-weight: 700; font-size: 12px;"
        )
        import_row.addWidget(dl_btn)
        b = QPushButton("Browse...")
        b.setObjectName("secondary")
        import_row.addWidget(b)
        ic.addLayout(import_row)

        # Import feedback area
        import_status = QFrame()
        import_status.setStyleSheet(f"background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px;")
        is_ = QHBoxLayout(import_status)
        is_.setContentsMargins(12, 6, 12, 6)
        is_icon = QLabel("✔")
        is_icon.setStyleSheet(f"color: {GREEN}; font-size: 11px; background: transparent;")
        is_.addWidget(is_icon)
        is_text = QLabel("recital_2024.mp4 loaded from file  ·  3 page changes detected")
        is_text.setStyleSheet(f"color: {INK}; font-size: 11px; background: transparent;")
        is_.addWidget(is_text, 1)
        is_status = QLabel("ready")
        is_status.setStyleSheet(f"color: {BG}; background: {GREEN}; font-size: 9px; font-weight: 700; border-radius: 8px; padding: 1px 8px; letter-spacing: 1px; text-transform: uppercase;")
        is_.addWidget(is_status)
        ic.addWidget(import_status)
        r.addWidget(import_card)

        # ── Extraction action card (review + extract) ──
        action_card = QFrame()
        action_card.setStyleSheet(f"background: {SURFACE2}; border: 1px solid {BRASS}80; border-radius: 10px;")
        ac = QHBoxLayout(action_card)
        ac.setContentsMargins(18, 14, 18, 14)
        ac.setSpacing(14)

        ac_icon = QLabel("▶")
        ac_icon.setStyleSheet(f"color: {BRASS}; font-size: 18px; background: transparent;")
        ac.addWidget(ac_icon)

        ac_info = QVBoxLayout()
        ac_info.setSpacing(2)
        ac_title = QLabel("Ready to extract")
        ac_title.setStyleSheet(f"color: {INK}; font-size: 14px; font-weight: 600; background: transparent;")
        ac_info.addWidget(ac_title)
        ac_sub = QLabel("3 page changes detected · current segment: recital_2024.mp4 (0:12 — 3:24)")
        ac_sub.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
        ac_info.addWidget(ac_sub)
        ac.addLayout(ac_info, 1)

        extract_btn = QPushButton("Start Extraction")
        extract_btn.setStyleSheet(
            f"background: {BRASS}; color: {BG}; border: none; border-radius: 8px; "
            f"padding: 10px 32px; font-weight: 700; font-size: 14px;"
        )
        ac.addWidget(extract_btn)
        r.addWidget(action_card)

        # ── Preview card (review before locating) ──
        prev_card = QFrame()
        prev_card.setStyleSheet(f"background: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 10px;")
        pv = QVBoxLayout(prev_card)
        pv.setContentsMargins(18, 14, 18, 14)
        pv.setSpacing(8)

        prev_header_row = QHBoxLayout()
        prev_header = QLabel("Page Preview")
        prev_header.setStyleSheet(f"color: {MUTED}; font-size: 9px; font-weight: 700; text-transform: uppercase; background: transparent; letter-spacing: 1px;")
        prev_header_row.addWidget(prev_header)
        prev_header_row.addStretch()
        prev_page = QLabel("Page 3 of 14")
        prev_page.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
        prev_header_row.addWidget(prev_page)
        pv.addLayout(prev_header_row)

        prev = QLabel()
        prev.setMinimumHeight(200)
        prev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prev.setText("  [ page preview ]  ")
        prev.setStyleSheet(f"background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; color: {MUTED}; font-size: 14px;")
        pv.addWidget(prev, 1)

        prev_nav = QHBoxLayout()
        prev_nav.setSpacing(8)
        prev_prev = QPushButton("◀ Prev")
        prev_prev.setObjectName("secondary")
        prev_prev.setStyleSheet(prev_prev.styleSheet() + "QPushButton { padding: 4px 12px; font-size: 11px; }")
        prev_nav.addWidget(prev_prev)
        prev_nav.addStretch()
        prev_thumbnails = QLabel("◼ ◼ ◼ ◼ ◼ ◼ ◼ ◼ ◼ ◼ ◼ ◼ ◼ ◼")
        prev_thumbnails.setStyleSheet(f"color: #444; font-size: 10px; background: transparent;letter-spacing: 3px;")
        prev_nav.addWidget(prev_thumbnails)
        prev_nav.addStretch()
        prev_next = QPushButton("Next ▶")
        prev_next.setObjectName("secondary")
        prev_next.setStyleSheet(prev_next.styleSheet() + "QPushButton { padding: 4px 12px; font-size: 11px; }")
        prev_nav.addWidget(prev_next)
        pv.addLayout(prev_nav)
        r.addWidget(prev_card, 1)

        # ── Project location card ──
        project_group = QFrame()
        project_group.setStyleSheet(f"background: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 10px;")
        pg = QVBoxLayout(project_group)
        pg.setContentsMargins(18, 14, 18, 14)
        pg.setSpacing(10)

        loc_header_row = QHBoxLayout()
        loc_header = QLabel("Project Location")
        loc_header.setStyleSheet(f"color: {MUTED}; font-size: 9px; font-weight: 700; text-transform: uppercase; background: transparent; letter-spacing: 1px;")
        loc_header_row.addWidget(loc_header)
        loc_header_row.addStretch()
        pg.addLayout(loc_header_row)

        loc_path = QHBoxLayout()
        loc_path.setSpacing(8)
        path_field = QLineEdit("C:/Users/me/Score_extractor/output/Bach_Prelude_1")
        path_field.setReadOnly(True)
        path_field.setStyleSheet(
            f"background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 5px; "
            f"color: {MUTED}; font-size: 12px; padding: 6px 10px;"
        )
        loc_path.addWidget(path_field, 1)

        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("secondary")
        browse_btn.setFixedWidth(80)
        loc_path.addWidget(browse_btn)
        pg.addLayout(loc_path)

        loc_actions = QHBoxLayout()
        loc_actions.setSpacing(10)

        config_hint = QLabel("score.json · crop.cfg · ocr.txt")
        config_hint.setStyleSheet(f"color: #666; font-size: 11px; background: transparent;")
        loc_actions.addWidget(config_hint)
        loc_actions.addStretch()

        open_btn = QPushButton("Open Folder")
        open_btn.setObjectName("secondary")
        loc_actions.addWidget(open_btn)

        regen_btn = QPushButton("⟳ Regenerate")
        regen_btn.setObjectName("secondary")
        loc_actions.addWidget(regen_btn)

        pg.addLayout(loc_actions)
        r.addWidget(project_group)

        # Delete row
        del_row = QHBoxLayout()
        del_row.addStretch()
        del_btn = QPushButton("Delete Project")
        del_btn.setObjectName("danger")
        del_btn.setStyleSheet(del_btn.styleSheet() + "QPushButton { padding: 6px 14px; font-size: 12px; }")
        del_row.addWidget(del_btn)
        r.addLayout(del_row)

        # ── Fixed bottom bar: status only ──
        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(52)
        bottom_bar.setStyleSheet(f"background: {SURFACE}; border-top: 1px solid {BORDER};")
        bb = QHBoxLayout(bottom_bar)
        bb.setContentsMargins(24, 0, 24, 0)
        bb.setSpacing(10)

        status_dot = QLabel("●")
        status_dot.setStyleSheet(f"color: {GREEN}; font-size: 10px; background: transparent;")
        bb.addWidget(status_dot)

        status_msg = QLabel("Bach_Prelude_1  ·  3 videos, 14 pages  ·  Last extracted 2024-06-15")
        status_msg.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
        bb.addWidget(status_msg, 1)

        status_meta = QLabel("PDF: output/Bach_Prelude_1.pdf")
        status_meta.setStyleSheet(f"color: #555; font-size: 11px; background: transparent;")
        bb.addWidget(status_meta)

        right_stack.addWidget(bottom_bar)

        outer.addWidget(right_container, 1)


# ═════════════════════════════════════════════════════════════════════
# VARIANT F — Timeline Editor
# Preview on top, waveform/timeline on bottom with detected page markers
# ═════════════════════════════════════════════════════════════════════

class VariantF(QWidget):
    NAME = "Timeline Editor"
    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Top: preview ──
        preview_area = QWidget()
        preview_area.setStyleSheet(f"background: {SURFACE};")
        pa = QVBoxLayout(preview_area)
        pa.setContentsMargins(16, 16, 16, 12)

        header = QLabel("recital_2024.mp4")
        header.setStyleSheet(f"font-size: 18px; font-weight: 600; color: {INK}; background: transparent;")
        pa.addWidget(header)

        prev = QLabel()
        prev.setMinimumHeight(200)
        prev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prev.setText("  [ frame preview — current position ]  ")
        prev.setStyleSheet(f"background: #0d0d0d; border: 1px solid {BORDER}; border-radius: 8px; color: {MUTED}; font-size: 14px;")
        pa.addWidget(prev, 1)
        outer.addWidget(preview_area, 3)

        # ── Timeline ──
        timeline_area = QWidget()
        timeline_area.setStyleSheet(f"background: {SURFACE2};")
        ta = QVBoxLayout(timeline_area)
        ta.setContentsMargins(16, 8, 16, 8)
        ta.setSpacing(4)

        # Segment label
        seg_info = QHBoxLayout()
        seg_info.addWidget(QLabel("Detected page changes"))
        seg_info.addStretch()
        seg_total = QLabel("6 pages  |  0:00 — 3:24")
        seg_total.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
        seg_info.addWidget(seg_total)
        ta.addLayout(seg_info)

        # Waveform / timeline block
        waveform = QWidget()
        waveform.setFixedHeight(60)
        waveform.setStyleSheet(f"background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px;")

        wf_layout = QHBoxLayout(waveform)
        wf_layout.setContentsMargins(0, 0, 0, 0)
        wf_layout.setSpacing(0)

        markers = [0, 12, 28, 45, 60, 78, 100]
        colors = ["#d4a843", "#5aaa5a", "#5aaa5a", "#d4a843", "#5aaa5a", "#d4a843"]
        for i in range(len(markers) - 1):
            pct_start = markers[i]
            pct_end = markers[i + 1]
            seg = QWidget()
            color = colors[i]
            seg.setStyleSheet(f"background: {color}; border: none; border-right: 1px solid {BG};")
            seg.setFixedWidth(int((pct_end - pct_start) * 5))
            wf_layout.addWidget(seg)
        wf_layout.addStretch()
        ta.addWidget(waveform)

        # Page markers row
        marker_row = QHBoxLayout()
        marker_row.setSpacing(0)
        page_labels = ["p1", "p2", "p3", "p4", "p5", "p6"]
        last_end = 0
        for i, label in enumerate(page_labels):
            pos = markers[i]
            gap = pos - last_end
            if gap > 0:
                marker_row.addSpacing(gap * 5)
            m = QLabel(label)
            m.setStyleSheet(f"color: {BRASS}; font-size: 10px; background: transparent; font-weight: 600;")
            marker_row.addWidget(m)
            last_end = pos
        marker_row.addStretch()
        ta.addLayout(marker_row)

        # Seek bar
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(0, 100)
        sl.setValue(28)
        ta.addWidget(sl)

        # Timestamp row
        ts_row = QHBoxLayout()
        ts_row.addWidget(QLabel("0:12.5"))
        ts_row.addStretch()
        ts_row.addWidget(QLabel("3:24.0"))
        ta.addLayout(ts_row)

        outer.addWidget(timeline_area, 2)

        # ── Bottom: controls ──
        controls = QWidget()
        controls.setStyleSheet(f"background: {SURFACE};")
        c = QHBoxLayout(controls)
        c.setContentsMargins(16, 6, 16, 8)

        c.addWidget(QLabel("Crop:"))
        sp = QDoubleSpinBox()
        sp.setValue(0.35)
        sp.setFixedWidth(70)
        c.addWidget(sp)
        c.addSpacing(16)
        c.addWidget(QLabel("OCR:"))
        ocr = QCheckBox("Enabled")
        ocr.setChecked(True)
        c.addWidget(ocr)
        c.addStretch()
        c.addWidget(QPushButton("Preview Page"))
        c.addWidget(QPushButton("Extract"))

        outer.addWidget(controls)


# ═════════════════════════════════════════════════════════════════════
# Main window — hosts variants + switcher
# ═════════════════════════════════════════════════════════════════════

VARIANTS = [
    ("A", VariantA.NAME), ("B", VariantB.NAME), ("C", VariantC.NAME),
    ("D", VariantD.NAME), ("E", VariantE.NAME), ("F", VariantF.NAME),
]
VARIANT_CLASSES = [VariantA, VariantB, VariantC, VariantD, VariantE, VariantF]


class PrototypeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PROTOTYPE — Score Extractor UI variants")
        self.setMinimumSize(960, 700)
        self.resize(1100, 780)
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Content area
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.content, 1)

        # Floating switcher
        self.switcher = VariantSwitcher(VARIANTS)
        sw_layout = QHBoxLayout()
        sw_layout.addStretch()
        sw_layout.addWidget(self.switcher)
        sw_layout.addStretch()
        sw_layout.setContentsMargins(0, 0, 0, 12)
        main_layout.addLayout(sw_layout)

        # Add label
        proto_label = QLabel("PROTOTYPE — Use \u2190 \u2192 arrow keys to switch variants")
        proto_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        proto_label.setStyleSheet(f"color: #666; font-size: 11px; background: transparent; padding: 2px;")
        main_layout.addWidget(proto_label)

        self._variant_index = 0
        self._show_variant(0)

    def _show_variant(self, idx):
        for i in range(self.content_layout.count()):
            w = self.content_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        cls = VARIANT_CLASSES[idx]
        w = cls()
        self.content_layout.addWidget(w)

    def switch_variant(self, idx):
        self._show_variant(idx)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(FONT)
    w = PrototypeWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
