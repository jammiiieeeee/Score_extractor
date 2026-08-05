# Score Extractor — Context

A Windows-only desktop app that extracts piano sheet-music pages from screen-recorded videos and compiles them into a clean PDF. Its GUI ships a custom window chrome (a frameless title bar) that must behave indistinguishably from the native Windows title bar while keeping a custom dark visual style.

## Language

## Window Chrome

**Custom chrome**:
The app's window frame — a dark-QSS client strip with native caption behaviours — which must exhibit behavioural parity with the native Windows title bar. The window controls are OS-drawn; every other part of the bar is custom.
_Avoid_: custom title bar, fake title bar

**Caption zone**:
The part of the title bar strip not occupied by interactive widgets or the OS-drawn window controls. It is handed to native Windows (hit-tested as `HTCAPTION`) so dragging, Aero snap, the system menu, and double-click behave exactly as on a native caption.
_Avoid_: drag region, title bar background

**Window control**:
The OS-drawn minimize, maximize/restore, and close buttons Windows floats over the top-right of the chrome. They cannot be restyled, but keeping them is what grants the Windows 11 Snap Layouts flyout.
_Avoid_: title bar button, custom window button

**Behavioural parity**:
The property that a custom-chrome window responds to user gestures (drag, snap, double-click, system menu, keyboard shortcuts) identically to a native title-bar window, regardless of custom visuals.
_Avoid_: lookalike, emulation
