# World Cup 2026 Prediction Engine

[![CI](https://github.com/ogfrench/world-cup-2026-prediction/actions/workflows/ci.yml/badge.svg)](https://github.com/ogfrench/world-cup-2026-prediction/actions/workflows/ci.yml)

A Monte Carlo simulation of the 2026 World Cup. It runs the full tournament, all 104 matches and the
knockout bracket, 50,000 times under five match-rating models and reports each team's probability of
reaching every stage.

The app is a single self-contained `index.html` with no dependencies. It opens on the market-based
model; the five models can be switched within the page.

## Models

All five share the same tournament engine (FIFA Annex C round-of-32, extra time, penalties) and
differ only in how each match's expected goals are estimated.

- **Pure Elo** - results-only ratings.
- **Score (Dixon-Coles)** - team attack and defense fitted from 15,431 internationals.
- **Hybrid** - the average of Pure Elo and Dixon-Coles.
- **Model + Market** - the Hybrid blended with the betting market.
- **Pure Market** - the betting market, calibrated to published title odds. The default view.

Methodology and validation are in [source/REPORT.md](source/REPORT.md).

## Layout

- `index.html` - the built app. Generated, not edited by hand.
- `netlify.toml` - static hosting configuration.
- `CLAUDE.md` - contributor notes: the build rule and conventions.
- `source/` - the simulation engine, parameters, validation scripts, and the app template. See [source/README.md](source/README.md).

## Build

Changes go in `source/wc2026_template.html`; `index.html` is generated from it.

```
python source/build_app.py          # rebuild index.html
python source/build_app.py --check  # verify index.html is in sync (CI)
```

Regenerate the simulation data with `python source/wc2026_engine.py 50000`, then rebuild.

## Run locally

Open `index.html` in a browser, or run `python -m http.server` from the repository root.

## Deployment

Deployed on Netlify from the repository root, redeploying on each push to `main`.

## Disclaimer

A transparent baseline built from public data, not tested against a real World Cup. Not betting advice.
