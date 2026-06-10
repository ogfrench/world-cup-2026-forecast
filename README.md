# World Cup 2026 Prediction Engine

[![CI](https://github.com/ogfrench/world-cup-2026-prediction/actions/workflows/ci.yml/badge.svg)](https://github.com/ogfrench/world-cup-2026-prediction/actions/workflows/ci.yml)

A Monte Carlo simulation of the 2026 World Cup. It runs the full tournament, all 104 matches and the
knockout bracket, 50,000 times under five match-rating models and reports each team's probability of
reaching every stage.

The app is a single self-contained `index.html` with no dependencies, and the five models can be
switched within the page.

## Models

All five share the same tournament engine (FIFA Annex C round-of-32, extra time, penalties) and
differ only in how each match's expected goals are estimated.

- **Pure Elo** - ranks teams on results alone, like a chess rating. Simple, and the most favorite-heavy of the five.
- **Score (Dixon-Coles)** - learns each team's attack and defense from 15,431 internationals and predicts actual scorelines, not just a winner.
- **Hybrid** - the average of Pure Elo and Dixon-Coles. The best performer on out-of-sample tests.
- **Model + Market** - the Hybrid blended halfway with the ratings implied by the betting market.
- **Pure Market** - the betting market alone, calibrated so the simulated title odds match the published ones. The default view.

Methodology and validation are in [source/REPORT.md](source/REPORT.md).

## How it works

The simulation is plain Python, no ML framework, all in [`source/`](source/):

- **`wc2026_engine.py`** runs the tournament: the group stage, the eight best third-placed teams, the official FIFA Annex C round-of-32 (all 495 possible line-ups), then the knockout bracket with extra time and penalties. Each match's expected goals come from the chosen model, and the score is drawn from a Dixon-Coles-adjusted Poisson. Run 50,000 times, it produces `wc2026_results.json`, which the app reads.
- **`fit_dc.py`** fits the Dixon-Coles model by weighted maximum-likelihood on 15,431 internationals since 2010 (recent matches count for more). **`build_params.py`** combines those fitted parameters with official Elo ratings into `model_params.json`.
- **`val_assess.py`** and **`val_market.py`** are the validation: out-of-sample scoring on 1,230 held-out internationals, and a market-versus-model backtest on 5,327 club matches with real closing odds.

The page itself runs no Python. It only reads the pre-computed JSON, which is why it can be a single static file.

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
