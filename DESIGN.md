---
name: Score Extractor
description: Piano score video-to-PDF extraction tool — Windows desktop (PyQt6)
colors:
  bg: "#161616"
  surface: "#1e1e1e"
  surface-elevated: "#282828"
  ink: "#e8e8e8"
  muted: "#888888"
  warm-brass: "#d4a843"
  brass-hover: "#e0b85a"
  brass-dark: "#b89230"
  input-bg: "#0d0d0d"
  green: "#5aaa5a"
  danger: "#cc4444"
  border: "#333333"
  border-emphasized: "#444444"
typography:
  display:
    fontFamily: "Segoe UI, 'Noto Sans SC', 'Noto Sans JP', 'Noto Sans', sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "0.5px"
  body:
    fontFamily: "Segoe UI, 'Noto Sans SC', 'Noto Sans JP', 'Noto Sans', sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "0.3px"
  label:
    fontFamily: "Segoe UI, 'Noto Sans SC', 'Noto Sans JP', 'Noto Sans', sans-serif"
    fontSize: "12px"
    fontWeight: 400
    letterSpacing: "0.4px"
  tab:
    fontFamily: "Segoe UI, 'Noto Sans SC', 'Noto Sans JP', 'Noto Sans', sans-serif"
    fontSize: "14px"
    fontWeight: 600
    letterSpacing: "0.3px"
  count:
    fontFamily: "Segoe UI, 'Noto Sans SC', 'Noto Sans JP', 'Noto Sans', sans-serif"
    fontSize: "14px"
    fontWeight: 600
    letterSpacing: "0.4px"
  mono:
    fontFamily: "Consolas, 'Courier New', monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  xxs: "2px"
  sm: "4px"
  md: "6px"
  fill: "5px"
  lg: "8px"
spacing:
  xxs: "2px"
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.warm-brass}"
    textColor: "{colors.bg}"
    rounded: "{rounded.md}"
    padding: "8px 18px"
  button-primary-hover:
    backgroundColor: "{colors.brass-hover}"
    textColor: "{colors.bg}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "8px 14px"
  button-secondary-hover:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.ink}"
  button-danger:
    backgroundColor: "transparent"
    textColor: "{colors.danger}"
    rounded: "{rounded.md}"
    padding: "8px 14px"
  input:
    backgroundColor: "#0d0d0d"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "7px 12px"
  tab:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    rounded: "0"
    padding: "8px 20px"
  tab-selected:
    textColor: "{colors.warm-brass}"
  groupbox:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "20px 14px 14px"
  progressbar:
    backgroundColor: "#0d0d0d"
    rounded: "{rounded.md}"
    height: "28px"
  slider-handle:
    backgroundColor: "{colors.warm-brass}"
    size: "16px"
    rounded: "8px"
---

# Design System: Score Extractor

## Overview

**Creative North Star: "The Master's Studio"**

A modern recording studio control room translated to desktop software. The interface is dim and ambient — a dark lacquer background (#161616) like polished ebony, with warm brass controls (#d4a843) that glow against the darkness like studio hardware illuminated by a single lamp. Surfaces are layered tonal blacks (1e1e1e → 282828) rather than shadow-cast planes, giving the UI the solidity of machined equipment rather than the illusion of floating paper.

This is a precision tool for a single focused task: extracting clean pages from a piano score video. The interface recedes so the score preview leads. Controls are deliberate, not decorative — every button, knob, and input serves the workflow. The warmth of brass accents provides orientation and hierarchy without competing with the content.

**Key Characteristics:**
- Studio-dark ambient environment with tonal layering
- Warm brass as the sole accent color — rare enough that it guides attention
- Precision typography: Segoe UI with CJK fallbacks, clean 13px body
- Controls recede; the score preview is the star
- Flat surfaces at rest, subtle shadows on elevated containers (dialogs, popups, dropdowns)
- Every element serves the task: no decoration without purpose

## Colors

A restrained studio palette: deep blacks, warm brass accents, and desaturated functional signals.

### Primary
- **Warm Brass** (#d4a843): The sole accent. Used for interactive elements (buttons, tab selection, slider handles, progress, focus rings, crop overlay). Its rarity on screen — typically <10% of any view — is what makes it effective. When brass appears, the user knows: this is something I can act on.

### Brass Variants
- **Brass Dark** (#b89230): Pressed state for brass buttons. Darker tone indicates active engagement.
- **Brass Hover** (#e0b85a): Hover state for brass buttons. Lighter tone signals interactivity.

### Neutral
- **Ebony Base** (#161616): The deepest layer — main window background, scrollbar tracks.
- **Studio Surface** (#1e1e1e): Card and section backgrounds — group boxes, list items, the crop preview widget.
- **Elevated Surface** (#282828): Hover states, selected items, elevated containers, slider grooves.
- **Input Background** (#0d0d0d): Text input, checkbox, radio, combo box, and progress bar backgrounds. Slightly darker than base for visible containment.
- **Ink** (#e8e8e8): Primary text and labels — maximum contrast against the dark surfaces.
- **Muted** (#888888): Secondary text, placeholders, disabled states, metadata, status messages.
- **Border** (#333333): Default borders on inputs, group boxes, separators.
- **Emphasized Border** (#444444): Hover borders, secondary button outlines.

### Semantic
- **Green** (#5aaa5a): Success states, confirmation signals (currently unused in the main UI — reserved).
- **Danger** (#cc4444): Destructive actions (Cancel button, error states).

### Named Rules

**The Single Accent Rule.** Warm Brass is the only saturated color in the UI. It must never share the stage with another accent color. Every green or red signal must be clearly semantic (success/error), never decorative.

**The Rarity Rule.** Warm Brass occupies ≤10% of any screen. Its job is to direct attention, not to decorate. If more than one element needs brass emphasis in the same view, space them apart or demote the lesser element to border-only.

## Typography

**Body Font:** Segoe UI (with CJK fallbacks: Noto Sans SC, Noto Sans JP, Noto Sans)
**Monospace Font:** Consolas / Courier New

**Character:** Clean, legible, unexpressive. Segoe UI is the Microsoft ecosystem workhorse — familiar, neutral, precise. No display font competition. The body text is comfortable at 13px; hierarchy is achieved through weight (700 for headings) and size (22px for titles), never through decorative type choices. On the dark studio surfaces, every role carries a slight positive tracking (0.3–0.5px) so ink and brass letters hold their open counterforms against the near-black fields.

### Hierarchy
- **Display** (700, 22px, 0.5px tracking): Screen titles — the "Settings" heading, the "Review before saving" dialog title. Used sparingly.
- **Body** (400, 13px, 0.3px tracking, 1.4 line-height): All primary interface text — button labels, form fields, status, descriptions. The workhorse.
- **Tab / Emphasis** (600, 14px, 0.3px tracking): Tab labels, page count indicators, emphasized numeric displays.
- **Count** (600, 14px, 0.4px tracking): Live data readouts in brass — the page badge, the completion peak status.
- **Label** (400, 12px, 0.4px tracking): Secondary information, metadata, muted status text. The `.muted` style.
- **Mono** (400, 12px): Log output, debug information, diagnostic text in QTextEdit.

### Named Rules

**The Single-Size Rule.** Body text is 13px everywhere. Tab labels and count indicators may use 14px for visual hierarchy. No other size variation for body copy across contexts.

**The No-Display-Font Rule.** No decorative or display face is used. Segoe UI carries all typographic weight. A second font would break the studio-instrument precision.

**The Role-Selector Rule.** Type roles are applied through the Qt `class` property (`_set_widget_class`), matched by `.title`, `.muted`, `.count` selectors — never through `objectName`, which Qt QSS only matches via `#id` selectors and would silently drop the style.

## Layout

The layout follows a stacked vertical rhythm with a 4px-base spacing scale:

- **xxs** (2px): Tightest — grip lines on the crop overlay, seek bar controls within their row.
- **xs** (4px): Dense sub-controls — horizontal gaps between inline actions (quality combo + download button).
- **sm** (8px): The base unit — uniform spacing between all major layout children in the Extract tab.
- **md** (12px): Section spacing on the Config tab, form row gaps.
- **lg** (16px): Toggle row spacing (local vs YouTube radio buttons), major section boundaries.
- **xl** (24px): Reserved for window-level padding.

Labels align to 115px fixed-width left column across form rows (project name, output PDF, crop ratio) for visual alignment. The crop preview is the dominant vertical element with `Expanding` size policy — it grows to fill available space above the control rows.

### Named Rules

**The Uniform Gap Rule.** Within each tab, spacing is uniform (`setSpacing(8)` on Extract, `setSpacing(12)` on Config). Major section changes are signaled by content boundaries, not by variable gaps. No ad-hoc spacers.

## Elevation & Depth

The interface uses **tonal layering with subtle shadows on elevated surfaces**. Most of the time, depth is conveyed purely by surface lightness (#161616 → #1e1e1e → #282828), not by shadows — giving the UI the solid, stacked feel of physical equipment.

**Elevated surfaces** (dialogs, dropdown menus, popups, combo-box flyouts) receive a soft drop shadow to separate them from the base UI. Shadows are used only for containers that must visually "lift off" the surface — never for resting cards or panels.

### Shadow Vocabulary
- **Overlay** (`box-shadow: 0 8px 32px rgba(0,0,0,0.4)`): Modal dialogs and popups that need clear separation.
- **Dropdown** (`box-shadow: 0 4px 16px rgba(0,0,0,0.3)`): Combo box flyouts, context menus.

### Named Rules

**The Flat-by-Default Rule.** Surfaces are flat at rest. Shadows appear only as a response to elevation change (modals, dropdowns, popups). A resting card or panel never casts a shadow.

## Shapes

A unified radius vocabulary across all interactive and container elements:

- **xxs** (2px): Sub-element radii — slider groove and sub-page fill corners, where 4px would be visually too large.
- **sm** (4px): Small touches — scrollbar handles, check indicator corners, QComboBox item corners.
- **fill** (5px): Progress bar fill chunk — sits between sm and md for a distinct fill appearance.
- **md** (6px): The standard radius for all interactive controls — buttons, inputs, spin boxes, progress bars, combo boxes.
- **lg** (8px): Containers and grouped surfaces — group boxes, the crop preview widget, list items.

Borders are 1px solid, using `border` (#333333) at rest and `border-emphasized` (#444444) on hover/focus. No double borders, inset shadows, or decorative strokes. The brass focus ring (1px solid #d4a843) is the only focus indicator.

## Components

### Buttons
- **Shape:** Moderately rounded corners (6px). Solid 1px borders on secondary/danger variants.
- **Primary (Warm Brass):** Solid brass background (#d4a843) with dark text (#161616). 700 weight label. Hover shifts to lighter brass (#e0b85a). Pressed shifts to dark brass (#b89230).
- **Secondary:** Transparent background with emphasized border (#444444). Hover fills with elevated surface (#282828), border shifts to brass.
- **Danger:** Transparent background with danger border (#cc4444). Hover fills solid danger with white text.

### Inputs / Fields
- **Style:** Dark background (#0d0d0d), 1px border (#333333), 6px radius. 7px vertical / 12px horizontal padding. Brass selection background with dark selection text.
- **Focus:** Border shifts to Warm Brass (#d4a843). No glow, no shadow — a clean line shift.
- **Placeholder:** Muted (#888888) at body weight.

### Tabs
- **Style:** Underline navigation. Transparent background, muted text. 4px tab separation, 8px vertical / 20px horizontal padding. Bold (600) weight at 14px.
- **Selected:** Warm Brass text + 2px solid Warm Brass bottom border.
- **Hover:** Text shifts to full Ink (#e8e8e8).

### Group Boxes
- **Style:** Studio Surface (#1e1e1e) background with border (#333333), 8px radius. 12px top margin collapsed to 14px left offset for the title. Warm Brass title text (600 weight).

### Progress Bar
- **Style:** Dark background (input-bg #0d0d0d), md (6px) radius, 28px height. 600 weight centered label. Warm Brass fill chunk with fill (5px) radius.

### Slider / Seek Bar
- **Style:** Dual-handle seek bar for video trimming. Groove (#282828) at 4px height with xxs (2px) radius. Circular handles (16px diameter, lg (8px) radius) in Warm Brass with 2px dark outline for definition.

### Scroll Bars
- **Style:** 8px wide, minimal. Dark (#161616) track, elevated (#282828) handle with 4px radius and 30px minimum length. Handle shifts to emphasized border on hover. No arrow buttons.

### Checkboxes / Radio Buttons
- **Style:** 18px square (checkbox) / 16px circle (radio). Dark background (#0d0d0d) with border (#444444). Checked fills with Warm Brass. Check mark is a white hand-drawn path (2.5px stroke). 8px label spacing.
- **Hover:** Border shifts to Warm Brass.

### Combo Boxes
- **Style:** Dark background (#0d0d0d), 6px radius, 6px vertical / 12px horizontal padding. 24px min height. Drop-down icon (Warm Brass chevron) in a 28px-wide button area. Dropdown list uses surface background with elevated hover states and Warm Brass selected text.

### Labels
- **Muted:** 12px, #888888 — secondary/descriptive text, status messages.
- **Count:** 14px, 600 weight, Warm Brass — page counts and numeric indicators.
- **Title:** 22px, 700 weight, Ink — screen-level headings.

## Do's and Don'ts

### Do:
- **Do** use Warm Brass sparingly — it's a spotlight, not a wash.
- **Do** let the score preview occupy the majority of vertical space.
- **Do** use tonal surfaces for depth — stack #161616 → #1e1e1e → #282828.
- **Do** align form labels to a consistent left column (115px).

### Don't:
- **Don't** introduce a second accent color. Warm Brass is the only accent.
- **Don't** use drop shadows on resting surfaces — flat is the default.
- **Don't** use decorative borders thicker than 2px or colored borders on card sides.
- **Don't** add display or decorative fonts — Segoe UI carries everything.
- **Don't** use gradient text, glass effects, or sparklines — the studio aesthetic is solid and tactile.
