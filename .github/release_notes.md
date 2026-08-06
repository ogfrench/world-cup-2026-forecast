The final version. A from-scratch Monte Carlo forecast of the 2026 World Cup, live at https://wc2026forecast.xyz, now the complete self-contained archive of a tournament that is over.

One `index.html`, no backend and no dependencies. It played the full 48-team tournament (104 matches, the eight best third-placed teams, the official FIFA Annex C round of 32, and the bracket through the final with extra time and penalties) 50,000 times, five different ways, and overlaid the real results as they came in.

## How it finished
1. Spain (beat Argentina 1-0 after extra time in the final)
2. Argentina
3. England (beat France 6-4 in the third-place play-off)
4. France

## Five models, one engine
Every model shares the same tournament engine and differs only in how it rates a single match.
- Pure Elo: results only, like a chess rating.
- Pure Goals: Dixon-Coles, fit on internationals since 2010.
- Hybrid: the average of the two, best on out-of-sample tests.
- Hybrid + Market: the Hybrid blended halfway to the bookmaker-implied ratings.
- Pure Market: the bookmakers' ratings run through the bracket, the default and recommended view.

## What it shows
- Title Odds: now that the tournament is decided, a top-four results overview (champion, runners-up, third and fourth, with the deciding scorelines) in place of the live title odds, with the pre-tournament reach-round forecast kept below for the record. During the tournament this was each team's live chance of winning, against Opta and the bookmakers as pre-tournament comparisons.
- All Games: every fixture by local kickoff, the predicted score against the real result, color-coded on the score shown.
- Group Phase: the final table against the predicted finish, with movement arrows, and how many groups the model called in full.
- Knockout Phase: the whole bracket, every tie carrying its real date, time and venue and the real score, with the final and third-place play-off predicted once the semi-finals were decided.
- Top Scorers: the bookmakers' Golden Boot pick next to the final leaderboard parsed from the feed.
- Method & Caveats: the models, the validation (held-out internationals plus a club-odds proxy), and the honest weaknesses.

## Archive and reuse
- The exact deployed version is frozen under `archive/wc2026/` (the self-contained page, its payload, and the final standings), so the record survives independently.
- `REUSE.md` documents how the engine and pipeline map onto another tournament: another World Cup or a Euro are largely a data swap; the Champions League and Europa League are a different structure (league phase, two-legged aggregate ties) and are called out as new work, not a port.

## Honest by design
Built and validated entirely from public data. A transparent baseline, not a sure thing; nothing in it was tested against a real World Cup before this one. Not betting advice.
