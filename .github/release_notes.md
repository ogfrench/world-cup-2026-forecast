A from-scratch Monte Carlo forecast of the 2026 World Cup, live at https://wc2026forecast.xyz.

One self-contained `index.html`, no backend and no dependencies. It plays the full 48-team
tournament (104 matches, the eight best third-placed teams, the official FIFA Annex C round of
32, and the bracket through the final with extra time and penalties) 50,000 times, five
different ways, then overlays real results as they come in.

## Five models, one engine
Every model shares the same tournament engine and differs only in how it rates a single match.
- Pure Elo: results only, like a chess rating.
- Pure Goals: Dixon-Coles, fit on internationals since 2010.
- Hybrid: the average of the two, best on out-of-sample tests.
- Hybrid + Market: the Hybrid blended halfway to the bookmaker-implied ratings.
- Pure Market: the bookmakers' ratings run through the bracket, the default and recommended view.

## What it shows
- Title Odds: each team's chance of winning plus a reach-round matrix, against Opta and the
  bookmakers as pre-tournament comparisons on the Day 0 view, with a Live / Day 0 toggle.
- All Games: every fixture by local kickoff, the predicted score against the real result,
  color-coded on the score shown, with an In play / Awaiting result flag that stays up until the
  feed posts the score. Opening the tab jumps to the match in focus right now.
- Group Phase: the live table against the predicted finish, with movement arrows, and how many
  finished groups the model called in full (the whole finishing order, against its Day 0 prediction).
- Knockout Phase: the bracket fills in match by match as each group finishes, every tie carrying
  its real date, time and venue, an in-play / awaiting badge, live reach-round odds, and the real
  score as it lands. The live Road to the final narrows to the teams still in it and the rounds
  still to play.
- Top Scorers: the bookmakers' Golden Boot pick next to a live leaderboard parsed from the feed.
- Method & Caveats: the models, the validation (held-out internationals plus a club-odds proxy),
  and the honest weaknesses, with a panel for the selected model.

## Live and self-updating
- Real results overlay in the browser from the public openfootball feed (no key, no backend) on
  one adaptive heartbeat that also drives the live scorer leaderboard. This layer is deterministic
  and never changes the odds.
- A scheduled GitHub Action re-runs the conditional 50,000-sim and redeploys whenever a new result
  lands, gated by the test suite before it commits. This is what re-conditions the odds.
- Group and knockout results are baked into the payload, so the page stays a full, self-contained
  archive after the live feed stops (a week past the final, the sundown cutoff).

## Honest by design
Built and validated entirely from public data. A transparent baseline, not a sure thing; nothing
in it has been tested against a real World Cup. Not betting advice.
