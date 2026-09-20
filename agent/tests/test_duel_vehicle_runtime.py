from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_vehicle_runtime import _try_target, scan


class _Job:
    succeeded = True

    def wait(self):
        return self


class _Controller:
    def __init__(self):
        self.swipes = 0

    def post_swipe(self, *_args):
        self.swipes += 1
        return _Job()


class _Context:
    def __init__(self):
        self.tasker = type("Tasker", (), {"controller": _Controller()})()


def _card(vehicle_id: str, vehicle_class: str = "D") -> dict:
    return {
        "vehicle": {"id": vehicle_id, "title": vehicle_id, "confidence": 1.0},
        "class": vehicle_class,
        "performance": [2000, None],
        "stars_lit": None,
        "star_slots": None,
        "card": [100, 168, 420, 212],
        "target": [285, 273],
    }


class DuelVehicleRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    def test_edge_requires_two_unchanged_swipes(self) -> None:
        context = _Context()
        pages = [
            (self.frame, [_card("a"), _card("b")], True),
            (self.frame, [_card("a"), _card("b")], True),
            (self.frame, [_card("c"), _card("d")], True),
            (self.frame, [_card("c"), _card("d")], True),
            (self.frame, [_card("c"), _card("d")], True),
        ]
        catalog = [{"id": value, "title": value, "class": "D"}
                   for value in "abcd"]
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      side_effect=pages), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "D", catalog, max_pages=8)
        self.assertEqual(report["status"], "edge_reached")
        self.assertTrue(report["scan_complete"])
        self.assertEqual(report["pages"], 5)
        self.assertEqual(context.tasker.controller.swipes, 4)
        self.assertEqual({row["vehicle"]["id"] for row in report["vehicles"]},
                         {"a", "b", "c", "d"})

    def test_mixed_transition_page_keeps_requested_class_tail(self) -> None:
        context = _Context()
        pages = [
            (self.frame, [_card("r1", "R"), _card("s1", "S")], True),
            (self.frame, [_card("s1", "S"), _card("s2", "S")], True),
        ]
        catalog = [
            {"id": "r1", "title": "r1", "class": "R"},
            {"id": "s1", "title": "s1", "class": "S"},
            {"id": "s2", "title": "s2", "class": "S"},
        ]
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      side_effect=pages), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "R", catalog, max_pages=5)
        self.assertEqual(report["status"], "class_boundary")
        self.assertEqual(report["next_class"], "S")
        self.assertEqual([row["vehicle"]["id"] for row in report["vehicles"]], ["r1"])

    def test_wrong_detail_reacquires_same_vehicle_before_retry(self) -> None:
        context = _Context()
        card = _card("target")
        assigned = {"status": "assigned", "assignment_complete": True,
                    "pages": 1, "vehicles": [card]}
        with patch("ma9_agent.duel_vehicle_runtime._finish_target",
                   side_effect=[{"status": "wrong_detail"}, assigned]), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True) as click, \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      return_value=(self.frame, [card], True)), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = _try_target(context, card, 1, [card], "target",
                                 [{"id": "target", "title": "target", "class": "D"}],
                                 choose=True, expected_performance=2000,
                                 expected_stars=None)
        self.assertEqual(report["status"], "assigned")
        self.assertEqual(report["target_attempts"], 2)
        click.assert_called_once_with(context, 32, 25)

    def test_page_hint_fast_forwards_before_target_ocr(self) -> None:
        context = _Context()
        card = _card("target")
        catalog = [{"id": "target", "title": "target", "class": "D"}]
        assigned = {"status": "assigned", "assignment_complete": True,
                    "pages": 5, "vehicles": [card]}
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      return_value=(self.frame, [card], True)), \
                patch("ma9_agent.duel_vehicle_runtime._try_target",
                      return_value=assigned), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "D", catalog, target_id="target", choose=True,
                          max_pages=10, page_hint=6,
                          expected_performance=2000)
        # Page six normally needs five swipes. Stop one page early, then OCR
        # and locate the exact card instead of assuming the swipe landed.
        self.assertEqual(context.tasker.controller.swipes, 4)
        self.assertEqual(report["status"], "assigned")
        self.assertEqual(report["fast_forward_swipes"], 4)


if __name__ == "__main__":
    unittest.main()
