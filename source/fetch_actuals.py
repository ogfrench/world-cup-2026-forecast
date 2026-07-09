#!/usr/bin/env python3
"""Refresh wc2026_actuals.json from the openfootball feed.

Downloads the public World Cup 2026 results and writes two files: the played GROUP
matches from cup.txt (mapped to engine names, oriented to the official home/away via
wc2026_schedule.json) into wc2026_actuals.json, and the played KNOCKOUT results from
cup_finals.txt (with the penalty-shootout winner on a draw) into wc2026_ko_actuals.json.
The autonomous refresh runs this before re-simulating; it is also safe to run by hand.

    python3 source/fetch_actuals.py
"""
import json, os, re, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = 'https://raw.githubusercontent.com/openfootball/worldcup/master/2026--usa/cup.txt'
# Knockout results live in a separate file, lines keyed by match number, e.g.
#   (74) 16:30 UTC-4  Germany 1-1 a.e.t. (1-1, 1-1), 4-2 pen. Paraguay  @ Boston  ## 1E / 3A/B/C/D/F
# The score is the 120-minute result; a "P1-P2 pen." note (openfootball's convention, see 2022) gives
# the shootout winner on a draw, which the score alone cannot.
KO_SRC = 'https://raw.githubusercontent.com/openfootball/worldcup/master/2026--usa/cup_finals.txt'
# feed name -> engine name (everything else is identical); mirrors ACT_NAME in the app.
# Includes the official FIFA names the feed's own notes warn it may switch to (Côte d'Ivoire,
# Korea Republic, ...), so a normalised feed still lands as a group game, not a phantom knockout tie.
NAME = {'Czech Republic': 'Czechia', 'Bosnia & Herzegovina': 'Bosnia-Herzegovina',
        'Bosnia and Herzegovina': 'Bosnia-Herzegovina', 'Turkey': 'Turkiye', 'Türkiye': 'Turkiye',
        'Curaçao': 'Curacao', "Côte d'Ivoire": 'Ivory Coast', 'Korea Republic': 'South Korea',
        'IR Iran': 'Iran', 'Cabo Verde': 'Cape Verde', 'Congo DR': 'DR Congo'}
MON = {'May': 5, 'June': 6, 'July': 7}
nm = lambda s: NAME.get(s.strip(), s.strip())

# The openfootball feed occasionally rate-limits (HTTP 429) or returns a transient 5xx, which used to
# red-X the whole scheduled refresh on a single hiccup. Retry those (and network errors) with a short
# backoff; a 429 Retry-After is honored when present. A 4xx that is not 429 is a real error, not retried.
RETRY_CODES = {429, 500, 502, 503, 504}

def fetch(url, timeout=30, tries=4):
    for attempt in range(1, tries + 1):
        try:
            return urllib.request.urlopen(url, timeout=timeout).read().decode('utf-8')
        except urllib.error.HTTPError as ex:
            if ex.code not in RETRY_CODES or attempt == tries:
                raise
            wait = ex.headers.get('Retry-After') if ex.code == 429 else None
            delay = int(wait) if (wait or '').isdigit() else 2 ** attempt
        except (urllib.error.URLError, TimeoutError) as ex:
            if attempt == tries:
                raise
            delay = 2 ** attempt
        sys.stderr.write('fetch %s failed (attempt %d/%d): retrying in %ds\n' % (url, attempt, tries, delay))
        time.sleep(delay)

DRE = re.compile(r'^[A-Z][a-z]{2}\s+([A-Z][a-z]+)\s+(\d{1,2})\s*$')
# the half-time score in parentheses is optional: a played game that is missing it must still parse,
# not be silently dropped (which would also leave it out of the conditioned odds).
MRE = re.compile(r'^\s*\d{1,2}:\d{2}\s+UTC[+-]\d+\s+(.+?)\s+(\d+)-(\d+)(?:\s+\([0-9-]+\))?\s+(.+?)\s+@\s+')

# A played knockout line: "(74) 16:30 UTC-4  Germany 1-1 a.e.t. (1-1, 1-1), 4-2 pen. Paraguay  @ ..."
# Captures match number, home, the 120-minute score, an optional "P1-P2 pen." shootout, and away.
# An unplayed line reads "Germany v Paraguay", whose " v " has no digits, so it does not match.
KRE = re.compile(
    r'^\s*\((\d+)\)\s+\d{1,2}:\d{2}\s+UTC[+-]\d+\s+'   # (match#) kickoff
    r'(.+?)\s+(\d+)-(\d+)'                              # home, 120-minute score
    r'(?:\s+a\.e\.t\.?)?'                               # optional "a.e.t."
    r'(?:\s*\([0-9,\s-]+\))?'                           # optional "(reg, et)" breakdown
    r'(?:\s*,?\s*(\d+)-(\d+)\s+pen\.?)?'                # optional "P1-P2 pen." shootout
    r'\s+(.+?)\s+@\s')                                  # away, then "@ venue"

def played_finals_lines(txt):
    """Loose count of knockout lines that look PLAYED: a "(NN)" match number, a real "H-A" score, and
    "@ venue". Deliberately looser than KRE, so if parse_finals (strict) matches none while this finds
    some, the feed format has drifted. Unplayed lines read " v " and have no H-A, so they do not count."""
    return len([l for l in (txt or '').splitlines() if re.search(r'\(\d+\)\s.*\d-\d.*@', l)])

def parse_finals(txt, canon):
    """Parse played knockout results from the finals feed into
    [{home, away, hs, as, winner, aet}] (120-minute score; winner from the score, or the shootout on a
    draw, or None if a draw has no shootout line yet; aet True if the tie went to extra time, i.e. the
    line is marked a.e.t. or has a penalty shootout). Names mapped to engine names; unknown skipped."""
    out = []
    for ln in txt.splitlines():
        m = KRE.match(ln)
        if not m:
            continue
        h, hs, ag, a = nm(m.group(2)), int(m.group(3)), int(m.group(4)), nm(m.group(7))
        if h not in canon or a not in canon:
            sys.stderr.write('warning: unrecognised team in finals feed, skipped: %r vs %r\n' % (h, a))
            continue
        pens = m.group(5) is not None
        pk = [int(m.group(5)), int(m.group(6))] if pens else None   # shootout score, home-away as the feed gives it
        if hs > ag:
            winner = h
        elif ag > hs:
            winner = a
        elif pens:                                     # level, decided on penalties
            winner = h if pk[0] > pk[1] else a if pk[1] > pk[0] else None
        else:
            winner = None                              # drawn, no shootout line yet
        aet = pens or ('a.e.t' in ln.lower())          # went to extra time (then maybe penalties)
        rec = {'home': h, 'away': a, 'hs': hs, 'as': ag, 'winner': winner, 'aet': aet}
        if pk:
            rec['pens'] = pk                           # carried so the app can show "won on penalties (5-4)"
        out.append(rec)
    return out

def parse(txt):
    out, date = [], None
    for ln in txt.splitlines():
        d = DRE.match(ln)
        if d:
            mo = MON.get(d.group(1))
            if mo:
                date = '2026-%02d-%02d' % (mo, int(d.group(2)))
            continue
        m = MRE.match(ln)
        if m and date:
            out.append((nm(m.group(1)), int(m.group(2)), int(m.group(3)), nm(m.group(4))))
    return out

def build_index(sched):
    """Map each scheduled fixture's team pair to its (group, official home, official away)."""
    return {frozenset((f['home'], f['away'])): (f['group'], f['home'], f['away']) for f in sched}


def split_games(games, idx):
    """Split parsed (home, hs, as, away) games into oriented group rows and knockout rows.

    A pair found in the schedule index is a group fixture: its score is reoriented to the
    official home/away. A pair of two known teams that is not a group fixture is a knockout tie.
    A pair with a team that is not in the schedule at all is an unrecognised feed name: it is
    flagged and skipped, never guessed into a phantom knockout tie. Pure (no IO), so it is unit-tested."""
    rows, ko = [], []
    canon = set().union(*idx.keys()) if idx else set()    # every team that appears in the schedule
    for h, hs, ag, a in games:
        rec = idx.get(frozenset((h, a)))
        if rec:                                       # a group fixture
            g, oh, oa = rec
            ohs, oas = (hs, ag) if h == oh else (ag, hs)  # orient to the official home/away
            rows.append({'group': g, 'home': oh, 'away': oa, 'hs': ohs, 'as': oas})
        elif h in canon and a in canon:               # two known teams, not a group fixture: a knockout tie
            # 120-minute result; the advancing side is the higher score, or unknown on a draw
            # (a shootout decides it; the feed's penalty line is parsed best-effort if present)
            winner = h if hs > ag else a if ag > hs else None
            ko.append({'home': h, 'away': a, 'hs': hs, 'as': ag, 'winner': winner})
        else:                                         # a name we could not map: flag it, do not guess
            sys.stderr.write('warning: unrecognised team in feed, skipped: %r vs %r\n' % (h, a))
    rows.sort(key=lambda r: (r['group'], r['home']))
    return rows, ko


def merge_ko(*lists):
    """Combine knockout results from both feeds, keyed by team pair; a later list wins (the finals
    feed, which carries the shootout winner, overrides anything routed from the group feed)."""
    by_pair = {}
    for lst in lists:
        for k in lst:
            by_pair[frozenset((k['home'], k['away']))] = k
    return sorted(by_pair.values(), key=lambda k: (k['home'], k['away']))


def main():
    sched = json.load(open(os.path.join(HERE, 'wc2026_schedule.json')))
    idx = build_index(sched)
    canon = set().union(*idx.keys()) if idx else set()
    try:
        txt = fetch(SRC)
    except Exception as ex:
        sys.exit('fetch failed: %s' % ex)
    rows, ko_grp = split_games(parse(txt), idx)
    try:
        ko_txt = fetch(KO_SRC)
    except Exception as ex:
        sys.stderr.write('warning: finals feed fetch failed (%s); knockout results skipped\n' % ex)
        ko_txt = ''
    ko = merge_ko(ko_grp, parse_finals(ko_txt, canon))
    json.dump(rows, open(os.path.join(HERE, 'wc2026_actuals.json'), 'w'), indent=1)
    json.dump(ko, open(os.path.join(HERE, 'wc2026_ko_actuals.json'), 'w'), indent=1)
    print('wrote %d group games and %d knockout games' % (len(rows), len(ko)))
    # Durable, NOTIFYING guard against a silent cup_finals.txt format change: if the feed clearly has
    # played knockout lines (a "(NN) ... H-A ... @") but parse_finals matched none, the line format has
    # probably drifted from what KRE expects. Exit non-zero so the refresh Action FAILS (a warning would
    # only sit in the logs; a failed scheduled run emails the repo owner), instead of quietly shipping
    # an empty bracket. Data parsed so far is already written above. Only fires on real drift.
    played_ko = played_finals_lines(ko_txt)
    if played_ko and not ko:
        sys.exit('::error::cup_finals.txt has %d played-looking knockout line(s) but parse_finals '
                 'matched none; the feed format likely changed (update KRE / parse_finals).' % played_ko)

if __name__ == '__main__':
    main()
