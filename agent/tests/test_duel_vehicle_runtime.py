from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_lineup_slot import (BUTTON_CENTER_BASE, EXPANDED_WIDTH,
                                        PANEL_RIGHT_BASE, SLOT_PITCH,
                                        observe_lineup_slot)
from ma9_agent.duel_vehicle_runtime import (_detail, _finish_target,
                                            _lineup_identity, _try_target,
                                            assign_visible, scan)
from ma9_agent.vehicle_screen import match_vehicle

_UNSET = object()

#: Colours of a synthetic 1280x720 Duel lineup page that the real read-only
#: observer accepts: a dark background, the bright expanded panel and its
#: bright-green selection button.
_LINEUP_BACKGROUND = (60, 25, 45)
_LINEUP_PANEL = (200, 90, 140)
_LINEUP_BUTTON = (20, 240, 180)


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


def _lineup_frame(slot: int = 1, *, select_button: bool = False) -> np.ndarray:
    """A lineup page whose expanded ``slot`` passes the real observer.

    Geometry comes from the committed observer constants, so the frame only
    moves horizontally with the slot exactly as the five real cells do.
    """
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[:, :] = _LINEUP_BACKGROUND
    right = PANEL_RIGHT_BASE + SLOT_PITCH * (slot - 1)
    frame[210:545, right - EXPANDED_WIDTH:right + 1] = _LINEUP_PANEL
    left = int(round(BUTTON_CENTER_BASE + SLOT_PITCH * (slot - 1) - 96))
    frame[495:545, left:left + 192] = _LINEUP_BUTTON
    if select_button:
        frame[625:690, 1045:1235] = _LINEUP_BUTTON
    return frame


def _panel_right(slot: int = 1) -> int:
    return PANEL_RIGHT_BASE + SLOT_PITCH * (slot - 1)


def _page_rows(slot: int = 1, *, brand: str = "RIMAC", model: str = "NEVERA",
               track: int = 0) -> list[tuple[str, list[int], float]]:
    """Text of a recorded lineup frame, moved onto ``slot``.

    Coordinates mirror the production OCR boxes of the 05L evidence frames:
    the two-line identity block right-anchored inside the panel, the expanded
    track name left of it, the performance score + class letter row below it
    and the neighbouring collapsed cell right of the panel.  ``track`` replaces
    the identity block with the "no car selected" placeholder.
    """
    shift = SLOT_PITCH * (slot - 1)
    right = _panel_right(slot) - 78
    if track:
        return [("旷野飙车", [198 + shift, 216, 116, 34], .998),
                ("4,837S", [572 + shift, 259, 142, 47], .825),
                ("花都疾驰", [_panel_right(slot) + 26, 219, 63, 24], .999),
                ("回", [2, 346, 28, 24], .791)]
    return [
        ("旷野飙车", [198 + shift, 216, 116, 34], .998),
        (brand, [right - 11 * len(brand), 214, 11 * len(brand), 26], .99),
        (model, [right - 11 * len(model), 238, 11 * len(model), 22], .99),
        ("4,837S", [572 + shift, 259, 142, 47], .825),
        ("更换车辆", [566, 491, 58, 15], .999),
        ("花都疾驰", [_panel_right(slot) + 26, 219, 63, 24], .999),
        ("回", [2, 346, 28, 24], .791),
    ]


def _clip(box: list[int], roi: tuple[int, int, int, int]) -> list[int] | None:
    left, top = max(box[0], roi[0]), max(box[1], roi[1])
    right = min(box[0] + box[2], roi[0] + roi[2])
    bottom = min(box[1] + box[3], roi[1] + roi[3])
    if right <= left or bottom <= top:
        return None
    return [left, top, right - left, bottom - top]


def _frame_ocr(rows: list[tuple[str, list[int], float]]):
    """Model the production OCR engine: it only reports text inside the ROI."""
    def ocr(_context, _frame_value, roi):
        return [{"text": text, "confidence": confidence, "box": clipped}
                for text, box, confidence in rows
                if (clipped := _clip(box, roi)) is not None]
    return ocr


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
    def _lineup_catalog():
        """Decoys that reproduce the real Nevera / Nevera R margin the live run hit."""
        return [
            {"id": "nevera", "title": "Rimac Nevera", "class": "S"},
            {"id": "nevera_r", "title": "Rimac Nevera R", "class": "R"},
            {"id": "jesko", "title": "Koenigsegg Jesko Absolut", "class": "R"},
            {"id": "glickenhaus", "title": "Glickenhaus 004C", "class": "D"},
            {"id": "praga", "title": "Praga R1", "class": "D"},
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
        frame = _lineup_frame(1, select_button=True)
        page = _frame_ocr(_page_rows(1, brand="MITSUBISHI",
                                     model="LANCER EVOLUTION"))

        def ocr(context, frame_value, roi):
            if roi == (160, 76, 300, 110):
                return [{"text": "MITSUBISHI", "confidence": .99, "box": [160, 76, 170, 25]},
                        {"text": "LANCER EVOLUTION", "confidence": .99, "box": [160, 104, 220, 25]}]
            if roi == (900, 90, 210, 90):
                return [{"text": "37/4,897", "confidence": .99, "box": [900, 126, 130, 30]}]
            return page(context, frame_value, roi)

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
        self.assertEqual(report["lineup_identity"]["vehicle"]["id"], "lancer")
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

    # ------------------------------ post-selection lineup identity (MA9-05L)
    @staticmethod
    def _read_identity(frame, rows, catalog):
        """Run the production identity read behind its own OCR mock."""
        with patch("ma9_agent.duel_vehicle_runtime._ocr", _frame_ocr(rows)):
            return _lineup_identity(_Context(), frame, catalog)

    def test_identity_region_reads_every_slot_and_rejects_the_page_wide_band(self) -> None:
        """The recorded page still fails the old band and passes the new region."""
        catalog = self._lineup_catalog()
        for slot in range(1, 6):
            with self.subTest(slot=slot):
                frame = _lineup_frame(slot)
                panel = observe_lineup_slot(frame)["evidence"]["panel"]
                page = _frame_ocr(_page_rows(slot))
                wide = page(context := _Context(), frame, (0, 170, 1280, 190))
                self.assertIn("4,837S", [row["text"] for row in wide])
                self.assertIsNone(match_vehicle(wide, catalog))
                with patch("ma9_agent.duel_vehicle_runtime._ocr", page):
                    result = _lineup_identity(context, frame, catalog)
                self.assertEqual(result["panel"], panel)
                self.assertEqual(result["region"],
                                 [panel["right"] - 340, 200, 340, 58])
                self.assertEqual(result["vehicle"]["id"], "nevera")
                self.assertEqual([row["text"] for row in
                                  page(context, frame, tuple(result["region"]))],
                                 ["RIMAC", "NEVERA"])

    def test_identity_region_never_covers_score_track_or_neighbour_text(self) -> None:
        for slot in range(1, 6):
            with self.subTest(slot=slot):
                frame = _lineup_frame(slot)
                region = tuple(self._read_identity(
                    frame, _page_rows(slot), self._lineup_catalog())["region"])
                shift = SLOT_PITCH * (slot - 1)
                outside = {
                    "score_and_class": [572 + shift, 259, 142, 47],
                    "track_name": [198 + shift, 216, 116, 34],
                    "neighbour_cell": [_panel_right(slot) + 26, 219, 63, 24],
                    "left_rail": [2, 346, 28, 24],
                }
                for name, box in outside.items():
                    with self.subTest(text=name):
                        self.assertIsNone(_clip(box, region))

    def test_identity_region_keeps_digit_and_single_letter_suffix_names(self) -> None:
        """No text filter: a digit name and a lone ``R`` suffix stay intact."""
        catalog = self._lineup_catalog()
        for brand, model, expected in (("RIMAC", "NEVERA", "nevera"),
                                       ("RIMAC", "NEVERA R", "nevera_r"),
                                       ("GLICKENHAUS", "004C", "glickenhaus"),
                                       ("PRAGA", "R1", "praga")):
            with self.subTest(model=model):
                result = self._read_identity(
                    _lineup_frame(1), _page_rows(1, brand=brand, model=model), catalog)
                self.assertEqual(result["vehicle"]["id"], expected)

    def test_identity_region_leaves_an_unreadable_cell_unassigned(self) -> None:
        """The "no car selected" panel names no vehicle even though the read works."""
        frame = _lineup_frame(4)
        result = self._read_identity(frame, _page_rows(4, track=1),
                                     self._lineup_catalog())
        self.assertEqual(result["panel"]["right"], _panel_right(4))
        self.assertIsNone(result["vehicle"])

    def test_identity_read_never_passes_an_expected_slot(self) -> None:
        frame = _lineup_frame(3)
        with patch("ma9_agent.duel_vehicle_runtime.observe_lineup_slot",
                   return_value=observe_lineup_slot(frame)) as observe, \
                patch("ma9_agent.duel_vehicle_runtime._ocr",
                      _frame_ocr(_page_rows(3))):
            result = _lineup_identity(_Context(), frame, self._lineup_catalog())
        self.assertEqual(result["vehicle"]["id"], "nevera")
        self.assertEqual(observe.call_count, 1)
        self.assertEqual(len(observe.call_args.args), 1)
        self.assertIs(observe.call_args.args[0], frame)
        self.assertEqual(observe.call_args.kwargs, {})

    def _return_page_run(self, *, model="LANCER EVOLUTION", brand="MITSUBISHI",
                         catalog=None, extra_frame=None):
        """Drive ``_finish_target`` onto a lineup return page and report the run."""
        card = _card("lancer")
        card["performance"] = [4837, 4897]
        frame = extra_frame if extra_frame is not None else _lineup_frame(1, select_button=True)
        page = _frame_ocr(_page_rows(1, brand=brand, model=model))

        def ocr(context, frame_value, roi):
            if roi == (160, 76, 300, 110):
                return [{"text": "MITSUBISHI", "confidence": .99, "box": [160, 76, 170, 25]},
                        {"text": "LANCER EVOLUTION", "confidence": .99, "box": [160, 104, 220, 25]}]
            if roi == (900, 90, 210, 90):
                return [{"text": "37/4,897", "confidence": .99, "box": [900, 126, 130, 30]}]
            return page(context, frame_value, roi)

        context = _DetailContext([True] * 40)
        with patch("ma9_agent.duel_vehicle_runtime._frame", return_value=frame), \
                patch("ma9_agent.duel_vehicle_runtime._ocr", ocr), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True) as click, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = _finish_target(
                context, card, 1, [card], "lancer",
                catalog or self._detail_catalog() + self._lineup_catalog(),
                choose=True, expected_performance=None, expected_stars=None,
                verify_list_detail_rating=False)
        return report, [call.args[1:] for call in click.call_args_list]

    def test_return_page_naming_another_vehicle_stays_unverified(self) -> None:
        report, clicks = self._return_page_run(brand="RIMAC", model="NEVERA R")
        self.assertEqual(report["status"], "assignment_unverified")
        self.assertFalse(report["assignment_complete"])
        self.assertFalse(report["scan_complete"])
        self.assertEqual(report["lineup_identity"]["vehicle"]["id"], "nevera_r")
        self.assertEqual(clicks, [tuple(_card("lancer")["target"]), (1139, 658)])

    def test_ambiguous_return_page_stays_unverified(self) -> None:
        frame = _lineup_frame(1, select_button=True)
        second = int(round(BUTTON_CENTER_BASE - 96)) + 300
        frame[495:545, second:second + 192] = _LINEUP_BUTTON
        report, clicks = self._return_page_run(extra_frame=frame)
        self.assertEqual(report["status"], "assignment_unverified")
        self.assertFalse(report["assignment_complete"])
        self.assertEqual(report["lineup_identity"],
                         {"panel": None, "region": None, "vehicle": None})
        self.assertEqual(clicks, [tuple(_card("lancer")["target"]), (1139, 658)])

    def test_scan_assigns_only_after_the_identity_read_confirms_the_target(self) -> None:
        card = _card("lancer")
        card["performance"] = [4837, 4897]
        catalog = self._detail_catalog() + self._lineup_catalog()
        frame = _lineup_frame(1, select_button=True)
        page = _frame_ocr(_page_rows(1, brand="MITSUBISHI", model="LANCER EVOLUTION"))

        def ocr(context, frame_value, roi):
            if roi == (160, 76, 300, 110):
                return [{"text": "MITSUBISHI", "confidence": .99, "box": [160, 76, 170, 25]},
                        {"text": "LANCER EVOLUTION", "confidence": .99, "box": [160, 104, 220, 25]}]
            if roi == (900, 90, 210, 90):
                return [{"text": "37/4,897", "confidence": .99, "box": [900, 126, 130, 30]}]
            return page(context, frame_value, roi)

        context = _DetailContext([True] * 40)
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      return_value=(frame, [card], True)), \
                patch("ma9_agent.duel_vehicle_runtime._frame", return_value=frame), \
                patch("ma9_agent.duel_vehicle_runtime._ocr", ocr), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "D", catalog, target_id="lancer", choose=True,
                          verify_list_detail_rating=False)
        self.assertEqual(report["status"], "assigned")
        self.assertTrue(report["assignment_complete"])
        self.assertEqual(report["lineup_identity"]["vehicle"]["id"], "lancer")


if __name__ == "__main__":
    unittest.main()
