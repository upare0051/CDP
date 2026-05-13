# Fonts

## Included
- **Proxima Nova** (Mark Simonson) — Light, Regular, Medium *(approx via Semibold)*, Semibold, Bold, Bold Italic, Extrabold, Black, plus italic complements. Loaded as `font-family: "Proxima Nova"` in `colors_and_type.css`.

## Substitutions / flagged for follow-up
- **Arquitecta** (Latinotype) — used heavily for tags, banners, eyebrows and the "Editorial" headline style. We do not have a license file. The CSS substitutes **Barlow** (Google Fonts) which has similar geometric proportions.
  - **Action for the user:** Drop the licensed `Arquitecta-*.otf` files into `/fonts` and add matching `@font-face` entries in `colors_and_type.css`. Then change `--font-tag` to put `"Arquitecta"` first.
- A few stray Figma uses of Poppins, SF Pro, Helvetica, Roboto, Futura — these are mostly placeholder mocks of OS chrome (iOS status bar, web search bars). Not part of the design system.
