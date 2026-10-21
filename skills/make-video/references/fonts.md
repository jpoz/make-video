# Fonts

`./make.sh setup` downloads the default fonts and their license files into `fonts/`. To repeat
only that step, use `./make.sh fonts`. Downloads use fixed upstream revisions in `doctor.py`.
The default theme stops with a clear error if either required family cannot load.

For an offline project, copy the `fonts/` folder from a prepared project, including both OFL
license files. `theme.mjs` registers every `.ttf` or `.otf` file under its embedded family name.

## The default pair

`theme.mjs` uses **Atkinson Hyperlegible** (body and titles) and **JetBrains Mono** (code, labels,
and the fallback for arrows and symbols such as → ↔ ✓ ⋯). Both use the SIL Open Font License.
Setup fetches full font files, not web subsets, so symbols are present. For a manual download,
use the URLs listed in `doctor.py`, or run its standard-library installer:

```sh
python3 doctor.py --install-fonts
```

## Other families

- **Google Fonts, static files:** `https://github.com/google/fonts/tree/main/ofl/<family>`. Many
  families now ship only a variable font (`Family[wght].ttf`). `@napi-rs/canvas` can draw only
  the default instance of a variable font, so use static files when you need more than one weight.
- **Fontsource (any Google font, one file per weight):**
  `https://cdn.jsdelivr.net/fontsource/fonts/<slug>@latest/<subset>-<weight>-<style>.ttf`.
  For example: `inter@latest/latin-600-normal.ttf`. The `latin` subset has no arrows or box
  symbols, so keep JetBrains Mono as the fallback in the font stack.
- **The product's own brand font:** if the film is about a product, use its real typeface when the
  repo or the site has the files (look for `*.woff2`, `*.ttf`, or `@font-face` in its CSS). Convert
  a `.woff2` file to `.ttf` before you use it (`pip install fonttools brotli`, then
  `python -c "from fontTools.ttLib import TTFont; f=TTFont('x.woff2'); f.flavor=None; f.save('x.ttf')"`).
- **System fonts:** on macOS, `/System/Library/Fonts` and `/Library/Fonts` hold fonts such as
  Avenir Next and Menlo. Do not copy them into a project you share.

After you add a family, change `SANS`, `MONO` or `DISPLAY` and the required-family check in
`theme.mjs`. Keep the font's license with the files. Then run
`./make.sh samples 6` and look at the sheet to make sure the new face is in use. A silent fallback
looks like Helvetica or Arial.
