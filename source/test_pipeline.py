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


@unittest.skipUnless(HAVE_NUMPY, "engine requires numpy")
class TestGroupRanking(unittest.TestCase):
    """FIFA 2026 group ranking, including the head-to-head re-application recursion."""

    @classmethod
    def setUpClass(cls):
        import wc2026_engine as e
        cls.e = e

    def test_head_to_head_reapplication(self):
        e = self.e
        A, B, C, D = (t[0] for t in e.GROUPS['A'])      # Mexico, South Korea, Czechia, South Africa
        # A beat B 2-0, B beat C 3-0, C beat A 1-0; all three also beat D. The three-team head-to-head
        # is a cycle, head-to-head GD ties A and B at +1 (C drops to 3rd). FIFA re-applies the criteria
        # to {A,B}, where A 2-0 B puts A first. The old flat sort went to three-team head-to-head goals
        # (A 2, B 3) and wrongly put B first.
        res = [(A, B, 2, 0), (B, C, 3, 0), (C, A, 1, 0), (A, D, 1, 0), (B, D, 1, 0), (C, D, 1, 0)]
        order, _ = e.rank_group('A', res)
        self.assertEqual(order, [A, B, C, D])
        # decided by head-to-head, not Elo, so flipping the Elo tail must not change the top three
        self.assertEqual(e.rank_group('A', res, elo_sign=-1)[0][:3], [A, B, C])


@unittest.skipUnless(HAVE_NUMPY, "engine requires numpy")
class TestBracket(unittest.TestCase):
    """Incremental actual_bracket: fills ties as groups finish, places K/L thirds once clinched,
    and defers a boundary that only the Elo tail would decide."""

    @classmethod
    def setUpClass(cls):
        import wc2026_engine as e
        cls.e = e
        from itertools import combinations
        cls.combinations = staticmethod(combinations)

    def _elo_order(self, g):
        return [t[0] for t in self.e.GROUPS[g]]          # group lists are in descending Elo order

    def _rr(self, g, margin, win_order=None):
        """A finished group: each team beats every lower team in win_order by margin-0 (distinct
        points 9/6/3/0). A per-group margin gives the thirds distinct GD so the best-8 cut is clean."""
        win_order = win_order or self._elo_order(g)
        rank = {t: i for i, t in enumerate(win_order)}
        out = []
        for x, y in self.combinations([t[0] for t in self.e.GROUPS[g]], 2):
            hi, lo = (x, y) if rank[x] < rank[y] else (y, x)
            out.append((hi, lo, margin, 0))
        return out

    def test_empty_input(self):
        self.assertEqual(self.e.actual_bracket({}, []), {})

    def test_two_groups_unlock_only_tie_73(self):
        e = self.e
        br = e.actual_bracket({'A': self._rr('A', 1), 'B': self._rr('B', 1)}, [])
        self.assertEqual(sorted(br), [73])               # 2A v 2B; everything else needs another group
        self.assertEqual(br[73]['round'], 'r32')
        self.assertEqual((br[73]['a'], br[73]['b']),
                         (self._elo_order('A')[1], self._elo_order('B')[1]))

    def test_full_group_stage_gives_16_r32(self):
        e = self.e
        full = {g: self._rr(g, gi + 2) for gi, g in enumerate(e.GROUPS)}   # distinct margins -> thirds separated
        br = e.actual_bracket(full, [])
        self.assertEqual(sorted(s for s in br if br[s]['round'] == 'r32'), list(range(73, 89)))

    def test_kl_third_placed_once_clinched(self):
        e = self.e
        marg = {g: (2 if g in ('K', 'L') else 6 + gi) for gi, g in enumerate(e.GROUPS)}  # K/L thirds best
        sub = {g: self._rr(g, marg[g]) for g in e.GROUPS if g != 'G'}      # 11 settled, G pending
        br = e.actual_bracket(sub, [])
        self.assertIn(80, br); self.assertIn(87, br)
        self.assertEqual(br[80]['b'], self._elo_order('K')[2])             # 3rd of K at slot 80
        self.assertEqual(br[87]['b'], self._elo_order('L')[2])             # 3rd of L at slot 87

    def test_kl_third_absent_when_not_clinched(self):
        e = self.e
        marg = {g: (12 if g in ('K', 'L') else 2 + gi) for gi, g in enumerate(e.GROUPS)}  # K/L thirds weak
        sub = {g: self._rr(g, marg[g]) for g in e.GROUPS if g != 'G'}
        br = e.actual_bracket(sub, [])
        self.assertNotIn(80, br); self.assertNotIn(87, br)

    def test_third_qualified_boundary(self):
        e = self.e
        groups = list(e.GROUPS)
        third = lambda g: [t[0] for t in e.GROUPS[g]][2]
        def settled(n_above):                            # all 12 settled, distinct points (no Elo ties)
            others = [g for g in groups if g != 'A']
            pts = {'A': 50}
            for i, g in enumerate(others[:n_above]): pts[g] = 100 + i
            for i, g in enumerate(others[n_above:]): pts[g] = 1 + i
            return {g: dict(W='w', R='r', third=third(g), tstat=(pts[g], 0, 0)) for g in groups}
        self.assertTrue(e._third_qualified('A', settled(7)))    # 7 ahead + 0 remaining <= 7
        self.assertFalse(e._third_qualified('A', settled(8)))   # 8 ahead -> not guaranteed

    def test_defers_an_elo_only_boundary(self):
        e = self.e
        A, B, C, D = (t[0] for t in e.GROUPS['A'])
        # Mexico 1st, South Africa 4th, South Korea and Czechia identical (drawn head-to-head): their
        # 2nd/3rd split is decided only by the Elo tail, so the runner-up of A is ambiguous.
        tie = [(A, B, 1, 0), (A, C, 1, 0), (A, D, 1, 0), (B, C, 0, 0), (B, D, 1, 0), (C, D, 1, 0)]
        Bgrp = self._rr('B', 1)
        self.assertNotIn(73, e.actual_bracket({'A': tie, 'B': Bgrp}, []))        # deferred
        self.assertIn(73, e.actual_bracket({'A': self._rr('A', 1), 'B': Bgrp}, []))  # clean -> emitted

    def test_locks_invariant_third_beyond_kl(self):
        # With one group still open, a third whose Annex C slot is the same across every possible
        # set of eight qualifiers is placed early, not just K and L. Here groups A-L minus J are
        # settled with separated thirds; several winner-vs-third ties lock before J finishes.
        e = self.e
        sub = {g: self._rr(g, gi + 2) for gi, g in enumerate(e.GROUPS) if g != 'J'}
        br = e.actual_bracket(sub, [])
        third_fed = [s for s in br if br[s]['round'] == 'r32'
                     and any(f[0] == '3' for f in e.R32_SYMBOLIC[s])]
        beyond_kl = [s for s in third_fed if s not in (80, 87)]
        self.assertTrue(beyond_kl, "no third-fed tie locked beyond the old K/L special case")

    def test_emitted_third_slots_are_sound(self):
        # Soundness: every third-fed slot the partial bracket emits must hold in the full bracket
        # under every way the open group can finish. Vary J's third across the full strength range
        # (and which J team finishes third); an emitted slot must never change team.
        e = self.e
        sub = {g: self._rr(g, gi + 2) for gi, g in enumerate(e.GROUPS) if g != 'J'}
        partial = e.actual_bracket(sub, [])
        emitted = {s: (partial[s]['a'], partial[s]['b']) for s in partial
                   if partial[s]['round'] == 'r32' and any(f[0] == '3' for f in e.R32_SYMBOLIC[s])}
        self.assertTrue(emitted)
        jteams = [t[0] for t in e.GROUPS['J']]
        for margin in (1, 3, 7, 30):                       # J's third weak to overwhelming
            for win_order in (jteams, list(reversed(jteams))):
                full = dict(sub); full['J'] = self._rr('J', margin, win_order)
                fb = e.actual_bracket(full, [])
                for s, pair in emitted.items():
                    self.assertIn(s, fb)
                    self.assertEqual((fb[s]['a'], fb[s]['b']), pair,
                                     f"slot {s} changed once J finished: emitted early but not locked")


@unittest.skipUnless(HAVE_NUMPY, "engine requires numpy")
class TestKoReport(unittest.TestCase):
    """The knockout predicted scoreline is the mode of the simulated final distribution (90 minutes,
    plus extra time added on when level), so a favorite is decisive, not headlined on the draw cell.
    p_pens carries the chance it stays level and goes to a shootout."""

    @classmethod
    def setUpClass(cls):
        import wc2026_engine as e
        cls.e = e

    def _strong_weak(self):
        elo = self.e.ELO
        return max(elo, key=elo.get), min(elo, key=elo.get)

    def test_top_scores_sum_is_a_distribution(self):
        rep = self.e.ko_report(*self._strong_weak())
        # the four most likely scorelines are descending probabilities, each a sensible percentage
        ps = [s[2] for s in rep['top_scores']]
        self.assertEqual(ps, sorted(ps, reverse=True))
        self.assertTrue(0 < ps[0] <= 100)

    def test_favorite_is_predicted_to_win_not_draw(self):
        # the most likely simulated final score is decisive on the favorite's side
        strong, weak = self._strong_weak()
        rep = self.e.ko_report(strong, weak)
        self.assertGreater(rep['modal'][0], rep['modal'][1])
        self.assertGreater(rep['adv_a'], 50)

    def test_tight_tie_still_predicts_a_winner(self):
        # Germany v Paraguay: a 90-minute draw is the biggest single cell, but the simulated final is
        # most often a Germany win, so the headline is decisive (not a phantom 1-1 to penalties).
        rep = self.e.ko_report('Germany', 'Paraguay')
        self.assertNotEqual(rep['modal'][0], rep['modal'][1])
        self.assertGreater(rep['modal'][0], rep['modal'][1])

    def test_pens_probability_is_reported_and_modest(self):
        # the shootout chance is surfaced separately, positive but well below the regulation draw rate
        # (only the still-level-after-extra-time slice of it reaches penalties), never the headline
        rep = self.e.ko_report('Germany', 'Paraguay')
        self.assertIn('p_pens', rep)
        self.assertGreater(rep['p_pens'], 0)
        self.assertLess(rep['p_pens'], rep['p_draw'])
        self.assertLess(rep['p_pens'], 50)


@unittest.skipUnless(HAVE_NUMPY, "engine requires numpy")
class TestKoScheduleAlignment(unittest.TestCase):
    """The KO calendar's bracket descriptors must match the engine, so a tie can never be stamped
    with the wrong date or venue."""

    def test_every_slot_matches_the_engine_bracket(self):
        import wc2026_engine as e
        ko = json.load(open(os.path.join(HERE, 'wc2026_ko_schedule.json'), encoding='utf-8'))
        token = lambda ref: ({'W': '1', 'R': '2'}[ref[0]] + ref[1]) if ref[0] in ('W', 'R') else '3'
        feeders = {**e.R16_PAIRS, **e.QF_PAIRS, **e.SF_PAIRS, 103: e.FINAL_FEEDERS}
        for r in ko:
            if r['round'] == 'third':
                continue                      # display-only consolation match, no engine slot to align
            s = r['slot']
            if s in e.R32_SYMBOLIC:
                fa_, fb_ = e.R32_SYMBOLIC[s]
                self.assertEqual((r['home_desc'], r['away_desc']), (token(fa_), token(fb_)),
                                 f"R32 slot {s} descriptor mismatch")
            else:
                p, q = feeders[s]
                self.assertEqual((r['home_desc'], r['away_desc']), (f'W{p}', f'W{q}'),
                                 f"feeder slot {s} mismatch")


class TestKoScheduleFile(unittest.TestCase):
    """The KO schedule is hand-checked data; lock its shape so a bad edit fails fast. No engine."""

    def setUp(self):
        self.ko = json.load(open(os.path.join(HERE, 'wc2026_ko_schedule.json'), encoding='utf-8'))

    def test_covers_every_engine_slot_once(self):
        engine = sorted(r['slot'] for r in self.ko if r['round'] != 'third')
        self.assertEqual(engine, list(range(73, 104)))                 # slots 73-103: the bracket
        third = [r for r in self.ko if r['round'] == 'third']
        self.assertEqual(len(third), 1)                                # plus the third-place play-off
        self.assertEqual((third[0]['home_desc'], third[0]['away_desc']), ('L101', 'L102'))

    def test_kickoff_utc_is_well_formed(self):
        import datetime
        for r in self.ko:
            datetime.datetime.strptime(r['kickoff_utc'], '%Y-%m-%dT%H:%MZ')   # raises on a bad value
            for k in ('date', 'venue', 'home_desc', 'away_desc', 'round'):
                self.assertTrue(r.get(k), f"slot {r['slot']} missing {k}")


class TestMergeKnockout(unittest.TestCase):
    """merge_schedule.annotate_knockout attaches the schedule to a tie by slot. No engine."""

    def test_attaches_date_and_venue_by_slot(self):
        ko = json.load(open(os.path.join(HERE, 'wc2026_ko_schedule.json'), encoding='utf-8'))
        results = {'models': {'m': {'knockout': {'73': {'slot': 73, 'a': 'x', 'b': 'y'}}}}}
        n = ms.annotate_knockout(results, ko)
        self.assertEqual(n, 1)
        tie = results['models']['m']['knockout']['73']
        s73 = next(r for r in ko if r['slot'] == 73)
        self.assertEqual(tie['kickoff_utc'], s73['kickoff_utc'])
        self.assertEqual(tie['venue'], s73['venue'])

    def test_empty_knockout_is_a_no_op(self):
        self.assertEqual(ms.annotate_knockout({'models': {'m': {'knockout': {}}}}, []), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
