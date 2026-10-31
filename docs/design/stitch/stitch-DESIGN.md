---
name: Civic Trust
colors:
  surface: '#edfdf4'
  surface-dim: '#ceded5'
  surface-bright: '#edfdf4'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#e7f7ee'
  surface-container: '#e1f2e8'
  surface-container-high: '#dcece3'
  surface-container-highest: '#d6e6dd'
  on-surface: '#111e19'
  on-surface-variant: '#424841'
  inverse-surface: '#25332d'
  inverse-on-surface: '#e4f5eb'
  outline: '#737971'
  outline-variant: '#c2c8bf'
  surface-tint: '#466649'
  primary: '#37563b'
  on-primary: '#ffffff'
  primary-container: '#4f6f52'
  on-primary-container: '#ccf0cc'
  inverse-primary: '#acd0ad'
  secondary: '#755b00'
  on-secondary: '#ffffff'
  secondary-container: '#fed255'
  on-secondary-container: '#735a00'
  tertiary: '#005c33'
  on-tertiary: '#ffffff'
  tertiary-container: '#117745'
  on-tertiary-container: '#9ffbbd'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#c8ecc8'
  primary-fixed-dim: '#acd0ad'
  on-primary-fixed: '#03210b'
  on-primary-fixed-variant: '#2f4e33'
  secondary-fixed: '#ffe08e'
  secondary-fixed-dim: '#ecc246'
  on-secondary-fixed: '#241a00'
  on-secondary-fixed-variant: '#584400'
  tertiary-fixed: '#9af6b8'
  tertiary-fixed-dim: '#7ed99e'
  on-tertiary-fixed: '#00210f'
  on-tertiary-fixed-variant: '#00522d'
  background: '#edfdf4'
  on-background: '#111e19'
  surface-variant: '#d6e6dd'
typography:
  display-lg:
    fontFamily: Literata
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Literata
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Literata
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Literata
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
  headline-sm:
    fontFamily: Literata
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Source Sans 3
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-base:
    fontFamily: Source Sans 3
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-base-mobile:
    fontFamily: Source Sans 3
    fontSize: 17px
    fontWeight: '400'
    lineHeight: 26px
  body-sm:
    fontFamily: Source Sans 3
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-lg:
    fontFamily: Source Sans 3
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 20px
  label-md:
    fontFamily: Source Sans 3
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 18px
  label-sm:
    fontFamily: Source Sans 3
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.03em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 1.5rem
  margin-desktop: 2.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
  space-2xl: 2rem
  space-3xl: 3rem
---

## Brand & Style

This design system establishes a tranquil, institutional, and human-centric visual language for civic verification and public fraud reporting across India. The aesthetic blends the physical tactility of archival paper, stationery registries, and community noticeboards with modern, accessible digital ergonomics.

The design targets everyday citizens—from non-technical elders verifying suspicious banking calls to local shopkeepers verifying payment QR codes—who require an interface that reduces panic, eliminates sensationalism, and inspires quiet, reliable authority. 

### Core Design Values
- **Civic Calm:** Avoid alarmist neon tones, hacker tropes, flashing badges, or gamified security graphics. Danger and fraud statuses are conveyed with decisive editorial weight rather than panic-inducing visual noise.
- **Stationery & Archival Clarity:** Rely on flat, warm tones (cream, linen, ivory) reminiscent of official ledger cards and public record desks. Physical boundaries are built strictly with single-pixel structural strokes rather than multi-layered dropshadows.
- **Honest Utility:** Avoid glassmorphism, blur filters, saturated gradients, floating decorative artifacts, and emojis. Every icon acts strictly as a visual anchor and must be accompanied by an explicit text label.
- **Multilingual Readability:** Designed from the baseline up to balance Latin and Indic scripts with comfortable ascenders, open counters, and generous line spacing suited for varying typographic densities.

## Colors

The system uses an intentional, earthy palette built exclusively for light-mode readability under high ambient sunlight. Dark mode is intentionally omitted to preserve the parchment-and-ledger civic identity and ensure legible ink-style contrasts.

### Foundational Palette
- **Canvas Base (`#F6F1E4`):** Warm cream foundation that eliminates screen glare and mimics natural unbleached paper.
- **Surface Layer (`#FFFDF7`):** Ivory surface for cards, dialog sheets, map control overlays, and inputs.
- **Structural Border (`#E5DECC`):** Linen 1px solid hairline dividers defining all cards, rows, and input perimeters.
- **Primary Brand (`#4F6F52`):** Deep sage used for top app navigation bars, active segment tabs, primary operational buttons, and verified identity badges.
- **Accent & Interaction (`#C9A227`):** Muted gold for focus indicators, selection rings, subtle highlighted tags, and inline textual actions.
- **Primary Text (`#22302A`):** Charcoal green with high contrast against Ivory and Cream, offering deep editorial legibility without the harshness of pure `#000000`.
- **Secondary Text (`#5E6B63`):** Slate sage for timestamps, metadata, secondary instructions, and structural captions.

### Civic Status Palette
- **Widely Reported Scam:** Solid brick red (`#B5452F`) container border (4px structural indicator) over a 10% tinted tint background (`#B5452F1A`).
- **Moderate Reports / Caution:** Warm amber (`#D99A1E`) accent border over a 10% tinted background (`#D99A1E1A`).
- **No Reports / Unreported:** Muted warm grey (`#8A8577`) perimeter for unverified or neutral entities over transparent/ivory cards.
- **Verified Authentic Business:** Leaf green (`#2E8B57`) indicator border with a 10% tinted tint background (`#2E8B571A`).

*Constraint:* Under no circumstances should purple, bright cyan, saturated primary blues, or metallic gradients enter the palette.

## Typography

The type system pairs the literary authority of **Literata** (with Noto Serif Devanagari fallback) with the functional clarity of **Source Sans 3** (with Noto Sans Devanagari fallback). 

### Layout Hierarchy Rules
- **Editorial Headings:** All section headings, entity names, incident titles, and official metrics use Literata. Its sculpted serifs and bookish weight communicate long-standing institutionality and deliberate review.
- **Dynamic Mobile Sizing:** Body text on mobile viewports defaults to 17px with a relaxed 26px line height. On desktop screens, it transitions to 16px with 24px line height to suit narrower reading columns.
- **Language Inclusivity:** Font fallback stacks must always chain `Source Sans 3, "Noto Sans Devanagari", sans-serif` for body copy, and `Literata, "Noto Serif Devanagari", serif` for display. Letter-spacing on Indian language text runs must remain neutral (`0em`) to prevent conjunct glyph breakage.
- **Labels & Forms:** Field headers, verification chips, table rows, and button calls-to-action use Source Sans 3 Semibold (`fontWeight: 600`) to guarantee fast optical identification under bright daylight conditions.

## Layout & Spacing

The layout is grounded in a responsive fluid-grid structure that shifts gracefully between hand-held mobile field use and desktop municipal monitoring.

### Breakpoints & Layout Architecture
- **Mobile (< 640px):** Single column. Safe margins of 16px (`1rem`). The map takes full viewport height while community incident lists and verification lookups anchor into bottom-anchored sheets.
- **Tablet (640px - 1023px):** 6-column fluid grid. Outer margins of 24px (`1.5rem`) with 16px gutters. Split-view layouts divide map context (60%) and card incident details (40%).
- **Desktop (≥ 1024px):** 12-column structured layout capped at a maximum width of 1280px. 40px (`2.5rem`) margins with 24px (`1.5rem`) gutters. Side-by-side persistent navigation, dedicated filter drawer, and dual-pane verification maps.

### Spacing Model
Spacing increments follow an arithmetic cadence centered around 4px and 8px units. Content elements use tight internal breathing room (`space-md` or `space-lg`), while sectional transitions and form card separations rely on `space-xl` and `space-2xl` to mimic official form segments.

## Elevation & Depth

This design system rejects ambient drop shadows, multi-tiered z-index stacks, and skeuomorphic embossing. Depth is conveyed strictly through **tonal paper layering** and crisp structural outlines.

### Architectural Rules
- **Flat Baseline:** All static cards, forms, tables, headers, and banners rest entirely flat on the canvas without elevation shadows. Distinction is achieved solely by setting `#FFFDF7` (Ivory) surfaces against the `#F6F1E4` (Warm Cream) page background, bound by 1px solid `#E5DECC` (Linen).
- **Floating Overlays (Exception Rule):** Drop shadows are restricted exclusively to mobile bottom sheets, transient toast notices, and floating zoom/layer toggles placed over the active scam map.
- **Shadow Specifications:** When required, the floating shadow must be singular, muted, and tinted with the neutral tone: `box-shadow: 0 4px 16px -2px rgba(34, 48, 42, 0.12), 0 2px 6px -1px rgba(34, 48, 42, 0.06)`. Pure black shadows are prohibited.
- **Scam Result Callouts:** High-severity warnings use left-anchored 4px solid borders (`#B5452F`) rather than elevated layers or pop-out modals, reinforcing the look of marked index cards.

## Shapes

All interactive containers, surface cards, alert banners, and form fields share a consistent corner radius of **12px (`0.75rem`)**. This softens the civic utility into an approachable community tool without feeling playful or toy-like.

### Corner Radius Standards
- **Containers & Surfaces:** Cards, bottom-sheet top corners, filter dialogs, and verification result boxes use 12px corners.
- **Inputs & Buttons:** Search bars, text inputs, dropdown triggers, and buttons use 12px corners.
- **Interactive Tags & Badges:** Category chips and status badges retain 8px corners to maintain visual hierarchy against primary structural surfaces.
- **Prohibitions:** Circular pill-shaped buttons (`9999px`) are reserved exclusively for icon-only floating map controls. Standard action buttons and text badges must never use pill radiuses.

## Components

All components must respect a strict minimum interactive hit area of **48×48px** for touch accessibility. Every icon used across the design system must render with a uniform **1.75px stroke** and must always sit alongside a descriptive textual label.

### 1. Primary & Secondary Buttons
- **Primary Button:** `#4F6F52` (Deep sage) solid fill, `#FFFDF7` text, 12px corner radius, height 48px, horizontal padding `24px` (`space-xl`). Hover state shifts to `#425D45`.
- **Secondary Button:** Surface `#FFFDF7`, 1px solid border `#4F6F52`, text `#4F6F52`.
- **Ghost/Destructive:** Surface transparent, 1px solid border `#E5DECC`, text `#B5452F` for flagging reports.
- **Focus Rings:** 2px solid `#C9A227` offset by 2px against all button boundaries.

### 2. Search & Verification Input Fields
- **Container:** Height 52px, surface `#FFFDF7`, border 1px solid `#E5DECC`, radius 12px.
- **Text:** 17px mobile / 16px desktop in `#22302A`. Placeholder text in `#5E6B63`.
- **Icon Attachment:** Search magnifying glass (1.75px stroke, `#5E6B63`) placed leading; "Clear" or "Verify UPI/Phone" text button placed trailing.
- **Focus State:** 1px solid `#4F6F52` perimeter accompanied by a 2px outer ring in `#C9A227`.

### 3. Verification & Report Result Cards
- **Base Style:** 12px radius, `#FFFDF7` background, 1px solid `#E5DECC` perimeter.
- **Widely Reported Scam:** Left border amplified to 4px solid `#B5452F`. Header alert surface rendered in 10% tinted brick red (`#B5452F1A`). Sub-text explicitly lists report tally and latest reported location.
- **Some Reports (Amber):** Left border amplified to 4px solid `#D99A1E`. Header surface rendered in 10% tinted amber (`#D99A1E1A`).
- **Verified Business (Leaf Green):** Left border amplified to 4px solid `#2E8B57`. Header surface rendered in 10% tinted green (`#2E8B571A`) with an authentic seal icon (1.75px stroke) and "Govt / Bank Registered" label.
- **No Reports (Neutral):** Standard 1px solid `#E5DECC` card perimeter. Header badge in `#8A8577` outlines.

### 4. Status Chips & Category Filter Tabs
- **Filter Chip:** Height 36px, radius 8px, surface `#FFFDF7`, border 1px solid `#E5DECC`, text `#5E6B63`.
- **Selected Filter Chip:** Surface `#4F6F52`, border 1px solid `#4F6F52`, text `#FFFDF7`. Accompanied by a checkmark icon (1.75px stroke).
- **Status Badges:** Text in uppercase 12px Source Sans 3 (`fontWeight: 600`), 8px radius, padded 6px vertical by 10px horizontal. Paired with a 6px solid circular status dot to avoid relying on color alone.

### 5. Checkboxes, Radio Buttons & Switches
- **Checkbox:** 22×22px box, radius 4px, 1.5px solid border `#5E6B63`, surface `#FFFDF7`. When checked: surface `#4F6F52`, border `#4F6F52`, checkmark icon `#FFFDF7` with 2px stroke.
- **Radio Button:** 22×22px circular frame, 1.5px solid border `#5E6B63`. When selected: interior 10px circle in `#4F6F52`.
- **Hit targets:** The surrounding label container must always expand to a minimum 48px height touch target.

### 6. Incident Lists & Data Feeds
- **Row Architecture:** Background `#FFFDF7`, bordered bottom with 1px solid `#E5DECC`.
- **Padding:** 16px vertical, 16px horizontal.
- **Content Hierarchy:** Top row displays incident categorization tag and time elapsed ("UPI Impersonation • 2 hrs ago"). Second row highlights the masked identifier or merchant name in Literata Semibold. Third row presents human-written context notes in 14px slate sage.

### 7. Civic Map Pins & Floating Overlays
- **Map Pins:** Physical drop-pin silhouette rendered with flat solid fills (`#B5452F` scam, `#D99A1E` caution, `#2E8B57` verified) with a crisp 1.5px `#FFFDF7` outline. Pins are anchored with an unambiguous numeric count or category symbol.
- **Map Floating Bottom Sheet:** Restricted to mobile viewports. `#FFFDF7` surface, top radius 16px, 1px solid `#E5DECC` border, elevated using the ambient tinted drop shadow. Includes an accessible drag indicator pill (36×4px in `#E5DECC`).