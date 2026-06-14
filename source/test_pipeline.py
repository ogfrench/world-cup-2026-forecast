#!/usr/bin/env python3
"""Tests for the update pipeline: the code that keeps the live app current.

These cover the mission-critical, low-maintenance path (parse the feed, orient
results to the official home/away, split group from knockout, condition the
engine on played games, validate the output). Run with the standard library,
no dependencies:

    python3 -m unittest discover -s source -p 'test_*.py'   # or: python3 source/test_pipeline.py

The engine tests need numpy; they skip cleanly when it is absent (as in light CI).
The JavaScript counterpart (the live badge clock and the in-browser feed parser)
is covered by source/test_app.js.
"""
import os
import sys
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fetch_actuals as fa
import merge_schedule as ms

try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


class TestParseFeed(unittest.TestCase):
    """fetch_actuals.parse: the regex layer that reads the openfootball text feed."""

    def test_played_game_is_parsed(self):
        txt = "Sat June 13\n  21:00 UTC-7    Mexico   2-0 (1-0)   South Africa   @ Estadio Azteca\n"
        self.assertEqual(fa.parse(txt), [('Mexico', 2, 0, 'South Africa')])

    def test_unplayed_game_is_skipped(self):
        # the exact Australia v Turkiye case: scheduled, kicked off, no score in the feed yet.
        # the parser must not invent a result, and must not crash on the " v " separator.
        txt = "Sat June 13\n  21:00 UTC-7    Australia       v Turkey   @ Vancouver\n"
        self.assertEqual(fa.parse(txt), [])

    def test_team_names_are_mapped_to_engine_names(self):
        txt = ("Sat June 13\n"
               "  18:00 UTC-4    Turkey   1-1 (0-0)   Czech Republic   @ X\n"
               "  20:00 UTC-4    Bosnia & Herzegovina   0-2 (0-1)   Curaçao   @ Y\n")
        self.assertEqual(fa.parse(txt), [
            ('Turkiye', 1, 1, 'Czechia'),
            ('Bosnia-Herzegovina', 0, 2, 'Curacao'),
        ])

    def test_official_fifa_names_map_to_engine_names(self):
        # the feed's own notes warn it may switch to normalised FIFA names; those must still map,
        # or the game silently misses the schedule and is misfiled as a knockout tie.
        self.assertEqual(fa.nm("Côte d'Ivoire"), 'Ivory Coast')
        self.assertEqual(fa.nm('Korea Republic'), 'South Korea')
        self.assertEqual(fa.nm('IR Iran'), 'Iran')
        self.assertEqual(fa.nm('Cabo Verde'), 'Cape Verde')
        self.assertEqual(fa.nm('Congo DR'), 'DR Congo')
        self.assertEqual(fa.nm('Türkiye'), 'Turkiye')

    def test_played_game_without_half_time_score_still_parses(self):
        # the feed sometimes posts a result before the "(x-x)" half-time token; it must not be
        # dropped, which would silently leave the game out of the conditioned odds.
        txt = "Sat June 13\n  21:00 UTC-7    Mexico   2-0   South Africa   @ X\n"
        self.assertEqual(fa.parse(txt), [('Mexico', 2, 0, 'South Africa')])

    def test_score_lines_without_a_date_header_are_dropped(self):
        # a result line that appears before any date header has no date to key on
        txt = "  21:00 UTC-7    Mexico   2-0 (1-0)   South Africa   @ X\n"
        self.assertEqual(fa.parse(txt), [])

    def test_only_recognised_month_headers_set_a_date(self):
        # "April" is not in MON, so the following result has no active date and is dropped
        txt = "Wed April 1\n  21:00 UTC-7    Mexico   2-0 (1-0)   South Africa   @ X\n"
        self.assertEqual(fa.parse(txt), [])


class TestSplitGames(unittest.TestCase):
    """fetch_actuals.split_games: orient to official home/away, split group from knockout."""

    def setUp(self):
        # Spain and France sit in different groups, so they are known teams (in the schedule),
        # but Spain v France is not a group fixture, which is exactly a knockout tie.
        sched = [
            {'group': 'A', 'home': 'Mexico', 'away': 'South Africa'},
            {'group': 'D', 'home': 'Australia', 'away': 'Turkiye'},
            {'group': 'H', 'home': 'Spain', 'away': 'Uruguay'},
            {'group': 'I', 'home': 'France', 'away': 'Senegal'},
        ]
        self.idx = fa.build_index(sched)

    def test_group_game_already_in_official_orientation(self):
        rows, ko = fa.split_games([('Mexico', 2, 0, 'South Africa')], self.idx)
        self.assertEqual(ko, [])
        self.assertEqual(rows, [{'group': 'A', 'home': 'Mexico', 'away': 'South Africa', 'hs': 2, 'as': 0}])

    def test_group_game_is_reoriented_when_feed_flips_home_away(self):
        # feed lists South Africa as home, but the official fixture is Mexico (home) v South Africa
        rows, ko = fa.split_games([('South Africa', 0, 2, 'Mexico')], self.idx)
        self.assertEqual(ko, [])
        self.assertEqual(rows, [{'group': 'A', 'home': 'Mexico', 'away': 'South Africa', 'hs': 2, 'as': 0}])

    def test_unknown_pair_becomes_a_knockout_tie(self):
        rows, ko = fa.split_games([('Spain', 3, 1, 'France')], self.idx)
        self.assertEqual(rows, [])
        self.assertEqual(ko, [{'home': 'Spain', 'away': 'France', 'hs': 3, 'as': 1, 'winner': 'Spain'}])

    def test_knockout_draw_has_no_winner(self):
        # a 1-1 over 120 minutes is decided on penalties, which the 120-min line does not carry
        _, ko = fa.split_games([('Spain', 1, 1, 'France')], self.idx)
        self.assertIsNone(ko[0]['winner'])

    def test_unrecognised_team_name_is_skipped_not_misfiled_as_knockout(self):
        # a name that maps to nothing in the schedule (e.g. a feed rename we have not aliased)
        # must be flagged and dropped, never guessed into a phantom knockout tie.
        err = io.StringIO()
        with redirect_stderr(err):
            rows, ko = fa.split_games([('Mexico', 3, 2, 'Atlantis')], self.idx)
        self.assertEqual(rows, [])
        self.assertEqual(ko, [])
        self.assertIn('unrecognised', err.getvalue())

    def test_group_rows_are_sorted_by_group_then_home(self):
        games = [('Australia', 1, 0, 'Turkiye'), ('Mexico', 2, 0, 'South Africa')]
        rows, _ = fa.split_games(games, self.idx)
        self.assertEqual([(r['group'], r['home']) for r in rows], [('A', 'Mexico'), ('D', 'Australia')])


class TestFeedSampleEndToEnd(unittest.TestCase):
    """End to end: the representative sample feed (source/test_feed_sample.txt) through the whole
    parse + orient + split path. Shares the fixture with test_app.js so both sides stay honest."""

    def setUp(self):
        with open(os.path.join(HERE, 'test_feed_sample.txt'), encoding='utf-8') as f:
            self.txt = f.read()
        sched = [
            {'group': 'A', 'home': 'Mexico', 'away': 'South Africa'},
            {'group': 'D', 'home': 'USA', 'away': 'Paraguay'},
            {'group': 'E', 'home': 'Germany', 'away': 'Curacao'},
            {'group': 'E', 'home': 'Ivory Coast', 'away': 'Ecuador'},
            {'group': 'H', 'home': 'Spain', 'away': 'Uruguay'},
            {'group': 'I', 'home': 'France', 'away': 'Senegal'},
        ]
        self.idx = fa.build_index(sched)

    def test_parse_skips_the_unplayed_fixture_and_maps_official_names(self):
        games = fa.parse(self.txt)
        self.assertEqual(games, [
            ('Germany', 7, 1, 'Curacao'),
            ('USA', 4, 1, 'Paraguay'),            # this line has no half-time score in the feed
            ('Mexico', 2, 0, 'South Africa'),     # nor this one
            ('Ivory Coast', 1, 0, 'Ecuador'),     # parsed from the official name "Côte d'Ivoire"
            ('Spain', 1, 1, 'France'),
        ])

    def test_split_routes_group_games_and_the_knockout_tie(self):
        rows, ko = fa.split_games(fa.parse(self.txt), self.idx)
        self.assertEqual([(r['group'], r['home']) for r in rows],
                         [('A', 'Mexico'), ('D', 'USA'), ('E', 'Germany'), ('E', 'Ivory Coast')])
        self.assertIn({'group': 'E', 'home': 'Ivory Coast', 'away': 'Ecuador', 'hs': 1, 'as': 0}, rows)
        self.assertIn({'group': 'A', 'home': 'Mexico', 'away': 'South Africa', 'hs': 2, 'as': 0}, rows)
        self.assertEqual(ko, [{'home': 'Spain', 'away': 'France', 'hs': 1, 'as': 1, 'winner': None}])


class TestReorient(unittest.TestCase):
    """merge_schedule.reorient: flipping a match to the official home/away is an involution."""

    def _match(self):
        return {'home': 'A', 'away': 'B', 'p_home': 60.0, 'p_draw': 25.0, 'p_away': 15.0,
                'xg_home': 1.8, 'xg_away': 0.9, 'modal': [2, 1],
                'top_scores': [[2, 1, 9.0], [1, 0, 8.0]]}

    def test_reorient_swaps_every_paired_field(self):
        m = ms.reorient(self._match())
        self.assertEqual((m['home'], m['away']), ('B', 'A'))
        self.assertEqual((m['p_home'], m['p_away']), (15.0, 60.0))
        self.assertEqual(m['p_draw'], 25.0)  # the draw probability is orientation-invariant
        self.assertEqual((m['xg_home'], m['xg_away']), (0.9, 1.8))
        self.assertEqual(m['modal'], [1, 2])
        self.assertEqual(m['top_scores'], [[1, 2, 9.0], [0, 1, 8.0]])

    def test_reorient_twice_is_identity(self):
        original = self._match()
        m = ms.reorient(ms.reorient(self._match()))
        self.assertEqual(m, original)


@unittest.skipUnless(HAVE_NUMPY, "engine requires numpy")
class TestEngineConditioning(unittest.TestCase):
    """The engine functions that lock played games in and guard the output. Need numpy."""

    @classmethod
    def setUpClass(cls):
        import wc2026_engine as e
        cls.e = e

    def test_load_actuals_groups_rows_by_group(self):
        e = self.e
        rows = [{'group': 'A', 'home': 'Mexico', 'away': 'South Africa', 'hs': 2, 'as': 0}]
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump(rows, f)
            path = f.name
        try:
            A = e.load_actuals(path)
        finally:
            os.unlink(path)
        self.assertEqual(A['A'], [('Mexico', 'South Africa', 2, 0)])
        self.assertEqual(A['B'], [])  # every group key is present, played or not

    def test_load_actuals_missing_file_is_empty(self):
        self.assertEqual(self.e.load_actuals('/no/such/file.json'), {})

    def test_fixed_overrides_orient_to_fixture_home_away(self):
        e = self.e
        g = next(iter(e.GROUPS))
        h, a = e.GROUP_FIXTURES[g][0]            # the first fixture's official (home, away)
        # supply the same game with the feed's orientation flipped; the override must flip it back
        A = {g: [(a, h, 1, 3)]}                  # away listed first, away 1 - home 3
        fixed = e._fixed_overrides(A)
        self.assertEqual(fixed[g][0], (3, 1))    # oriented to (home 3, away 1)

    def test_validate_accepts_a_monotonic_run(self):
        probs = self._fake_run()
        self.assertEqual(self.e.validate(probs), [])

    def test_validate_flags_non_monotonic_rounds(self):
        e = self.e
        probs = self._fake_run()
        t = e.TEAMS[0]
        probs[t]['champ'] = probs[t]['advance'] + 50  # win more often than you advance: impossible
        errs = e.validate(probs)
        self.assertTrue(any('monotonic' in x for x in errs))

    def test_validate_flags_champ_sum_off_100(self):
        e = self.e
        probs = self._fake_run()
        probs[e.TEAMS[0]]['champ'] += 40  # break the "champ shares sum to 100" invariant
        self.assertTrue(any('not ~100' in x for x in self.e.validate(probs)))

    def _fake_run(self):
        # a structurally valid output: one champion, monotonic reach-round odds, no simulation
        e = self.e
        probs = {}
        for i, t in enumerate(e.TEAMS):
            probs[t] = dict(win_group=0.0, advance=0.0, r16=0.0, qf=0.0, sf=0.0, final=0.0, champ=0.0)
        champ = e.TEAMS[0]
        probs[champ] = dict(win_group=100.0, advance=100.0, r16=100.0, qf=100.0,
                            sf=100.0, final=100.0, champ=100.0)
        return probs


if __name__ == '__main__':
    unittest.main(verbosity=2)
