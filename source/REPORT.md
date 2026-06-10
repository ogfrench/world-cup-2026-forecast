# World Cup 2026 Prediction Engine: Final Report

A from-scratch Monte Carlo of the 48-team World Cup, with five interchangeable ways to rate a match
sitting on one shared tournament engine. 50,000 simulated tournaments per model. Built and validated
from public data and standard methods. This is a transparent baseline, not an oracle, and nothing in
it has been tested on an actual World Cup.

## 1. What it does

Every model runs the identical simulation: 72 group games, the eight best third-placed teams, the
official FIFA Annex C round-of-32 assignment (all 495 group-finish combinations), then the real
bracket through the final with extra time and penalty shootouts. The models differ only in how each
match's two expected-goal rates are set. The app lets you switch models live, and every tab (Title
Race, Knockout Odds, Groups and Scores, a Netherlands match timeline, and Method and Caveats)
re-renders for the selected model. It opens on Pure Market, the recommended forecast (see section 6).

## 2. The five models

- **Pure Elo.** Official eloratings.net ratings turned into a goal supremacy. Results only.
- **Score (Dixon-Coles).** A goals model fit by maximum likelihood to 15,431 internationals
  (2010 to 2026, recency-weighted): per-team attack and defense, a home effect, and the low-score
  dependence rho. Home edge came out at 1.31x, rho at -0.039, both earned from data.
- **Hybrid Elo + Score.** Equal blend of the two. Each covers the other's blind spot. The app's recommended standalone model.
- **Model + Market.** The hybrid pulled halfway toward the betting market.
- **Pure Market.** The market on its own, calibrated to reproduce the published title odds, then run
  through the full bracket.

The market-implied ratings come from inverting the model's own log(title odds) versus Elo line, then
a short calibration loop pins the pure-market simulation to the published odds within 0.58 points.

## 3. What the models say (title odds, 50k sims)

| Model | Top of the board |
|---|---|
| Pure Elo | Spain 28.9, Argentina 19.8, France 12.2, England 7.2 |
| Score (Dixon-Coles) | Argentina 15.4, Brazil 10.1, Spain 10.1, England 5.3, Japan 5.3 |
| Hybrid | Spain 19.8, Argentina 18.7, France 8.3, Brazil 7.2, England 7.0 |
| Model + Market | Spain 18.5, Argentina 12.8, France 12.1, England 9.3, Brazil 8.4 |
| Pure Market | Spain 16.6, France 15.8, England 11.5, Brazil 8.9, Argentina 8.3 |

The spread on a single team is large (Spain ranges from 10 to 29 percent across the five) because a
small per-match edge compounds across seven knockout rounds. Read the five as a sensitivity check on
how much the answer depends on method, not as five independent forecasts.

## 4. Predictive power: the evidence

**Match models, out of sample (1,230 held-out internationals, 2025 to 2026).** Train before 2025,
test after. Lower is better except accuracy.

| Model | Log-loss | RPS | Accuracy | Calibration error |
|---|---|---|---|---|
| Naive base rate | 1.0472 | 0.2279 | 48% | - |
| Pure Elo | 0.8464 | 0.1632 | 60% | 0.037 |
| Score (Dixon-Coles) | 0.8558 | 0.1667 | 61% | 0.041 |
| Hybrid | 0.8409 | 0.1627 | 60% | 0.026 |

All three crush the baseline. The hybrid is best by every proper score and clearly the best
calibrated. A paired bootstrap shows it beats the score model with confidence, but ties pure Elo
inside the margin of error. Its real contribution is reining in the score model's overconfidence
(the goal-padding that overrates Japan and Algeria), not out-predicting Elo. The fancy goals model
never out-scores plain Elo on probability quality, edging it only on raw hit-rate. The quiet lesson
is that complexity is not the same as accuracy.

**Does following the market pay? (executable proxy, 5,327 held-out club matches, real closing odds.)**
The World Cup market cannot be backtested directly (no historical international odds), so the
principle was tested on club football, where odds exist on every game.

| Model | Log-loss | RPS | Accuracy | Calibration error |
|---|---|---|---|---|
| Elo model | 0.9808 | 0.1988 | 53.1% | 0.025 |
| Market | 0.9660 | 0.1941 | 54.2% | 0.016 |
| Elo + Market | 0.9702 | 0.1956 | 53.7% | 0.019 |

The market beats a competent Elo model on every measure (bootstrap CI clear). The model-and-market
blend improves on the model but does not beat the market on its own. So "markets tend to win" holds,
with the honest nuance that blending pulls a model toward a stronger forecaster, it does not surpass
it. The caveat is that this was club football; the World Cup is among the most heavily bet events, so
its market is likely just as sharp, but that part is not proven here.

## 5. The Netherlands match timeline

A focused tab gives one coherent storyline per Dutch fixture: first-goal minute, half-time score, and
full-time score, derived together so they actually agree. It follows the model switcher, so switching
to Pure Market shows the market's read.

**How it is built.** The result lean and goal volume come from the selected model's expected goals.
The cards then commit to a single representative scenario per match (the modal scoreline, skipping a
goalless draw) and read the half-time and the first-goal minute from that same scenario, so they
cannot contradict each other. The first-goal minute itself comes from the real empirical curve of
when goals are scored (scoring rises through a match, lowest in the opening fifteen, a peak in the
closing fifteen): a first-half goal lands near the 26th minute, and if the half projects goalless the
lone goal lands near the 70th.

**The interesting finding: the market and the model disagree about the Netherlands.** The market
rates the Netherlands a shade above the results-based rating (implied Elo about 1973 versus the
official 1944), so under Pure Market the Dutch are favored in all three group games. The hybrid, by
contrast, makes the Japan game a coin flip (36/27/37), and the Dixon-Coles goals model actually leans
Japan. Against Tunisia the market even shifts the representative result from a narrow 1-0 to a 2-0,
which because it is a two-goal game pulls the projected first goal forward from late in the match to
before the break. Sweden is a comfortable Dutch win under every model. Switching models is the honest
way to see how much of this is method rather than fact.

**Health warning, repeated on the tab.** The exact score is soft (each is only the tallest bar in a
flat pile), and the first-goal minute is the softest output of all: it is driven almost entirely by a
league-average timing curve identical in shape for every team, so it carries little that is specific
to these sides. Read the result lean and the goal volume; treat the minute as the typical rhythm of a
match like this, not a real per-game forecast.

## 6. Recommendation

- **For the best estimate of what will happen: Pure Market.** Both lines of evidence and decades of
  market-efficiency work point the same way. For the title race it essentially is the bookmakers'
  number.
- **For an honest model you can defend on its own terms: Hybrid.** Best-calibrated thing built from
  data, best of the testable models out of sample, and the only one validated directly on
  internationals. Most interesting because it shows where cold results-based reasoning parts from the
  crowd (Argentina high, France low).
- **Do not center Model + Market.** The test showed the blend is dominated at both ends: less
  accurate than Pure Market, less pure than the Hybrid. A reasonable "can't decide" setting, nothing
  more.
- **Hold all of it loosely.** None of the five is validated on the actual tournament yet.

## 7. Honest limitations

- **Results-based models lean top-heavy.** A fixed-strength simulation cannot see in-tournament
  swings (injury, form, a red card), so Pure Elo especially crowds probability onto favorites. There
  is no rating uncertainty in the model, which is the deepest single reason it is overconfident.
- **Injuries are not modeled.** The model reflects results through 6 June 2026 and nothing about who
  is fit at kickoff. Brazil, for one, is rated at full strength.
- **Draws run a little low.** The hybrid's group draw rate is about 23 to 24 percent, under the
  roughly 26 to 28 percent World Cup norm. It is the honest fitted value (pure Elo lower, the score
  model on the norm).
- **The out-of-sample test is mostly qualifiers and friendlies**, often lopsided, where any decent
  model looks good. Tight elite knockouts, the games a World Cup turns on, are barely represented, so
  the numbers are encouraging rather than decisive. The test also scores the match models, not the
  title odds, which cannot be checked until the tournament is played.
- **The market view leans on title odds plus a club-football proxy.** Pure Market is the market seen
  through this engine's bracket, calibrated to the published title odds, not a live feed of the
  market's own match-by-match prices, and the "markets win" claim rests on club data, not
  international odds, which were unreachable in the sandbox.
- **Market values below the top eight are approximate** reads of long prices. To tighten the tail,
  drop a full odds board into MARKET_FULL in the engine.
- **Exact scorelines are the weakest output, and goal timing is not really modeled.** The win/draw/
  loss leans and total-goal expectations hold up, but the single most likely scoreline is the peak of
  a very flat distribution (often under 15 percent), it skews low on goals, and it was never
  calibrated against correct-score markets. First-goal minutes come from a generic league-average
  curve with no team-specific content. Use the result and the over/under, not the digits.

## 8. Files and how to rebuild

Canonical set:

- `wc2026_predictions.html`: the interactive app, self-contained (built artifact, do not hand-edit).
- `wc2026_template.html`: the app source, with a `/*DATA*/` token. Edit this, then re-inject to build.
- `wc2026_engine.py`: the simulation engine (all five models, market calibration, Annex C).
- `wc2026_results.json`: the 50k simulation output the app renders.
- `model_params.json`: fitted Dixon-Coles parameters and official Elo ratings.
- `annexc_data.py`: the official FIFA Annex C round-of-32 table (495 rows) and parser.
- `fit_dc.py`, `build_params.py`: the fitting pipeline that produced `model_params.json`.
- `val_assess.py`: out-of-sample assessment of the three testable match models.
- `val_market.py`: the market-versus-model proxy backtest on club odds.
- `REPORT.md` (this file) and `CLAUDE.md` (project handoff for future sessions).

Rebuild in two steps. First regenerate the simulation: `python3 wc2026_engine.py 50000` writes
`wc2026_results.json`. Then build the app by replacing the `/*DATA*/` token in
`wc2026_template.html` with the contents of `wc2026_results.json`, writing `wc2026_predictions.html`.
The fitting pipeline (`fit_dc.py` then `build_params.py`) regenerates `model_params.json` and needs
the match dataset `results.csv` (49,411 internationals, public).

## 9. Sanity check

Passed end to end: the engine compiles and all five model paths execute; every model conserves at
every bracket stage (champions sum to 100, finalists to 200, on through round of 32 to 3,200); each
model carries 12 groups of 6 match predictions with W/D/L summing to 100; Pure Market reproduces the
published odds within 0.58 points; the Netherlands tab derives a coherent scenario under every model
(first-goal minute under 45 exactly when half-time shows a goal); the shipped page has no unfilled
data, valid JavaScript, all five models and labels, the tiered switcher, and the mobile rules intact;
no stale copy; and every number cited in the prose matches the data.
