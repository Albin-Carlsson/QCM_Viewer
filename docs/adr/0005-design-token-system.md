# 0005 — Single tokenised stylesheet under shadow DOM

Status: Accepted

## Context

The UI is one "scientific minimalism" identity (white base, one blue accent,
dense instrument layout, sans UI + mono numerics). Without a single source of
truth, colours and spacing drift across components. Critically, **Panel 1.x +
Bokeh 3 render every component in its own shadow root**: cross-component CSS
descendant selectors silently fail, and ad-hoc inline styles scatter the design.

## Decision

A token-based design system with one stylesheet:

- `qcm/viz/tokens.py` is the **only** file holding raw hex. It emits CSS
  `--qcm-*` custom properties via `root_css()` and Python constants for
  Bokeh/plot code. Tokens are role-based (radius, control/header heights, `fs-*`
  type scale, focus ring).
- `qcm/viz/design.py` is the **one** stylesheet (`APP_CSS = root_css() + …`),
  scoped by class so rules win without `!important` (only a couple of
  unavoidable exceptions).
- `docs/design-system.md` is the written spec; every rule is an instance of a
  definition there.

Shadow-DOM rules that follow from this (the hard-won ones):

1. Style a component via **its own class** (`.qcm-runinfo { … }`); every card
   must carry an explicit `qcm-card` class because `.bk-card` doesn't match
   Panel's element.
2. Cross-component descendant selectors don't work; use `:host(.parent) .child`
   (raw_css is injected into each shadow root) or inject `stylesheets=[…]` into a
   widget's own root. CSS custom properties *do* inherit across shadow
   boundaries, so `var(--qcm-*)` works everywhere.
3. The `stretch_width` sizing default writes inline `width:100%; min-width:0` on
   child hosts and can collapse flex items to 0 px — fix with a `:host` rule and
   `!important`, diagnosed via a DOM walk, not by reading CSS.

Verify UI work by **screenshot** (`tools/shoot.py`), never by reading CSS —
shipped CSS ≠ rendered result.

## Consequences

- **Good:** one identity, no raw hex outside tokens, themable via variables;
  plot code and CSS share the same palette.
- **Cost:** the shadow-DOM constraints are non-obvious and have repeatedly caused
  "my rule does nothing" bugs; they are now written down here and in
  CONTEXT.md.
- **Obligation:** new components get a dedicated class + `qcm-card` where
  applicable; new colours go in `tokens.py` only.
