# Reusing this for another tournament

This project is a Monte Carlo of one specific competition, the 2026 World Cup. A fair amount of it is
general and a fair amount is not. This is the honest map of which is which, so a future tournament does
not start from a wrong assumption about how much is a config swap.

The one thing to be clear about up front: this engine models a **single-leg, group-stage-then-knockout**
tournament. Another World Cup or a European Championship are the same shape and are mostly a data swap
plus a small format change. The **Champions League and Europa League are not the same shape**: they have
a league (Swiss) phase and two-legged knockout ties decided on aggregate. None of that exists here, and
no amount of config adds it. That is new engine work, described honestly at the end.

## What is genuinely reusable (unchanged for any single-leg tournament)

- The match model and its fit. Dixon-Coles by weighted Poisson MLE (`fit_dc.py`, `build_params.py`),
  the Elo pair, the market-implied Elo (`market_implied_elo` + `calibrate_market`), and the five ways of
  rating a single match. Give it a different set of teams and it just works.
- The tournament engine's mechanics. The Monte Carlo loop, the per-match sampling, extra time and
  shootouts, the FIFA 2026 group ranking with head-to-head re-application (`rank_group`), the
  conditional mode that locks played games and samples the rest (`run(..., actuals=...)`), and
  `validate()`.
- The whole front end. The template, the render layer, the live-results overlay, the in-browser feed
  parsers, the schedule merge, the build step, the three test layers, and the refresh Action. All of it
  is competition-agnostic: it renders whatever the payload contains.

## What is specific to this competition (the config boundary you swap)

Everything below encodes "this is the 2026 World Cup" and would change for another tournament:

- `source/wc2026_engine.py`, `GROUPS` (top of file): the teams, their Elo, and the group layout
  (12 groups of 4). This is the single biggest input. It also fixes the format constants everything
  downstream reads (`len(GROUPS)`, the number of qualifying third-placed teams).
- `source/wc2026_engine.py`, `MARKET_FULL`: the published pre-tournament title odds, used only to
  calibrate the two market models. Without them, the market models cannot be built (use `hybrid`).
- `source/annexc_data.py`: the official FIFA Annex C table that maps which best-third-placed teams fill
  which round-of-32 slots. This is 48-team-World-Cup-specific. A Euro has its own equivalent table for
  its four best thirds; another 48-team World Cup can reuse this as-is.
- The "best 8 thirds" rule: `ranked_thirds[:8]`, `_third_qualified` (top-8 clinch test), and
  `_resolve_thirds` all assume 8 of 12 thirds advance. A competition with a different count changes these.
- `source/model_params.json`: the fitted per-team attack/defense and the official Elo, for this team set.
  Regenerate with `fit_dc.py` + `build_params.py` on the new teams (needs `results.csv`).
- `source/wc2026_schedule.json` and `source/wc2026_ko_schedule.json`: the fixtures (group dates/venues and
  the knockout calendar by bracket slot).
- `source/fetch_actuals.py`, `SRC` and `KO_SRC`: the openfootball feed paths for this competition.
- The template copy and the reference odds (Opta / bookmakers) baked into the payload: all written for
  2026, all to be rewritten.

## Porting checklist

### Another World Cup (e.g. 2030), same 48-team format

Close to a drop-in. Swap `GROUPS`, `MARKET_FULL`, `model_params.json`, the two schedule files, and the
feed paths; rewrite the copy and reference odds. Annex C and the "8 best thirds" logic carry over
unchanged. Re-fit the parameters on current results. Budget: a data-gathering exercise, not an
engine rewrite.

### A European Championship (24 teams, 6 groups of 4, 4 best thirds)

Same family, a bit more than config. On top of the World Cup checklist:
- Reparametrize the thirds count: 4 of 6 advance, not 8 of 12 (`ranked_thirds[:8]` and the top-8 clinch
  test become the Euro numbers).
- Replace the Annex C table with UEFA's best-third-placed allocation table (which of the four thirds go
  to which round-of-16 group winner), and adjust `assign_thirds`.
- The bracket is a 16-team round of 16 onward rather than a round of 32; the bracket builder is otherwise
  the same single-leg logic.
Budget: a focused engine change plus the data, not a rewrite. Same test structure applies.

### Champions League / Europa League (do not underestimate this)

These are a different tournament structure, not a config of this one. What this engine does not have and
would need built:
- A **league (Swiss-model) phase**: 36 teams, eight games each against seeded opponents, one combined
  table, with a cut to a knockout play-off round. The current group stage (round-robin within fixed
  groups) does not model this.
- **Two-legged knockout ties** decided on aggregate over home and away legs, including the historical
  away-goals rule and the modern extra-time/shootout-on-aggregate resolution. The current bracket plays
  a single leg per tie.
- The **seeding and draw constraints** (pot structure, same-association restrictions) that shape who can
  meet whom.

What does carry over: the match model (Dixon-Coles / Elo / market), the render and live-results layer,
the build and test scaffolding, and the conditional "lock played games, sample the rest" idea. So it is
a real head start, but the tournament structure is new work, on the order of a rebuild of the engine's
scheduling and bracket, not a port. Do not promise it as a config change.

## The market-model caveat, wherever you take it

`market` and `market_pure` exist only because there were published pre-tournament title odds to calibrate
against (`MARKET_FULL`). For any competition where you cannot get those, drop both and ship `hybrid`,
which is the standalone model validated on internationals rather than a club-odds proxy. Do not fake the
market ratings.
