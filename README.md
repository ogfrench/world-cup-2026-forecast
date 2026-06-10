# World Cup 2026 Prediction Engine

[![CI](https://github.com/ogfrench/world-cup-2026-prediction/actions/workflows/ci.yml/badge.svg)](https://github.com/ogfrench/world-cup-2026-prediction/actions/workflows/ci.yml)

Who actually wins the World Cup? This plays out all 104 matches and the full knockout bracket
50,000 times over, five different ways, from cold results to the betting market, and shows where
they agree and disagree. It opens on the market's view, the smartest single guess. Hover anything
for a plain-English explanation.

The page itself is one self-contained `index.html`: no server, no dependencies, no framework. It
works offline if you just open the file.

## The five ways it guesses

- **Pure Elo** - ranks teams on results alone, like a chess rating. Backs the favorites hardest.
- **Score (Dixon-Coles)** - learns each team's attack and defense from 15,431 real internationals.
- **Hybrid** - the two above, averaged. The best guess built from results alone.
- **Model + Market** - the Hybrid nudged halfway toward the betting market.
- **Pure Market** - the bookmakers alone, calibrated to the published title odds. The default view.

Same tournament underneath every time. The fun is in where the five disagree.

## Live

Deployed on Netlify, which serves `index.html` at the root and redeploys on every push to `main`.

First-time setup (one time only): go to [app.netlify.com](https://app.netlify.com), "Add new site" >
"Import an existing project", pick this repo, leave the build command empty and the publish directory
as `.` (the included `netlify.toml` already sets this). Every push after that updates the live site.

Quickest possible alternative, no GitHub: drag the folder onto
[app.netlify.com/drop](https://app.netlify.com/drop) and it is live in seconds.

## What's in here

- `index.html` - the deployed app, self-contained. A built artifact, do not hand-edit it.
- `netlify.toml` - tells Netlify to serve the repo root as-is.
- `CLAUDE.md` - how to work on the repo (the build rule, conventions, the keep-it-simple note).
- `.github/workflows/ci.yml` - CI: checks the build is in sync and the app parses.
- `source/` - the full project behind it, so the repo is real and reproducible:
  - `wc2026_template.html` - the app's source, with a `/*DATA*/` slot where the results get injected.
  - `wc2026_results.json` - the 50,000-run output the app reads.
  - `build_app.py` - builds `index.html` from the template and the results.
  - `wc2026_engine.py` - the simulation engine (all five models, calibration, the official FIFA bracket).
  - `model_params.json`, `annexc_data.py` - fitted parameters and the official round-of-32 table.
  - `fit_dc.py`, `build_params.py` - the fitting pipeline.
  - `val_assess.py`, `val_market.py` - the validation tests (model accuracy, and model vs market).
  - `REPORT.md`, `CLAUDE.md` - the full write-up and the model handoff doc.

## Rebuilding it

The page is generated, so changes go in the template, not in `index.html`.

```
python source/build_app.py          # rebuild index.html from the template + results
python source/build_app.py --check  # verify index.html is in sync (CI runs this)
```

To regenerate the numbers themselves: `python source/wc2026_engine.py 50000` rewrites
`source/wc2026_results.json`, then rebuild as above.

## The honest disclaimer

It is a transparent baseline built from public data, not an oracle, and it has never been tested on
a real World Cup. Great for the shape of the tournament. Not betting advice.

made with love by François
