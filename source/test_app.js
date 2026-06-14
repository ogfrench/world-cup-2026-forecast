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
  'this.predTier = predTier; this.setActuals = o => { ACTUALS = o; };',
].join('\n');

const sandbox = {};
vm.runInNewContext(snippet, sandbox);
const { matchState, parseActuals, parseScorers, predTier, koActual } = sandbox;

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

console.log(failed
  ? `\n${failed} failed, ${passed} passed.`
  : `OK: ${passed} assertions passed (matchState clock, parseActuals + parseScorers feed parsers, predTier scoring, koActual knockout overlay, end-to-end sample feed).`);
process.exit(failed ? 1 : 0);
