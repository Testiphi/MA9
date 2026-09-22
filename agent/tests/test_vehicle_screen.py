from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.models import League, Rect
from ma9_agent.vehicle_screen import LEAGUE_CENTERS, match_vehicle, normalize, parse_fuel, read_page, selected_league


class VehicleScreenTest(unittest.TestCase):
    def test_league_centers_and_ambiguous_selection(self) -> None:
        self.assertEqual(len(LEAGUE_CENTERS), len(League))
        self.assertEqual(tuple(sorted(set(LEAGUE_CENTERS))), LEAGUE_CENTERS)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.assertIsNone(selected_league(frame))
        for rank, x in zip(League, LEAGUE_CENTERS):
            frame[:] = 0
            frame[132, x] = (60, 0, 200)
            self.assertIs(selected_league(frame), rank)
        frame[132, LEAGUE_CENTERS[0]] = (60, 0, 200)
        self.assertIsNone(selected_league(frame))

    def test_normalize_preserves_reference_and_rejects_wrong_aspect(self) -> None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.assertIs(normalize(frame), frame)
        self.assertEqual(normalize(np.zeros((360, 640, 3), dtype=np.uint8)).shape, frame.shape)
        self.assertEqual(normalize(np.zeros((720, 1290, 3), dtype=np.uint8)).shape, frame.shape)
        for width, height in ((800, 600), (720, 1280), (1310, 720)):
            with self.subTest(size=(width, height)), self.assertRaises(ValueError):
                normalize(np.zeros((height, width, 3), dtype=np.uint8))

    def test_fuel_bounds_and_ocr_list_signature(self) -> None:
        for text, expected in (("7/9", 7), ("0／9", 0), ("abc", None),
                               ("10/9", None), ("0/0", None), ("-1/9", None), ("1/-9", None)):
            with self.subTest(text=text):
                self.assertEqual(parse_fuel([{"text": text}]), expected)
        self.assertIsNone(parse_fuel([]))

    def test_card_target_uses_single_geometry_definition_and_remains_a_list(self) -> None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        card = (20, 195, 453, 227)
        with patch("ma9_agent.vehicle_screen.detect_cards", return_value=[card]):
            item, = read_page(frame, [], [])
            self.assertEqual(set(item), {"vehicle", "fuel", "card", "target"})
            self.assertEqual(item["target"], list(Rect(*card).safe_vehicle_point()))
            with patch.object(Rect, "safe_vehicle_point", return_value=(123, 456)) as point:
                self.assertEqual(read_page(frame, [], [])[0]["target"], [123, 456])
                point.assert_called_once()

    def test_low_score_ambiguity_and_empty_catalog_do_not_guess(self) -> None:
        words = [{"text": "Example Car", "confidence": .99, "box": [0, 0, 20, 10]}]
        catalog = [{"id": "one", "title": "Example Car", "league": "黄金"}]
        match = match_vehicle(words, catalog)
        self.assertEqual(set(match), {"id", "title", "confidence"})
        self.assertEqual(match["id"], "one")
        self.assertIsNone(match_vehicle(words, []))
        self.assertIsNone(match_vehicle(words, catalog + [{**catalog[0], "id": "two"}]))
        self.assertIsNone(match_vehicle([{**words[0], "text": "zzz"}], catalog))
        self.assertIsNone(match_vehicle([{**words[0], "confidence": .69}], catalog))

    def test_match_score_and_runner_up_gap_boundaries(self) -> None:
        words = [{"text": "Example Car", "confidence": .99, "box": [0, 0, 20, 10]}]
        catalog = [{"id": "one", "title": "First", "league": "黄金"},
                   {"id": "two", "title": "Second", "league": "黄金"}]
        for scores, accepted in (((.78, .73), True), ((.779, .70), False), ((.82, .78), False)):
            with self.subTest(scores=scores), patch("ma9_agent.vehicle_screen.SequenceMatcher") as matcher:
                matcher.return_value.ratio.side_effect = scores
                result = match_vehicle(words, catalog)
                self.assertEqual(result is not None, accepted)

    def test_unique_model_line_survives_misread_brand(self) -> None:
        catalog = [
            {"id": "praga", "title": "Praga Bohema", "league": "黄金"},
            {"id": "other", "title": "Other Bohema", "league": "白银"},
        ]
        words = [
            {"text": "Proqo", "confidence": .895, "box": [332, 327, 35, 11]},
            {"text": "BOHEMA", "confidence": .992, "box": [334, 339, 69, 18]},
        ]
        self.assertEqual(match_vehicle(words, catalog, League.GOLD)["id"], "praga")
        self.assertIsNone(match_vehicle(words, catalog, League.BRONZE))


if __name__ == "__main__":
    unittest.main()
