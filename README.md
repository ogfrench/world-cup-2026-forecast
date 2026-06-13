# World Cup 2026 Forecast

[![CI](https://github.com/ogfrench/world-cup-2026-prediction/actions/workflows/ci.yml/badge.svg)](https://github.com/ogfrench/world-cup-2026-prediction/actions/workflows/ci.yml)

**Live: https://wc2026forecast.xyz/**

A Monte Carlo forecast of the 2026 World Cup. It plays the full tournament, all 104 matches and the
knockout bracket, 50,000 times under five match-rating models and reports each team's probability of
reaching every stage. As games are played, real results overlay onto the predictions, so you can see
where the forecast is holding up.

The app is a single self-contained `index.html` with no dependencies; switch between the five models
in the page.

## Models

All five share the same tournament engine (FIFA Annex C round-of-32, extra time, penalties) and
differ only in how each match's expected goals are estimated.

- **Pure Elo** - ranks teams on results alone, like a chess rating. Simple, and the most favorite-heavy of the five.
- **Pure Goals (Dixon-Coles)** - learns each team's attack and defense from 15,431 internationals and predicts actual scorelines, not just a winner.
- **Hybrid** - the average of Pure Elo and Dixon-Coles. The best performer on out-of-sample tests.
- **Hybrid + Market** - the Hybrid blended halfway with the ratings implied by the betting market.
- **Pure Market** - the betting market alone, calibrated so the simulated title odds match the published ones. The default view.

Methodology and validation are in [source/REPORT.md](source/REPORT.md).

## What the app shows

One model selected at a time (pills on desktop, a dropdown on mobile), across these tabs:

- **Title Odds** - each team's chance of winning the tournament, plus how often it reaches each round, against Opta and the betting market as a sanity check.
- **Schedule** - every fixture by kickoff time, the model's predicted score, and the real result as it comes in, color-coded (dark green exact, green right result, red wrong).
- **Groups & Scores** - the live group table against where the model predicted each team to finish, marking who is ahead of the forecast and who is behind. Expand a group for its match predictions and results.
- **Knockout Phase** - a placeholder until the round-of-32 is set, then the predicted bracket against the real results.
- **Method & Caveats** - the write-up, the validation, and the honest weaknesses.
- **Netherlands** and **France** - a per-model, game-by-game timeline for a single team.

## How it works

The simulation is plain Python, no ML framework, all in [`source/`](source/):

- **`wc2026_engine.py`** runs the tournament: the group stage, the eight best third-placed teams, the official FIFA Annex C round-of-32 (all 495 possible line-ups), then the knockout bracket with extra time and penalties. Each match's expected goals come from the chosen model, and the score is drawn from a Dixon-Coles-adjusted Poisson. Run 50,000 times, it produces `wc2026_results.json`, which the app reads.
- **`merge_schedule.py`** folds the official fixture schedule (`wc2026_schedule.json`, from the public openfootball dataset) into the results: the date, kickoff, venue, and the correct home/away side for every group match.
- **`fit_dc.py`** fits the Dixon-Coles model by weighted maximum-likelihood on 15,431 internationals since 2010 (recent matches count for more). **`build_params.py`** combines those fitted parameters with official Elo ratings into `model_params.json`.
- **`val_assess.py`** and **`val_market.py`** are the validation: out-of-sample scoring on 1,230 held-out internationals, and a market-versus-model backtest on 5,327 club matches with real closing odds.

The page itself runs no Python. It only reads the pre-computed JSON, which is why it can be a single static file.

## Live results

As games are played, the real result appears next to each prediction. The page fetches results in
the browser from the public, CORS-enabled [openfootball](https://github.com/openfootball/worldcup)
World Cup 2026 feed (no key, no backend), caches them in local storage, and refreshes adaptively
(faster while a match is in play, paused when the tab is hidden). Results overlay onto the static
predictions and feed the live group table; the prediction data itself never changes. If the feed is
unreachable, the page falls back to predictions only. The fetch is feed-agnostic: swap `ACT_SRC` and
`parseActuals` in the template to use a JSON API instead.

## Layout

- `index.html` - the built app. Generated, not edited by hand.
- `netlify.toml` - static hosting configuration.
- `CLAUDE.md` - contributor notes: the build rule and conventions.
- `source/` - the simulation engine, schedule, parameters, validation scripts, and the app template. See [source/README.md](source/README.md).

## Build

Changes go in `source/wc2026_template.html`; `index.html` is generated from it.

```
python source/build_app.py          # rebuild index.html
python source/build_app.py --check  # verify index.html is in sync (CI)
```

To regenerate the simulation, run `python source/wc2026_engine.py 50000`, then
`python source/merge_schedule.py` to fold the fixture schedule back in, then rebuild.

## Run locally

Open `index.html` in a browser, or run `python -m http.server` from the repository root.

## Deployment

Deployed on Netlify, served from the repository root and redeployed on each push to `main`. Live at
<https://wc2026forecast.xyz/>, with a backup at <https://wc2026forecast.netlify.app/>.

## Roadmap

Intentionally narrow: a forecast viewer, not a prediction game. Tracked in
[issue #1](https://github.com/ogfrench/world-cup-2026-prediction/issues/1). Shipped: matches sorted
by date, home/away corrected from the official fixture list, live results overlaid on the predictions
with color-coded accuracy, and a live group table compared against the predicted finish. A full
knockout bracket diff waits for the round-of-32 to be set. User picks, scoring, and a leaderboard are
out of scope.

## Disclaimer

A transparent baseline built from public data, not tested against a real World Cup. Not betting advice.
