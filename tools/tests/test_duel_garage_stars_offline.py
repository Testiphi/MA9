"""Bounded checks for the saved-frame-only star reader."""

import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from duel_garage_stars_offline import aggregate_observations, read_star_bar


DEBUG = (Path(__file__).resolve().parents[2] / 'build' /
         'user-test-garage-bcd-4ef2923/MA9-preview/debug')


def saved_frame(run, number):
    path = DEBUG / f'duel-garage-{run}' / 'frames' / f'{number:06}.png'
    if not path.exists():
        raise unittest.SkipTest(f'saved evidence unavailable: {path}')
    return cv2.imread(str(path))


class SavedFrameReaderTests(unittest.TestCase):
    def test_two_formula_e_frames_preserve_sixth_dark_slot(self):
        cases = [('ce3b515fe3624bb5b32b1951eb0fbf4f', 34, 644),
                 ('b8ebb7e58f0a4793b0b7d48613682568', 152, 633)]
        for run, capture, left in cases:
            with self.subTest(run=run):
                row = read_star_bar(saved_frame(run, capture), [left, 395, 420, 212])
                self.assertTrue(row['complete'], row)
                self.assertEqual((row['stars_lit'], row['star_slots']), (5, 6))

    def test_gold_and_blue_bars_and_wrong_left_edge(self):
        frame = saved_frame('b8ebb7e58f0a4793b0b7d48613682568', 126)
        gold = read_star_bar(frame, [429, 168, 420, 212])
        self.assertEqual((gold['stars_lit'], gold['star_slots']), (6, 6))
        for shift in (-18, 18):
            with self.subTest(shift=shift):
                wrong = read_star_bar(frame, [429 + shift, 168, 420, 212])
                self.assertFalse(wrong['complete'])
        blue = read_star_bar(saved_frame('ce3b515fe3624bb5b32b1951eb0fbf4f', 34),
                             [1077, 168, 420, 212])
        self.assertEqual((blue['stars_lit'], blue['star_slots']), (3, 5))

    def test_last_star_occlusion_is_not_a_shorter_bar(self):
        frame = saved_frame('b8ebb7e58f0a4793b0b7d48613682568', 126).copy()
        frame[174:192, 520:538] = (20, 20, 20)
        row = read_star_bar(frame, [429, 168, 420, 212])
        self.assertFalse(row['complete'])
        self.assertIsNone(row['star_slots'])

    def test_yellow_rectangles_are_not_stars(self):
        frame = saved_frame('b8ebb7e58f0a4793b0b7d48613682568', 13).copy()
        left, top = 865, 168
        bg = np.median(frame[top+26:top+30, left+4:left+127], axis=0).astype(np.uint8)
        frame[top+5:top+24, left+4:left+127] = bg
        for index in range(4):
            x = left + 15 + 18 * index
            frame[top+10:top+22, x-5:x+5] = (40, 230, 255)
        row = read_star_bar(frame, [left, top, 420, 212])
        self.assertFalse(row['complete'])
        self.assertIsNone(row['star_slots'])

    def test_yellow_circles_are_not_stars(self):
        frame = saved_frame('b8ebb7e58f0a4793b0b7d48613682568', 13).copy()
        left, top = 865, 168
        bg = np.median(frame[top+26:top+30, left+4:left+127], axis=0).astype(np.uint8)
        frame[top+5:top+24, left+4:left+127] = bg
        for index in range(4):
            cv2.circle(frame, (left+15+18*index, top+16), 7, (40, 230, 255), -1)
        row = read_star_bar(frame, [left, top, 420, 212])
        self.assertFalse(row['complete'])
        self.assertIsNone(row['star_slots'])

    def test_bad_card_is_unknown(self):
        row = read_star_bar(None, None)
        self.assertEqual(row['reason'], 'invalid_input')


def observation(capture, digest, *, lit=5, slots=6, account='account', scope='garage',
                vehicle='car_1', run='run_1'):
    return {'complete': True, 'stars_lit': lit, 'star_slots': slots,
            'vehicle_id': vehicle, 'account_key': account, 'evidence_scope': scope,
            'source_run': run, 'source_capture': capture, 'image_sha256': digest}


class AggregationTests(unittest.TestCase):
    def test_independent_agreement_and_raw_conflict(self):
        a = observation(1, 'a' * 64)
        b = observation(2, 'b' * 64)
        self.assertEqual(aggregate_observations([a, b])['status'], 'offline_consistent')
        self.assertEqual(aggregate_observations([a, {**b, 'star_slots': 5}])['status'], 'conflict')

    def test_binding_and_provenance_must_be_independent(self):
        a = observation(1, 'a' * 64)
        self.assertEqual(aggregate_observations([a, {**a}])['status'], 'unknown')
        self.assertEqual(aggregate_observations([a, observation(2, 'a' * 64)])['status'], 'unknown')
        self.assertEqual(aggregate_observations([a, observation(2, 'b' * 64, account='other')])['status'], 'conflict')
        self.assertEqual(aggregate_observations([a, observation(2, 'b' * 64, scope='other')])['status'], 'conflict')
        self.assertEqual(aggregate_observations([a, observation(2, 'b' * 64, vehicle='car_2')])['status'], 'conflict')
        self.assertEqual(aggregate_observations([a, observation(1, 'b' * 64)])['status'], 'conflict')
        self.assertEqual(aggregate_observations([a, observation(2, 'z' * 64)])['status'], 'unknown')
        self.assertEqual(aggregate_observations([a, observation(2, 'b' * 64, account=None)])['status'], 'conflict')
        self.assertEqual(aggregate_observations([a, observation(2, 'b' * 64),
                                                 observation(3, None)])['status'], 'unknown')
        self.assertEqual(aggregate_observations([a, observation(2, 'b' * 64),
                                                 observation(3, 'c' * 64, lit=True)])['status'], 'unknown')
        self.assertEqual(aggregate_observations([observation(1, 'a' * 64, run=' '),
                                                 observation(2, 'b' * 64, run=' ')])['status'], 'unknown')


if __name__ == '__main__':
    unittest.main()
