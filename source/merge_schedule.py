#!/usr/bin/env python3
"""Merge the official fixture schedule into wc2026_results.json.

The engine builds group fixtures with itertools.combinations, so within each
group the six matches are in combinatorial order and "home" is just whichever
team comes first in the group listing. That is not the real schedule. This step
attaches the official date, kickoff (UTC), venue, and group to every group
match, and reorients home/away to the official designation, swapping the
home/away probabilities and scores to match.

Source of the schedule: source/wc2026_schedule.json, parsed from the openfootball
World Cup 2026 dataset (public, CC0). It is data, so it lives in the JSON; the
template never hardcodes it.

This does NOT touch the 50,000-run team statistics. It only annotates and
reorients the per-match group predictions, and it is idempotent (after a match
is reoriented, home already equals the official home, so a second run is a
no-op on orientation).

Usage:
    python3 source/merge_schedule.py
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, 'wc2026_results.json')
SCHEDULE = os.path.join(HERE, 'wc2026_schedule.json')


def reorient(m):
    """Flip a match dict so the first team becomes the second and vice versa."""
    m['home'], m['away'] = m['away'], m['home']
    m['p_home'], m['p_away'] = m['p_away'], m['p_home']
    m['xg_home'], m['xg_away'] = m['xg_away'], m['xg_home']
    m['modal'] = [m['modal'][1], m['modal'][0]]
    m['top_scores'] = [[s[1], s[0], s[2]] for s in m['top_scores']]
    return m


def main():
    results = json.load(open(RESULTS, encoding='utf-8'))
    schedule = json.load(open(SCHEDULE, encoding='utf-8'))
    by_pair = {frozenset((s['home'], s['away'])): s for s in schedule}

    n_reoriented = 0
    n_annotated = 0
    for model in results['models'].values():
        for g, matches in model['group_matches'].items():
            for m in matches:
                s = by_pair.get(frozenset((m['home'], m['away'])))
                if s is None:
                    raise SystemExit(f"no schedule entry for {m['home']} v {m['away']} (group {g})")
                if m['home'] != s['home']:
                    reorient(m)
                    n_reoriented += 1
                m['group'] = g
                m['date'] = s['date']
                m['local_time'] = s['local_time']
                m['tz'] = s['tz']
                m['kickoff_utc'] = s['kickoff_utc']
                m['venue'] = s['venue']
                n_annotated += 1

    json.dump(results, open(RESULTS, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print(f"annotated {n_annotated} match predictions, reoriented {n_reoriented} to official home/away")


if __name__ == '__main__':
    main()
