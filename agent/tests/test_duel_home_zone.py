"""Strict same-frame home zone recognition tests."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ma9_agent import duel_home_zone as zone


def frame(selected=True):
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    if selected:
        image[630:685, 690:810] = 255
    return image


def rows(label="赛区 V"):
    return [dict(text="世界系列赛", confidence=.997, box=[298, 443, 112, 24]),
            dict(text="对决", confidence=.996, box=[890, 391, 73, 40]),
            dict(text=label, confidence=.997, box=[893, 432, 68, 26])]


class HomeZoneTest(unittest.TestCase):
    def test_valid_v_iv_unicode_and_duplicate(self):
        for label, expected in (("赛区 V", "五区"), ("赛区Ⅳ", "四区")):
            with self.subTest(label=label):
                reading = zone.observe_home_zone(frame(), ocr=rows(label)+rows(label)[-1:])
                self.assertEqual(reading["selected_zone"], expected)
                self.assertTrue(reading["zone_verified"])

    def test_bad_labels_conflicts_and_anchors(self):
        for label in ("赛区VI", "赛区V1", "赛区", "V", "赛区 V 奖励"):
            with self.subTest(label=label):
                self.assertFalse(zone.observe_home_zone(frame(), ocr=rows(label))["zone_verified"])
        self.assertFalse(zone.observe_home_zone(frame(), ocr=rows()+rows("赛区IV")[-1:])["zone_verified"])
        self.assertFalse(zone.observe_home_zone(frame(), ocr=rows()[1:])["zone_verified"])
        misplaced = rows()
        misplaced[-1]["box"] = [100, 432, 68, 26]
        self.assertFalse(zone.observe_home_zone(frame(), ocr=misplaced)["zone_verified"])
        self.assertFalse(zone.observe_home_zone(frame(False), ocr=rows())["zone_verified"])
        self.assertFalse(zone.observe_home_zone(np.zeros((100,100,3), dtype=np.uint8), ocr=rows())["zone_verified"])

    def test_two_consecutive_frames_and_error_break(self):
        with patch.object(zone, "frame_of", side_effect=[frame(), frame(), frame()]), \
             patch.object(zone, "ocr_roi", side_effect=[rows(), rows("赛区IV"), rows("赛区IV")]), \
             patch.object(zone.time, "sleep"):
            reading = zone.read_stable_home_zone(object(), attempts=3)
        self.assertTrue(reading["stable"])
        self.assertEqual(reading["selected_zone"], "四区")
        with patch.object(zone, "frame_of", side_effect=[frame(), RuntimeError("bad"), frame()]), \
             patch.object(zone, "ocr_roi", side_effect=[rows(), rows()]), \
             patch.object(zone.time, "sleep"):
            self.assertFalse(zone.read_stable_home_zone(object(), attempts=3)["stable"])

    def test_invalid_budget_touches_no_context(self):
        for args in ({"attempts": True}, {"timeout": 31}, {"interval": -1}):
            with patch.object(zone, "frame_of") as capture:
                with self.assertRaises(ValueError):
                    zone.read_stable_home_zone(object(), **args)
                capture.assert_not_called()


if __name__ == "__main__":
    unittest.main()
