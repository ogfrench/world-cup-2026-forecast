# CLAUDE.md

Project context and handoff for the World Cup 2026 Prediction Engine. Read this first if you are
picking the project up in a new session.

## Working preferences (apply these)

- No em dashes anywhere. Use commas, parentheses, colons, or shorter sentences.
- No emojis. US English. Minimal formatting in prose, no decorative bolding or bullet spam.
- Be brutally honest and flag weaknesses proactively. Do not oversell. Give one decisive
  recommendation, not a menu of options.
- Do not trust the user blindly. Check the logic, recompute when a number matters, and call out
  inconsistencies directly. The user catches sloppy reasoning and dislikes hedging.

## What this project is

A from-scratch Monte Carlo of the 48-team 2026 World Cup. Five interchangeable ways to rate a single
match all sit on one shared tournament engine (group stage, the 8 best third-placed teams, the
official FIFA Annex C round-of-32, then the full bracket with extra time and shootouts). 50,000
simulated tournaments per model. Outputs an interactive self-contained HTML app that opens on Pure Market, the recommended forecast. Built and validated
entirely from public data. It is a transparent baseline, not an oracle, and nothing in it has been
tested against an actual World Cup.

## File map

Build artifacts and source:
- `wc2026_predictions.html` — the built app, self-contained. DO NOT hand-edit; rebuild it.
- `wc2026_template.html` — the app source. Has a single `/*DATA*/` token where the JSON is injected.
  Edit this for any app change.
- `wc2026_engine.py` — the simulation engine. All five models, market calibration, Annex C, KO logic.
- `wc2026_results.json` — the 50k simulation output the app renders, with the fixture schedule merged in.
- `wc2026_schedule.json` — the official 72-match group schedule (date, kickoff, home/away, venue), from openfootball.
- `merge_schedule.py` — folds the schedule into the results JSON (step 1b in How to rebuild).

Parameters and data tables:
- `model_params.json` — fitted Dixon-Coles params (intercept, home, rho, c, total, alpha), per-team
  attack/defense, and official Elo for all 48 teams.
- `annexc_data.py` — the official FIFA Annex C R32 table (495 group-finish combinations) and parser.

Fitting and validation:
- `fit_dc.py` — fits Dixon-Coles by weighted Poisson MLE on the match dataset.
- `build_params.py` — assembles `model_params.json` from the fit plus official Elo.
- `val_assess.py` — out-of-sample predictive test of the three testable match models.
- `val_market.py` — market-versus-model proxy backtest on club odds.

Docs:
- `REPORT.md` — the final report.
- `CLAUDE.md` — this file.

Data not shipped (live in `/home/claude` during development):
- `results.csv` — 49,411 internationals 1872 to 2026. Columns: date, home_team, away_team,
  home_score, away_score, tournament, city, country, neutral.
- `matches.csv` — ~43MB club dataset (top-5 leagues, real closing odds) for the market proxy,
  downloaded from `raw.githubusercontent.com/xgabora/Club-Football-Match-Data-2000-2025`.

## How to rebuild

1. Regenerate the simulation: `python3 wc2026_engine.py 50000` writes `wc2026_results.json`.
Note: the app opens on Pure Market because `wc2026_template.html` hardcodes `let CUR = 'market_pure'`; the engine also emits `default_model='market_pure'` for consistency.

1b. Fold the fixture schedule back in: `python3 merge_schedule.py`. The engine builds group
   fixtures with `itertools.combinations`, so it has no dates and arbitrary home/away. This step
   annotates each group match with its official date, kickoff, venue, and reorients home/away to
   the official side (swapping the home/away probabilities and scores with it). It is idempotent
   and does not touch the 50k team statistics. The schedule lives in `wc2026_schedule.json`,
   parsed from the public openfootball World Cup 2026 dataset.

2. Build the app: replace the `/*DATA*/` token in `wc2026_template.html` with the full contents of
   `wc2026_results.json`, write the result to `wc2026_predictions.html`. One-liner:
   ```python
   tpl=open('wc2026_template.html').read(); data=open('wc2026_results.json').read()
   open('wc2026_predictions.html','w').write(tpl.replace('/*DATA*/', data))
   ```
3. QC the build: parse the JSON back out of the HTML, syntax-check both `<script>` blocks (Node `vm`
   or `node --check`), confirm 5 models and labels are present, confirm stage conservation, and sweep
   for stale strings.

To re-derive parameters: `python3 fit_dc.py` then `python3 build_params.py` (needs `results.csv`).

## The five models (how each match's two expected-goal rates are set)

Set by the module global `CURRENT_MODEL`; `lambdas(home, away)` dispatches on it.
- `elo` — Pure Elo. `_elo_pair` on official Elo: supremacy = c*(Elo_h - Elo_a), split around TOTAL/2.
- `score` — Pure Goals. `_dc_pair`: exp(intercept + ATT + DFN + home). Goal-pads weak opponents.
- `hybrid` — `_hybrid_pair`: 50/50 of elo and score pairs. The recommended standalone model.
- `market` — Hybrid + Market. 0.5*hybrid + 0.5*(`_elo_pair` on MARKET_ELO).
- `market_pure` — Pure Market. `_elo_pair` on MARKET_ELO alone.

MARKET_ELO is built by `market_implied_elo` (invert the pure-Elo log-title-odds vs Elo line, map the
published `MARKET_FULL` odds back to implied ratings; teams outside the published top-20 keep their
official Elo), then nudged by `calibrate_market` so a pure-market sim reproduces the published title
odds (converges to within ~0.4 to 0.6 points).

## Key parameters (fitted)

Home effect +0.270 (a 1.31x goal multiplier), rho -0.039, total goals 2.728, c 0.00519, alpha 0.5.
Dixon-Coles fit on 15,431 internationals (window 2010+, half-life 2.5 years, min 15 matches/team).

## Validation, the honest bottom line

- Out of sample (1,230 held-out internationals): hybrid is best by every proper score and best
  calibrated; it beats the Dixon-Coles model with bootstrap confidence but ties pure Elo within the
  margin of error. Complexity is not the same as accuracy.
- Market proxy (5,327 club matches, real odds): the market beats a competent Elo model; a 50/50 blend
  beats the model but does not beat the market. Markets tend to win.
- Recommendation: Pure Market for the best forecast; Hybrid as the defensible standalone model
  (only one validated on internationals); do not center Hybrid + Market (dominated both ways); hold
  all of it loosely (none validated on a real World Cup).

## The Netherlands tab (how it works and how to extend)

In `wc2026_template.html`, the model-aware Netherlands timeline lives in the `renderNL` block.
- It reads `CUR` (the selected model) and uses `NL_LAM[model][opponent]` expected goals (pulled from
  the engine and embedded).
- `nlScenario` derives one coherent scenario per match: take the modal scoreline (skip 0-0); a lone
  goal (total 1) skews to the second half (half-time 0-0, first goal near minute 71); two or more
  goals put the first goal in the first half (near minute 26); the winner scores first, a draw breaks
  on the higher single-match win probability.
- The first-goal minute comes from `NL_BANDS`, the empirical 15-minute goal-share curve (rising, peak
  in the final fifteen). The half-time and the minute are read from the same scenario so they agree.

To add knockout fixtures once the bracket is set:
1. Compute the opponent's per-model expected goals from the engine (set `CURRENT_MODEL`, call
   `lambdas('Netherlands', opp)`), and add them to `NL_LAM` and a fixture entry to `NL_FIX`.
2. IMPORTANT: knockout games go to extra time and penalties, but the group cards use a straight
   90-minute Poisson. For KO fixtures switch the scoreline math to regulation-only (the engine has
   separate ET and shootout logic), or the full-time score and over/under will be off.

## The conceptual trap that bit us repeatedly (do not repeat)

Do not stitch the marginal mode of one quantity to a different statistic of another. Example: the
most likely half-time score is 0-0 (dominated by goalless first halves), while the average first-goal
minute is around 35 (averaged only over matches that had a goal). These describe different
sub-populations, so pairing "0-0 at half" with "first goal minute 35" is a contradiction. Always
derive a prediction from one single scenario, then read every figure (minute, half-time, full-time)
out of that same scenario. The rule of thumb: a goal before minute 45 means half-time cannot be 0-0.

## Conventions and gotchas

- numpy is 2.0: `np.trapz` is gone, use `np.trapezoid`.
- The `sh` used by the bash tool does not support process substitution `<(...)`. To Node-check a
  script extracted from the HTML, write it to a temp file first, or use Node `vm`.
- Match-data team names differ from engine names; `NAME_MAP` in `fit_dc.py` handles the mapping.
- For the club dataset, `raw.githubusercontent.com` works; `api.github.com` rate-limits.
- In-simulation "now" is 6 June 2026; the app header reads "As of Jun 6 2026".

## Open items

- The market story rests on title odds plus a club-football proxy because historical international
  match odds were unreachable in the sandbox. `val_market.py` is shaped to run the true international
  test if such odds are obtained.
- No rating uncertainty in the model is the deepest reason it is top-heavy; adding it would widen the
  title race sensibly.
- Exact scorelines and goal timing are the soft outputs; the first-goal minute is a generic
  league-average curve with no team-specific content.
