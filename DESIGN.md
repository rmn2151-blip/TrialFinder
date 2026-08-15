---
name: TrialFinder
description: Clinical trials that fit you, explained in plain English.
colors:
  clinical-trust-blue: "#1f6feb"
  clinical-trust-blue-deep: "#1457c4"
  clinical-trust-blue-tint: "#eaf1fe"
  recruiting-green: "#1f9d57"
  recruiting-green-tint: "#e6f6ec"
  caution-amber: "#b8770a"
  caution-amber-tint: "#fdf3df"
  biomarker-violet: "#7d5cff"
  biomarker-violet-deep: "#4a39a8"
  biomarker-violet-tint: "#f1ecff"
  biomarker-violet-chip: "#e3d9ff"
  alert-red: "#b3261e"
  alert-red-tint: "#fdeceb"
  ink: "#14202e"
  ink-soft: "#4a5a6a"
  ink-faint: "#7d8b99"
  neutral-tier: "#6b7785"
  neutral-tint: "#eef1f5"
  surface: "#ffffff"
  neutral-bg: "#f6f8fb"
  hairline: "#e3e9f0"
typography:
  display:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "clamp(1.7rem, 4.5vw, 2.5rem)"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "1.2rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.07em"
rounded:
  sm: "9px"
  md: "14px"
  pill: "999px"
  circle: "50%"
spacing:
  x: "0.85rem"
components:
  button-primary:
    backgroundColor: "{colors.clinical-trust-blue}"
    textColor: "#ffffff"
    rounded: "{rounded.pill}"
    padding: "0.65rem 1.3rem"
  button-primary-hover:
    backgroundColor: "{colors.clinical-trust-blue-deep}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.pill}"
    padding: "0.65rem 1.3rem"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "1.05rem 1.15rem"
  field-input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0.7rem 0.85rem"
  chip:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.pill}"
    padding: "0.4rem 0.85rem"
  fit-badge-strong:
    backgroundColor: "{colors.recruiting-green-tint}"
    textColor: "#136b3b"
    rounded: "{rounded.pill}"
    padding: "0.3rem 0.7rem 0.3rem 0.4rem"
---

# Design System: TrialFinder

## Overview

**Creative North Star: "The Clear Path"**

TrialFinder turns an intimidating, scattered process (finding an eligible clinical trial) into a small number of visible, sequential steps: intake progress ticks forward, results are ranked and scored rather than dumped as a list, and warnings/eligibility caveats are disclosed rather than buried. The system reads as **professional enough for an enterprise/pharma audience, calm enough for a patient reading it hours after a diagnosis.** It is not a consumer-brand experience and not a bare clinical tool — it sits deliberately between the two: restrained color, generous whitespace, one accent used sparingly, and status expressed through color + shape (pill badges, a circular score) rather than iconography or illustration.

A single soft ambient shadow (see Elevation & Depth) is the only depth cue; everything else is flat, bordered, and quiet.

**Key Characteristics:**
- One accent color (Clinical Trust Blue), used sparingly; everything else is neutral or purely semantic (status)
- Pill (999px) and circle (50%) as the almost-exclusive corner language — nothing sharp-cornered
- Status is color-coded consistently across the whole app: green = recruiting/strong/covered, amber = caution/medium/opening soon, violet = a distinct "insight" callout (biomarkers only), red = error only
- Flat by default; one shared soft shadow token marks a surface as a card
- Small, sparing use of uppercase label type (eyebrows, section labels) as the only typographic "voice" beyond size/weight

## Colors

Deliberately narrow: one brand accent, a neutral scale for structure and text, and four semantic colors that never wander outside their assigned meaning.

### Primary
- **Clinical Trust Blue** (#1f6feb): The single brand accent. Primary buttons, links, the active intake-step indicator, the brand mark, focus rings. Used narrowly — most of the interface is neutral.
- **Clinical Trust Blue Deep** (#1457c4): Hover/active state for the primary accent only.
- **Clinical Trust Blue Tint** (#eaf1fe): Low-emphasis fills that still read as "on-brand" — default pill/tag background, focus-ring glow.

### Neutral
- **Ink** (#14202e): Primary text and headings.
- **Ink Soft** (#4a5a6a): Secondary text — body copy, descriptions, ghost-button label.
- **Ink Faint** (#7d8b99): Tertiary/meta text — hints, stat captions, disclaimers.
- **Surface** (#ffffff): Card and input backgrounds.
- **Neutral Bg** (#f6f8fb): Page background, one step darker than Surface so cards read as raised without needing a shadow to separate them.
- **Hairline** (#e3e9f0): All borders and dividers.
- **Neutral Tier** (#6b7785) / **Neutral Tint** (#eef1f5): The "weak fit" / muted semantic pair — used when a status is neither positive nor negative, just unremarkable.

### Semantic status colors

These four pairs (a saturated color + a pale tint) are the only place color carries meaning beyond brand. Never repurpose a status color for decoration.

- **Recruiting Green** (#1f9d57) / **Recruiting Green Tint** (#e6f6ec): Strong trial fit, "Recruiting" status, insurance-covered chips. Positive outcomes only.
- **Caution Amber** (#b8770a) / **Caution Amber Tint** (#fdf3df): Medium trial fit, warning flags, "opening soon" status. Something the reader should notice, not something wrong.
- **Biomarker Violet** (#7d5cff, border/icon), **Biomarker Violet Deep** (#4a39a8, text), **Biomarker Violet Tint** (#f1ecff, callout background), **Biomarker Violet Chip** (#e3d9ff, chip background): Reserved entirely for the biomarker callout component. Not a general-purpose fourth brand color — its rarity is what makes it register as "this is a distinct kind of information."
- **Alert Red** (#b3261e) / **Alert Red Tint** (#fdeceb): Error states only (e.g. the error state-card icon). Never used for form validation styling elsewhere in the system today — if that's added, reuse this pair rather than inventing a new red.

### Named Rules
**The One Accent Rule.** Clinical Trust Blue is the only color used for brand/interactive emphasis. Every other color on screen is either neutral (structure/text) or semantic (status) — never decorative.

## Typography

**Display/Body/Label Font:** Inter (with system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial fallback)

**Known gap:** Inter is declared in the font stack but is not actually loaded anywhere (no `<link>`, `@import`, `@font-face`, or npm font package) — every browser today renders the system-ui fallback, not Inter. Treat "Inter" as the intended face; either load it properly or update this doc to declare the system-ui stack as canonical, but don't let the two silently diverge further.

**Character:** One typeface for everything; hierarchy comes from size and weight, not font pairing. Efficient and unfussy — type gets out of the way of the content.

### Hierarchy
- **Display** (800, `clamp(1.7rem, 4.5vw, 2.5rem)`, 1.2 line-height, -0.02em): Hero title and the results-page condition heading (1.6rem fixed variant). One per page, at most.
- **Title** (700, 1.18–1.3rem, 1.2 line-height, -0.01em): Trial card titles, intake step legend, state-card title.
- **Body** (400, 1rem, 1.55 line-height): Default paragraph text; no explicit body class, this is the page-level default.
- **Label** (700, 0.75–0.78rem, uppercase, 0.07–0.08em letter-spacing): Eyebrows and section micro-labels (hero eyebrow, results eyebrow, insurance label). Small, loud, sparing.

### Named Rules
**The One-Display Rule.** Only one Display-scale heading exists per screen. Everything else steps down to Title or smaller — there is no secondary "big" heading competing for attention.

## Layout

Content is capped at a narrow `860px` max-width (`--maxw`) and centered — a single-column, reading-width layout throughout, not a wide dashboard grid. Horizontal page padding is a single responsive token (`--pad-x`: 0.85rem baseline, tightening to 0.7rem and 0.55rem at smaller breakpoints) rather than a multi-step spacing scale — density is controlled narrowly, not through a large spacing system. Cards and results stack vertically with small, consistent gaps (0.75rem between result cards). The header is sticky; a sticky disclaimer bar pins to the bottom of the results list. Responsive steps observed in the stylesheet: `1000px`, `720px` (header switches from single-row to stacked), `560px`, `480px`.

## Elevation & Depth

Flat by default. Structure is conveyed first by the Neutral Bg / Surface contrast and Hairline borders; a single shared shadow token (`--shadow`) is layered on top only for surfaces that should read as distinctly raised (cards, the intake panel, state cards, the sticky header on scroll). One deliberately heavier shadow exists for an overlay/modal-level surface. This is restrained on purpose — elevation marks "this is a discrete unit," not decoration, and there is no multi-step elevation scale to keep consistent with.

### Shadow Vocabulary
- **Ambient card** (`box-shadow: 0 1px 2px rgba(20,32,46,0.04), 0 8px 24px rgba(20,32,46,0.06)`): Default for any card-like surface (trial card, intake panel, state card).
- **Overlay** (`box-shadow: 0 8px 30px rgba(20,32,46,0.16)`): Reserved for the one surface that sits above the page (modal/overlay-level), not for ordinary cards.

### Named Rules
**The Flat-by-Default Rule.** Nothing gets a shadow just for being a container. A shadow means "this specific surface is meant to feel lifted above the page," and there are exactly two shadow values in the whole system — reach for a third only with real justification.

## Shapes

Two corner values only: **pill** (999px) for anything button- or status-shaped (buttons, chips, pills, badges, progress track), and **circle** (50%) for anything that holds a single glyph, initial, or number (step numbers, fit-score badge, state-card icon). Cards and inputs use a smaller, fixed radius (14px / 9px) rather than the pill treatment — the pill/circle language is reserved for interactive and status elements, not containers.

### Named Rules
**The No-Sharp-Corners Rule.** Nothing in the system has a 0px or small-arbitrary radius. Every shape is either a pill, a circle, or one of the two named radii (14px card, 9px control).

## Components

Efficient and unfussy: components carry status through color and shape, not through extra ornament, icons, or motion.

### Buttons
- **Shape:** Pill (999px radius).
- **Primary:** Clinical Trust Blue fill, white text, 600 weight, `0.65rem 1.3rem` padding (`0.85rem 1.9rem` at the `--lg` size).
- **Ghost:** Transparent fill, Ink Soft text, Hairline border.
- **Link:** No fill or border, Clinical Trust Blue text, underline on hover only.
- **Hover / Focus:** Primary darkens to Clinical Trust Blue Deep; all buttons get a 1px translateY press on `:active`. Focus uses the global 3px Clinical Trust Blue outline, not a button-specific treatment.

### Chips (selectable)
- **Style:** White background, Hairline border, Ink Soft text, pill shape.
- **State:** Selected = Clinical Trust Blue fill + border, white text. Unselected hover = Clinical Trust Blue border + text, background unchanged.

### Status pills / fit badge
- **Style:** Pill-shaped, tinted background matching the semantic color, a small circular score badge (solid semantic color, white bold number) nested at the left edge when a numeric score applies.
- **Variants:** Strong (green), Medium (amber), Weak (neutral gray) — always this exact three-step scale, never a different color for the same meaning.

### Cards / Containers
- **Corner Style:** 14px (`--radius`).
- **Background:** Surface white on Neutral Bg page background.
- **Shadow Strategy:** Ambient card shadow (see Elevation & Depth).
- **Border:** 1px Hairline.
- **Internal Padding:** ~1.05–1.2rem, tightening slightly on dense components.

### Inputs / Fields
- **Style:** White background, 1px Hairline border, 9px radius (`--radius-sm`).
- **Focus:** Border shifts to Clinical Trust Blue plus a 3px Clinical Trust Blue Tint glow ring — no color change to the field background.
- **Error / Disabled:** No dedicated field-error treatment exists yet in the codebase; if added, reuse Alert Red / Alert Red Tint rather than introducing a new red.

### Callout (biomarker)
A left-border-accent callout (4px Biomarker Violet border, Biomarker Violet Tint background, top-right corners only rounded to 9px) is the one component allowed to break from the neutral/semantic palette — reserved exclusively for biomarker information, never reused for generic emphasis.

### Navigation
Sticky header, white surface, Hairline bottom border. Content nav and account controls are visually separated by a left border on the account cluster. Active/hover states use standard link color shift (Ink Soft → Clinical Trust Blue) with no underline until hover.

## Do's and Don'ts

### Do:
- **Do** keep Clinical Trust Blue as the only interactive/brand accent — resist adding a second "brand" color even for a new feature.
- **Do** use the pill/circle shape language for anything status- or action-shaped; use the 14px/9px radii only for containers and inputs.
- **Do** reuse the exact green/amber/gray three-step scale for any new "fit" or "quality" ranking rather than inventing a new scale.
- **Do** keep the biomarker violet exclusive to biomarker content so its rarity keeps doing work.
- **Do** respect `prefers-reduced-motion` (already implemented globally) when adding any new transition or animation.

### Don't:
- **Don't** add a shadow to a surface that isn't meant to read as a distinct raised card — flat is the default, not the fallback.
- **Don't** introduce a second display-scale heading on one screen; step everything else down to Title or smaller.
- **Don't** let "Inter" stay declared-but-unloaded — either load the webfont for real or stop claiming it in this document.
- **Don't** use Alert Red for anything other than true error states, even under pressure to make a warning feel more urgent — that's what Caution Amber is for.
