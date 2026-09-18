from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.models import League
from ma9_agent.selection_runtime import _detail_ready, _open_vehicle, scan_rank, select_recommended


class SelectionRuntimeSearchTest(unittest.TestCase):
    def test_scrolling_detail_name_does_not_reject_fueled_car(self) -> None:
        context = SimpleNamespace(run_recognition=lambda *_: SimpleNamespace(hit=True))
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        with patch("ma9_agent.selection_runtime._frame", return_value=frame), \
                patch("ma9_agent.selection_runtime._ocr", return_value=[{"text": "3/3"}]):
            self.assertTrue(_detail_ready(context))

    def test_unknown_card_does_not_count_as_completed_rank_scan(self) -> None:
        context = SimpleNamespace(run_recognition=lambda *_: SimpleNamespace(hit=True))
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        with patch("ma9_agent.selection_runtime._rank_start", return_value=True), \
                patch("ma9_agent.selection_runtime._frame", return_value=frame), \
                patch("ma9_agent.selection_runtime.selected_league", return_value=League.GOLD), \
                patch("ma9_agent.selection_runtime._read_records", return_value=(frame, [{"vehicle": None}], False)):
            _, status, pages = scan_rank(context, League.GOLD, [], max_pages=3)
        self.assertEqual((status, pages), ("ocr_incomplete", 0))

    def test_first_priority_card_stops_scan_on_visible_page(self) -> None:
        context = SimpleNamespace(run_recognition=lambda *_: SimpleNamespace(hit=True))
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        card = {"vehicle": {"id": "dbs"}, "fuel": 3, "target": [400, 350]}
        with patch("ma9_agent.selection_runtime._rank_start", return_value=True), \
                patch("ma9_agent.selection_runtime._frame", return_value=frame), \
                patch("ma9_agent.selection_runtime.selected_league", return_value=League.PLATINUM), \
                patch("ma9_agent.selection_runtime._read_records", return_value=(frame, [card], True)):
            found, status, pages = scan_rank(context, League.PLATINUM, [], stop_when="dbs")
        self.assertEqual((status, pages), ("target_visible", 1))
        self.assertEqual(found["dbs"]["target"], [400, 350])

    def test_dry_priority_stops_scan_before_rank_boundary(self) -> None:
        context = SimpleNamespace(run_recognition=lambda *_: SimpleNamespace(hit=True))
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        card = {"vehicle": {"id": "panamera"}, "fuel": 0, "target": [400, 350]}
        with patch("ma9_agent.selection_runtime._rank_start", return_value=True), \
                patch("ma9_agent.selection_runtime._frame", return_value=frame), \
                patch("ma9_agent.selection_runtime.selected_league", return_value=League.GOLD), \
                patch("ma9_agent.selection_runtime._read_records", return_value=(frame, [card], True)):
            _, status, pages = scan_rank(context, League.GOLD, [], stop_when="panamera")
        self.assertEqual((status, pages), ("target_visible", 1))

    def test_first_priority_opens_from_scan_without_second_pass(self) -> None:
        car = {"catalog_id": "dbs", "league": "白金", "title": "Aston Martin DBS Superleggera"}
        card = {"vehicle": {"id": "dbs"}, "fuel": 3, "target": [400, 350]}
        with patch("ma9_agent.selection_runtime.planned_vehicles", return_value=[car]), \
                patch("ma9_agent.selection_runtime.scan_rank", return_value=({"dbs": card}, "target_visible", 8)) as scan, \
                patch("ma9_agent.selection_runtime._open_visible_card", return_value=True) as open_card, \
                patch("ma9_agent.selection_runtime._open_vehicle") as second_pass:
            result = select_recommended(None, Path("."), "白金", {"vehicles": []}, {}, {})
        self.assertEqual(result["status"], "selected")
        self.assertEqual(result["rank_scans"]["白金"]["pages"], 8)
        scan.assert_called_once_with(None, League.PLATINUM, [], stop_when="dbs")
        open_card.assert_called_once_with(None, card)
        second_pass.assert_not_called()

    def test_rejected_first_priority_continues_to_next_car(self) -> None:
        first = {"catalog_id": "dbs", "league": "白金", "title": "DBS"}
        second = {"catalog_id": "next", "league": "白金", "title": "Next"}
        cards = {"dbs": {"vehicle": {"id": "dbs"}, "fuel": 3, "target": [400, 350]},
                 "next": {"vehicle": {"id": "next"}, "fuel": 3, "target": [800, 350]}}
        context = SimpleNamespace(run_recognition=lambda *_: SimpleNamespace(hit=True))
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        with patch("ma9_agent.selection_runtime.planned_vehicles", return_value=[first, second]), \
                patch("ma9_agent.selection_runtime.scan_rank",
                      side_effect=[({"dbs": cards["dbs"]}, "target_visible", 8),
                                   ({"next": cards["next"]}, "target_visible", 12)]) as scan, \
                patch("ma9_agent.selection_runtime._open_visible_card", side_effect=[False, True]) as open_card, \
                patch("ma9_agent.selection_runtime._open_vehicle") as second_pass:
            result = select_recommended(context, Path("."), "白金", {"vehicles": []}, {}, {})
        self.assertEqual(result["status"], "selected")
        self.assertEqual(result["vehicle_id"], "next")
        self.assertEqual(scan.call_count, 2)
        self.assertEqual(open_card.call_count, 2)
        second_pass.assert_not_called()

    def test_second_pass_rechecks_cards_instead_of_replaying_page_count(self) -> None:
        controller = MagicMock()
        controller.post_swipe.return_value.wait.return_value.succeeded = True
        context = SimpleNamespace(tasker=SimpleNamespace(controller=controller))
        context.run_recognition = lambda *_: SimpleNamespace(hit=True)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        cards = [[{"vehicle": {"id": "other"}, "target": [100, 300]}],
                 [{"vehicle": {"id": "target"}, "target": [350, 400]}]]
        with patch("ma9_agent.selection_runtime._rank_end", return_value=False), \
                patch("ma9_agent.selection_runtime._rank_start", return_value=True), \
                patch("ma9_agent.selection_runtime._frame", return_value=frame), \
                patch("ma9_agent.selection_runtime.selected_league", return_value=League.GOLD), \
                patch("ma9_agent.selection_runtime._read_records",
                      side_effect=[(frame, cards[0], True), (frame, cards[1], True)]), \
                patch("ma9_agent.selection_runtime._click", return_value=True) as click, \
                patch("ma9_agent.selection_runtime._detail_ready", return_value=True), \
                patch("ma9_agent.selection_runtime.time.sleep"):
            self.assertTrue(_open_vehicle(context, League.GOLD, "target", []))
        controller.post_swipe.assert_called_once_with(1000, 420, 600, 420, 320)
        click.assert_called_once_with(ANY, 350, 400)

    def test_second_pass_prefers_reverse_search_from_rank_end(self) -> None:
        controller = MagicMock()
        controller.post_swipe.return_value.wait.return_value.succeeded = True
        context = SimpleNamespace(tasker=SimpleNamespace(controller=controller))
        context.run_recognition = lambda *_: SimpleNamespace(hit=True)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        cards = [[{"vehicle": {"id": "other"}, "target": [100, 300]}],
                 [{"vehicle": {"id": "target"}, "target": [350, 400]}]]
        with patch("ma9_agent.selection_runtime._rank_end", return_value=True), \
                patch("ma9_agent.selection_runtime._rank_start") as rank_start, \
                patch("ma9_agent.selection_runtime._frame", return_value=frame), \
                patch("ma9_agent.selection_runtime.selected_league", return_value=League.GOLD), \
                patch("ma9_agent.selection_runtime._read_records",
                      side_effect=[(frame, cards[0], True), (frame, cards[1], True)]), \
                patch("ma9_agent.selection_runtime._click", return_value=True) as click, \
                patch("ma9_agent.selection_runtime._detail_ready", return_value=True), \
                patch("ma9_agent.selection_runtime.time.sleep"):
            self.assertTrue(_open_vehicle(context, League.GOLD, "target", []))
        rank_start.assert_not_called()
        controller.post_swipe.assert_called_once_with(600, 420, 1000, 420, 320)
        click.assert_called_once_with(ANY, 350, 400)


if __name__ == "__main__":
    unittest.main()
