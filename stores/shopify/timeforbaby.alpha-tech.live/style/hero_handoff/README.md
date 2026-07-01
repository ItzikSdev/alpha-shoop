# Handoff: TIMEFOR BABY — Homepage Hero

## Overview
A premium, editorial hero section for the TIMEFOR BABY storefront (organic-cotton baby
essentials). Headline: **"Soft. Modern. Made for first moments."** It replaces the previous
version where the copy sat on a translucent dark box over the photo (illegible/broken-looking).
This version puts the copy on its own calm cream panel beside the photo, so it's always readable.

## About the Design Files
`hero.html` + `hero.css` are a **plain, framework-free reference implementation** — real,
working HTML/CSS you can open directly in a browser. They are NOT tied to any runtime.
Recreate this in your codebase using its existing patterns (React/Vue/Liquid/etc.). If you're
on Shopify, this maps cleanly to a section + schema with the headline, subtitle, button label,
and image as settings.

## Fidelity
**High-fidelity.** Final colors, type, spacing, and hover states are specified below and in
`hero.css`. Recreate pixel-faithfully, then wire the photo/copy to your CMS or section schema.

## Screen: Hero
- **Purpose:** First impression of the store; drive into the collection.
- **Layout:** CSS grid, 2 columns `1.05fr / 1fr`, `min-height: 760px`. Left = copy panel
  (cream `#f3efe9`); right = full-bleed lifestyle photo. Stacks to 1 column under 860px.
- **Left panel:** vertically centered, padding `88px clamp(48px,6vw,110px)`.
  - Eyebrow: 26px rule + "ORGANIC COTTON ESSENTIALS", 12.5px / 600 / 0.22em tracking / uppercase / `#9a7a6a`.
  - H1: Newsreader serif 400, `clamp(44px,5vw,76px)`, line-height 1.02, `#2e2722`;
    second line "Made for first moments." italic in terracotta `#b07a5f`.
  - Subtitle: Archivo, `clamp(16px,1.25vw,19px)`, line-height 1.6, `#6b5f56`, max-width 30ch.
  - Primary button: solid `#2e2722`, text `#f3efe9`, 13.5px/600/0.14em uppercase, radius 2px;
    hover → background `#b07a5f` + translateY(-2px).
  - Secondary link "Our story": underlined, `#2e2722`.
  - Two stats: "100% GOTS organic" / "1,000+ Happy parents", numbers in Newsreader 26px.
- **Right panel:** the photo. Placeholder shown via diagonal stripes; replace per the comment
  in `hero.css`. A left-edge cream gradient fade makes the seam read intentional.
- **Carousel dots:** bottom-right, active = 22px pill `#2e2722`, inactive = 8px `rgba(46,39,34,.3)`.

## Interactions
- Button + link hover states only (above). Dots are presentational here — wire to your
  existing carousel/slider if the hero rotates.

## Design Tokens
- Cream bg `#f3efe9` · Ink `#2e2722` · Terracotta `#b07a5f` · Muted brown `#6b5f56`
  · Eyebrow brown `#9a7a6a` · Rule `#b98e7a` · Photo teal `#a9c4c2` · Divider `#ddd2c6`.
- Fonts: **Newsreader** (serif display), **Archivo** (sans) — Google Fonts.
- Radius 2px · Stat gap 40px · Button padding `17px 34px`.

## Assets
- One lifestyle photo (mother + baby). Not included — supply your own; placeholder marks the spot.

## Files
- `hero.html` — markup
- `hero.css` — all styles (commented, with the photo-swap instructions inline)
