// Tests for the in-browser live layer, run against the BUILT index.html so they
// cover exactly what ships. No dependencies. Run: node source/test_app.js
//
// Mission-critical, low-maintenance pieces of the live layer:
//   matchState   - the clock that decides the live / awaiting badge. The regression
//                  it guards: a played game whose result the feed has not posted yet
//                  must keep its "awaiting" placeholder, not silently look unplayed.
//   parseActuals - the in-browser feed parser that overlays real results.
//   parseScorers - the live Golden Boot leaderboard parser. The feed is hand-edited free text,
//                  so the tests cover its sharp edges: a penalty written (p), an own goal (og),
//                  a multi-line scorer block, a missing half-time score, an official FIFA name.
// The end-to-end block runs source/test_feed_sample.txt (a representative feed) through the
// parsers and asserts the overlay and the scorer board, so a feed-format change cannot regress
// silently. Keep that fixture in sync with the openfootball format if it ever shifts.
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const sample = fs.readFileSync(path.join(__dirname, 'test_feed_sample.txt'), 'utf8');

let passed = 0, failed = 0;
function eq(actual, expected, msg) {
  const a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a === e) { passed++; }
  else { failed++; console.error(`FAIL: ${msg}\n  expected ${e}\n  got      ${a}`); }
}

// pull a snippet out of the built app by regex, asserting it is present exactly once
function pull(re, label) {
  const m = html.match(re);
  if (!m) { console.error(`FAIL: could not find ${label} in index.html`); process.exit(1); }
  return m[0];
}

// the live layer is inside one IIFE; lift just the pure pieces into a sandbox and run them.
// function declarations (matchState, parseActuals) land on the sandbox; the const helpers they
// close over (ACT_NAME, ACT_MON, actNm, actKey) stay in lexical scope, which is all they need.
const snippet = [
  pull(/const IN_PLAY_MS = [^\n]*/, 'IN_PLAY_MS'),
  pull(/const AWAIT_FAST_MS = [^\n]*/, 'AWAIT_FAST_MS'),
  pull(/function matchState\(now, ko, hasResult\)\{[\s\S]*?\n  \}/, 'matchState'),
  pull(/const ACT_NAME = \{[^}]*\};/, 'ACT_NAME'),
  pull(/const ACT_MON = \{[^}]*\};/, 'ACT_MON'),
  pull(/const actNm = [^\n]*/, 'actNm'),
  pull(/const actKey = [^\n]*/, 'actKey'),
  pull(/function parseActuals\(txt\)\{[\s\S]*?\n  \}/, 'parseActuals'),
  pull(/const SC_MLINE = [^\n]*/, 'SC_MLINE'),
  pull(/function addGoals\(tally, side, team\)\{[\s\S]*?\n  \}/, 'addGoals'),
  pull(/function parseScorers\(txt\)\{[\s\S]*?\n  \}/, 'parseScorers'),
  pull(/const scoreOutcome = [^\n]*/, 'scoreOutcome'),
  pull(/const actOutcome = [^\n]*/, 'actOutcome'),
  pull(/const predTier = \(mm,a\) =>[\s\S]*?'miss'\);/, 'predTier'),
  'let ACTUALS = {};',                                            // the live feed cache koActual reads
  pull(/function actualFor\(mm\)\{[\s\S]*?\n  \}/, 'actualFor'),
  pull(/function koActual\(t\)\{[\s\S]*?\n  \}/, 'koActual'),
  pull(/const byKO = [^\n]*/, 'byKO'),
  pull(/function scheduleAnchor\(matches, now\)\{[\s\S]*?\n  \}/, 'scheduleAnchor'),
  pull(/const esc = s => [^\n]*/, 'esc'),
  pull(/function scRow\(rk, who, sub, val\)\{[\s\S]*?\n  \}/, 'scRow'),
  'let G = {}, MODELS = {}, CUR = "", T = {}, DATA = {};',         // group + payload context the helpers close over
  pull(/function allMatches\(\)\{[\s\S]*?return a; \}/, 'allMatches'),
  pull(/function groupStandings\(g\)\{[\s\S]*?\n  \}/, 'groupStandings'),
  pull(/function predRankOf\(g\)\{[\s\S]*?\n  \}/, 'predRankOf'),
  pull(/function fullStandingCalled\(g\)\{[\s\S]*?\n  \}/, 'fullStandingCalled'),
  pull(/function thirdsRanking\(\)\{[\s\S]*?\n  \}/, 'thirdsRanking'),
  pull(/const KO_ROUNDS = \[[\s\S]*?\];/, 'KO_ROUNDS'),
  pull(/function koDesc\(d\)\{[\s\S]*?\n  \}/, 'koDesc'),
  pull(/function koSide\(desc\)\{[\s\S]*?\n  \}/, 'koSide'),
  pull(/function koLabel\(desc\)\{[\s\S]*?\n  \}/, 'koLabel'),
  pull(/function advanceLabel\(a\)\{[\s\S]*?\n  \}/, 'advanceLabel'),
  pull(/function scheduleUnits\(\)\{[\s\S]*?\n  \}/, 'scheduleUnits'),
  pull(/function koRounds\(\)\{[\s\S]*?\n  \}/, 'koRounds'),
  pull(/function matchSearch\(mm, a\)\{[\s\S]*?\n  \}/, 'matchSearch'),
  pull(/const liveSearch = [^\n]*/, 'liveSearch'),
  'this.predTier = predTier; this.setActuals = o => { ACTUALS = o; };',
  'this.esc = esc; this.scRow = scRow; this.groupStandings = groupStandings; this.matchSearch = matchSearch; this.liveSearch = liveSearch;',
  'this.predRankOf = predRankOf; this.fullStandingCalled = fullStandingCalled; this.thirdsRanking = thirdsRanking; this.koDesc = koDesc;',
  'this.scheduleUnits = scheduleUnits; this.koRounds = koRounds; this.parseActuals = parseActuals;',
  'this.setGroupCtx = (g, models, cur, t) => { G = g; MODELS = models; CUR = cur; T = t; }; this.setData = d => { DATA = d; };',
].join('\n');

const sandbox = {};
vm.runInNewContext(snippet, sandbox);
const { matchState, parseActuals, parseScorers, predTier, koActual, scheduleAnchor, esc, scRow, groupStandings, predRankOf, fullStandingCalled, thirdsRanking, koDesc, koSide, koLabel, advanceLabel, scheduleUnits, koRounds, matchSearch, liveSearch } = sandbox;

// ---- matchState: the live/awaiting clock ----
const KO = Date.parse('2026-06-14T04:00Z');   // Australia v Turkiye kickoff (the reported case)
const MIN = 60e3, HOUR = 3600e3;

eq(matchState(KO - HOUR, KO, false), 'future', 'before kickoff is future');
eq(matchState(KO + 30 * MIN, KO, false), 'live', 'within 2h of kickoff with no result is live');
eq(matchState(KO + 90 * MIN, KO, false), 'live', 'still live at +90 min');
// the regression: 7h47m after kickoff (now), feed has not posted the score yet
eq(matchState(Date.parse('2026-06-14T11:47Z'), KO, false), 'awaiting',
   'kicked off, +7.78h, no result: must stay awaiting (was wrongly dropped at +6h)');
eq(matchState(KO + 48 * HOUR, KO, false), 'awaiting', 'awaiting persists with no upper bound');
eq(matchState(KO + 48 * HOUR, KO, true), 'done', 'a result, however late, ends the badge');
eq(matchState(KO + 30 * MIN, KO, true), 'done', 'an early-posted result is done, never live');

// ---- parseActuals: the in-browser feed parser ----
const feed =
  'Sat June 13\n' +
  '  21:00 UTC-7    Mexico   2-0 (1-0)   South Africa   @ Estadio Azteca\n' +
  '  21:00 UTC-7    Australia       v Turkey   @ Vancouver\n' +    // not played yet: no score
  '  18:00 UTC-4    Turkey   1-1 (0-0)   Czech Republic   @ X\n';  // name-mapped both sides
const acts = parseActuals(feed);
const keys = Object.keys(acts).sort();

eq(keys.length, 2, 'two played games parsed, the unplayed one skipped');
eq(acts['2026-06-13|Mexico|South Africa'], { home: 'Mexico', away: 'South Africa', hs: 2, as: 0 },
   'played game parsed with correct score and key');
eq(acts['2026-06-13|Czechia|Turkiye'], { home: 'Turkiye', away: 'Czechia', hs: 1, as: 1 },
   'Turkey -> Turkiye and Czech Republic -> Czechia mapped');
eq(acts.hasOwnProperty('2026-06-13|Australia|Turkiye'), false,
   'an unplayed fixture produces no actual result');

// ---- predTier: the score colour must agree with the score the card shows ----
// graded on the modal scoreline, not the W/D/L favorite, so a drawn headline score can never
// read green against a decisive result.
const tier = (modal, hs, as) => predTier({ modal }, { hs, as });
eq(tier([1, 1], 1, 1), 'exact', 'modal equals the result: exact (dark green)');
// the reported bug: 1-1 predicted (a draw) against Australia 2-0 (a home win) must be a miss, not green
eq(tier([1, 1], 2, 0), 'miss', 'drawn prediction vs a 2-0 home win is a miss, not "right result"');
eq(tier([1, 1], 0, 1), 'miss', 'drawn prediction vs a 0-1 away win is a miss');
eq(tier([1, 1], 0, 0), 'result', 'drawn prediction vs a 0-0 draw: right result, wrong score');
eq(tier([2, 1], 3, 0), 'result', 'home prediction vs a home win, different score: right result');
eq(tier([2, 1], 0, 2), 'miss', 'home prediction vs an away win is a miss');

// ---- parseActuals: a played game missing its half-time score must still parse ----
// regression: the feed sometimes posts a result before the "(x-x)" half-time token, and the
// game must not be dropped (which would also leave it out of the live overlay).
const noHT = parseActuals('Sun June 14\n  12:00 UTC-5    Germany 7-1 Curacao   @ Houston\n');
eq(noHT['2026-06-14|Curacao|Germany'], { home: 'Germany', away: 'Curacao', hs: 7, as: 1 },
   'a played game with no half-time score still parses');

// ---- parseScorers: the live Golden Boot leaderboard from the feed ----
const sc = parseScorers(sample);
const find = name => sc.find(s => s.player === name);
const havertz = find('Kai Havertz');
eq(havertz && havertz.goals, 2, 'a penalty written (p) is credited: Havertz keeps his brace, not 1');
eq(havertz && havertz.team, 'Germany', "the scorer's team is read from the match line");
eq(find('p'), undefined, 'the (p) penalty tag is never read as a player named "p"');
eq(find('Damian Bobadilla'), undefined, 'an own goal (og) does not credit the scorer');
eq((find('Folarin Balogun') || {}).goals, 2, 'two minutes on one scorer count as two goals');
const comen = find('Livano Comenencia');
eq(comen && comen.goals, 1, "the away side's lone scorer is attributed correctly");
eq(comen && comen.team, 'Curacao', 'lone away scorer gets the away team');
eq((find('Sebastien Haller') || {}).team, 'Ivory Coast',
   "an official FIFA name (Cote d'Ivoire) maps to the engine team on the scorer");
eq(sc.reduce((a, b) => a + b.goals, 0), 15, 'every credited goal counted once, the own goal excluded');
eq(sc.length, 13, 'one row per real scorer, no phantom rows');

// the feed ships CRLF; it must parse identically to LF
const scCRLF = parseScorers(sample.replace(/\n/g, '\r\n'));
eq(scCRLF.length, sc.length, 'CRLF line endings parse the same as LF');
eq((scCRLF.find(s => s.player === 'Kai Havertz') || {}).goals, 2, 'CRLF: the penalty is still credited');

// ---- end to end: the whole sample feed through parseActuals ----
const overlay = parseActuals(sample);
eq(Object.keys(overlay).length, 5, 'five played games overlay, the unplayed " v " fixture skipped');
eq(overlay['2026-06-20|Ecuador|Ivory Coast'], { home: 'Ivory Coast', away: 'Ecuador', hs: 1, as: 0 },
   'official FIFA name maps and the result keys correctly end to end');
eq(overlay['2026-06-14|Mexico|South Africa'], { home: 'Mexico', away: 'South Africa', hs: 2, as: 0 },
   'a played game with no half-time score overlays end to end');
eq(overlay.hasOwnProperty('2026-06-14|Australia|Turkiye'), false, 'the unplayed fixture produces no result');

// ---- koActual: the knockout result, server-conditioned or live from the feed ----
// the bracket tab reuses the Schedule/Groups live pattern; koActual is the one new piece, so it is
// the one that gets pinned. (Built and verified against a synthetic bracket; the real ties carry
// kickoff times once the round of 32 is set.)
sandbox.setActuals(parseActuals(
  'Sun June 28\n' +
  '  16:00 UTC-4    Spain 2-1 (1-0) France   @ X\n' +
  '  19:00 UTC-4    Brazil 1-1 (0-0) England   @ Y\n'));
const koBase = { adv_a: 60, adv_b: 40, modal: [2, 1], p_a: 0.5, p_draw: 0.25, p_away: 0.25, top_scores: [[2, 1, 9]] };
const koTie = o => Object.assign({}, koBase, o);
eq(koActual(koTie({ a: 'Spain', b: 'France', played: { hs: 3, as_: 0, winner: 'Spain' } })),
   { hs: 3, as: 0, winner: 'Spain' }, 'a server-conditioned result takes priority and keeps its winner');
eq(koActual(koTie({ a: 'Spain', b: 'France', date: '2026-06-28' })),
   { hs: 2, as: 1, winner: 'Spain' }, 'a decisive live feed result overlays, the advancer derived from the score');
eq(koActual(koTie({ a: 'France', b: 'Spain', date: '2026-06-28' })),
   { hs: 1, as: 2, winner: 'Spain' }, 'the feed result orients to the tie, the advancer stays correct');
eq(koActual(koTie({ a: 'Brazil', b: 'England', date: '2026-06-28' })),
   { hs: 1, as: 1, winner: null }, 'a drawn feed result leaves the advancer to a shootout the score cannot read');
eq(koActual(koTie({ a: 'Spain', b: 'France' })), null, 'no server result and no date: nothing to overlay');

// later rounds behave exactly like the round of 32 (koActual is round-agnostic), and crucially a tie
// whose predicted matchup did not actually happen (the bracket diverged past R32) shows no result.
sandbox.setActuals(parseActuals('Sat July 4\n  16:00 UTC-4    Spain 2-0 (1-0) Portugal   @ X\n'));
eq(koActual(koTie({ a: 'Spain', b: 'Portugal', date: '2026-07-04', round: 'qf' })),
   { hs: 2, as: 0, winner: 'Spain' }, 'a later-round tie overlays the real result just like the round of 32');
eq(koActual(koTie({ a: 'Spain', b: 'Uruguay', date: '2026-07-04', round: 'qf' })), null,
   'a tie whose predicted opponent never advanced shows no result, never a wrong one');

// ---- scheduleAnchor: the Schedule jumps to the match in focus, by time (not by day) ----
// x 6pm, y 10pm, z midnight. The anchor follows the clock so you land on the live game.
const M = ko => ({ kickoff_utc: ko });
const day = [M('2026-06-20T18:00Z'), M('2026-06-20T22:00Z'), M('2026-06-21T00:00Z')];
const anchorAt = nowISO => { const t = scheduleAnchor(day, Date.parse(nowISO)); return t && t.kickoff_utc; };
eq(anchorAt('2026-06-20T19:00Z'), '2026-06-20T18:00Z', '7pm: the 6pm game in play (x)');
eq(anchorAt('2026-06-20T22:30Z'), '2026-06-20T22:00Z', '10:30pm: the 10pm game (y)');
eq(anchorAt('2026-06-20T23:59Z'), '2026-06-20T22:00Z', '11:59pm: still y, not the upcoming midnight game');
eq(anchorAt('2026-06-21T00:00Z'), '2026-06-21T00:00Z', 'midnight: the just-kicked-off game (z)');
eq(anchorAt('2026-06-20T12:00Z'), '2026-06-20T18:00Z', 'before any game: the next upcoming (x)');
eq(anchorAt('2026-06-21T05:00Z'), '2026-06-21T00:00Z', 'all done: the last game (z)');
// the rollover bug: an 11pm game running to 1am keeps focus at 00:30, not the next day
const lateNight = [M('2026-06-20T23:00Z'), M('2026-06-21T16:00Z')];
eq(scheduleAnchor(lateNight, Date.parse('2026-06-21T00:30Z')).kickoff_utc, '2026-06-20T23:00Z',
   'a game running past midnight keeps focus at 00:30, not jumping to the next day');

// ---- esc + scRow: feed-derived scorer names and teams are escaped before they reach innerHTML ----
// regression: a hostile or garbled feed line must not inject live markup into the Golden Boot list.
eq(esc('<img src=x onerror=alert(1)>'), '&lt;img src=x onerror=alert(1)&gt;', 'esc neutralizes angle brackets');
eq(esc('Mbappe'), 'Mbappe', 'esc leaves a normal name unchanged');
const xrow = scRow(1, '<b>x</b>', 'A&B', 3);
eq(xrow.includes('<b>x</b>'), false, 'scRow does not emit raw injected markup from a feed name');
eq(xrow.includes('&lt;b&gt;x&lt;/b&gt;'), true, 'scRow emits the escaped scorer name');
eq(xrow.includes('A&amp;B'), true, 'scRow escapes the ampersand in the team field');

// ---- groupStandings: the live table follows FIFA 2026 order (head-to-head before overall GD) ----
// A1 and A2 finish level on points; A1 beat A2 head-to-head but A2 has the better overall goal
// difference. The official rule ranks A1 above A2; an overall-GD-first sort would wrongly flip them.
sandbox.setGroupCtx(
  { A: ['A1', 'A2', 'A3', 'A4'] },
  { m: { teams: { A1: { elo: 1800 }, A2: { elo: 1810 }, A3: { elo: 1820 }, A4: { elo: 1790 } },
         group_matches: { A: [
    { home: 'A1', away: 'A2', date: '2026-06-20' },
    { home: 'A1', away: 'A3', date: '2026-06-21' },
    { home: 'A2', away: 'A4', date: '2026-06-22' },
    { home: 'A3', away: 'A4', date: '2026-06-23' },
  ] } } },
  'm', {});
sandbox.setActuals({
  '2026-06-20|A1|A2': { home: 'A1', away: 'A2', hs: 1, as: 0 },   // A1 beats A2 head-to-head
  '2026-06-21|A1|A3': { home: 'A1', away: 'A3', hs: 0, as: 2 },   // A1 overall GD sinks to -1
  '2026-06-22|A2|A4': { home: 'A2', away: 'A4', hs: 4, as: 0 },   // A2 overall GD climbs to +3
  '2026-06-23|A3|A4': { home: 'A3', away: 'A4', hs: 1, as: 0 },
});
const gs = groupStandings('A');
eq(gs.tbl.A1.pts === 3 && gs.tbl.A2.pts === 3, true, 'A1 and A2 are level on points');
eq(gs.tbl.A2.gd > gs.tbl.A1.gd, true, 'A2 has the better overall goal difference');
eq(gs.pos, { A3: 1, A1: 2, A2: 3, A4: 4 },
   'head-to-head ranks A1 above A2 despite A2 having the better overall GD (overall-GD-first would flip them)');

// a total tie (drawn head-to-head, equal points/GD/GF) falls through to the Elo tiebreak, last of all.
// regression guard: groupStandings reads Elo from MODELS[CUR].teams, not an out-of-scope global (which
// threw "T is not defined" at first render, when every team is level on zero points).
sandbox.setGroupCtx(
  { B: ['B1', 'B2'] },
  { m: { teams: { B1: { elo: 1700 }, B2: { elo: 1900 } }, group_matches: { B: [
    { home: 'B1', away: 'B2', date: '2026-06-20' },
  ] } } },
  'm', {});
sandbox.setActuals({ '2026-06-20|B1|B2': { home: 'B1', away: 'B2', hs: 0, as: 0 } });
eq(groupStandings('B').pos, { B2: 1, B1: 2 },
   'a total tie breaks to the higher Elo, and reading Elo never throws');

// ---- groupStandings: head-to-head re-application in a three-way tie (mirrors the engine) ----
// A1 beat A2 2-0, A2 beat A3 3-0, A3 beat A1 1-0; all three beat A4. The three-team head-to-head is
// a cycle, head-to-head GD ties A1 and A2 (A3 drops to 3rd). FIFA re-applies to {A1,A2}: A1 2-0 A2 ->
// A1 first. A flat sort would go to three-team head-to-head goals (A1 2, A2 3) and wrongly put A2 first.
sandbox.setGroupCtx(
  { A: ['A1', 'A2', 'A3', 'A4'] },
  { m: { teams: { A1: { elo: 1800 }, A2: { elo: 1810 }, A3: { elo: 1820 }, A4: { elo: 1790 } },
         group_matches: { A: [
    { home: 'A1', away: 'A2', date: '2026-06-20' }, { home: 'A2', away: 'A3', date: '2026-06-21' },
    { home: 'A3', away: 'A1', date: '2026-06-22' }, { home: 'A1', away: 'A4', date: '2026-06-23' },
    { home: 'A2', away: 'A4', date: '2026-06-24' }, { home: 'A3', away: 'A4', date: '2026-06-25' },
  ] } } }, 'm', {});
sandbox.setActuals({
  '2026-06-20|A1|A2': { home: 'A1', away: 'A2', hs: 2, as: 0 },
  '2026-06-21|A2|A3': { home: 'A2', away: 'A3', hs: 3, as: 0 },
  '2026-06-22|A3|A1': { home: 'A3', away: 'A1', hs: 1, as: 0 },
  '2026-06-23|A1|A4': { home: 'A1', away: 'A4', hs: 1, as: 0 },
  '2026-06-24|A2|A4': { home: 'A2', away: 'A4', hs: 1, as: 0 },
  '2026-06-25|A3|A4': { home: 'A3', away: 'A4', hs: 1, as: 0 },
});
eq(groupStandings('A').pos, { A1: 1, A2: 2, A3: 3, A4: 4 },
   'three-way tie: re-applying head-to-head to the survivors ranks A1 above A2 (a flat sort would flip them)');

// ---- fullStandingCalled: grades the whole finishing order against the Day 0 prediction ----
// A finished group: each higher-listed team beats the lower 1-0, so the table is T1,T2,T3,T4.
const rr = [['T1', 'T2'], ['T1', 'T3'], ['T1', 'T4'], ['T2', 'T3'], ['T2', 'T4'], ['T3', 'T4']];
const rrMatches = rr.map(([h, a], i) => ({ home: h, away: a, date: `2026-06-2${i}` }));
const rrActuals = {};
rr.forEach(([h, a], i) => { rrActuals[`2026-06-2${i}|${h}|${a}`] = { home: h, away: a, hs: 1, as: 0 }; });
const teamsWith = g0 => ({
  T1: { elo: 1800, win_group0: g0[0], advance0: 90 }, T2: { elo: 1700, win_group0: g0[1], advance0: 80 },
  T3: { elo: 1600, win_group0: g0[2], advance0: 70 }, T4: { elo: 1500, win_group0: g0[3], advance0: 60 },
});
// Day 0 order T1>T2>T3>T4 matches the actual table -> called (T is the teams dict, as in the app)
let tw = teamsWith([50, 30, 15, 5]);
sandbox.setGroupCtx({ A: ['T1', 'T2', 'T3', 'T4'] },
  { m: { teams: tw, group_matches: { A: rrMatches } } }, 'm', tw);
sandbox.setActuals(rrActuals);
eq(fullStandingCalled('A'), true, 'finished group whose Day 0 order matches the final table is called');
// Day 0 order reversed -> the model missed it
tw = teamsWith([5, 15, 30, 50]);
sandbox.setGroupCtx({ A: ['T1', 'T2', 'T3', 'T4'] },
  { m: { teams: tw, group_matches: { A: rrMatches } } }, 'm', tw);
sandbox.setActuals(rrActuals);
eq(fullStandingCalled('A'), false, 'finished group whose predicted order misses the table is not called');
// only some games played -> not gradable yet
sandbox.setActuals({ '2026-06-20|T1|T2': { home: 'T1', away: 'T2', hs: 1, as: 0 } });
eq(fullStandingCalled('A'), null, 'an unfinished group is null (excluded from the count)');

// ---- thirdsRanking: third-placed teams ranked across groups (points -> GD -> goals) ----
// Two finished groups; each third has 3 points, but group X's third has GD -2 (2-0 margins) and
// group Y's third GD -1 (1-0 margins), so Y's third must rank above X's.
(function(){
  const tm = g => [g+'1', g+'2', g+'3', g+'4'];
  const G = { X: tm('X'), Y: tm('Y') };
  const teams = {}; Object.values(G).flat().forEach((t,i)=>teams[t]={elo:1500+i});
  const pairs = ts => { const o=[]; for(let i=0;i<ts.length;i++) for(let j=i+1;j<ts.length;j++) o.push([ts[i],ts[j]]); return o; };
  const gm = {}, acts = {}; let d = 10;
  [['X',2],['Y',1]].forEach(([g,margin])=>{                 // first team in each pair wins margin-0
    gm[g] = pairs(G[g]).map(([h,a],k)=>{
      const date = `2026-07-${String(d+k).padStart(2,'0')}`;
      acts[`${date}|${h}|${a}`] = { home:h, away:a, hs:margin, as:0 };
      return { home:h, away:a, date };
    });
    d += 10;
  });
  sandbox.setGroupCtx(G, { m:{ teams, group_matches: gm } }, 'm', teams);
  sandbox.setActuals(acts);
  const r = thirdsRanking();
  eq(r.length, 2, 'one third-placed team per group');
  eq(r.map(x=>x.team), ['Y3','X3'], 'thirds tied on points are ordered by goal difference (Y3 -1 above X3 -2)');
  eq(r[0].pts === 3 && r[1].pts === 3 && r[0].gd > r[1].gd, true, 'both on 3 points, leader has the better GD');
})();

// ---- koDesc: bracket-position placeholders rendered for the schedule / bracket ----
eq(koDesc('1A'), 'Winner A', 'group winner descriptor');
eq(koDesc('2C'), 'Runner-up C', 'group runner-up descriptor');
eq(koDesc('3'), '3rd place', 'third-placed descriptor');
eq(koDesc('W73'), 'Winner M73', 'match-winner descriptor');
eq(koDesc('L101'), 'Loser M101', 'match-loser descriptor (third-place play-off)');

// ---- koSide / koLabel: half-known brackets (fill the side we already know, give context for the rest) ----
(function(){
  const rr=[['A1','A2'],['A1','A3'],['A1','A4'],['A2','A3'],['A2','A4'],['A3','A4']];   // A1>A2>A3>A4
  const gm=rr.map(([h,a],i)=>({home:h,away:a,date:`2026-06-2${i}`}));
  const acts={}; rr.forEach(([h,a],i)=>acts[`2026-06-2${i}|${h}|${a}`]={home:h,away:a,hs:1,as:0});
  const teams={A1:{elo:4},A2:{elo:3},A3:{elo:2},A4:{elo:1}};
  const ko={90:{a:'X',b:'Y',played:{hs:2,as_:1,winner:'X'}}};                          // a played match
  const koSched=[{slot:90,round:'r16',home_desc:'W73',away_desc:'W75'},{slot:75,round:'r32',home_desc:'1A',away_desc:'2A'}];
  sandbox.setGroupCtx({A:['A1','A2','A3','A4']}, {m:{teams, group_matches:{A:gm}, knockout:ko}}, 'm', teams);
  sandbox.setData({ ko_schedule: koSched });
  sandbox.setActuals(acts);
  eq(koSide('1A'),'A1','group winner known once the group finishes');
  eq(koSide('2A'),'A2','runner-up known');
  eq(koSide('W90'),'X','winner of a played match');
  eq(koSide('L90'),'Y','loser of a played match');
  eq(koSide('3'),null,'a best-third place stays unknown');
  // koLabel gives context for a not-yet-played match: the feeding matchup, with teams filled where known
  eq(koLabel('W75'),'Winner of A1/A2','undecided match reads as its feeding matchup (teams filled in)');
  eq(koLabel('W90'),'X','a decided match reads as the team that won it');
  // group not finished -> side unknown, label falls back to the group slot
  sandbox.setActuals({'2026-06-20|A1|A2':{home:'A1',away:'A2',hs:1,as:0}});
  eq(koSide('1A'),null,'group winner null until the group is finished');
  eq(koLabel('1A'),'Winner A','an unfinished group slot still reads clearly');
})();

// ---- advanceLabel: how a knockout tie was decided (penalties shown explicitly) ----
eq(advanceLabel({winner:'Canada',hs:1,as:0}),'Canada advanced','a decisive result advances');
eq(advanceLabel({winner:'Canada',hs:1,as:1}),'Canada won on penalties','a draw after 120 min with an advancer is penalties');
eq(advanceLabel({winner:null,hs:1,as:1}),'to a shootout','a draw with no advancer yet is pending the shootout');

// ---- scheduleUnits / koRounds: the data behind the Schedule list and the bracket ----
(function(){
  const koSched = [
    {slot:73, round:'r32',  kickoff_utc:'2026-06-28T19:00Z'},
    {slot:103,round:'final',kickoff_utc:'2026-07-19T19:00Z'},
    {slot:104,round:'third',kickoff_utc:'2026-07-18T21:00Z'},
  ];
  sandbox.setGroupCtx({ A:['A1','A2'] },
    { m:{ teams:{A1:{elo:1},A2:{elo:1}}, group_matches:{ A:[{home:'A1',away:'A2',kickoff_utc:'2026-06-11T19:00Z'}] } } }, 'm', {});
  sandbox.setData({ ko_schedule: koSched });
  const u = scheduleUnits();
  eq(u.length, 4, 'schedule merges group games and the whole knockout calendar');
  eq(u.map(x=>x.k), ['2026-06-11T19:00Z','2026-06-28T19:00Z','2026-07-18T21:00Z','2026-07-19T19:00Z'],
     'units are sorted by kickoff (group game, R32, third-place, final)');
  eq(u[0].kind, 'g', 'first unit is the group game'); eq(u[2].kind, 'k', 'third-place is a knockout unit');
  const rounds = koRounds().map(r=>r.round);
  eq(rounds, ['r32','third','final'], 'koRounds keeps round order and includes the third-place play-off');
})();

// ---- live overlay end-to-end: the real feed parser into a knockout result (closes the headless gap) ----
(function(){
  const feed = 'Sun June 28\n  20:00 UTC-7    South Africa   1-2 (0-1)   Canada   @ Los Angeles\n';
  sandbox.setActuals(parseActuals(feed));                       // exactly what the live heartbeat does
  const tie = { a:'South Africa', b:'Canada', date:'2026-06-28' };
  const res = koActual(tie);
  eq(res && res.hs, 1, 'a knockout result line parses through to koActual (home score)');
  eq(res.as, 2, 'away score'); eq(res.winner, 'Canada', 'the decisive score yields the advancer');
})();

// ---- matchSearch / liveSearch: a Google query that always pins one exact match ----
const finURL = matchSearch({ home: 'Mexico', away: 'South Africa', date: '2026-06-14' }, { hs: 2, as: 0 });
eq(decodeURIComponent(finURL.split('q=')[1]), 'Mexico vs South Africa 2-0 2026-06-14 World Cup',
   'finished card search: teams, score, date, and "World Cup" all in the query');
const liveURL = liveSearch({ home: 'Mexico', away: 'South Africa', date: '2026-06-14' });
eq(decodeURIComponent(liveURL.split('q=')[1]), 'Mexico vs South Africa 2026-06-14 World Cup',
   'in play / awaiting search: teams and date, no score (unknown), no leftover double space');

console.log(failed
  ? `\n${failed} failed, ${passed} passed.`
  : `OK: ${passed} assertions passed (matchState clock, parseActuals + parseScorers feed parsers, predTier scoring, koActual knockout overlay, scheduleAnchor jump, end-to-end sample feed).`);
process.exit(failed ? 1 : 0);
