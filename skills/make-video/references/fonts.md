# Fonts

The skill ships no font files. Put them in the project's `fonts/` folder. `theme.mjs` registers
every `.ttf` or `.otf` file there under the family name inside the file. If the folder is empty,
the film renders with system fonts and `theme.mjs` prints a warning. Do not render a film for
review in that state: the type will not match the storyboard.

## The default pair

`theme.mjs` uses **Atkinson Hyperlegible** (body and titles) and **JetBrains Mono** (code, labels,
and the fallback for arrows and symbols such as → ↔ ✓ ⋯). Both use the SIL Open Font License.
Get the full font files, not web subsets, so that the symbols are there:

```sh
mkdir -p fonts && cd fonts
G=https://raw.githubusercontent.com/google/fonts/main/ofl/atkinsonhyperlegible
curl -fsSLO $G/AtkinsonHyperlegible-Regular.ttf
curl -fsSLO $G/AtkinsonHyperlegible-Bold.ttf
curl -fsSLO $G/AtkinsonHyperlegible-Italic.ttf
J=https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/fonts/ttf
curl -fsSLO $J/JetBrainsMono-Regular.ttf
curl -fsSLO $J/JetBrainsMono-Medium.ttf
curl -fsSLO $J/JetBrainsMono-Bold.ttf
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

After you add a family, change `SANS`, `MONO` or `DISPLAY` in `theme.mjs`. Then run
`./make.sh samples 6` and look at the sheet to make sure the new face is in use. A silent fallback
looks like Helvetica or Arial.
