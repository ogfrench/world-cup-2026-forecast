// Tests for the in-browser live layer, run against the BUILT index.html so they
// cover exactly what ships. No dependencies. Run: node source/test_app.js
//
// Two mission-critical, low-maintenance pieces:
//   matchState  - the clock that decides the live / awaiting badge. The regression
//                 it guards: a played game whose result the feed has not posted yet
//                 must keep its "awaiting" placeholder, not silently look unplayed.
//   parseActuals - the in-browser feed parser that overlays real results.
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

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
  pull(/const scoreOutcome = [^\n]*/, 'scoreOutcome'),
  pull(/const actOutcome = [^\n]*/, 'actOutcome'),
  pull(/const predTier = \(mm,a\) =>[\s\S]*?'miss'\);/, 'predTier'),
  'this.predTier = predTier;',   // predTier is a const arrow, so surface it on the sandbox
].join('\n');

const sandbox = {};
vm.runInNewContext(snippet, sandbox);
const { matchState, parseActuals, predTier } = sandbox;

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

console.log(failed
  ? `\n${failed} failed, ${passed} passed.`
  : `OK: ${passed} assertions passed (matchState clock, parseActuals feed parser, predTier scoring).`);
process.exit(failed ? 1 : 0);
