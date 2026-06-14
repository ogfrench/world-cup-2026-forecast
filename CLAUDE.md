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
- App and doc copy is for the reader, not the author. Cut filler and tighten relentlessly.
  No first-person voice ("I tested", "I take"), no notes-to-self, no "the classic trap" style
  asides. Say it in fewer words. If a sentence only explains your own process, delete it.

## Repo layout

- `index.html` - the deployed app, self-contained. This is a built artifact. DO NOT hand-edit.
- `netlify.toml` - tells Netlify to serve the repo root as static files.
- `og.png` - the 1200x630 social-share card (og:image / twitter:image). Regenerate with `python source/make_og.py`.
- `source/` - everything real behind it:
  - `wc2026_template.html` - the app source. Edit this for any app change. Has one `/*DATA*/` token.
  - `wc2026_results.json` - the live 50,000-run output the app renders (conditioned on played games, with the fixture schedule merged in and each team's Day 0 values attached).
  - `wc2026_baseline.json` - the frozen Day 0 (pre-tournament) snapshot the live before/after compares against.
  - `wc2026_actuals.json` - the played group results that condition the live run. Refreshed from the feed by `fetch_actuals.py`.
  - `wc2026_schedule.json` - the official 72-match group schedule (date, kickoff, home/away, venue), parsed from the public openfootball dataset. Data, so it lives here, not in the template.
  - `make_data.py` - the data generator: runs the engine unconditioned (Day 0) and conditioned (live) from one shared calibration, writes both JSON files. This is the regeneration entry point.
  - `fetch_actuals.py` - pulls played group games from the openfootball feed into `wc2026_actuals.json` (engine names, official home/away).
  - `merge_schedule.py` - merges the schedule into `wc2026_results.json`: annotates each group match with its date/venue and reorients home/away to the official side. Idempotent, no re-simulation.
  - `build_app.py` - injects the JSON into the template and writes `index.html`.
  - `check_app.js` - CI sanity check: script blocks parse, five models present, file is built.
  - `test_pipeline.py` - tests for the update pipeline (feed parse, home/away orientation, engine conditioning + validation). Stdlib unittest; engine tests skip without numpy. Run: `python -m unittest discover -s source -p 'test_*.py'`.
  - `test_app.js` - tests the built app's live layer (the in-play/awaiting badge clock, the in-browser feed parser), run against `index.html`. Run: `node source/test_app.js`.
  - `wc2026_engine.py` - the simulation engine (all five models, FIFA Annex C, knockout logic, conditional mode).
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

To regenerate the data itself: `python source/fetch_actuals.py` (refresh the played games from
the feed), then `python source/make_data.py 50000` (writes `source/wc2026_results.json` live and
`source/wc2026_baseline.json` Day 0), then `python source/merge_schedule.py` to fold the fixture
schedule back in (dates and official home/away), then rebuild as above. CI does not run the engine
or the merge; it only checks `index.html` is in sync with the committed JSON.

The live odds update on their own: `.github/workflows/refresh.yml` runs this pipeline on a windowed
cron, but only when `wc2026_actuals.json` actually changes (a new played game), and commits the
result so Netlify redeploys. Both the Action and the in-browser polling stop a week after the final
(the sundown cutoff, 26 Jul).

Live actual results also overlay in the browser at runtime from the openfootball feed (public,
CORS-enabled, no key); see the live-results block in the template. That overlay is deterministic and
never changes the static odds; only the Action re-conditions them.

## Front-end conventions

- Plain vanilla JS in three `<script>` blocks, no libraries. The first is the injected
  `DATA`, the second is the app (one IIFE that renders everything), the third is the tooltip engine.
- Tooltips: add a `data-tip="..."` attribute to any element. Event delegation means elements
  that `render()`/`renderSchedule()`/`renderNL()` add later get tooltips for free. `data-tip` may contain simple `<b>` markup.
- Live results: fetched in the browser from a CORS-enabled feed, cached in localStorage, refreshed
  adaptively (faster while a match is in play, paused when the tab is hidden). The render code is
  feed-agnostic: swap `ACT_SRC` and `parseActuals` to change source. Never block render on the fetch.
- Responsive: a single max-width column with breakpoints at 760, 520, and 360 px. Tables scroll
  horizontally on small screens. Do not try to reflow them into cards.
- The app opens on Pure Market (`let CUR = 'market_pure'`). Keep it that way unless the
  recommendation actually changes.

## CI and deploy

`.github/workflows/ci.yml` runs on push and PR. It checks that `index.html` is in sync with the
template and data (`build_app.py --check`), that the results JSON is valid, that the page's
script blocks parse, and that the test suites pass (`test_pipeline.py`, `test_app.js`). CI does not
install numpy, so the engine tests skip there; the refresh Action (which installs numpy) runs the full
suite before it commits a refreshed forecast. CI does not deploy. Netlify deploys automatically on
every push to `main`.

## Local preview

Open `index.html` directly in a browser, or serve the folder: `python -m http.server 8000`.

## Where it is going

Keep the scope narrow. This is a simple, elegant forecast viewer, the same tournament seen five
ways, not a prediction game like Scorito. No user picks, no scorelines to fill in, no points, no
leaderboard.

Shipped (issue #1):
- Matches sorted by date: a Schedule tab (all fixtures by date) and date-ordered fixtures under
  each group card. Home/away corrected from the official 2026 fixture list.
- Live actual results fetched in the browser and overlaid on the predictions. Each played match
  shows the model's predicted score colour-coded against the result (dark green exact, green right
  result, red wrong).
- Groups show the live table set against the model's predicted finishing position, with an arrow
  for who is beating or missing the forecast. Match predictions collapse behind a toggle.
- Title Race and Knockout Odds merged into one Title & Knockout tab; the page is titled
  "World Cup 2026 Forecast".
- Model switcher pinned with the tabs in a sticky bar: pills on desktop, a dropdown on mobile.
  Tab switches no longer force a scroll to the top.

Still cut: the full user-prediction game (Scorito-style picks, scoring, leaderboard). Backlog: a
full knockout bracket diff, which only becomes meaningful once the round-of-32 is set. Do not
overkill it.
