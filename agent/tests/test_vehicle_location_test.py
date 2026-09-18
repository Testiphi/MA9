from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.models import League
from ma9_agent.vehicle_location_test import _rank_end, locate_once, run_location_test


class VehicleLocationTest(unittest.TestCase):
    def test_unknown_card_stops_instead_of_skipping_target(self) -> None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        unknown = [{"vehicle": None, "target": [350, 400], "card": [200, 190, 450, 227]}]
        with patch("ma9_agent.vehicle_location_test._ensure_owned_on", return_value=True), \
                patch("ma9_agent.vehicle_location_test._rank_start", return_value=True), \
                patch("ma9_agent.vehicle_location_test._frame", return_value=frame), \
                patch("ma9_agent.vehicle_location_test.selected_league", return_value=League.GOLD), \
                patch("ma9_agent.vehicle_location_test._hit", return_value=True), \
                patch("ma9_agent.vehicle_location_test._ocr", return_value=[]), \
                patch("ma9_agent.vehicle_location_test.read_page", side_effect=[unknown] * 5), \
                patch("ma9_agent.vehicle_location_test._click") as click, \
                patch("ma9_agent.vehicle_location_test.time.sleep"):
            report = locate_once(object(), "target", League.GOLD, "start", [])
        self.assertEqual(report["status"], "ocr_incomplete")
        click.assert_not_called()

    def test_end_anchor_uses_next_rank_then_moves_left(self) -> None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        with patch("ma9_agent.vehicle_location_test._rank_start", return_value=True) as start, \
                patch("ma9_agent.vehicle_location_test._swipe", return_value=True) as swipe, \
                patch("ma9_agent.vehicle_location_test._frame", return_value=frame), \
                patch("ma9_agent.vehicle_location_test.selected_league", return_value=League.GOLD), \
                patch("ma9_agent.vehicle_location_test._hit", return_value=True), \
                patch("ma9_agent.vehicle_location_test.time.sleep"):
            self.assertTrue(_rank_end(object(), League.GOLD))
        start.assert_called_once_with(ANY, League.PLATINUM)
        swipe.assert_called_once_with(ANY, "end")

    def test_legend_end_request_uses_legend_start_without_list_wrap(self) -> None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        cards = [[{"vehicle": {"id": "other"}, "target": [100, 300]}],
                 [{"vehicle": {"id": "target", "confidence": 1.0}, "target": [350, 400]}]]
        with patch("ma9_agent.vehicle_location_test._ensure_owned_on", return_value=True), \
                patch("ma9_agent.vehicle_location_test._rank_start", return_value=True) as start, \
                patch("ma9_agent.vehicle_location_test._rank_end") as end, \
                patch("ma9_agent.vehicle_location_test._frame", return_value=frame), \
                patch("ma9_agent.vehicle_location_test.selected_league", return_value=League.LEGEND), \
                patch("ma9_agent.vehicle_location_test._hit", return_value=True), \
                patch("ma9_agent.vehicle_location_test._ocr", return_value=[]), \
                patch("ma9_agent.vehicle_location_test.read_page", side_effect=cards), \
                patch("ma9_agent.vehicle_location_test._swipe", return_value=True) as swipe, \
                patch("ma9_agent.vehicle_location_test._click", return_value=True), \
                patch("ma9_agent.vehicle_location_test._detail_check", return_value={"status": "found"}), \
                patch("ma9_agent.vehicle_location_test.time.sleep"):
            report = locate_once(object(), "target", League.LEGEND, "end", [])
        self.assertEqual(report["status"], "found")
        start.assert_called_once_with(ANY, League.LEGEND)
        end.assert_not_called()
        swipe.assert_called_once_with(ANY, "start")

    def test_finds_card_and_only_clicks_car_body(self) -> None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        cards = [
            [{"vehicle": {"id": "other"}, "target": [100, 300]}],
            [{"vehicle": {"id": "target", "confidence": 1.0}, "target": [350, 400]}],
        ]
        catalog = [{"id": "target", "title": "Target", "league": "黄金"}]
        with patch("ma9_agent.vehicle_location_test._ensure_owned_on", return_value=True), \
                patch("ma9_agent.vehicle_location_test._rank_start", return_value=True), \
                patch("ma9_agent.vehicle_location_test._frame", return_value=frame), \
                patch("ma9_agent.vehicle_location_test.selected_league", return_value=League.GOLD), \
                patch("ma9_agent.vehicle_location_test._hit", return_value=True), \
                patch("ma9_agent.vehicle_location_test._ocr", return_value=[]), \
                patch("ma9_agent.vehicle_location_test.read_page", side_effect=cards), \
                patch("ma9_agent.vehicle_location_test._swipe", return_value=True) as swipe, \
                patch("ma9_agent.vehicle_location_test._click", return_value=True) as click, \
                patch("ma9_agent.vehicle_location_test._detail_check", return_value={"status": "found"}), \
                patch("ma9_agent.vehicle_location_test.time.sleep"):
            report = locate_once(object(), "target", League.GOLD, "start", catalog)
        self.assertEqual(report["status"], "found")
        self.assertEqual(report["pages"], 2)
        swipe.assert_called_once_with(ANY, "start")
        click.assert_called_once_with(ANY, 350, 400)

    def test_repeated_trials_return_to_list_but_leave_final_detail_open(self) -> None:
        catalog = {"vehicles": [{"id": "car", "title": "Car", "league": "白银"}]}
        rotation = {"groups": []}
        garage = {"vehicles": {"car": {"owned": True}}}
        request = {"schema_version": 1, "vehicle_id": "car", "from": "end", "repeats": 3}
        with patch("ma9_agent.vehicle_location_test.locate_once", return_value={"status": "found", "pages": 2}) as locate, \
                patch("ma9_agent.vehicle_location_test._back_to_list", return_value=True) as back:
            report = run_location_test(object(), catalog, rotation, garage, request)
        self.assertEqual(report["status"], "found")
        self.assertEqual(locate.call_count, 3)
        self.assertEqual(back.call_count, 2)


if __name__ == "__main__":
    unittest.main()
