# World Cup 2026 Forecast

[![CI](https://github.com/ogfrench/world-cup-2026-prediction/actions/workflows/ci.yml/badge.svg)](https://github.com/ogfrench/world-cup-2026-prediction/actions/workflows/ci.yml)

**Live: https://wc2026forecast.xyz/**

A Monte Carlo forecast of the 2026 World Cup. It plays the full tournament, all 104 matches and the
knockout bracket, 50,000 times under five match-rating models and reports each team's probability of
reaching every stage. As games are played, real results overlay onto the predictions and the odds
re-simulate to condition on what has happened, so you see both where the forecast is holding up and
how the title race is shifting against its Day 0 starting point.

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

- **Title Odds** - each team's chance of winning the tournament, plus how often it reaches each round, against Opta and the betting market as a sanity check. Once games are played the odds re-condition on the results, with a Day 0 marker on each bar showing the pre-tournament starting point and the move since; the reach-round table can flip to show the change since Day 0.
- **Schedule** - every fixture by kickoff time, the model's predicted score, and the real result as it comes in, color-coded (dark green exact, green right result, red wrong).
- **Groups & Scores** - the live group table against where the model predicted each team to finish, marking who is ahead of the forecast and who is behind. Expand a group for its match predictions and results.
- **Knockout Phase** - a placeholder until the round-of-32 is set, then the predicted bracket against the real results.
- **Top Scorers** - the betting market's pre-tournament Golden Boot pick next to a live leaderboard of who is actually scoring, parsed from the feed. The engine rates teams, not players, so the expected side is the market, not the simulation.
- **Method & Caveats** - the write-up, the validation, and the honest weaknesses.
- **Netherlands** and **France** - a per-model, game-by-game timeline for a single team.

## How it works

The simulation is plain Python, no ML framework, all in [`source/`](source/):

- **`wc2026_engine.py`** runs the tournament: the group stage, the eight best third-placed teams, the official FIFA Annex C round-of-32 (all 495 possible line-ups), then the knockout bracket with extra time and penalties. Each match's expected goals come from the chosen model, and the score is drawn from a Dixon-Coles-adjusted Poisson. Conditioned on the played games, it locks those results and samples only the rest.
- **`make_data.py`** runs the engine twice per model from one shared market calibration, unconditioned (the frozen Day 0 baseline) and conditioned on the played games (the live forecast), and writes both `wc2026_results.json` and `wc2026_baseline.json`. **`fetch_actuals.py`** refreshes the played-results file (`wc2026_actuals.json`) from the openfootball feed.
- **`merge_schedule.py`** folds the official fixture schedule (`wc2026_schedule.json`, from the public openfootball dataset) into the results: the date, kickoff, venue, and the correct home/away side for every group match.
- **`fit_dc.py`** fits the Dixon-Coles model by weighted maximum-likelihood on 15,431 internationals since 2010 (recent matches count for more). **`build_params.py`** combines those fitted parameters with official Elo ratings into `model_params.json`.
- **`val_assess.py`** and **`val_market.py`** are the validation: out-of-sample scoring on 1,230 held-out internationals, and a market-versus-model backtest on 5,327 club matches with real closing odds.

The page itself runs no Python. It only reads the pre-computed JSON, which is why it can be a single static file.

## Live results and the self-updating forecast

Two layers keep the page current, both backend-free and low-maintenance:

- **In the browser (instant).** As games are played, the real result appears next to each prediction.
  The page fetches results from the public, CORS-enabled [openfootball](https://github.com/openfootball/worldcup)
  World Cup 2026 feed (no key), caches them in local storage, and refreshes adaptively (faster while a
  match is in play, paused when the tab is hidden). This overlay is deterministic: it never alters the
  underlying odds, and if the feed is unreachable the page falls back to predictions only. A kicked-off
  match shows an "In play" badge, then an "Awaiting result" badge that stays until the feed posts the
  score (the community feed can lag by hours), each linking to a search so you can check the score
  meanwhile. The badge never expires early, so a played game never reverts to looking unplayed.
- **The odds themselves (on redeploy).** A scheduled GitHub Action (`.github/workflows/refresh.yml`)
  re-runs the 50,000-tournament simulation conditioned on the played games and commits the result, so
  Netlify redeploys. It polls the feed on a windowed cron but only re-simulates when a new result
  actually lands, and validates the output before committing. Title Odds then shows each team's live
  chance against its frozen Day 0 baseline.

Both layers stop a week after the final (the "sundown" cutoff): the page stops polling and the Action
stops running. The fetch is feed-agnostic: swap `ACT_SRC` and `parseActuals` in the template to use a
JSON API instead.

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

## Tests

A small, dependency-free suite covers the code that keeps the app current, so the self-updating path
stays trustworthy with no babysitting. CI runs all of it on every push and PR.

```
python -m unittest discover -s source -p 'test_*.py'   # update pipeline (Python)
node source/check_app.js                               # build is clean, every script block parses
node source/test_app.js                                # the in-browser live layer (JavaScript)
```

### What the tests guard

The fragile surface is the live layer: it parses a public, hand-edited, free-text feed (openfootball)
that has no schema and can change format without warning. Most of these tests exist because that feed
has bitten us, so they pin the exact edge cases:

- **Feed parsing** (`test_pipeline.py`, `test_app.js`). A played game with no half-time score still
  parses, so it is not silently dropped from the conditioned odds. An unplayed " v " fixture is
  skipped, not invented. Official FIFA names the feed warns it may switch to (Cote d'Ivoire, Korea
  Republic, IR Iran, Cabo Verde, Congo DR, Turkiye) map to the engine names, so a renamed game is not
  lost. A name that maps to nothing is flagged and skipped, never guessed into a phantom knockout tie.
- **Scorer parsing** (`test_app.js`). A penalty written in the feed's shorthand `(p)` credits the
  scorer instead of inventing a player called "p". An own goal `(og)` does not credit the scorer. A
  scorer block that spans several lines is gathered whole. CRLF line endings parse the same as LF.
- **Live badge clock** (`test_app.js`). A played game whose result the feed has not posted yet keeps
  its "Awaiting result" badge with no upper time bound, instead of silently looking unplayed.
- **Score colouring** (`test_app.js`). The predicted-versus-actual colour is graded on the scoreline
  the card shows, so a drawn prediction can never read green against a decisive result.
- **Orientation and engine invariants** (`test_pipeline.py`). Reorienting a match to the official
  home/away is its own inverse. The engine conditions on played games and validates its output
  (champion shares sum near 100, reach-round odds never rise from one round to the next). The engine
  tests need numpy and skip when it is absent, as in light CI; the refresh Action installs it and runs
  them before committing a refreshed forecast.

### End to end

`source/test_feed_sample.txt` is a small, representative feed that packs every edge case above into
one file. Both `test_pipeline.py` and `test_app.js` run it through their full parsers and assert the
overlay, the group rows, the knockout split, and the scorer board, so a feed-format change cannot
regress one side without failing the suite. When you find a new feed quirk, add a line to that fixture
and an assertion to both suites.

To regenerate the simulation, run `python source/make_data.py 50000` (the live + Day 0 generator,
which conditions on `wc2026_actuals.json`), then `python source/merge_schedule.py` to fold the
fixture schedule back in, then rebuild. `python source/fetch_actuals.py` refreshes the played-results
file from the feed first.

## Run locally

Open `index.html` in a browser, or run `python -m http.server` from the repository root.

## Deployment

Deployed on Netlify, served from the repository root and redeployed on each push to `main`. Live at
<https://wc2026forecast.xyz/>, with a backup at <https://wc2026forecast.netlify.app/>.

## Roadmap

Intentionally narrow: a forecast viewer, not a prediction game. Tracked in
[issue #4](https://github.com/ogfrench/world-cup-2026-prediction/issues/4). Shipped: matches sorted by
date, home/away corrected from the official fixture list, live results overlaid with color-coded
accuracy, a live group table against the predicted finish, the conditional live title odds with a Day 0
before/after, the autonomous refresh, and the Top Scorers tab. The predicted-vs-actual knockout bracket
waits for the round-of-32 to be set (around June 28). User picks, scoring, and a leaderboard stay out of
scope.

## Disclaimer

A transparent baseline built from public data, not tested against a real World Cup. Not betting advice.
