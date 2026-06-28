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
- `index.html`: the built app, self-contained and deployed. Generated, do not hand-edit; rebuild it.
- `wc2026_template.html`: the app source. Has a single `/*DATA*/` token where the JSON is injected.
  Edit this for any app change.
- `build_app.py`: injects `wc2026_results.json` into the template's `/*DATA*/` token and writes
  `index.html`. `build_app.py --check` verifies the two are in sync (CI runs this).
- `make_data.py`: the regeneration entry point. Runs the engine unconditioned (Day 0) and conditioned
  (live) from one shared calibration, validates, and writes both JSON files (default 50,000 sims).
- `fetch_actuals.py`: refreshes `wc2026_actuals.json` from the openfootball feed (engine names, official
  home/away), splitting any knockout ties into `wc2026_ko_actuals.json`.
- `merge_schedule.py`: folds the schedule into the results JSON (annotates date/venue, reorients
  home/away to the official side). Idempotent, no re-simulation.
- `wc2026_engine.py`: the simulation engine. All five models, market calibration, Annex C, KO logic.
  `run(..., actuals=...)` conditions the Monte Carlo on played games (locks them, samples the rest);
  `load_actuals()` reads `wc2026_actuals.json`; `validate()` checks the invariants. Seeds are fixed, so
  identical inputs give identical output. The market calibration must stay unconditioned (it pins the
  market-implied Elo to the published pre-tournament odds); only the final output runs take `actuals`.
- `wc2026_results.json`: the 50k simulation output the app renders, with the fixture schedule merged in.
- `wc2026_baseline.json`: the frozen Day 0 (pre-tournament) snapshot. The before/after deltas compare
  the live conditional run against this.
- `wc2026_actuals.json`: played group results in engine team names, the conditioning input (refreshed
  from openfootball). `wc2026_ko_actuals.json` is the same for played knockout ties.
- `wc2026_schedule.json`: the official 72-match group schedule (date, kickoff, home/away, venue), from openfootball.
- `wc2026_ko_schedule.json`: the official knockout calendar keyed by engine bracket slot (73-103), date/
  kickoff/venue plus the bracket descriptors used to verify slot alignment, from openfootball `cup_finals.txt`.

Checks and tests:
- `check_app.js`: CI check that `index.html` is built, every `<script>` block parses, and all five models are present.
- `test_pipeline.py`: stdlib unittest for the update pipeline (feed parse, home/away orientation, engine
  conditioning + validation). Engine tests skip without numpy.
- `test_app.js`: tests the built app's live layer (the in-play/awaiting badge clock, the in-browser feed parser).

Parameters and data tables:
- `model_params.json`: fitted Dixon-Coles params (intercept, home, rho, c, total, alpha), per-team
  attack/defense, and official Elo for all 48 teams.
- `annexc_data.py`: the official FIFA Annex C R32 table (495 group-finish combinations) and parser.

Fitting and validation:
- `fit_dc.py`: fits Dixon-Coles by weighted Poisson MLE on the match dataset.
- `build_params.py`: assembles `model_params.json` from the fit plus official Elo.
- `val_assess.py`: out-of-sample predictive test of the three testable match models.
- `val_market.py`: market-versus-model proxy backtest on club odds.

Docs:
- `REPORT.md`: the final report.
- `CLAUDE.md`: this file.

Data not shipped (live in `/home/claude` during development):
- `results.csv`: 49,411 internationals 1872 to 2026. Columns: date, home_team, away_team,
  home_score, away_score, tournament, city, country, neutral.
- `matches.csv`: ~43MB club dataset (top-5 leagues, real closing odds) for the market proxy,
  downloaded from `raw.githubusercontent.com/xgabora/Club-Football-Match-Data-2000-2025`.

## How to rebuild

1. Refresh the played results: `python3 fetch_actuals.py` (pulls new games from the openfootball feed
   into `wc2026_actuals.json` and `wc2026_ko_actuals.json`).

2. Regenerate the simulation: `python3 make_data.py 50000` writes `wc2026_results.json` (live,
   conditioned on the played games) and `wc2026_baseline.json` (the frozen Day 0 snapshot). The app
   opens on Pure Market because `wc2026_template.html` hardcodes `let CUR = 'market_pure'`; the engine
   also emits `default_model='market_pure'` for consistency.

3. Fold the fixture schedule back in: `python3 merge_schedule.py`. The engine builds group fixtures with
   `itertools.combinations`, so it has no dates and arbitrary home/away. This annotates each group match
   with its official date, kickoff, venue, and reorients home/away to the official side (swapping the
   home/away probabilities and scores with it). Idempotent, and it does not touch the 50k team statistics.

4. Build the app: `python3 build_app.py` injects `wc2026_results.json` into the `/*DATA*/` token in
   `wc2026_template.html` and writes `index.html`. Confirm it is in sync with `python3 build_app.py --check`.

5. QC: `node check_app.js` (build is clean, script blocks parse, five models present), then the test
   suites: `python -m unittest discover -s source -p 'test_*.py'` and `node test_app.js`.

The autonomous refresh (`.github/workflows/refresh.yml`) runs steps 1 to 4 on a windowed cron, but only
when `wc2026_actuals.json` actually changes, and commits the result so Netlify redeploys.

To re-derive parameters: `python3 fit_dc.py` then `python3 build_params.py` (needs `results.csv`).

## The five models (how each match's two expected-goal rates are set)

Set by the module global `CURRENT_MODEL`; `lambdas(home, away)` dispatches on it.
- `elo`: Pure Elo. `_elo_pair` on official Elo: supremacy = c*(Elo_h - Elo_a), split around TOTAL/2.
- `score`: Pure Goals. `_dc_pair`: exp(intercept + ATT + DFN + home). Goal-pads weak opponents.
- `hybrid`: `_hybrid_pair`, 50/50 of elo and score pairs. The recommended standalone model.
- `market`: Hybrid + Market. 0.5*hybrid + 0.5*(`_elo_pair` on MARKET_ELO).
- `market_pure`: Pure Market. `_elo_pair` on MARKET_ELO alone.

MARKET_ELO is built by `market_implied_elo` (invert the pure-Elo log-title-odds vs Elo line, map the
published `MARKET_FULL` odds back to implied ratings; teams outside the published top-20 keep their
official Elo), then nudged by `calibrate_market` so a pure-market sim reproduces the published title
odds (converges to within ~0.4 to 0.6 points).

## Key parameters (fitted)

Home effect +0.270 (a 1.31x goal multiplier), rho -0.039, total goals 2.728, c 0.00519, alpha 0.5.
Dixon-Coles fit on 15,751 internationals (window 2010+, half-life 2.5 years, min 15 matches/team).
The app reads this count from `meta.dc_matches` (do not hardcode it); the 1,230 held-out and 5,327
club-match validation figures are still hardcoded in the copy and must be refreshed when the fit is re-run.

## Validation, the honest bottom line

- Out of sample (1,230 held-out internationals): hybrid is best by every proper score and best
  calibrated; it beats the Dixon-Coles model with bootstrap confidence but ties pure Elo within the
  margin of error. Complexity is not the same as accuracy.
- Market proxy (5,327 club matches, real odds): the market beats a competent Elo model; a 50/50 blend
  beats the model but does not beat the market. Markets tend to win.
- Recommendation: Pure Market for the best forecast; Hybrid as the defensible standalone model
  (the one recommendation validated on internationals, not a club-odds proxy); do not center Hybrid + Market (dominated both ways); hold
  all of it loosely (none validated on a real World Cup).

## The Knockout tab

The bracket fills in incrementally as groups finish, not all-at-once. `actual_bracket` settles each
group that has all six games played and emits an R32 tie the moment both its feeders are known: the
eight ties with no third-placed team unlock as their two groups complete, and a third-fed tie unlocks
as soon as its third's slot is pinned down. A third's Annex C slot depends on which eight of the twelve
groups supply a qualifying third, so `_resolve_thirds` places a third early only when its slot is the
same across every still-possible set of eight. It forces in the thirds that have clinched a top-8 finish
(`_third_qualified`: `ahead + remaining <= 7`, settled thirds above it plus one per unsettled group,
worst case), enumerates the ways the remaining qualifying spots can be filled from the open groups, and
emits any slot that lands on the same already-known group in all of them. Enumerating the open groups is
a slight superset of the genuinely reachable sets (it ignores the fixed ordering among settled
non-clinched thirds), so the test is conservative, never wrong: a slot locked under the superset is
locked under the reachable subset too. This subsumes the old K/L special case (their slots happen to be
combination-invariant) and generalizes it: at the back end of the group stage, with only a group or two
left, several winner-vs-third ties (e.g. a clinched group winner against a clinched third whose slot no
longer moves) lock a full matchday before the stage ends, instead of waiting for all twelve. `make_data`
emits the per-model `knockout` section via `ko_predictions`; `renderKnockout` shows a "N of 16 set" note
while the R32 is partial.

The whole bracket is built under both Elo tails (`_bracket_core(..., elo_sign=+1/-1)`) and only slots
that agree are emitted. This is the defer guard: a boundary that only the Elo tail would decide (a dead
tie FIFA would settle on fair play / ranking / lots, which we have no data for) is left pending rather
than guessed. It resolves once the official bracket is published.

The real score shown and graded is the regulation-plus-extra-time result, and penalties never count
toward it (a 1-1 that goes to a shootout stays 1-1; the shootout only decides who advances, carried
separately as `played.winner`). The predicted scoreline follows the single most likely PATH the tie
takes, the same primitive as a group match plus the knockout continuation: `ko_report` takes the most
likely 90-minute scoreline (`argmax(M)`); if it is level, it adds the most likely extra-time result
(`argmax` of the third-rate ET matrix) on top of that draw; if it is STILL level, the tie is predicted
to go to penalties and `pens` is set. So a dominant team is predicted to win in regulation (France 2-0)
and a tight tie is predicted level and to a shootout (Germany v Paraguay 1-1, pens), which is how a
knockout actually runs and is consistent with the group cards (a draw is a legal headline). `koCard`
shows a muted `pens` tag on the predicted score for the level ties. Honest caveat: `pens` marks the
most likely path, not a high probability of a shootout (aggregate chance of reaching penalties is only
~13%), so the card hedges with "trust the advance odds more than this exact number" and the advance bar
carries the real signal. The W/D/L split (`p_a`/`p_draw`/`p_b`) stays the 90-minute regulation result,
which is what the advance odds are built from (`adv_a = p_a + p_draw * (et_a + et_d * shootout)`). The
90-minute Poisson modal is also what the group cards show.

The bracket has the same live state as Schedule and Groups, reusing `matchState`/`liveBadge`/`actualFor`.
`koActual(t)` resolves a tie's real result, preferring the server-conditioned `played`, else the live
browser feed keyed by the tie's `date` (the advancer derived from a decisive score; a draw is a shootout
the feed score cannot read, so the winner is left unknown). KO scheduling is keyed by bracket slot (the
teams are unknown until the groups finish): `wc2026_ko_schedule.json` carries date/kickoff/venue per slot
from the official openfootball calendar, and `merge_schedule.py` attaches it onto each emitted tie.
`test_pipeline.py` guards that every slot's bracket descriptors match the engine (`R32_SYMBOLIC` and the
feeder pairs), so a tie can never carry the wrong date. The engine's final is slot 103 (official match
104). The engine does not simulate the third-place play-off (official match 103), so it rides in the
schedule as a display-only fixture with `round:"third"` and synthetic `slot:104`: shown in the Schedule
and the bracket with the two beaten semi-finalists and the real score but no model pick. The alignment
guard skips it. The Schedule and the Knockout tab both render the whole calendar from `ko_schedule` via
`scheduleUnits()` / `koRounds()` (pure, unit-tested), so all 104 fixtures appear before the teams are known.
A tie with a `kickoff_utc` shows the in-play/awaiting badge and folds into the live heartbeat via
`koTies()`. The one thing only confirmable once the R32 actually plays is the live feed's KO line format;
the front end degrades safely if a predicted matchup did not happen (no result shown, never a wrong one).

The per-team Netherlands and France timeline tabs were removed: prediction-only surface (a generic
first-goal-minute curve, a derived half-time) with no live state, not worth the maintenance. The app
is the shared forecast tabs only.

## Group ranking (FIFA 2026)

`rank_group` (engine) and `groupStandings` (JS) implement the 2026 order: points, then head-to-head
(points, GD, goals) among the tied teams, then overall GD, overall goals. Head-to-head before overall
GD is new for 2026; do not "correct" it back. Both do FIFA's re-application: when head-to-head separates
some teams but leaves a subset tied, the criteria are re-applied to that subset with its head-to-head
recomputed among just those teams (a flat sort gets 3-/4-way ties wrong). Elo is the final separator,
standing in for fair play (cards), the FIFA world ranking, and drawing of lots, none of which we have
data for. In the simulation that substitution is harmless (exact multi-way ties are rare). In the live
bracket it could drift, so `actual_bracket` defers any boundary the Elo tail alone decides (see above).
The group "standings called" stat grades the full finishing order against the Day 0 prediction
(`win_group0`), not the live-conditioned `win_group`, and only counts finished groups.

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
- Exact scorelines are the soft output of the engine; goal timing is not modeled.
