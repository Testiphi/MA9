from __future__ import annotations

import inspect
import hashlib
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_lineup_slot import (BUTTON_CENTER_BASE, EXPANDED_WIDTH,
                                        PANEL_RIGHT_BASE, SLOT_PITCH,
                                        observe_lineup_slot)
from ma9_agent.duel_vehicle_runtime import (CLASS_X, EDGE_REPOSITION_LIMIT,
                                            EDGE_REPOSITION_SWIPE,
                                            TARGET_GEOMETRY_TOLERANCE, _detail,
                                            _finish_target, _lineup_identity,
                                            _same_target_card, _sample_visible,
                                            _stable_sample_visible, _try_target,
                                            assign_visible, scan)
from ma9_agent.vehicle_screen import match_vehicle
from ma9_agent.duel_vehicle_screen import read_visible_cards

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
            (self.frame, [_card("a"), _card("b")], True, []),
            (self.frame, [_card("a"), _card("b")], True, []),
            (self.frame, [_card("c"), _card("d")], True, []),
            (self.frame, [_card("c"), _card("d")], True, []),
            (self.frame, [_card("c"), _card("d")], True, []),
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
            (self.frame, [_card("r1", "R"), _card("s1", "S")], True, []),
            (self.frame, [_card("s1", "S"), _card("s2", "S")], True, []),
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
                      return_value=(self.frame, [card], True, [])), \
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
                      return_value=(self.frame, [card], True, [])), \
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
        unstable = (self.frame, [_card("untrusted")], False, [])
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
        unstable = (self.frame, [_card("untrusted")], False, [])
        settled = (self.frame, [_card("trusted")], True, [])
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
        """A single target sighting may not be overwritten by a settled page.

        MA9-05N2: the first sampling window names ``target`` but cannot confirm
        it, and the second window settles on the same page without it.  Reading
        that as a settled page the target is simply not on would authorise the
        next page swipe and lose the car whose rolling name the OCR happened to
        drop, so the page is reported unverified instead: nothing is opened and
        no page swipe is made.
        """
        context = _Context()
        target = _card("target")
        stable_other = (self.frame, [_card("other")], True, [])
        catalog = [{"id": "target", "title": "target", "class": "D"},
                   {"id": "other", "title": "other", "class": "D"}]
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      side_effect=[(self.frame, [target], False, []), stable_other,
                                   stable_other, stable_other]), \
                patch("ma9_agent.duel_vehicle_runtime._try_target") as try_target, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "D", catalog, target_id="target", choose=True, max_pages=4)
        self.assertEqual(report["status"], "page_ocr_unverified")
        self.assertFalse(report["scan_complete"])
        self.assertEqual(report["vehicles"], [])
        self.assertEqual(report["target_id"], "target")
        self.assertEqual(report["unstable_samples"], 2)
        self.assertEqual(context.tasker.controller.swipes, 0)
        try_target.assert_not_called()

    def test_assign_visible_refuses_a_continuously_unstable_target(self) -> None:
        context = _Context()
        target = _card("target")
        catalog = [{"id": "target", "title": "target", "class": "D"}]
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.frame), \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      side_effect=[(self.frame, [target], False, [])] * 2), \
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
                      side_effect=[(self.frame, [target], False, [])] * 2), \
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
        unstable_lower = (self.frame, [lower], False, [])
        catalog = [{"id": "trusted", "title": "trusted", "class": "R"},
                   {"id": "lower", "title": "lower", "class": "S"}]
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._sample_visible",
                      side_effect=[(self.frame, [trusted], True, []),
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
                      side_effect=[([card], []) for card in cards]), \
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
                      return_value=(self.frame, [card], True, [])), \
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
                      return_value=(frame, [card], True, [])), \
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
                      return_value=(frame, [card], True, [])), \
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
                      return_value=(frame, [card], True, [])), \
                patch("ma9_agent.duel_vehicle_runtime._frame", return_value=frame), \
                patch("ma9_agent.duel_vehicle_runtime._ocr", ocr), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "D", catalog, target_id="lancer", choose=True,
                          verify_list_detail_rating=False)
        self.assertEqual(report["status"], "assigned")
        self.assertTrue(report["assignment_complete"])
        self.assertEqual(report["lineup_identity"]["vehicle"]["id"], "lancer")


#: Catalog of the right-edge/detail scenes below.  Formula E Gen 2 keeps the
#: family honest: it shares the ``FORMULA E`` brand line with the Gen 3 car and
#: must never be resolved by the Gen 3 fragments.
_ROLLING_CATALOG = [
    {"id": "fe3", "title": "Formula E Gen 3 EVO Championship Edition", "class": "A"},
    {"id": "fe2", "title": "Formula E Gen 2 Asphalt Edition", "class": "B"},
    {"id": "mclaren650", "title": "McLaren 650S GT3", "class": "A"},
]
#: The clipped right-edge card of the recorded 11:55:52.818 page: the car is at
#: left 1069 (x 1069+420 > 1295), so only its name fragments are readable.  The
#: scene is a splice of recorded OCR rows, not a continuous live capture.
_CLIPPED_EDGE_ROWS = [
    {"text": "FORMU", "confidence": .993, "box": [1077, 332, 72, 22]},
    {"text": "J CHAMPIONSHIP EDIT", "confidence": .947, "box": [1073, 350, 201, 22]},
]
_PAGE_TITLE_ROWS = [
    {"text": "车辆选择", "confidence": .999, "box": [40, 72, 120, 30]},
]
_VISIBLE_PAGE_ROWS = [
    {"text": "MCLAREN", "confidence": .936, "box": [256, 329, 101, 26]},
    {"text": "650S GT3", "confidence": .966, "box": [256, 350, 94, 22]},
]
#: The two recorded detail frames of the same car, alternating as the scrolling
#: detail title does (see the 20260925-fe3-full-intake native OCR).
_DETAIL_FRAME_A = [
    {"text": "FORMULA E", "confidence": .935, "box": [173, 110, 124, 19]},
    {"text": "N", "confidence": .994, "box": [172, 133, 25, 26]},
    {"text": "GEN 3 EV0 CI", "confidence": .940, "box": [246, 135, 160, 24]},
    {"text": "a", "confidence": .254, "box": [176, 166, 31, 17]},
    {"text": "最高", "confidence": 1.0, "box": [261, 166, 41, 19]},
]
_DETAIL_FRAME_B = [
    {"text": "FORMULA E", "confidence": .926, "box": [172, 110, 125, 19]},
    {"text": "3 EVO CHAMPIONSH", "confidence": .936, "box": [170, 132, 236, 28]},
    {"text": "", "confidence": 0.0, "box": [177, 167, 25, 14]},
    {"text": "最高", "confidence": .999, "box": [260, 163, 42, 22]},
]
#: A *synthesised* detail pair, not a recorded capture: it applies the same
#: evidenced marquee shapes (a truncated brand line plus one model fragment) to
#: the detail layout, so that neither frame resolves through the exact matcher
#: and only the accumulated reading can decide.
_DETAIL_TRUNCATED_A = [
    {"text": "FORMU", "confidence": .935, "box": [173, 110, 124, 19]},
    {"text": "GEN 3 EV0 CI", "confidence": .940, "box": [246, 135, 160, 24]},
    {"text": "最高", "confidence": 1.0, "box": [261, 166, 41, 19]},
]
_DETAIL_TRUNCATED_B = [
    {"text": "FORMU", "confidence": .926, "box": [172, 110, 125, 19]},
    {"text": "3 EVO CHAMPIONSH", "confidence": .936, "box": [170, 132, 236, 28]},
    {"text": "最高", "confidence": .999, "box": [260, 163, 42, 22]},
]


class _RollingScene:
    """Device model whose list page carries one clipped right-edge card.

    ``sticky`` simulates a list that does not move at all; otherwise the small
    re-position request itself moves the recorded rows, exactly as the real
    swipe would.  A card detail is entered by clicking it, and each read of a
    detail page advances to the next marquee phase.  The frame pixels are a
    placeholder: only the text of this scene is measured.
    """

    def __init__(self, *, sticky: bool = False, detail_frames=None) -> None:
        self.sticky = sticky
        self.detail_frames = detail_frames or [_DETAIL_FRAME_A, _DETAIL_FRAME_B]
        self.pixels = DuelVehicleRuntimeTest._active_button_frame()
        self.active = self.detail_frames[0]
        self.shift = 0
        self.page = "list"
        self.detail_index = 0
        self.swipes: list[tuple[int, ...]] = []
        self.clicks: list[tuple[int, int]] = []
        self.controller = self

    def post_swipe(self, x1, y1, x2, y2, duration):
        self.swipes.append((x1, y1, x2, y2, duration))
        if not self.sticky:
            self.shift += x1 - x2
        return _Job()

    def frame(self):
        """The next screen: a new marquee phase while a detail is open."""
        if self.page == "detail":
            self.active = self.detail_frames[self.detail_index % len(self.detail_frames)]
            self.detail_index += 1
        return self.pixels

    def rows(self) -> list[dict]:
        if self.page == "detail":
            return self.active
        # The title bar is fixed chrome; only the card list moves.
        return [*_PAGE_TITLE_ROWS,
                *[{**row, "box": [row["box"][0] - self.shift, *row["box"][1:]]}
                  for row in [*_VISIBLE_PAGE_ROWS, *_CLIPPED_EDGE_ROWS]]]

    def open_detail(self) -> None:
        self.page = "detail"
        self.detail_index = 0


class DuelEdgeCoverageTest(unittest.TestCase):
    """The bounded right-edge observation and the bounded detail read."""

    @staticmethod
    def _context(scene: _RollingScene):
        context = _DetailContext([True] * 40)
        context.tasker = SimpleNamespace(controller=scene)
        return context

    @staticmethod
    def _ocr(scene: _RollingScene):
        def ocr(_context, _frame_value, roi):
            return [{**row, "box": clipped} for row in scene.rows()
                    if (clipped := _clip(row["box"], roi)) is not None]
        return ocr

    def _scan(self, scene: _RollingScene, *, choose=False, **kwargs):
        context = self._context(scene)

        def click(_context, x, y):
            scene.clicks.append((x, y))
            if (x, y) != (940, 103):  # the A-class tab is not a detail entry
                scene.open_detail()
            return True

        with patch("ma9_agent.duel_vehicle_runtime._ocr", self._ocr(scene)), \
                patch("ma9_agent.duel_vehicle_runtime._frame",
                      lambda _context: scene.frame()), \
                patch("ma9_agent.duel_vehicle_runtime._click", click), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            return scan(context, "A", _ROLLING_CATALOG, target_id="fe3",
                        choose=choose, max_pages=3, **kwargs)

    def test_clipped_edge_card_is_observed_whole_before_the_scan_moves_on(self) -> None:
        """The recorded right-edge page must not be swiped past.

        The old scan skipped the clipped card and its next fling lost the car.
        The new scan spends one bounded, small re-position (the recorded 300 px
        page shift), reads the card whole at left 769, and only then clicks it.
        """
        scene = _RollingScene()
        report = self._scan(scene)
        self.assertEqual(scene.swipes, [(1010, 470, 710, 470, 650)])
        self.assertEqual(report["edge_repositions"], 1)
        self.assertEqual(report["status"], "detail_verified")
        # The recorded detail pair needs its second frame before the car is
        # named, exactly as the dedicated detail test records.
        self.assertEqual(report["detail_name_frames"], 2)
        self.assertEqual(report["detail_identity_basis"], "title")
        self.assertIn("fe3", [row["vehicle"]["id"] for row in report["vehicles"]])
        clicked = [call for call in scene.clicks if call != (940, 103)]
        self.assertEqual(clicked, [(769 + 185, 168 + 105)])
        # The clicked geometry is fully inside the complete-card bound.
        self.assertLessEqual(769 + 420, 1295)
        self.assertFalse(report["assignment_complete"])

    def test_clipped_edge_budget_reports_incomplete_instead_of_a_missing_target(self) -> None:
        """A list that never moves may not be reported as a complete traversal."""
        scene = _RollingScene(sticky=True)
        report = self._scan(scene)
        self.assertEqual(report["status"], "edge_candidate_unresolved")
        self.assertFalse(report["scan_complete"])
        self.assertEqual(report["edge_repositions"], EDGE_REPOSITION_LIMIT)
        self.assertEqual(report["edge_candidate"]["vehicle"]["id"], "fe3")
        self.assertEqual(scene.swipes, [EDGE_REPOSITION_SWIPE] * EDGE_REPOSITION_LIMIT)
        self.assertEqual(scene.clicks, [(940, 103)])

    def test_clipped_only_target_is_never_clicked_by_assign_visible(self) -> None:
        """The locate-only path keeps refusing a target it cannot see whole."""
        scene = _RollingScene()
        context = self._context(scene)
        with patch("ma9_agent.duel_vehicle_runtime._ocr", self._ocr(scene)), \
                patch("ma9_agent.duel_vehicle_runtime._frame",
                      lambda _context: scene.frame()), \
                patch("ma9_agent.duel_vehicle_runtime._click",
                      lambda _context, x, y: scene.clicks.append((x, y)) or True), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = assign_visible(context, "fe3", _ROLLING_CATALOG)
        self.assertEqual(report["status"], "target_not_visible")
        self.assertEqual(report["clipped_target"]["vehicle"]["id"], "fe3")
        self.assertEqual(scene.clicks, [])
        self.assertEqual(scene.swipes, [])

    def _detail_run(self, frames, expected="fe3", titles=()):
        scene = _RollingScene(detail_frames=frames)
        scene.open_detail()
        context = self._context(scene)
        titles = list(titles)
        index = [0]

        def ocr(_context, _frame_value, roi):
            if roi == (40, 60, 220, 60):
                return ([{"text": titles[index[0]], "confidence": .99,
                          "box": [40, 72, 120, 30]}] if index[0] < len(titles) else [])
            return [{**row, "box": clipped} for row in scene.rows()
                    if (clipped := _clip(row["box"], roi)) is not None]

        with patch("ma9_agent.duel_vehicle_runtime._ocr", ocr), \
                patch("ma9_agent.duel_vehicle_runtime._frame",
                      lambda _context: scene.frame()), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            return _detail(context, expected, _ROLLING_CATALOG)

    def test_detail_identity_accumulates_two_bounded_frames_of_one_page(self) -> None:
        """One detail frame may stay undecidable; two of them must decide.

        The recorded pair is used as read: frame A alone names nothing, and the
        second frame's exact reading (confidence .786) is what verifies the car,
        which is why the frame count is reported next to the basis.
        """
        single = self._detail_run([_DETAIL_FRAME_A])
        self.assertEqual(single["status"], "detail_not_verified")
        sequence = self._detail_run([_DETAIL_FRAME_A, _DETAIL_FRAME_B])
        self.assertEqual(sequence["status"], "detail_verified")
        self.assertEqual(sequence["detail_name_frames"], 2)
        self.assertEqual(sequence["detail_identity_basis"], "title")
        self.assertEqual(sequence["detail_vehicle"]["confidence"], .786)
        self.assertEqual(sequence["detail_vehicle"]["id"], "fe3")

    def test_detail_rolling_name_decides_only_with_two_frames(self) -> None:
        """Synthesised marquee pair: only the accumulated reading may decide.

        Neither frame resolves through the exact matcher, one frame is never
        enough, and the unique catalog resolution still has to name the expected
        car before anything is treated as verified.
        """
        single = self._detail_run([_DETAIL_TRUNCATED_A])
        self.assertEqual(single["status"], "detail_not_verified")
        sequence = self._detail_run([_DETAIL_TRUNCATED_A, _DETAIL_TRUNCATED_B])
        self.assertEqual(sequence["status"], "detail_verified")
        self.assertEqual(sequence["detail_name_frames"], 2)
        self.assertEqual(sequence["detail_identity_basis"], "rolling_fragment")
        self.assertEqual(sequence["detail_vehicle"]["id"], "fe3")

    def test_detail_rolling_name_of_another_vehicle_keeps_the_retry(self) -> None:
        """A uniquely read other car is a wrong page, not an unclear one."""
        report = self._detail_run([_DETAIL_TRUNCATED_A, _DETAIL_TRUNCATED_B],
                                  expected="mclaren650")
        self.assertEqual(report["status"], "wrong_detail")
        self.assertEqual(report["detail_vehicle"]["id"], "fe3")

    def test_detail_identity_is_cleared_when_the_page_changes(self) -> None:
        """Fragments of another page may never complete this identity."""
        report = self._detail_run([_DETAIL_TRUNCATED_A, _DETAIL_TRUNCATED_B],
                                  titles=["车辆选择"] * 8)
        self.assertEqual(report["status"], "detail_not_verified")


class DuelScanCounterexampleFixTest(unittest.TestCase):
    """The three scan-ordering counterexamples of the 05N1 repair round.

    Real call premise: each case drives the production ``scan`` end to end and
    only stubs the IO/sampling/detail dependencies (``_stable_sample_visible``,
    ``_click``, ``_detail`` and ``time.sleep``), exactly as the recorded 05N
    repro did.  The sampled pages are synthetic boundary scenes -- not device
    evidence -- and the swipe/edit budgets are the production ones.
    """

    FRAME = np.zeros((720, 1280, 3), dtype=np.uint8)

    @staticmethod
    def _catalog() -> list[dict]:
        return [{"id": "wanted", "title": "wanted", "class": "A"},
                {"id": "other", "title": "other", "class": "A"},
                {"id": "lower", "title": "lower", "class": "B"}]

    @staticmethod
    def _row(vehicle_id: str, vehicle_class: str = "A", *, left: int = 100) -> dict:
        row = _card(vehicle_id, vehicle_class)
        row["card"] = [left, 168, 420, 212]
        row["target"] = [left + 185, 273]
        row["performance"] = [1000, 1000]
        return row

    def _run(self, target_id, pages):
        """Drive ``scan`` on the A tab with one page limit over ``pages``."""
        clicks: list[tuple[int, int]] = []
        swipes: list[tuple[int, ...]] = []

        class _Ctrl:
            def post_swipe(self, *args):
                swipes.append(args)
                return _Job()

        context = _Context()
        context.tasker = SimpleNamespace(controller=_Ctrl())
        detail = {"status": "detail_verified",
                  "detail_vehicle": {"id": "wanted", "title": "wanted",
                                     "confidence": 1.0},
                  "performance": 1000, "stars_lit": 6, "star_slots": 6,
                  "occupied_elsewhere": False, "select_available": True}
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.FRAME), \
                patch("ma9_agent.duel_vehicle_runtime._stable_sample_visible",
                      side_effect=pages), \
                patch("ma9_agent.duel_vehicle_runtime._click",
                      side_effect=lambda _context, x, y: clicks.append((x, y)) or True), \
                patch("ma9_agent.duel_vehicle_runtime._detail",
                      return_value=detail), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "A", self._catalog(), target_id=target_id,
                          choose=False, max_pages=1)
        return report, clicks, swipes

    def test_visible_target_is_served_before_an_unrelated_edge_card(self) -> None:
        """F1: a fully visible target may not be slid away for the edge card.

        The first sampled page shows ``wanted`` whole while the right edge clips
        a different car (``other``).  The page/class guards and the current
        complete-target path must run first, so the target's own detail is opened
        with no re-position at all; an unrelated edge card never displaces it.
        """
        wanted = self._row("wanted")
        other = self._row("other")
        clipped = self._row("other", left=1069)
        clipped["clipped"] = True
        report, clicks, swipes = self._run(
            "wanted", [(self.FRAME, [wanted], True, [clipped]),
                       (self.FRAME, [other], True, [])])
        self.assertEqual(report["status"], "detail_verified")
        self.assertEqual(report["edge_repositions"], 0)
        self.assertEqual(swipes, [])
        self.assertIn(tuple(wanted["target"]), clicks)

    def test_complete_cards_are_booked_before_the_edge_reposition(self) -> None:
        """F2: the first page's cars survive the bounded re-position.

        With no target, the first sampled page shows ``wanted`` whole and clips
        ``other``; the one re-position then reveals ``other`` whole.  A complete
        observation is booked when it is seen, so both cars stay in the
        inventory instead of the first one being lost to the re-position.
        """
        wanted = self._row("wanted")
        other = self._row("other")
        clipped = self._row("other", left=1069)
        clipped["clipped"] = True
        report, _clicks, _swipes = self._run(
            None, [(self.FRAME, [wanted], True, [clipped]),
                   (self.FRAME, [other], True, [])])
        self.assertEqual({row["vehicle"]["id"] for row in report["vehicles"]},
                         {"wanted", "other"})

    def test_unresolved_edge_candidate_never_fakes_a_complete_scan(self) -> None:
        """F3: an owed candidate is a debt a later frame may not erase.

        ``wanted`` is the clipped target on page one; the single bounded
        re-position lands on a lower-class page without it and without a new
        clipped candidate.  Dropping the debt there would report
        ``target_not_found`` with ``scan_complete`` true; the owed car must keep
        the traversal explicitly incomplete instead.
        """
        other = self._row("other")
        pending = self._row("wanted", left=1069)
        pending["clipped"] = True
        report, _clicks, swipes = self._run(
            "wanted", [(self.FRAME, [other], True, [pending]),
                       (self.FRAME, [self._row("lower", "B")], True, [])])
        self.assertIs(report["scan_complete"], False)
        self.assertNotEqual(report["status"], "target_not_found")
        self.assertEqual(report["status"], "edge_candidate_unresolved")
        self.assertEqual(report["edge_candidate"]["vehicle"]["id"], "wanted")
        self.assertEqual(len(swipes), 1)


class DuelTargetStabilityTest(unittest.TestCase):
    """MA9-05N2: the target's own two independent reads confirm it.

    Every case drives the real ``_sample_visible``/``_stable_sample_visible`` (or
    the real ``scan`` chain) and stubs only the IO boundary -- ``_frame``,
    ``_selection_title``, ``_visible``, ``_click``, ``_try_target`` and
    ``time.sleep``.  The card lists are synthetic scenes (not device evidence);
    the geometry bound and the two-window capture budget are the production ones.
    """

    FRAME = np.zeros((720, 1280, 3), dtype=np.uint8)

    @staticmethod
    def _catalog() -> list[dict]:
        return [{"id": value, "title": value, "class": "D"}
                for value in ("wanted", "other", "spare", "lower")]

    @staticmethod
    def _moved(vehicle_id: str, *, left: int = 100, top: int = 168,
               vehicle_class: str = "D") -> dict:
        row = _card(vehicle_id, vehicle_class)
        row["card"] = [left, top, 420, 212]
        row["target"] = [left + 185, top + 105]
        return row

    def _sampling(self, pages, target_id, *, attempts: int = 4):
        """Run the real two-window sampler over synthetic ``(cards, clipped)``."""
        with patch("ma9_agent.duel_vehicle_runtime._frame",
                   return_value=self.FRAME), \
                patch("ma9_agent.duel_vehicle_runtime._selection_title",
                      return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._visible",
                      side_effect=list(pages)) as visible, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            result = _stable_sample_visible(_Context(), self._catalog(),
                                            attempts=attempts, target_id=target_id)
        return result, visible

    def _scan(self, pages, target_id, *, max_pages: int = 4):
        """Drive the real ``scan`` over synthetic pages, stubbing only IO/entry."""
        context = _Context()
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.FRAME), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._frame",
                      return_value=self.FRAME), \
                patch("ma9_agent.duel_vehicle_runtime._selection_title",
                      return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._visible",
                      side_effect=list(pages)) as visible, \
                patch("ma9_agent.duel_vehicle_runtime._try_target",
                      return_value={"status": "detail_verified"}) as try_target, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "D", self._catalog(), target_id=target_id,
                          choose=False, max_pages=max_pages)
        return report, context, visible, try_target

    def test_two_consecutive_target_reads_confirm_on_the_newest_frame(self) -> None:
        """The recorded case: a neighbour's rolling name changed, the target did not.

        The fingerprints of the two reads differ (``spare`` dropped out), which
        is exactly why the old whole-page rule could not confirm the car the OCR
        had identified twice.  The target's own pair is enough, and the returned
        geometry is the second frame's.
        """
        pages = [([self._moved("wanted", left=100), self._moved("other"),
                   self._moved("spare")], []),
                 ([self._moved("wanted", left=102), self._moved("other")], [])]
        (_frame, cards, stable, _clipped), visible = self._sampling(pages, "wanted")
        self.assertTrue(stable)
        self.assertEqual([row["vehicle"]["id"] for row in cards], ["wanted", "other"])
        newest = next(row for row in cards if row["vehicle"]["id"] == "wanted")
        self.assertEqual(newest["target"], [287, 273])
        self.assertEqual(visible.call_count, 2)

    def test_target_seen_in_alternate_frames_never_accumulates(self) -> None:
        """Non-consecutive sightings are not a run: four alternations decide nothing."""
        pages = [([self._moved("wanted")], []), ([self._moved("other")], [])] * 4
        (_frame, _cards, stable, _clipped), visible = self._sampling(pages, "wanted")
        self.assertFalse(stable)
        self.assertEqual(visible.call_count, 8)

    def test_target_geometry_jump_between_rows_or_columns_is_not_confirmed(self) -> None:
        """A repeated id is not enough: the card box and target must stay put."""
        for name, second in (("next_row", self._moved("wanted", top=395)),
                             ("column_shift", self._moved("wanted", left=500))):
            with self.subTest(name=name):
                # A one-card page never settles early, so both windows read the
                # full ``attempts`` budget: four alternating pages twice.
                pages = [([self._moved("wanted")], []), ([second], []),
                         ([self._moved("wanted")], []), ([second], [])] * 2
                (_frame, _cards, stable, _clipped), visible = self._sampling(
                    pages, "wanted")
                self.assertFalse(stable)
                self.assertEqual(visible.call_count, 8)

    def test_two_cards_of_the_same_target_id_never_confirm_the_target(self) -> None:
        """An ambiguous page may not steady itself into a click either."""
        twin = self._moved("wanted", left=600)
        pages = [([self._moved("wanted"), twin, self._moved("other"),
                   self._moved("spare")], [])] * 8
        report, context, visible, try_target = self._scan(pages, "wanted")
        self.assertEqual(report["status"], "page_ocr_unverified")
        self.assertFalse(report["scan_complete"])
        self.assertEqual(context.tasker.controller.swipes, 0)
        try_target.assert_not_called()
        self.assertEqual(visible.call_count, 8)

    def test_single_target_read_lost_afterwards_stops_without_swiping(self) -> None:
        """One sighting then a settled page without it: unconfirmed, no big swipe."""
        pages = [([self._moved("wanted")], [])] + [([self._moved("other")], [])] * 7
        report, context, visible, try_target = self._scan(pages, "wanted")
        self.assertEqual(report["status"], "page_ocr_unverified")
        self.assertFalse(report["scan_complete"])
        self.assertEqual(report["vehicles"], [])
        self.assertEqual(report["target_id"], "wanted")
        self.assertEqual(report["unstable_samples"], 2)
        self.assertEqual(context.tasker.controller.swipes, 0)
        try_target.assert_not_called()
        # The two windows share one bounded budget: attempts * 2 captures.
        self.assertEqual(visible.call_count, 8)

    def test_target_only_as_a_clipped_row_is_not_target_evidence(self) -> None:
        """The right edge's card has no click target and cannot confirm the car."""
        clipped = self._moved("wanted", left=1069)
        clipped["clipped"] = True
        pages = [([self._moved("other")], [clipped])] * 8
        (_frame, cards, stable, _clipped_rows), _visible = self._sampling(
            pages, "wanted")
        self.assertTrue(stable)
        self.assertEqual([row["vehicle"]["id"] for row in cards], ["other"])

    def test_no_target_geometry_state_is_borrowed_across_calls(self) -> None:
        """A fresh call starts its run from nothing, not from the previous page."""
        pages = ([([self._moved("other")], []), ([self._moved("wanted")], [])] * 2)
        with patch("ma9_agent.duel_vehicle_runtime._frame",
                   return_value=self.FRAME), \
                patch("ma9_agent.duel_vehicle_runtime._selection_title",
                      return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._visible",
                      side_effect=pages), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            first = _sample_visible(_Context(), self._catalog(),
                                    attempts=2, target_id="wanted")
            second = _sample_visible(_Context(), self._catalog(),
                                     attempts=2, target_id="wanted")
        self.assertFalse(first[2])
        self.assertFalse(second[2])

    def test_real_scan_confirms_before_opening_and_uses_the_newest_target(self) -> None:
        """The scan chain opens the car only after its own second read agrees."""
        pages = [([self._moved("wanted", left=100), self._moved("other"),
                   self._moved("spare")], []),
                 ([self._moved("wanted", left=102), self._moved("other")], [])]
        report, _context, visible, try_target = self._scan(pages, "wanted")
        self.assertEqual(visible.call_count, 2)
        try_target.assert_called_once()
        opened = try_target.call_args.args[1]
        self.assertEqual(opened["vehicle"]["id"], "wanted")
        self.assertEqual(opened["target"], [287, 273])
        self.assertEqual(report["status"], "detail_verified")

    def test_target_geometry_tolerance_admits_the_recorded_jitter_only(self) -> None:
        """The bound is the recorded 2 px jitter plus margin, not a real move.

        A 2 px shift is the measured FE3 jitter, 227 px is the next card row and
        >= 320 px is the neighbouring column, so the bound has to sit between
        them; the class and the row are checked independently of the margin.
        """
        first = self._moved("wanted")
        for delta, expected in ((0, True), (2, True),
                                (TARGET_GEOMETRY_TOLERANCE, True),
                                (TARGET_GEOMETRY_TOLERANCE + 1, False),
                                (227, False), (400, False)):
            with self.subTest(delta=delta):
                self.assertIs(
                    _same_target_card(first, self._moved("wanted", left=100 + delta)),
                    expected)
        self.assertIs(_same_target_card(first, self._moved("wanted", top=395)), False)
        self.assertIs(_same_target_card(first, self._moved("wanted",
                                                           vehicle_class="C")), False)

    # --------------------- MA9-05N2A: seen-target history and window boundary
    @staticmethod
    def _three_neighbours() -> list[dict]:
        return [DuelTargetStabilityTest._moved("other", left=0, top=395),
                DuelTargetStabilityTest._moved("spare", left=430, top=168),
                DuelTargetStabilityTest._moved("lower", left=430, top=395)]

    def test_seen_target_history_blocks_the_early_whole_page_return(self) -> None:
        """A whole-page repeat may not erase a target the first window saw.

        The orchestrator counterexample: capture 1 names ``wanted`` beside three
        neighbours, captures 2..N show the *same* set of 4/5/6 other cards.  The
        old early exit only looked at the current frame's ``target_claimed`` and
        returned a stable page without the target, so the scan swiped past a car
        it had read.  The seeing history now keeps the window unverified.
        """
        for count in (4, 5, 6):
            with self.subTest(neighbours=count):
                rest = [self._moved(f"n{index}") for index in range(count)]
                first = [self._moved("wanted"), *rest[:3]]
                pages = [(first, [])] + [(rest, [])] * 7
                (_frame, _cards, stable, _clipped), visible = self._sampling(
                    pages, "wanted")
                self.assertFalse(stable)
                self.assertEqual(visible.call_count, 6)

    def test_ambiguous_target_history_blocks_the_early_whole_page_return(self) -> None:
        """Two cards of the target id are a sighting too: no page may erase it."""
        rest = [self._moved(f"n{index}") for index in range(4)]
        first = [self._moved("wanted"), self._moved("wanted", left=600),
                 self._moved("other")]
        pages = [(first, [])] + [(rest, [])] * 7
        (_frame, _cards, stable, _clipped), visible = self._sampling(pages, "wanted")
        self.assertFalse(stable)
        self.assertEqual(visible.call_count, 6)

    def test_second_window_history_also_blocks_the_early_whole_page_return(self) -> None:
        """The same 4/5/6-card rule holds inside the second window.

        The first window never names the target, so the outer ``seen`` flag stays
        false; only the second window's own seeing history can block its early
        exit.  Without that gate the window would settle on a target-free page.
        """
        for count in (4, 5, 6):
            with self.subTest(neighbours=count):
                rest = [self._moved(f"n{index}") for index in range(count)]
                distinct = [self._moved(f"d{index}") for index in range(4)]
                pages = ([([row], []) for row in distinct]
                         + [([self._moved("wanted"), *rest], [])]
                         + [(rest, [])] * 3)
                (_frame, _cards, stable, _clipped), visible = self._sampling(
                    pages, "wanted")
                self.assertFalse(stable)
                self.assertEqual(visible.call_count, 8)

    def test_target_pair_split_by_the_window_boundary_confirms_on_the_newest(self) -> None:
        """A real run is not cut by the artificial window split.

        The recorded orchestrator scene: the first window's last capture (global
        4) names the target at left 0, the second window's first capture (global
        5) names it at left 2.  The two are one continuous run 2 px apart, so the
        second capture confirms immediately and its newest coordinates are used.
        """
        other = self._three_neighbours()
        first = self._moved("wanted", left=0, top=168)
        second = self._moved("wanted", left=2, top=168)
        pages = ([(other, [])] * 3
                 + [([first, *other], []), ([second, *other], [])]
                 + [(other, [])] * 3)
        (_frame, cards, stable, _clipped), visible = self._sampling(pages, "wanted")
        self.assertTrue(stable)
        self.assertEqual(visible.call_count, 5)
        newest = next(row for row in cards if row["vehicle"]["id"] == "wanted")
        self.assertEqual(newest["target"], [187, 273])

    def test_a_sighting_after_a_gap_is_not_a_consecutive_pair(self) -> None:
        """Capture 1 and capture 5 are not a pair: the window in between lost it.

        The first window's last capture does not name the target, so it hands the
        second window nothing to pair against; the lone capture 5 sighting stays
        a single reading and never confirms.
        """
        pages = [([self._moved("wanted")], []),
                 ([self._moved("other")], []),
                 ([self._moved("spare")], []),
                 ([self._moved("lower")], []),
                 ([self._moved("wanted")], [])] + [([self._moved("other")], [])] * 3
        (_frame, _cards, stable, _clipped), visible = self._sampling(pages, "wanted")
        self.assertFalse(stable)
        self.assertEqual(visible.call_count, 8)

    def test_boundary_pair_must_still_match_geometry_class_and_uniqueness(self) -> None:
        """Straddling the boundary relaxes nothing about the target's own read."""
        other = self._three_neighbours()
        first = self._moved("wanted", left=0, top=168)
        cases = {
            "obvious_move": [self._moved("wanted", left=100, top=168)],
            "next_row": [self._moved("wanted", left=0, top=395)],
            "other_class": [self._moved("wanted", left=2, top=168, vehicle_class="C")],
            "ambiguous": [self._moved("wanted", left=2, top=168),
                          self._moved("wanted", left=600, top=168)],
        }
        for name, tail in cases.items():
            with self.subTest(name=name):
                pages = ([(other, [])] * 3
                         + [([first, *other], []), ([*tail, *other], [])]
                         + [(other, [])] * 3)
                (_frame, _cards, stable, _clipped), visible = self._sampling(
                    pages, "wanted")
                self.assertFalse(stable)
                self.assertEqual(visible.call_count, 8)

    def test_window_carry_never_survives_the_sampling_call(self) -> None:
        """The continuity cell is local: a new call cannot borrow the old one.

        The first call confirms a pair and leaves the target as its last reading.
        The second call starts with the *same* target geometry but a moved-away
        second capture.  Borrowed state would confirm on the second call's first
        frame; a fresh call must not.
        """
        other = self._three_neighbours()
        same = self._moved("wanted", left=2, top=168)
        moved = self._moved("wanted", left=100, top=168)
        first_call = ([(other, [])] * 3
                      + [([self._moved("wanted", left=0, top=168), *other], [])]
                      + [([same, *other], [])])
        second_call = ([([same, *other], []), ([moved, *other], []),
                        ([same, *other], []), ([moved, *other], [])]
                       + [([self._moved(value)], [])
                          for value in ("other", "spare", "lower", "n4")])
        with patch("ma9_agent.duel_vehicle_runtime._frame",
                   return_value=self.FRAME), \
                patch("ma9_agent.duel_vehicle_runtime._selection_title",
                      return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._visible",
                      side_effect=first_call + second_call), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            first = _stable_sample_visible(_Context(), self._catalog(), target_id="wanted")
            second = _stable_sample_visible(_Context(), self._catalog(), target_id="wanted")
        self.assertTrue(first[2])
        self.assertFalse(second[2])

    def test_unverified_scan_never_clicks_a_card_or_swipes(self) -> None:
        """Entry clicks and target clicks stay separate facts on an unverified page.

        The class tab click is the only entry action; a page that read the target
        without confirming it must not open a card (no ``_click`` at a card
        target) and must not authorise the large page swipe.
        """
        neighbours = [self._moved(f"n{index}") for index in range(4)]
        pages = ([([self._moved("wanted"), *neighbours[:3]], [])]
                 + [(neighbours, [])] * 7)
        context = _Context()
        clicks: list[tuple[int, int]] = []
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=self.FRAME), \
                patch("ma9_agent.duel_vehicle_runtime._click",
                      side_effect=lambda _context, x, y: clicks.append((x, y)) or True), \
                patch("ma9_agent.duel_vehicle_runtime._frame",
                      return_value=self.FRAME), \
                patch("ma9_agent.duel_vehicle_runtime._selection_title",
                      return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._visible",
                      side_effect=list(pages)), \
                patch("ma9_agent.duel_vehicle_runtime._try_target") as try_target, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(context, "D", self._catalog(), target_id="wanted",
                          choose=True, max_pages=4)
        self.assertEqual(report["status"], "page_ocr_unverified")
        self.assertFalse(report["scan_complete"])
        self.assertEqual(clicks, [(CLASS_X["D"], 103)])
        self.assertEqual(context.tasker.controller.swipes, 0)
        try_target.assert_not_called()

    def test_scan_opens_the_newest_card_of_a_boundary_pair(self) -> None:
        """The confirmed boundary pair is handed to the real ``_try_target``."""
        other = self._three_neighbours()
        pages = ([(other, [])] * 3
                 + [([self._moved("wanted", left=0, top=168), *other], []),
                    ([self._moved("wanted", left=2, top=168), *other], [])]
                 + [(other, [])] * 3)
        report, context, visible, try_target = self._scan(pages, "wanted")
        self.assertEqual(visible.call_count, 5)
        self.assertEqual(context.tasker.controller.swipes, 0)
        try_target.assert_called_once()
        opened = try_target.call_args.args[1]
        self.assertEqual(opened["vehicle"]["id"], "wanted")
        self.assertEqual(opened["target"], [187, 273])
        self.assertEqual(report["status"], "detail_verified")


class FrozenFordBoundaryTest(unittest.TestCase):
    """Replay captured pixels and OCR; replace only capture and timing IO."""

    @staticmethod
    def _inventory_card(vehicle_id, left, top=168):
        card = _card(vehicle_id, "B")
        card["card"] = [left, top, 420, 212]
        card["target"] = [left + 185, top + 105]
        return card

    def test_moving_full_frame_is_receipted_then_two_card_epoch_confirms(self):
        moved = [self._inventory_card("sto", 454),
                 self._inventory_card("ford", 454, 395),
                 self._inventory_card("porsche", 900),
                 self._inventory_card("brabham", 900, 395)]
        sto = self._inventory_card("sto", 374)
        ford = self._inventory_card("ford", 374, 395)
        pages = [([*moved], []), ([sto, ford], []), ([sto], []),
                 ([sto], []), ([sto], []), ([sto, ford], [])]
        frames = [np.full((720, 1280, 3), index, dtype=np.uint8)
                  for index in range(len(pages))]
        context = _Context()
        context.current_frame = 129
        remaining = iter(frames)
        def capture(_context):
            context.current_frame += 1
            return next(remaining)
        notes = []
        with patch("ma9_agent.duel_vehicle_runtime._frame", side_effect=capture), \
                patch("ma9_agent.duel_vehicle_runtime._selection_title",
                      return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._visible",
                      side_effect=pages) as visible, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            frame, cards, stable, _clipped = _stable_sample_visible(
                context, [], target_id=None, sampling_notes=notes)
        self.assertTrue(stable)
        self.assertEqual(visible.call_count, 6)
        self.assertIs(frame, frames[5])
        self.assertEqual({card["vehicle"]["id"] for card in cards}, {"sto", "ford"})
        self.assertTrue({"porsche", "brabham"}.issubset(
            {note["id"] for note in notes}))
        self.assertTrue(all(note["capture"] == 130 for note in notes))

    def test_epoch_resets_on_missing_anchor_empty_duplicate_and_slot_conflict(self):
        first = [self._inventory_card("anchor", 100),
                 self._inventory_card("other", 500)]
        cases = [
            ("no_anchor", [self._inventory_card("fresh", 900)], "page_epoch_changed"),
            ("empty", [], "empty_page"),
            ("duplicate", [first[0], first[0]], "duplicate_identity"),
            ("slot_conflict", [first[0], self._inventory_card("fresh", 500)],
             "page_epoch_changed"),
        ]
        for name, second, reason in cases:
            with self.subTest(name=name):
                state = {"baseline": {}, "previous": {}, "seen": {},
                         "counts": {}, "max_size": 0, "notes": [], "captures": 0}
                with patch("ma9_agent.duel_vehicle_runtime._frame",
                           return_value=np.zeros((720, 1280, 3), dtype=np.uint8)), \
                        patch("ma9_agent.duel_vehicle_runtime._selection_title",
                              return_value=True), \
                        patch("ma9_agent.duel_vehicle_runtime._visible",
                              side_effect=[(first, []), (second, [])]), \
                        patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
                    _frame_value, _cards, stable, _clipped = _sample_visible(
                        _Context(), [], attempts=2, inventory_state=state)
                self.assertFalse(stable)
                self.assertIn(reason, {note["reason"] for note in state["notes"]})

    def test_duplicate_frame_receipts_survive_later_clean_confirmation(self):
        duplicate = [self._inventory_card("ambiguous", 100),
                     self._inventory_card("ambiguous", 500)]
        clean = [self._inventory_card("sto", 100),
                 self._inventory_card("ford", 500)]
        pages = [(duplicate, []), (clean, []), (clean, []), (clean, [])]
        frames = [np.full((720, 1280, 3), index, dtype=np.uint8)
                  for index in range(4)]
        context = _Context()
        context.current_frame = 20
        remaining = iter(frames)
        def capture(_context):
            context.current_frame += 1
            return next(remaining)
        notes = []
        with patch("ma9_agent.duel_vehicle_runtime._frame", side_effect=capture), \
                patch("ma9_agent.duel_vehicle_runtime._selection_title",
                      return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._visible",
                      side_effect=pages) as visible, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            frame, cards, stable, _clipped = _stable_sample_visible(
                context, [], sampling_notes=notes)
        self.assertTrue(stable)
        self.assertEqual(visible.call_count, 4)
        self.assertIs(frame, frames[3])
        self.assertEqual({card["vehicle"]["id"] for card in cards},
                         {"sto", "ford"})
        duplicates = [note for note in notes
                      if note["reason"] == "duplicate_identity"]
        self.assertEqual(len(duplicates), 2)
        self.assertEqual({note["capture"] for note in duplicates}, {21})
        self.assertEqual({tuple(note["card"]) for note in duplicates},
                         {(100, 168, 420, 212), (500, 168, 420, 212)})
        self.assertTrue(all(note["id"] == "ambiguous" for note in duplicates))

    def test_epoch_checks_first_geometry_and_lost_title(self):
        frames = [self._inventory_card("anchor", left)
                  for left in (100, 108, 116)]
        state = {"baseline": {}, "previous": {}, "seen": {},
                 "counts": {}, "max_size": 0, "notes": [], "captures": 0}
        with patch("ma9_agent.duel_vehicle_runtime._frame",
                   return_value=np.zeros((720, 1280, 3), dtype=np.uint8)), \
                patch("ma9_agent.duel_vehicle_runtime._selection_title",
                      return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._visible",
                      side_effect=[([card], []) for card in frames]), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            _sample_visible(_Context(), [], attempts=3, inventory_state=state)
        self.assertIn("page_epoch_changed",
                      {note["reason"] for note in state["notes"]})
        with patch("ma9_agent.duel_vehicle_runtime._frame",
                   return_value=np.zeros((720, 1280, 3), dtype=np.uint8)), \
                patch("ma9_agent.duel_vehicle_runtime._selection_title",
                      side_effect=[True, False]), \
                patch("ma9_agent.duel_vehicle_runtime._visible",
                      return_value=([frames[0]], [])), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            _frame_value, _cards, stable, _clipped = _sample_visible(
                _Context(), [], attempts=2, inventory_state=state)
        self.assertFalse(stable)
        self.assertIn("selection_lost", {note["reason"] for note in state["notes"]})

    def test_inventory_keeps_a_full_singleton_until_next_window_confirms(self):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        three = [_card(value, "B") for value in ("one", "two", "three")]
        for card, left in zip(three, (100, 430, 760)):
            card["card"] = [left, 168, 420, 212]
            card["target"] = [left + 185, 273]
        newest = _card("new", "B")
        newest["card"] = [100, 395, 420, 212]
        newest["target"] = [285, 500]
        four = [*three, newest]
        pages = [(three, []), (three, []), (four, []), (three, []),
                 (four, []), (four, [])]
        catalog = [{"id": value, "title": value, "class": "B"}
                   for value in ("one", "two", "three", "new")]
        state = {"baseline": {}, "previous": {}, "seen": {}, "counts": {},
                 "max_size": 0, "notes": [], "captures": 0}
        with patch("ma9_agent.duel_vehicle_runtime._frame", return_value=frame), \
                patch("ma9_agent.duel_vehicle_runtime._selection_title",
                      return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._visible",
                      side_effect=pages[:4]), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            _frame_value, cards, stable, _clipped = _sample_visible(
                _Context(), catalog, target_id=None, inventory_state=state)
        self.assertFalse(stable)
        self.assertIn("new", state["seen"])
        with patch("ma9_agent.duel_vehicle_runtime._frame", return_value=frame), \
                patch("ma9_agent.duel_vehicle_runtime._selection_title",
                      return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._visible",
                      side_effect=pages) as visible, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            _frame_value, cards, stable, _clipped = _stable_sample_visible(
                _Context(), catalog, target_id=None)
        self.assertTrue(stable)
        self.assertEqual(visible.call_count, 5)
        self.assertIn("new", [card["vehicle"]["id"] for card in cards])

    def test_real_fd_identity_still_stops_a_b_inventory_scan(self):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        catalog = [{"id": "car_e8df360ad07558bd",
                    "title": "Ford Mustang RTR Spec 5-FD", "class": "S"}]
        words = [{"text": "FORD", "confidence": .99, "box": [396, 558, 62, 24]},
                 {"text": "MUSTANG RTR SPEC 5-FD", "confidence": .99,
                  "box": [400, 578, 190, 22]}]
        cards = read_visible_cards(frame, words, catalog)
        self.assertEqual(cards[0]["vehicle"]["id"], catalog[0]["id"])
        with patch("ma9_agent.duel_vehicle_runtime._wait_selection_frame",
                   return_value=frame), \
                patch("ma9_agent.duel_vehicle_runtime._click", return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._stable_sample_visible",
                      return_value=(frame, cards, True, [])), \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report = scan(_Context(), "B", catalog, max_pages=1)
        self.assertEqual(report["status"], "class_or_ocr_unverified")
        self.assertEqual(report["unexpected_classes"], ["S"])

    def test_b_boundary_130_through_137(self):
        root = (Path(__file__).resolve().parents[2] / "build" /
                "user-test-garage-3dab97f" / "MA9-preview" / "debug" /
                "duel-garage-688af9416505470d953e43931a25ac92")
        if not (root / "frames.jsonl").exists():
            self.skipTest("user's frozen frame archive is unavailable")
        catalog = json.loads((Path(__file__).resolve().parents[2] / "data" /
                              "generated" / "vehicle_catalog.json").read_text(
                                  encoding="utf8"))["vehicles"]
        metadata = [json.loads(line) for line in (root / "frames.jsonl").read_text(
            encoding="utf8").splitlines() if 130 <= json.loads(line)["frame"] <= 137]
        ocr = {row["frame"]: row["words"] for line in (root / "ocr.jsonl").read_text(
            encoding="utf8").splitlines() if (row := json.loads(line))["frame"] in
            range(130, 138) and row["roi"] == [0, 120, 1280, 500]}
        observed = []
        for row in metadata:
            content = (root / row["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), row["sha256"])
            frame = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
            cards = read_visible_cards(frame, ocr[row["frame"]], catalog)
            observed.append((frame, cards, []))
        anniversary = "car_034bc4bec211f3f7"
        fd = "car_e8df360ad07558bd"
        self.assertEqual([anniversary in [card["vehicle"]["id"] for card in cards]
                          for _, cards, _ in observed],
                         [False, False, True, False, False, False, True, True])
        self.assertTrue(all(fd not in [card["vehicle"]["id"] for card in cards]
                            for _, cards, _ in observed))
        with patch("ma9_agent.duel_vehicle_runtime._frame",
                   side_effect=[frame for frame, _, _ in observed]), \
                patch("ma9_agent.duel_vehicle_runtime._selection_title",
                      return_value=True), \
                patch("ma9_agent.duel_vehicle_runtime._visible",
                      side_effect=[(cards, clipped) for _, cards, clipped in observed]) as visible, \
                patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            frame, cards, stable, _clipped = _stable_sample_visible(
                _Context(), catalog, target_id=None)
        self.assertEqual(visible.call_count, 7)
        self.assertTrue(stable)
        self.assertIn(anniversary, [card["vehicle"]["id"] for card in cards])
        self.assertIs(frame, observed[6][0])


if __name__ == "__main__":
    unittest.main()
