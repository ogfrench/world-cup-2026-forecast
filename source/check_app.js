// CI sanity check for the built app. Run: node source/check_app.js
// Confirms index.html is actually built (no leftover token), every <script>
// block parses, and DATA carries all five models. No dependencies.
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const file = path.join(__dirname, '..', 'index.html');
const html = fs.readFileSync(file, 'utf8');

function fail(msg) { console.error('FAIL: ' + msg); process.exit(1); }

if (html.includes('/*DATA*/')) fail('index.html still contains the /*DATA*/ token (it was not built).');

const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (blocks.length < 3) fail(`expected at least 3 script blocks, found ${blocks.length}.`);
blocks.forEach((b, i) => {
  try { new vm.Script(b, { filename: `script-block-${i}.js` }); }
  catch (e) { fail(`script block ${i} does not parse: ${e.message}`); }
});

const m = html.match(/const DATA = ([\s\S]*?);<\/script>/);
if (!m) fail('could not find the DATA assignment.');
let data;
try { data = JSON.parse(m[1]); }
catch (e) { fail(`DATA is not valid JSON: ${e.message}`); }

const models = Object.keys(data.models || {});
for (const k of ['elo', 'score', 'hybrid', 'market', 'market_pure']) {
  if (!models.includes(k)) fail(`missing model "${k}".`);
}

// each model must carry real content (a crash mid-write could leave an empty model that builds
// clean but breaks in the browser), and the group matches must carry the merged schedule the app
// sorts and renders (date + kickoff time). This catches a make_data/merge step that silently failed.
for (const k of models) {
  const m = data.models[k] || {};
  if (!m.teams || !Object.keys(m.teams).length) fail(`model "${k}" has no teams.`);
  if (!m.group_matches || !Object.keys(m.group_matches).length) fail(`model "${k}" has no group_matches.`);
}
const gm = data.models.market_pure.group_matches;
const sample = gm[Object.keys(gm)[0]][0];
if (!sample || !sample.kickoff_utc || !sample.date)
  fail('group matches lack the merged schedule (kickoff_utc/date); did merge_schedule.py run?');
const def = (data.meta || {}).default_model;
if (!['elo', 'score', 'hybrid', 'market', 'market_pure'].includes(def))
  fail(`meta.default_model "${def}" is not one of the five models.`);

console.log(`OK: ${blocks.length} script blocks parse, ${models.length} models present with teams + scheduled group matches, build is clean.`);
