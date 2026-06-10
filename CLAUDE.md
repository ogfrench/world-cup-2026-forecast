# CLAUDE.md

How to work on this repo. For the deep model details (the five models, the fitting,
the validation, the gotchas), read [source/CLAUDE.md](source/CLAUDE.md) and
[source/REPORT.md](source/REPORT.md). This file is about the repo and the build.

## Keep it simple (read this first)

This is a basic website, built for fun. Do not overkill it. No frameworks, no bundler,
no package.json, no TypeScript, no component library, no front-end test runner. If a
change can be a few lines of plain HTML, CSS, or vanilla JS in the template, that is the
right size. Match the existing style and move on. Reach for heavier tooling only if
something is genuinely broken without it. When in doubt, do less.

## What this is

A World Cup 2026 prediction site. One self-contained `index.html` that plays the whole
tournament out 50,000 times, five ways, and shows where the methods agree and disagree.
It is a static page: no build server, no backend, no dependencies. Netlify serves the
repo root as-is, so the homepage is the app.

## Working preferences (prose and commits)

- No em dashes. Use commas, parentheses, colons, or shorter sentences.
- No emojis. US English. Minimal formatting, no decorative bolding or bullet spam.
- Be honest and flag weaknesses. Do not oversell. One clear recommendation, not a menu.

## Repo layout

- `index.html` - the deployed app, self-contained. This is a built artifact. DO NOT hand-edit.
- `netlify.toml` - tells Netlify to serve the repo root as static files.
- `source/` - everything real behind it:
  - `wc2026_template.html` - the app source. Edit this for any app change. Has one `/*DATA*/` token.
  - `wc2026_results.json` - the 50,000-run output the app renders.
  - `build_app.py` - injects the JSON into the template and writes `index.html`.
  - `check_app.js` - CI sanity check: script blocks parse, five models present, file is built.
  - `wc2026_engine.py` - the simulation engine (all five models, FIFA Annex C, knockout logic).
  - `model_params.json`, `annexc_data.py` - fitted parameters and the official round-of-32 table.
  - `fit_dc.py`, `build_params.py` - the fitting pipeline (needs `results.csv`, which is not shipped).
  - `val_assess.py`, `val_market.py` - the validation tests.
  - `REPORT.md`, `CLAUDE.md` - the write-up and the model handoff doc.

## The one build rule

`index.html` is `wc2026_template.html` with the `/*DATA*/` token replaced by the contents of
`wc2026_results.json`. The template is the source of truth for everything the page looks like
and does. `index.html` is generated. So:

1. Make app changes in `source/wc2026_template.html`, never in `index.html`.
2. Rebuild: `python source/build_app.py`
3. Confirm it is in sync (CI runs this too): `python source/build_app.py --check`

To regenerate the data itself: `python source/wc2026_engine.py 50000` (writes
`source/wc2026_results.json`), then rebuild as above.

## Front-end conventions

- Plain vanilla JS in three `<script>` blocks, no libraries. The first is the injected
  `DATA`, the second is the app (one IIFE that renders everything), the third is the tooltip engine.
- Tooltips: add a `data-tip="..."` attribute to any element. Event delegation means elements
  that `render()`/`renderNL()` add later get tooltips for free. `data-tip` may contain simple `<b>` markup.
- Responsive: a single max-width column with breakpoints at 760, 520, and 360 px. Tables scroll
  horizontally on small screens. Do not try to reflow them into cards.
- The app opens on Pure Market (`let CUR = 'market_pure'`). Keep it that way unless the
  recommendation actually changes.

## CI and deploy

`.github/workflows/ci.yml` runs on push and PR. It checks that `index.html` is in sync with the
template and data (`build_app.py --check`), that the results JSON is valid, and that the page's
script blocks parse. CI does not deploy. Netlify deploys automatically on every push to `main`.

## Local preview

Open `index.html` directly in a browser, or serve the folder: `python -m http.server 8000`.

## Where it is going

Issue #1 tracks making the app future-proof as the tournament unfolds: actual scores next to
predictions, and letting users pick the knockout bracket, scorelines, and scorers themselves.
Keep that direction in mind. Still do not overkill it.
