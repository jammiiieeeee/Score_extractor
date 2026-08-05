# 0001 — Keep native window controls so the Snap Layouts flyout stays real

The custom chrome keeps the OS-drawn window controls and the native window frame, with the caption bar collapsed via `WM_NCCALCSIZE` and hit-testing routed so the strip behaves as `HTCAPTION`. This keeps Windows 11's genuine Aero Snap (top/edge/corner gestures, ghost previews, Snap Groups) and the Snap Layouts flyout on the maximize button, while the Qt layer only owns the hamburger, the dark visuals, and the invisible resize hit-zones. The app is Windows-only, so the Win32 dependency is acceptable.

## Considered Options

- **Native frame + native controls (`WM_NCCALCSIZE`)** — chosen. Only option with the real flyout; native owns drag/snap/system menu/double-click. Costs: OS-drawn buttons can't be restyled (mitigated with `DWMWA_USE_IMMERSIVE_DARK_MODE`), the core behaviour is not CI-testable (mitigated with a pure hit-test function + a manual acceptance checklist).
- **Frameless + custom buttons + manual snap** — rejected: reimplements drag/snap by hand and loses the flyout; a prior manual top-snap implementation was exactly where the recent bugs lived.
- **Custom buttons + hand-rolled flyout** — rejected: a custom flyout would drift from native on every Windows update and is the most fragile code in the change.

## Consequences

- The window is only resizable because we re-add invisible `WM_NCHITTEST` resize zones (the collapsed frame has no native border).
- A spike must confirm Qt's geometry bookkeeping tolerates the caption collapse before the change is committed.
