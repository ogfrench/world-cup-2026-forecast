# World Cup 2026 Forecast

[![CI](https://github.com/ogfrench/world-cup-2026-forecast/actions/workflows/ci.yml/badge.svg)](https://github.com/ogfrench/world-cup-2026-forecast/actions/workflows/ci.yml)

**Live: https://wc2026forecast.xyz/**

A Monte Carlo forecast of the 2026 World Cup. The full tournament, all 104 matches, played out 50,000 times under five match-rating models, giving each team's odds to reach every stage. The real result sits beside every prediction, and the odds are conditioned on the games as they were played.

A single self-contained `index.html`, no dependencies. Pick a model in the page.

## Models

All five share one tournament engine (FIFA Annex C round-of-32, extra time, penalties) and differ only in how each match's expected goals are set.

- **Pure Elo** - results only, like a chess rating. The most favorite-heavy.
- **Pure Goals (Dixon-Coles)** - each team's attack and defense from 15,751 internationals; predicts scorelines, not just winners.
- **Hybrid** - the average of the two. Best on out-of-sample tests.
- **Hybrid + Market** - the Hybrid blended halfway with the market-implied ratings.
- **Pure Market** - the betting market alone, calibrated to the published title odds. The default.

Methodology and validation: [source/REPORT.md](source/REPORT.md).

## Tabs

- **Title Odds** - the top four (champion, runners-up, third, fourth) with the deciding scores, and the pre-tournament reach-round forecast below.
- **Schedule** - every fixture in kickoff order, predicted score beside the real one, color-coded (dark green exact, green right result, red wrong).
- **Groups** - each final table against the predicted finish. Open a group for its match predictions.
- **Knockout** - the predicted bracket against the real results, round by round.
- **Top Scorers** - the market's pre-tournament Golden Boot pick beside who actually scored. The engine rates teams, not players.
- **Method & Caveats** - the models, validation, and weaknesses.

## How it works

Plain Python, no ML framework, in [`source/`](source/):

- **`wc2026_engine.py`** - the tournament: group stage, the eight best third-placed teams, the FIFA Annex C round-of-32 (all 495 line-ups), then the bracket with extra time and penalties. Each match's expected goals come from the chosen model; scores are drawn from a Dixon-Coles-adjusted Poisson. Conditioned on played games, it locks those and samples the rest.
- **`make_data.py`** - runs the engine per model from one market calibration, unconditioned (Day 0 baseline) and conditioned (the forecast), writing `wc2026_results.json` and `wc2026_baseline.json`. **`fetch_actuals.py`** pulled played results from the openfootball feed.
- **`merge_schedule.py`** - folds the official schedule (date, kickoff, venue, home/away) into the results.
- **`fit_dc.py`** / **`build_params.py`** - fit Dixon-Coles on 15,751 internationals since 2010 and combine with Elo into `model_params.json`.
- **`val_assess.py`** / **`val_market.py`** - validation: 1,230 held-out internationals, and a market-vs-model backtest on 5,327 club matches.

The page runs no Python; it reads the pre-computed JSON, which is why it is one static file.

## Live results

While the tournament ran, two backend-free layers kept the page current:

- **In the browser** - results appeared beside each prediction, fetched from the public [openfootball](https://github.com/openfootball/worldcup) feed (no key), cached locally, refreshed adaptively. Deterministic: it never changed the odds, and fell back to predictions only if the feed was down.
- **The odds** - a scheduled GitHub Action re-ran the 50,000-tournament simulation conditioned on new results and committed it, so Netlify redeployed.

Both stopped after the final. The page is now static: results are baked into the payload, so it renders in full with no feed. The frozen final version is under [`archive/wc2026/`](archive/wc2026/); [REUSE.md](REUSE.md) covers porting the engine to another tournament.

## Layout

- `index.html` - the built app. Generated, not hand-edited.
- `netlify.toml` - static hosting config.
- `CLAUDE.md` - the build rule and conventions.
- `source/` - engine, schedule, parameters, validation, and the app template. See [source/README.md](source/README.md).

## Build

Edit `source/wc2026_template.html`; `index.html` is generated from it.

```
python source/build_app.py          # rebuild index.html
python source/build_app.py --check  # verify it is in sync (CI)
```

## For maintainers and coding agents

Read [CLAUDE.md](CLAUDE.md) for the build and repository constraints, followed by [source/CLAUDE.md](source/CLAUDE.md) and [source/REPORT.md](source/REPORT.md) for model assumptions and validation. These are project instructions, usable as references by other assistants; they do not require a Claude-only toolchain. Keep the production page as a generated, self-contained static artifact and validate changes using the commands below.

## Tests

Dependency-free, run in CI on every push and PR:

```
python -m unittest discover -s source -p 'test_*.py'   # update pipeline
node source/check_app.js                               # build clean, scripts parse
node source/test_app.js                                # in-browser live layer
```

The fragile surface was the live layer, which parsed a hand-edited, schema-less feed. The tests pin the cases that bit it: feed parsing (missing half-time score, unplayed fixtures, official-name remaps), scorer parsing (`(p)` penalties, `(og)` own goals, multi-line blocks, CRLF), the live badge clock (a played-but-unposted game keeps its badge), knockout overlay (result from the server run or the feed, advancer left unknown on a draw), score colouring (graded on the score shown), and engine invariants (reorientation is its own inverse; reach-round odds never rise round to round). `source/test_feed_sample.txt` packs every case into one fixture both suites run.

## Run locally

Open `index.html`, or `python -m http.server` from the repo root.

## Deployment

Netlify, from the repo root, redeployed on each push to `main`. Live at <https://wc2026forecast.xyz/> (backup <https://wc2026forecast.netlify.app/>). Security headers, `robots.txt`, `sitemap.xml`, and JSON-LD are configured in `netlify.toml` and the repo root.

## License

MIT, see [LICENSE](LICENSE). Public data (openfootball, CC0; eloratings.net) keeps its own terms.

## Disclaimer

A transparent baseline built from public data, not tested against a real World Cup. Not betting advice.
