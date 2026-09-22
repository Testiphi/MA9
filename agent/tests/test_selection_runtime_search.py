from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.models import League
from ma9_agent.selection_runtime import _detail_ready, _open_vehicle, scan_rank, select_recommended
from ma9_agent import selection_runtime as runtime


class SelectionRuntimeSearchTest(unittest.TestCase):
    def test_public_frame_ocr_and_compatibility_aliases(self) -> None:
        self.assertIs(runtime._frame, runtime.frame_of)
        self.assertIs(runtime._ocr, runtime.ocr_roi)
        self.assertTrue({"frame_of", "ocr_roi", "_frame", "_ocr"} <= set(runtime.__all__))
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        context = MagicMock()
        context.tasker.controller.post_screencap.return_value.get.return_value = frame
        self.assertEqual(runtime.frame_of(context).shape, (720, 1280, 3))
        context.tasker.controller.post_screencap.return_value.get.assert_called_once_with(wait=True)
        context.run_recognition_direct.return_value = SimpleNamespace(all_results=[
            SimpleNamespace(text="7/9", score=.9, box=(1, 2, 3, 4))])
        roi = (0, 0, 100, 100)
        self.assertEqual(runtime.ocr_roi(context, frame, roi),
                         [{"text": "7/9", "confidence": .9, "box": [1, 2, 3, 4]}])
        args = context.run_recognition_direct.call_args.args
        self.assertIs(args[2], frame)
        self.assertEqual(tuple(args[1].roi), roi)
        context.run_recognition_direct.return_value = None
        self.assertEqual(runtime.ocr_roi(context, frame, roi), [])

    def test_ocr_retry_budget_returns_incomplete_without_skipping(self) -> None:
        context = SimpleNamespace(run_recognition=lambda *_: SimpleNamespace(hit=True))
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        unknown = [{"vehicle": None}]
        with patch.object(runtime, "_frame", return_value=frame), \
                patch.object(runtime, "_ocr", return_value=[]), \
                patch.object(runtime, "selected_league", return_value=League.GOLD), \
                patch.object(runtime, "read_page", return_value=unknown) as read, \
                patch.object(runtime.time, "sleep"):
            image, records, complete = runtime._read_records(context, frame, League.GOLD, [])
        self.assertIs(image, frame)
        self.assertEqual(records, unknown)
        self.assertFalse(complete)
        self.assertEqual(read.call_count, 5)  # five attempts total, not five plus an initial attempt

    def test_all_scan_exit_statuses(self) -> None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        card = {"vehicle": {"id": "car"}, "fuel": 3, "target": [400, 350]}
        cases = [
            ("rank_not_ready", False, League.GOLD, True, True, True, 3, None, 0),
            ("league_boundary", True, League.SILVER, True, True, True, 3, None, 0),
            ("rank_unknown", True, None, True, True, True, 3, None, 0),
            ("owned_filter_lost", True, League.GOLD, False, True, True, 3, None, 0),
            ("ocr_incomplete", True, League.GOLD, True, False, True, 3, None, 0),
            ("edge_reached", True, League.GOLD, True, True, True, 3, None, 3),
            ("target_visible", True, League.GOLD, True, True, True, 3, "car", 1),
            ("swipe_failed", True, League.GOLD, True, True, False, 3, None, 1),
            ("page_limit", True, League.GOLD, True, True, True, 1, None, 1),
        ]
        for expected, start, rank, owned, complete, swipe, limit, target, pages in cases:
            context = MagicMock()
            context.run_recognition.return_value = SimpleNamespace(hit=owned)
            context.tasker.controller.post_swipe.return_value.wait.return_value.succeeded = swipe
            with self.subTest(status=expected), \
                    patch.object(runtime, "_rank_start", return_value=start), \
                    patch.object(runtime, "_frame", return_value=frame), \
                    patch.object(runtime, "selected_league", return_value=rank), \
                    patch.object(runtime, "_read_records", return_value=(frame, [card], complete)), \
                    patch.object(runtime.time, "sleep"):
                _, status, count = scan_rank(context, League.GOLD, [], max_pages=limit, stop_when=target)
                self.assertEqual((status, count), (expected, pages))

    def test_report_shapes_statuses_and_real_diagnostic_file(self) -> None:
        car = {"catalog_id": "car", "league": "黄金", "title": "Car"}
        card = {"vehicle": {"id": "car"}, "fuel": 3, "target": [400, 350]}
        required = {"player_league", "priority_count", "rank_scans", "attempted", "status"}
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        for expected, scan_status, opened, screen_ok in (
                ("selected", "edge_reached", True, True),
                ("fallback", "edge_reached", False, True),
                ("scan_error", "ocr_incomplete", False, True),
                ("unexpected_screen", "edge_reached", False, False)):
            context = SimpleNamespace(run_recognition=lambda *_: SimpleNamespace(hit=screen_ok))
            with tempfile.TemporaryDirectory() as directory, self.subTest(status=expected), \
                    patch.object(runtime, "planned_vehicles", return_value=[car]), \
                    patch.object(runtime, "scan_rank", return_value=({"car": card}, scan_status, 2)), \
                    patch.object(runtime, "_open_vehicle", return_value=opened), \
                    patch.object(runtime, "_frame", return_value=frame):
                report = select_recommended(context, Path(directory), "黄金", {"vehicles": []}, {}, {})
                self.assertEqual(report["status"], expected)
                extra = ({"vehicle_id", "vehicle_name"} if expected == "selected" else
                         {"diagnostic_image"} if expected == "scan_error" else set())
                self.assertEqual(set(report), required | extra)
                self.assertEqual(report["rank_scans"], {"黄金": {
                    "status": scan_status, "pages": 2, "recognized": 1}})
                if expected == "scan_error":
                    path = Path(directory) / "debug/selection_ocr_failure.png"
                    self.assertEqual(report["diagnostic_image"], str(path))
                    self.assertTrue(path.is_file())
                    self.assertGreater(path.stat().st_size, 0)
        with patch.object(runtime, "planned_vehicles", return_value=[]):
            self.assertEqual(select_recommended(None, Path("."), "黄金", {}, {}, {}), {
                "player_league": "黄金", "priority_count": 0, "rank_scans": {}, "attempted": [], "status": "fallback"})

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
