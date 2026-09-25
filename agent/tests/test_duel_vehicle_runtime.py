from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_vehicle_runtime import (_detail, _finish_target, _try_target,
                                            assign_visible, scan)

_UNSET = object()


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


class _DetailContext(_Context):
    def __init__(self, template_hits):
        super().__init__()
        self.template_hits = iter(template_hits)
        self.template_calls = []

    def run_recognition_direct(self, recognition_type, params, frame):
        self.template_calls.append((recognition_type, params, frame))
        return SimpleNamespace(hit=next(self.template_hits, False))


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

    @staticmethod
    def _detail_ocr(*, selection_text="择", occupied=False, wrong_vehicle=False,
                    detail_rating="1,381"):
        def ocr(_context, _frame_value, roi):
            if roi == (160, 76, 300, 110):
                if wrong_vehicle:
                    return [
                        {"text": "OTHER", "confidence": .99, "box": [160, 76, 100, 25]},
                        {"text": "CAR", "confidence": .99, "box": [160, 104, 100, 25]},
                    ]
                return [
                    {"text": "MITSUBISHI", "confidence": .99, "box": [160, 76, 170, 25]},
                    {"text": "LANCER EVOLUTION", "confidence": .99, "box": [160, 104, 220, 25]},
                ]
            if roi == (200, 560, 800, 150):
                return ([{"text": "这辆车已被放置在赛道", "confidence": .99,
                          "box": [300, 610, 320, 25]}] if occupied else [])
            if roi == (900, 90, 210, 90):
                return [{"text": detail_rating, "confidence": .99, "box": [900, 126, 130, 30]}]
            if roi == (1000, 600, 270, 105):
                return [{"text": selection_text, "confidence": .99, "box": [1138, 643, 52, 25]}]
            return []
        return ocr

    @staticmethod
    def _detail_catalog():
        return [
            {"id": "lancer", "title": "Mitsubishi Lancer Evolution", "class": "D"},
            {"id": "other", "title": "Other Car", "class": "D"},
        ]

    @staticmethod
    def _active_button_frame(stars: int = 0):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame[625:690, 1045:1235] = (20, 240, 180)
        for index in range(stars):
            frame[95, 180 + 24 * index] = (20, 200, 200)
        return frame

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

    def test_continuously_unstable_page_stops_without_scanning_or_swiping(self) -> None:
        context = _Context()
        unstable = (self.frame, [_card("untrusted")], False)
        catalog = [{"id": "untrusted", "title": "untrusted", "class": "D"}]
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      return_value=unstable) as sample, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "D", catalog, max_pages=3)
        self.assertEqual(report["status"], "page_ocr_unverified")
        self.assertFalse(report["scan_complete"])
        self.assertEqual(report["vehicles"], [])
        self.assertEqual(context.tasker.controller.swipes, 0)
        self.assertEqual(sample.call_count, 2)

    def test_stable_resample_discards_prior_unstable_cards(self) -> None:
        context = _Context()
        unstable = (self.frame, [_card("untrusted")], False)
        settled = (self.frame, [_card("trusted")], True)
        catalog = [{"id": value, "title": value, "class": "D"}
                   for value in ("untrusted", "trusted")]
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      side_effect=[unstable, settled, settled, settled]), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "D", catalog, max_pages=4)
        self.assertEqual(report["status"], "edge_reached")
        self.assertEqual([row["vehicle"]["id"] for row in report["vehicles"]], ["trusted"])
        self.assertEqual(context.tasker.controller.swipes, 2)

    def test_unstable_target_is_never_opened_before_a_stable_read(self) -> None:
        context = _Context()
        target = _card("target")
        stable_other = (self.frame, [_card("other")], True)
        catalog = [{"id": "target", "title": "target", "class": "D"},
                   {"id": "other", "title": "other", "class": "D"}]
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      side_effect=[(self.frame, [target], False), stable_other,
                                   stable_other, stable_other]), \
                patch("ma9_agent.duel_vehicle_runtime._try_target") as try_target, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "D", catalog, target_id="target", choose=True, max_pages=4)
        self.assertEqual(report["status"], "target_not_found")
        self.assertTrue(report["scan_complete"])
        self.assertEqual([row["vehicle"]["id"] for row in report["vehicles"]], ["other"])
        try_target.assert_not_called()

    def test_assign_visible_refuses_a_continuously_unstable_target(self) -> None:
        context = _Context()
        target = _card("target")
        catalog = [{"id": "target", "title": "target", "class": "D"}]
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.frame), \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      side_effect=[(self.frame, [target], False)] * 2), \
                patch("ma9_agent.duel_vehicle_runtime._try_target") as try_target, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = assign_visible(context, "target", catalog)
        self.assertEqual(report["status"], "page_ocr_unverified")
        self.assertFalse(report["scan_complete"])
        try_target.assert_not_called()

    def test_detail_retry_refuses_a_continuously_unstable_replacement(self) -> None:
        context = _Context()
        target = _card("target")
        catalog = [{"id": "target", "title": "target", "class": "D"}]
        with patch("ma9_agent.duel_vehicle_runtime._finish_target",
                   return_value={"status": "wrong_detail"}) as finish, \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      side_effect=[(self.frame, [target], False)] * 2), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = _try_target(context, target, 1, [target], "target", catalog,
                                 choose=True, expected_performance=2000,
                                 expected_stars=None)
        self.assertEqual(report["status"], "target_temporarily_unreadable")
        self.assertEqual(report["target_attempts"], 1)
        finish.assert_called_once()

    def test_unstable_lower_class_page_cannot_finish_an_existing_scan(self) -> None:
        context = _Context()
        trusted = _card("trusted", "R")
        lower = _card("lower", "S")
        unstable_lower = (self.frame, [lower], False)
        catalog = [{"id": "trusted", "title": "trusted", "class": "R"},
                   {"id": "lower", "title": "lower", "class": "S"}]
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      side_effect=[(self.frame, [trusted], True),
                                   unstable_lower, unstable_lower]), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "R", catalog, max_pages=3)
        self.assertEqual(report["status"], "page_ocr_unverified")
        self.assertFalse(report["scan_complete"])
        self.assertEqual([row["vehicle"]["id"] for row in report["vehicles"]], ["trusted"])
        self.assertEqual(context.tasker.controller.swipes, 1)

    def test_real_sampler_rejects_four_distinct_animated_fingerprints(self) -> None:
        context = _Context()
        cards = [_card(f"car{index}") for index in range(8)]
        catalog = [{"id": card["vehicle"]["id"], "title": card["vehicle"]["id"], "class": "D"}
                   for card in cards]
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._frame", return_value=self.frame), \
                patch("ma9_agent.duel_vehicle_runtime._selection_title", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._visible",
                      side_effect=[[card] for card in cards]), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "D", catalog, max_pages=3)
        self.assertEqual(report["status"], "page_ocr_unverified")
        self.assertFalse(report["scan_complete"])
        self.assertEqual(report["vehicles"], [])
        self.assertEqual(context.tasker.controller.swipes, 0)

    def test_detail_waits_for_template_button_when_ocr_only_reads_single_character(self) -> None:
        context = _DetailContext([False, True])
        card = _card("lancer")
        card["performance"] = [1381, None]
        frame = self._active_button_frame()
        with patch("ma9_agent.duel_vehicle_runtime._frame", return_value=frame), \
                patch("ma9_agent.duel_vehicle_runtime._ocr", self._detail_ocr()), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True) as click, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = _finish_target(context, card, 1, [card], "lancer", self._detail_catalog(),
                                    choose=True, expected_performance=1381, expected_stars=None)
        self.assertEqual(report["status"], "assignment_unverified")
        self.assertEqual(len(context.template_calls), 2)
        self.assertEqual(context.template_calls[0][1].template,
                         ["navigation/duel/detail_select_text.png"])
        self.assertEqual(tuple(context.template_calls[0][1].roi), (1020, 610, 240, 100))
        self.assertEqual([call.args[1:] for call in click.call_args_list],
                         [tuple(card["target"]), (1139, 658)])

    def test_detail_never_clicks_missing_or_obscured_template_button(self) -> None:
        card = _card("lancer")
        card["performance"] = [1381, None]
        for name, template_hits, frame in (
                ("missing", [False] * 8, self._active_button_frame()),
                ("obscured", [True] * 8, self.frame),
        ):
            with self.subTest(name=name):
                context = _DetailContext(template_hits)
                with patch("ma9_agent.duel_vehicle_runtime._frame", return_value=frame), \
                        patch("ma9_agent.duel_vehicle_runtime._ocr",
                              self._detail_ocr(selection_text="选择")), \
                        patch("ma9_agent.duel_vehicle_runtime._click", return_value=True) as click, \
                        patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
                    report = _finish_target(
                        context, card, 1, [card], "lancer", self._detail_catalog(),
                        choose=True, expected_performance=1381, expected_stars=None)
                self.assertEqual(report["status"], "select_unavailable")
                self.assertEqual(len(context.template_calls), 8)
                self.assertEqual([call.args[1:] for call in click.call_args_list],
                                 [tuple(card["target"])])

    def test_detail_refuses_occupied_or_wrong_vehicle_before_selecting(self) -> None:
        card = _card("lancer")
        card["performance"] = [1381, None]
        for name, occupied, wrong_vehicle, status in (
                ("occupied", True, False, "occupied_elsewhere"),
                ("wrong", False, True, "wrong_detail"),
        ):
            with self.subTest(name=name):
                context = _DetailContext([True])
                with patch("ma9_agent.duel_vehicle_runtime._frame",
                           return_value=self._active_button_frame()), \
                        patch("ma9_agent.duel_vehicle_runtime._ocr",
                              self._detail_ocr(selection_text="选择", occupied=occupied,
                                               wrong_vehicle=wrong_vehicle)), \
                        patch("ma9_agent.duel_vehicle_runtime._click", return_value=True) as click, \
                        patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
                    report = _finish_target(
                        context, card, 1, [card], "lancer", self._detail_catalog(),
                        choose=True, expected_performance=1381, expected_stars=None)
                self.assertEqual(report["status"], status)
                self.assertEqual([call.args[1:] for call in click.call_args_list],
                                 [tuple(card["target"])])

    # ------------------------------------- name-first list/detail rating policy
    def _finish(self, card, *, choose=False, expected_performance=None,
                expected_stars=None, verify=_UNSET, stars=0, **ocr_kwargs):
        extras = {} if verify is _UNSET else {"verify_list_detail_rating": verify}
        context = _DetailContext([True] * 40)
        with patch("ma9_agent.duel_vehicle_runtime._frame",
                   return_value=self._active_button_frame(stars=stars)), \
                patch("ma9_agent.duel_vehicle_runtime._ocr",
                      self._detail_ocr(**ocr_kwargs)), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True) as click, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = _finish_target(
                context, card, 1, [card], "lancer", self._detail_catalog(),
                choose=choose, expected_performance=expected_performance,
                expected_stars=expected_stars, **extras)
        return report, [call.args[1:] for call in click.call_args_list]

    def test_default_still_rejects_the_live_list_detail_rating_mismatch(self) -> None:
        """Old default (verify omitted -> True) keeps the live 4837/4897 refusal."""
        card = _card("lancer")
        card["performance"] = [4837, 4897]
        report, clicks = self._finish(card, detail_rating="37/4,897")
        self.assertEqual(report["status"], "list_detail_rating_mismatch")
        self.assertEqual(report["performance"], 4897)
        self.assertNotIn("list_detail_rating_compare", report)
        self.assertEqual(clicks, [tuple(card["target"])])

    def test_name_first_disables_only_the_implicit_rating_compare(self) -> None:
        card = _card("lancer")
        card["performance"] = [4837, 4897]
        report, clicks = self._finish(card, verify=False, detail_rating="37/4,897")
        self.assertEqual(report["status"], "detail_verified")
        self.assertEqual(report["performance"], 4897)  # raw reading, never rewritten
        self.assertEqual(report["list_detail_rating_compare"], "disabled")
        self.assertTrue(report["select_available"])
        self.assertEqual(clicks, [tuple(card["target"])])

    def test_name_first_still_enforces_an_explicit_expected_performance(self) -> None:
        card = _card("lancer")
        card["performance"] = [4837, 4897]
        report, _clicks = self._finish(card, verify=False, expected_performance=4837,
                                       detail_rating="37/4,897")
        self.assertEqual(report["status"], "performance_mismatch")
        self.assertEqual(report["performance"], 4897)
        matching, _clicks = self._finish(card, verify=False, expected_performance=4897,
                                         detail_rating="37/4,897")
        self.assertEqual(matching["status"], "detail_verified")

    def test_name_first_still_enforces_expected_stars(self) -> None:
        card = _card("lancer")
        card["performance"] = [4837, 4897]
        report, _clicks = self._finish(card, verify=False, expected_stars=5, stars=6,
                                       detail_rating="37/4,897")
        self.assertEqual(report["status"], "stars_mismatch")
        self.assertEqual(report["stars_lit"], 6)
        matching, _clicks = self._finish(card, verify=False, expected_stars=6, stars=6,
                                        detail_rating="37/4,897")
        self.assertEqual(matching["status"], "detail_verified")

    def test_name_first_keeps_wrong_detail_and_occupied_guards(self) -> None:
        card = _card("lancer")
        card["performance"] = [4837, 4897]
        for label, keyword, status in (("wrong_detail", dict(wrong_vehicle=True), "wrong_detail"),
                                       ("occupied", dict(occupied=True), "occupied_elsewhere")):
            with self.subTest(case=label):
                report, clicks = self._finish(card, verify=False, choose=True,
                                              detail_rating="37/4,897", **keyword)
                self.assertEqual(report["status"], status)
                self.assertFalse(report["assignment_complete"])
                self.assertEqual(clicks, [tuple(card["target"])])

    def test_name_first_never_locates_a_missing_detail(self) -> None:
        card = _card("lancer")
        card["performance"] = [4837, 4897]
        context = _DetailContext([True] * 40)
        with patch("ma9_agent.duel_vehicle_runtime._frame",
                   return_value=self._active_button_frame()), \
                patch("ma9_agent.duel_vehicle_runtime._ocr", lambda *args: []), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = _finish_target(
                context, card, 1, [card], "lancer", self._detail_catalog(),
                choose=False, expected_performance=None, expected_stars=None,
                verify_list_detail_rating=False)
        self.assertEqual(report["status"], "detail_not_verified")
        self.assertFalse(report["assignment_complete"])

    def test_name_first_choose_still_runs_select_and_assignment_guards(self) -> None:
        card = _card("lancer")
        card["performance"] = [4837, 4897]
        frame = self._active_button_frame()

        def ocr(_context, _frame_value, roi):
            if roi == (160, 76, 300, 110):
                return [{"text": "MITSUBISHI", "confidence": .99, "box": [160, 76, 170, 25]},
                        {"text": "LANCER EVOLUTION", "confidence": .99, "box": [160, 104, 220, 25]}]
            if roi == (900, 90, 210, 90):
                return [{"text": "37/4,897", "confidence": .99, "box": [900, 126, 130, 30]}]
            if roi == (470, 470, 720, 90):
                return [{"text": "更换车辆", "confidence": .99, "box": [470, 470, 120, 25]}]
            if roi == (0, 170, 1280, 190):
                return [{"text": "MITSUBISHI", "confidence": .99, "box": [0, 170, 170, 25]},
                        {"text": "LANCER EVOLUTION", "confidence": .99, "box": [0, 200, 220, 25]}]
            return []

        context = _DetailContext([True] * 40)
        with patch("ma9_agent.duel_vehicle_runtime._frame", return_value=frame), \
                patch("ma9_agent.duel_vehicle_runtime._ocr", ocr), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True) as click, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = _finish_target(context, card, 1, [card], "lancer",
                                    self._detail_catalog(), choose=True,
                                    expected_performance=None, expected_stars=None,
                                    verify_list_detail_rating=False)
        self.assertEqual(report["status"], "assigned")
        self.assertTrue(report["assignment_complete"])
        self.assertEqual([call.args[1:] for call in click.call_args_list],
                         [tuple(card["target"]), (1139, 658)])

    def test_strict_defaults_are_preserved_and_the_flag_is_forwarded(self) -> None:
        for func in (scan, _try_target, _finish_target):
            self.assertIs(inspect.signature(func).parameters["verify_list_detail_rating"].default,
                          True, func.__name__)
        self.assertNotIn("verify_list_detail_rating",
                         inspect.signature(assign_visible).parameters)

        context = _Context()
        card = _card("target")
        catalog = [{"id": "target", "title": "target", "class": "D"}]
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      return_value=(self.frame, [card], True)), \
                patch("ma9_agent.duel_vehicle_runtime._try_target",
                      return_value={"status": "detail_verified"}) as try_target, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            scan(context, "D", catalog, target_id="target", verify_list_detail_rating=False)
            self.assertIs(try_target.call_args.kwargs["verify_list_detail_rating"], False)
            scan(context, "D", catalog, target_id="target")
            self.assertIs(try_target.call_args.kwargs["verify_list_detail_rating"], True)

    def test_non_bool_verify_flag_is_rejected_before_any_context_call(self) -> None:
        context = _Context()
        catalog = [{"id": "a", "title": "a", "class": "D"}]
        for bad in ("yes", 1, 0, None, []):
            with self.subTest(bad=repr(bad)):
                with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame") as wait:
                    with self.assertRaises(ValueError):
                        scan(context, "D", catalog, target_id="a",
                             verify_list_detail_rating=bad)
                    wait.assert_not_called()
                self.assertEqual(context.tasker.controller.swipes, 0)

    def test_scan_name_first_stops_on_the_target_detail_without_a_return_click(self) -> None:
        context = _DetailContext([True] * 40)
        card = _card("lancer")
        card["performance"] = [4837, 4897]
        frame = self._active_button_frame()
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True) as click, \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      return_value=(frame, [card], True)), \
                patch("ma9_agent.duel_vehicle_runtime._frame", return_value=frame), \
                patch("ma9_agent.duel_vehicle_runtime._ocr",
                      self._detail_ocr(detail_rating="37/4,897")), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "D", self._detail_catalog(), target_id="lancer",
                          choose=False, verify_list_detail_rating=False)
        self.assertEqual(report["status"], "detail_verified")
        self.assertEqual(report["performance"], 4897)
        self.assertEqual(report["list_detail_rating_compare"], "disabled")
        self.assertNotIn((32, 25), [call.args[1:] for call in click.call_args_list])

    def test_scan_strict_default_repeats_the_existing_mismatch_retry(self) -> None:
        context = _DetailContext([True] * 80)
        card = _card("lancer")
        card["performance"] = [4837, 4897]
        frame = self._active_button_frame()
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True) as click, \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      return_value=(frame, [card], True)), \
                patch("ma9_agent.duel_vehicle_runtime._frame", return_value=frame), \
                patch("ma9_agent.duel_vehicle_runtime._ocr",
                      self._detail_ocr(detail_rating="37/4,897")), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "D", self._detail_catalog(), target_id="lancer",
                          choose=False)
        self.assertEqual(report["status"], "list_detail_rating_mismatch")
        self.assertIn((32, 25), [call.args[1:] for call in click.call_args_list])


if __name__ == "__main__":
    unittest.main()
