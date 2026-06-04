# QCM-D Viewer — Design System

> **One material, one grid, one accent.** The interface should read like a single
> instrument panel, not a stack of features. Every decision below is a rule, not a
> suggestion — when a new element is added, it inherits from these definitions
> rather than inventing its own treatment. This is the source of visual cohesion.

The system is implemented as code in two files; this document is the spec they
follow:

- `qcm/viz/tokens.py` — the only place raw values live. Emits CSS custom
  properties (`--qcm-*`) and Python constants for plot code.
- `qcm/viz/design.py` — the single stylesheet, built entirely from tokens, with
  rules scoped by class so they win on structure (never `!important`, except two
  unavoidable Bokeh `display:grid` overrides + one defensive hide).

---

## 1. Principles

1. **Flat and bordered, not layered with shadow.** Surfaces separate by a single
   hairline border. Shadow is reserved for things that genuinely float (drawer,
   sticky top bar). A screen of drop-shadowed cards is the look we are removing.
2. **The 4px grid governs everything.** Every size, gap, and padding is a
   multiple of 4. Nothing is "nudged" by an odd pixel.
3. **Hierarchy from type and space, never decoration.** No gratuitous gradients,
   no second accent color, no decorative rules.
4. **One blue.** A single accent drives every interactive affordance — primary
   action, focus ring, active state, selection, link. Filled blue appears *only*
   on the single primary action in any view, so the eye always knows where to go.
5. **Numbers are monospace, always.** Every figure (stat, table cell, readout,
   axis tick) uses the mono face with tabular figures so columns align.
6. **Everything fits its box.** Flex children carry `min-width:0`; cards clip
   content (`overflow:hidden`) where it would spill; plots and tables never
   exceed their container.

---

## 2. Grid & spacing

Base unit **4px**. Scale (token → value):

| token | px | use |
|---|---|---|
| `space-1` | 4 | hairline gaps, icon/label gap |
| `space-2` | 8 | tight groups, chip padding |
| `space-3` | 12 | card body padding, intra-card gaps |
| `space-4` | 16 | page padding, gap between cards/sections |
| `space-5` | 24 | major section separation |
| `space-6` | 32 | page-level breathing room |

- **Page padding:** 16. **Stack gap between cards:** 16. **Inside a card:** 12.
- Cards never set their own margin; the parent stack owns spacing via `gap`.

---

## 3. Surfaces & elevation (the material)

There is **one** card material, used for every panel:

> white background · 1px `border` · `radius-card` (10px) · **no shadow**

| role | token | value | use |
|---|---|---|---|
| canvas | `bg` | `#f4f6f9` | the page behind all surfaces |
| surface | `surface` | `#ffffff` | every card, the sidebar, the top bar |
| sunken | `surface-muted` | `#f5f7fa` | nested wells: table headers, toggle tracks, readouts |
| border | `border` | `#e4e8ee` | the hairline that separates surfaces |
| border-strong | `border-strong` | `#cbd3dd` | input/control outlines, axis lines |

**Elevation levels** — only two, and most things are level 0:

- **0 — bordered (default).** All cards, the top bar's resting state. Border only.
- **1 — floating.** Drawer and sticky top bar. Border + `shadow-1`/`shadow-2`.

Radius is **role-based**, not a t-shirt scale:

| token | value | applies to |
|---|---|---|
| `radius-control` | 8px | buttons, inputs, selects, toggles, chips |
| `radius-card` | 10px | cards, stat tiles, tables, big toggle cards |
| `radius-pill` | 999px | pills, status dots, segmented all-toggles |

---

## 4. Color roles

Semantic roles — components reference these, never raw hex.

**Text**

| role | token | value |
|---|---|---|
| primary (ink) | `text` | `#0f172a` |
| secondary | `text-soft` | `#334155` |
| tertiary (muted) | `muted` | `#64748b` |
| faint/disabled | `faint` | `#94a3b8` |

**Accent (the one blue)**

| role | token | value |
|---|---|---|
| accent | `accent` | `#2563eb` |
| hover | `accent-strong` | `#1d4ed8` |
| active | `accent-active` | `#1e40af` |
| surface (soft bg) | `accent-soft` | `#eff6ff` |
| border | `accent-border` | `#bfdbfe` |
| on-accent | `on-accent` | `#ffffff` |
| focus ring | `ring` | `0 0 0 3px rgba(37,99,235,.30)` |

**Status** — each a foreground + a soft surface. Used sparingly, never as chrome.

| | fg | surface |
|---|---|---|
| success | `success` `#16a34a` | `success-soft` `#ecfdf5` |
| warning | `warning` `#d97706` | `warning-soft` `#fffbeb` |
| danger | `danger` `#dc2626` | `danger-soft` `#fef2f2` |

**Data colors** (plots/phases only — never UI chrome): the Wong colorblind-safe
overtone palette, the green/orange baseline/event pair, and the semantic phase
palette. Violet (`#7c3aed`) lives here only — it is never used in chrome.

---

## 5. Typography

- **UI:** Inter (system sans fallback). **Numerics:** IBM Plex Mono.
- Sizes are absolute px (predictable; base body = 13px).

| role | size | weight | tracking | color | use |
|---|---|---|---|---|---|
| display | 18 | 700 | -0.01em | text | page / run title in top bar |
| title | 14 | 700 | — | text | card & section headings |
| eyebrow | 11 | 700 | 0.06em, UPPER | muted | label above a group/section |
| label | 12 | 600 | — | text-soft | control labels |
| body | 13 | 450 | — | text-soft | descriptions, prose |
| value | 15 | 700 | — | text | a data readout (**mono, tabular**) |
| value-lg | 20 | 700 | — | text | headline stat (**mono, tabular**) |
| caption | 11 | 450 | — | muted | sub-text under a value |

**Rule:** anything numeric uses the mono face + `font-feature-settings:"tnum"`.
Labels are always `eyebrow` or `label`. This single discipline is what makes
stat tiles, chips, tables, and the run-info list look like one family.

---

## 6. Component anatomy

Each component is defined **once**; every instance follows. Class names in
parentheses are the implementation hooks.

### Card (`.qcm-card`, `.bk-card`, `.qcm-anchor`)
- The material from §3. `margin:0`.
- **Header** (`.bk-card-header`): height 40, padding `0 space-4`, bottom
  hairline, `title` type. Collapse chevron right-aligned. Optional action =
  accent quiet button on the right.
- **Body** (`.bk-card-body`): padding `space-3`.

### Section header (`.qcm-section-title-row`)
- Optional `eyebrow`, then `title`; optional accent action link on the right.
- `space-2` below before content.

### Button (`.bk-btn`)
- Height = `control-h` (34), padding `0 14`, `radius-control`, `label` type,
  icon 18 with `space-2` gap, `motion` transition. Focus → `ring`.
- **primary** (`.bk-btn-primary`): accent bg, on-accent text, no border;
  hover → accent-hover; active → accent-active. The only filled-blue element.
- **secondary / default** (`.bk-btn-default`): surface bg, `border-strong`,
  text-soft; hover → accent border + ink text.
- **ghost** (nav items, minor toolbar): transparent, text-soft; hover → sunken.
- **danger**: danger fg, danger-soft on hover. Destructive only.
- Icon-only: square `control-h` × `control-h`.

### Input / Select (`.bk-input`, `select`)
- Height `control-h`, `radius-control`, 1px `border-strong`, surface bg,
  padding `0 10`, `body` size. Focus → accent border + `ring`.
- Numeric inputs: right-aligned, mono, tabular.
- Label sits above as an `eyebrow`; the widget's own inline label is hidden.

### Segmented toggle — the **default** for every `RadioButtonGroup` / `CheckButtonGroup`
- Styled generically on `.bk-btn-group`, so *any* radio/check group is a
  segmented control with no per-widget class needed. Never set
  `button_type="primary"` on a toggle — the segmented styling is the look.
- **Track:** sunken bg, `radius-control`, 3px inner padding, inline-flex.
- **Segment:** transparent, text-soft. **Active:** raised white segment
  (surface + hairline border + faint shadow) with accent text.
- The chip-grid channel chooser (`.channel-toggles`) is the one opt-out: it
  resets the track and renders full-width chips instead.

### Big mode cards (`.draw-mode-toggle`)
- 3-up grid of tall cards: surface + `border-strong` + `radius-card`, left
  aligned title + sub. **Active:** `accent-soft` bg + accent text + 3px accent
  inset bar. (Same active language as nav.)

### Channel chooser (`.channel-toggles`)
- Grid of full-width chip-buttons sharing the secondary-button look; active =
  accent-soft + accent text + inset bar.

### Stat tile (`.qcm-stat`, `.qcm-iconstat`)
- Card cell: surface, border, `radius-card`, padding `space-3`.
- `eyebrow` label, then `value` (mono). The value's **unit renders as a small,
  light sans span on the same baseline** (`icon_stat` splits "6,037.6 ng/cm²"
  into a bold number + a muted unit) so units never orphan onto their own line.
- Optional `caption`. Optional leading icon chip: 36px rounded square,
  accent-soft bg, accent icon. **Tone is for status, not decoration** — leave
  summary metrics neutral (accent); only use success/warning/danger when the
  value actually means that.
- Grid (`.qcm-statgrid`, `.qcm-metric-strip`): `auto-fit minmax`, gap `space-3`.

### Pill / chip (`.qcm-pill`, `.qcm-selchip`)
- Compact inline readout: `radius-pill`, sunken bg, hairline border;
  `eyebrow` key + `value` (mono). Accent variant uses accent-soft + accent text.

### Key/value list (`.qcm-kvtable`, `.qcm-def`)
- Two columns: key (text-soft, left) · value (mono, right). 4px row padding.

### Table (`.tabulator`, `.summary-table`)
- Contained in a card: `radius-card`, `overflow:hidden` so corners clip.
- Header: sunken bg, `eyebrow`-style column labels, bottom hairline. **Always
  use human column titles with units** (Tabulator `titles=`), never raw
  `snake_case` (`echem.pretty_column_titles`).
- Rows: hairline dividers (no zebra), hover → sunken. Cells `body` size,
  numbers mono/tabular, padding `6 10`.
- Narrow rail tables (≤ `rail-w`): keep to 2 columns, `layout="fit_columns"`,
  and pin the label column width so values get the room.

### Navigation (`.qcm-nav-item`)
- Full-width ghost button, left-aligned, icon + label, padding `9 11`,
  `radius-control`. Sublabel = `caption` indented under the label.
- **Active:** `accent-soft` bg + accent text + 3px accent inset bar.

### Top bar (`.qcm-topbar`)
- Card spanning content width, **sticky** at top (elevation 1: `shadow-1`).
- Left: run title (`display`). Right: actions, with **Export** as the single
  primary button.

### Drawer (`.qcm-drawer`)
- Right sheet, surface, left border, `shadow-2`. Backed by a **scrim**
  (`.qcm-scrim`, token `--qcm-scrim`) that dims the page and closes on click.
- Header row: `display`-size title + close button, divided by a bottom hairline.
  Same card language inside.

### Plot card (`.qcm-anchor`)
- Borderless plot region inside the card; the range slider rides flush beneath
  with a dashed hairline top divider, reading as the plot's own scrubber.
- Bokeh theme matches chrome: white plot bg, hairline axes (`border-strong`),
  faint grid, axis labels in sans, **tick labels in mono**.
- **Axes are always labeled with quantity + unit** (e.g. "Time [s]",
  "Δf / n [Hz]") — never the generic "x"/"y". When composing overlays (phase
  labels, zero line) set `xlabel`/`ylabel` on the *outermost* overlay, since
  composing resets them to the dimension names of the added elements.
- Tool palette is set to autohide (appears on hover) for a clean resting state.
- Legend is an opaque white box (`background_fill_alpha` ≈ .94) so it stays
  readable over curves.

### States (applied uniformly)
- hover · active/pressed · focus (`ring`) · selected (`accent-soft`) ·
  disabled (60% opacity, no pointer).

### Iconography
- Line icons, 1.75 stroke, `currentColor`. 18px in controls, 20px in stat chips.

---

## 7. Layout templates

App = sidebar | content. Content = sticky top bar + active page. 16px page
padding, 16px stack gap throughout.

| region | width | behavior |
|---|---|---|
| sidebar | `sidebar-w` 232 | sticky, full-height, own scroll |
| rail (all pages) | `rail-w` **320** | sticky, own scroll — unified across Data/Results/Report |
| main column | fluid | `flex:1; min-width:0` |

- **Data:** full-width toolbar strip under the top bar → body = plot zone (main)
  + rail; selection cards beneath the plot.
- **Results:** a short **top row** (summary tiles + the Technique/Cycle column),
  then the plots span **full width** below. Don't run a side column the full page
  height when its content is short — it leaves a dead quadrant; put short
  controls in the top row and let plots/tables use the whole canvas.
- **Report:** main + side.

**Avoid dead space.** Bottom-anchor secondary items (sidebar Help) with a spacer
so the *void lands at the bottom*, not in the middle. Where a card has slack
(e.g. the selection card), fill it with guidance rather than blank surface.
- **Responsive:** ≤1280 rails drop below as full-width; ≤900 sidebar becomes a
  horizontal bar.

**Fit-its-box rules:** `*{box-sizing:border-box}`; every flex child of the
shell/page/rail/plot-zone gets `min-width:0`; cards that hold tables or plots
clip overflow; media/plots `max-width:100%`.

---

## 8. Affordances & first-run clarity

- **Labels say what they do.** No internal jargon in the UI ("y = 0 line", not
  "Zero line"; "Save view", not "Save workspace"; the signals matrix column is
  "Channel", matching its "Ch N · n=…" rows).
- **Tooltips** via Panel's `description=` on widgets that support it
  (Button, Select, RadioButtonGroup, FloatInput — **not** Checkbox, whose label
  must carry the meaning). Use them on any control whose effect isn't obvious.
- **Teach in place.** A multi-mode control (the range Selection mode) carries a
  short inline explainer of each mode and how it's set — this both onboards and
  fills the card's slack.
- **Time-domain controls stay labeled as time** ("Time window (s)") even when the
  plot x-axis is potential/charge, so the scrubber's meaning never drifts.

## 9. Motion

`motion` = 120ms ease for color/border/background on hover & focus; 160ms for
the drawer slide. Subtle and consistent — never bouncy.
