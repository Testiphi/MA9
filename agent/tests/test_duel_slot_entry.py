"""Offline tests for the bounded Duel defence slot entry callback.

Every test drives the production callback through a fake context, in-memory
synthetic frames and stubbed OCR/frame sources: no device, no ADB, no game and
no account data.  ``observe_lineup_slot`` and ``observe_stable_lineup_slot`` are
**never** stubbed - the synthetic lineup frames are really interpreted by the
production observers, only the frame source (``frame_of``) and the OCR rows
(``ocr_roi``) are replaced.  The 05F selection adapter is reused unchanged, with
only its ``scan`` dependency stubbed.

The calibrated frame recipe is imported (read only) from the 05F test module so
the synthetic geometry stays in one place; that module's ``main`` is guarded and
is not executed by importing it.
"""

from __future__ import annotations

import ast
import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ma9_agent import duel_lineup_slot, duel_slot_entry, duel_slot_selection
from ma9_agent import selection_runtime
from ma9_agent.duel_lineup_slot import (BUTTON_CENTER_BASE, EXPANDED_WIDTH,
                                        LINEUP_TITLE_ROI, PANEL_RIGHT_BASE,
                                        SELECTION_PAGE_TITLE, SLOT_PITCH,
                                        SUPPORTED_SIZE, observe_lineup_slot)
from ma9_agent.duel_slot_entry import (ARRIVAL_CONSECUTIVE, ARRIVAL_INTERVAL,
                                       ARRIVAL_SAMPLES, ENTRY_BUTTON_TEXTS,
                                       SELECTION_PAGE_TITLE_ROI,
                                       TEXT_CONFIDENCE_FLOOR,
                                       enter_defense_slot_selection)
from ma9_agent.duel_slot_selection import (DEFENSE_PAGE_TITLE, MAX_SAMPLES,
                                           STATUS_ENTRY_FAILED, STATUS_LOCATED,
                                           UNSUPPORTED_PAGE_TITLE,
                                           SlotSelectionRequest,
                                           select_vehicle_for_slot)
from test_duel_slot_selection import (BLANK, BUTTON_COLOR, BUTTON_HEIGHT,
                                      BUTTON_WIDTH, CATALOG, OWNED, PANEL_COLOR,
                                      SLOT_FRAMES, blank_frame, detail_report,
                                      request, title_row)

MODULE_PATH = Path(__file__).resolve().parents[1] / "ma9_agent/duel_slot_entry.py"

UNSET = object()


# --------------------------------------------------------------------- fixtures
def observed(slot: int) -> dict:
    """Real observer verdict for the synthetic slot frame; must be verified."""
    report = observe_lineup_slot(SLOT_FRAMES[slot], ocr=[title_row(DEFENSE_PAGE_TITLE)])
    assert report["slot_verified"] is True and report["title_guard_passed"] is True
    return report


REPORTS = {slot: observed(slot) for slot in range(1, 6)}
#: Detected button box per slot, taken from the real observer output - never
#: hardcoded, so the click point is the geometry the production code sees.
BUTTON_BOX = {slot: tuple(int(value) for value in REPORTS[slot]["evidence"]["button"]["box"])
              for slot in range(1, 6)}


def click_point(slot: int) -> tuple[int, int]:
    left, top, width, height = BUTTON_BOX[slot]
    return int(round(left + width / 2.0)), int(round(top + height / 2.0))


def evidence_for(slot: int) -> dict:
    """The exact 05F slot-evidence shape, built from the real observer report."""
    report = REPORTS[slot]
    return {
        "expanded_slot": report["expanded_slot"],
        "page_title": report["page_title"],
        "verification_basis": report["verification_basis"],
        "title_guard_passed": report["title_guard_passed"],
        "panel": dict(report["evidence"]["panel"]),
        "button": dict(report["evidence"]["button"]),
        "consecutive": 2,
        "samples": 2,
    }


def arrival_row(text: str = SELECTION_PAGE_TITLE, confidence: float = 0.98,
                box: tuple[int, int, int, int] = (50, 70, 180, 40)) -> dict:
    return {"text": text, "confidence": confidence, "box": list(box)}


def off_grid_button_frame(slot: int = 1, shift: int = 60) -> np.ndarray:
    """Panel of ``slot`` with its selection button pushed off the slot grid."""
    frame = blank_frame()
    right = PANEL_RIGHT_BASE + SLOT_PITCH * (slot - 1)
    frame[210:545, right - EXPANDED_WIDTH:right + 1] = PANEL_COLOR
    center = BUTTON_CENTER_BASE + SLOT_PITCH * (slot - 1) + shift
    left = int(round(center - BUTTON_WIDTH / 2))
    frame[495:495 + BUTTON_HEIGHT, left:left + BUTTON_WIDTH] = BUTTON_COLOR
    return frame


def with_fields(evidence: dict, **overrides) -> dict:
    result = copy.deepcopy(evidence)
    result.update(overrides)
    return result


def without(evidence: dict, *keys: str) -> dict:
    result = copy.deepcopy(evidence)
    for key in keys:
        result.pop(key, None)
    return result


def with_panel(evidence: dict, **changes) -> dict:
    result = copy.deepcopy(evidence)
    panel = result["panel"]
    for key, value in changes.items():
        if value is UNSET:
            panel.pop(key, None)
        else:
            panel[key] = value
    return result


def with_button(evidence: dict, **changes) -> dict:
    result = copy.deepcopy(evidence)
    button = result["button"]
    for key, value in changes.items():
        if value is UNSET:
            button.pop(key, None)
        else:
            button[key] = value
    return result


# ------------------------------------------------------------- fake API shapes
class _Job:
    """Stand-in for ``maa.job.Job``: ``wait()`` returns self, ``succeeded`` bool."""

    def __init__(self, succeeded: bool) -> None:
        self._succeeded = succeeded

    def wait(self) -> "_Job":
        return self

    @property
    def succeeded(self) -> bool:
        return self._succeeded


class _Controller:
    """Fake ``controller``: real ``post_click(x, y, contact, pressure)`` shape."""

    def __init__(self, order: list, *, succeeded: bool = True,
                 error: Exception | None = None) -> None:
        self.order = order
        self.succeeded = succeeded
        self.error = error
        self.posts: list[tuple[int, int]] = []

    def post_click(self, x: int, y: int, contact: int = 0, pressure: int = 1) -> _Job:
        self.order.append("post_click")
        self.posts.append((x, y))
        if self.error is not None:
            raise self.error
        return _Job(self.succeeded)


class _Context:
    def __init__(self, controller: _Controller) -> None:
        self.tasker = _Tasker(controller)


class _Tasker:
    def __init__(self, controller: _Controller) -> None:
        self.controller = controller


class _Harness:
    """Ordered synthetic frame source plus ROI-aware OCR rows; records the order."""

    def __init__(self, order: list, frames: list, *, slot: int = 1,
                 button_roi: tuple | None = None, button_rows: list | None = None,
                 arrival_rows: list | None = None, title_rows: list | None = None) -> None:
        self.order = order
        self.frames = list(frames)
        self.frame_calls = 0
        self.ocr_rois: list[tuple] = []
        self.button_roi = tuple(BUTTON_BOX[slot] if button_roi is None else button_roi)
        self.title_rows = ([title_row(DEFENSE_PAGE_TITLE)] if title_rows is None
                           else list(title_rows))
        if button_rows is None:
            left, top, width, height = self.button_roi
            self.button_rows = [{"text": ENTRY_BUTTON_TEXTS[0], "confidence": 0.98,
                                 "box": [left + 40, top + 10, width - 80, height - 20]}]
        else:
            self.button_rows = list(button_rows)
        self.arrival_rows = arrival_rows
        self.arrival_calls = 0

    def frame_of(self, _context) -> np.ndarray:
        index = self.frame_calls
        self.frame_calls += 1
        self.order.append("frame")
        return self.frames[index] if index < len(self.frames) else self.frames[-1]

    def ocr_roi(self, _context, _frame, roi) -> list[dict]:
        self.order.append("ocr")
        key = tuple(roi)
        self.ocr_rois.append(key)
        if key == tuple(LINEUP_TITLE_ROI):
            return [dict(row) for row in self.title_rows]
        if key == tuple(SELECTION_PAGE_TITLE_ROI):
            return self._next_arrival_rows()
        if key == self.button_roi:
            return [dict(row) for row in self.button_rows]
        return []

    def _next_arrival_rows(self) -> list[dict]:
        index = self.arrival_calls
        self.arrival_calls += 1
        if self.arrival_rows is None:
            return [arrival_row()]
        rows = self.arrival_rows[index] if index < len(self.arrival_rows) else self.arrival_rows[-1]
        return [dict(row) for row in rows]


# ----------------------------------------------------------------------- tests
class SlotEntryCallbackTest(unittest.TestCase):
    def _flow(self, *, slot: int = 1, evidence: object = UNSET, frames: list | None = None,
              controller: _Controller | None = None, button_roi: tuple | None = None,
              button_rows: list | None = None, arrival_rows: list | None = None,
              title_rows: list | None = None):
        order: list = []
        if controller is None:
            controller = _Controller(order)
        harness = _Harness(order, frames if frames is not None else [SLOT_FRAMES[slot]] * 8,
                           slot=slot, button_roi=button_roi, button_rows=button_rows,
                           arrival_rows=arrival_rows, title_rows=title_rows)
        evidence = evidence_for(slot) if evidence is UNSET else evidence
        sleeps: list = []
        # ``observe_stable_lineup_slot`` lives in 05F and resolves ``frame_of``/
        # ``ocr_roi`` from its own module namespace, so the one fake device has to
        # be installed on both modules - exactly as one real device serves both.
        with mock.patch.object(duel_slot_entry, "frame_of", harness.frame_of), \
                mock.patch.object(duel_slot_entry, "ocr_roi", harness.ocr_roi), \
                mock.patch.object(duel_slot_selection, "frame_of", harness.frame_of), \
                mock.patch.object(duel_slot_selection, "ocr_roi", harness.ocr_roi), \
                mock.patch.object(duel_slot_entry.time, "sleep", sleeps.append):
            result = enter_defense_slot_selection(_Context(controller), evidence)
        return result, harness, controller, order, sleeps

    # ------------------------------------------------------------- happy paths
    def test_every_slot_enters_with_one_click_at_the_observed_button_center(self) -> None:
        for slot in range(1, 6):
            with self.subTest(slot=slot):
                result, harness, controller, order, _sleeps = self._flow(slot=slot)
                self.assertIs(result, True)
                self.assertEqual(controller.posts, [click_point(slot)])
                self.assertEqual(order, ["frame", "ocr", "frame", "ocr", "frame", "ocr",
                                         "ocr", "post_click", "frame", "ocr",
                                         "frame", "ocr"])
                self.assertEqual(harness.frame_calls, 5)
                self.assertEqual(harness.ocr_rois,
                                 [LINEUP_TITLE_ROI, LINEUP_TITLE_ROI, LINEUP_TITLE_ROI,
                                  BUTTON_BOX[slot], SELECTION_PAGE_TITLE_ROI,
                                  SELECTION_PAGE_TITLE_ROI])

    def test_both_unselected_and_selected_button_labels_are_accepted(self) -> None:
        for label in ENTRY_BUTTON_TEXTS:
            with self.subTest(label=label):
                left, top, width, height = BUTTON_BOX[1]
                rows = [{"text": f"  {label} ", "confidence": 0.94,
                         "box": [left + 30, top + 8, width - 60, height - 16]}]
                result, _harness, controller, _order, _sleeps = self._flow(button_rows=rows)
                self.assertIs(result, True)
                self.assertEqual(controller.posts, [click_point(1)])

    def test_a_repeated_same_label_is_not_a_conflict(self) -> None:
        left, top, width, height = BUTTON_BOX[2]
        rows = [{"text": "选择车辆", "confidence": 0.95,
                 "box": [left + 20, top + 6, width - 40, height - 12]},
                {"text": "选择车辆", "confidence": 0.99,
                 "box": [left + 40, top + 12, width - 80, height - 24]}]
        result, _harness, controller, _order, _sleeps = self._flow(slot=2, button_rows=rows)
        self.assertIs(result, True)
        self.assertEqual(len(controller.posts), 1)

    def test_supplied_evidence_is_not_mutated_in_depth(self) -> None:
        evidence = evidence_for(3)
        snapshot = copy.deepcopy(evidence)
        nested = {key: id(value) for key, value in evidence.items()}
        result, _harness, _controller, _order, _sleeps = self._flow(
            slot=3, evidence=evidence)
        self.assertIs(result, True)
        self.assertEqual(evidence, snapshot)
        self.assertEqual({key: id(value) for key, value in evidence.items()}, nested)

    def test_the_declared_budgets_and_seams_are_the_contracted_ones(self) -> None:
        self.assertEqual(ARRIVAL_SAMPLES, 6)
        self.assertEqual(ARRIVAL_INTERVAL, 0.2)
        self.assertEqual(ARRIVAL_CONSECUTIVE, 2)
        self.assertEqual(TEXT_CONFIDENCE_FLOOR, 0.90)
        self.assertEqual(SELECTION_PAGE_TITLE_ROI, (40, 60, 220, 60))
        self.assertEqual(tuple(ENTRY_BUTTON_TEXTS), ("选择车辆", "更换车辆"))
        self.assertEqual(SUPPORTED_SIZE, (1280, 720))
        self.assertEqual(LINEUP_TITLE_ROI, (62, 86, 110, 52))
        self.assertEqual(duel_slot_entry.DEFENSE_PAGE_TITLE, DEFENSE_PAGE_TITLE)
        self.assertEqual(duel_slot_entry.SELECTION_PAGE_TITLE, SELECTION_PAGE_TITLE)
        self.assertIs(duel_slot_entry.observe_lineup_slot, duel_lineup_slot.observe_lineup_slot)
        self.assertIs(duel_slot_entry.observe_stable_lineup_slot,
                      duel_slot_selection.observe_stable_lineup_slot)
        self.assertIs(duel_slot_entry.frame_of, selection_runtime.frame_of)
        self.assertIs(duel_slot_entry.ocr_roi, selection_runtime.ocr_roi)

    # ------------------------------------------------- malformed evidence gate
    def test_malformed_evidence_is_refused_before_any_capture(self) -> None:
        good = evidence_for(1)
        cases = {
            "not_a_dict": None,
            "is_a_list": [],
            "is_a_string": "slot 1",
            "slot_missing": without(good, "expanded_slot"),
            "slot_zero": with_fields(good, expanded_slot=0),
            "slot_six": with_fields(good, expanded_slot=6),
            "slot_float": with_fields(good, expanded_slot=1.0),
            "slot_bool": with_fields(good, expanded_slot=True),
            "slot_string": with_fields(good, expanded_slot="1"),
            "title_missing": without(good, "page_title"),
            "title_attack": with_fields(good, page_title=UNSUPPORTED_PAGE_TITLE),
            "title_garage": with_fields(good, page_title=SELECTION_PAGE_TITLE),
            "title_blank": with_fields(good, page_title=""),
            "title_not_str": with_fields(good, page_title=7),
            "basis_missing": without(good, "verification_basis"),
            "basis_geometry_only": with_fields(good, verification_basis="geometry_only"),
            "basis_rejected": with_fields(good, verification_basis="rejected"),
            "guard_missing": without(good, "title_guard_passed"),
            "guard_false": with_fields(good, title_guard_passed=False),
            "guard_int": with_fields(good, title_guard_passed=1),
            "guard_string": with_fields(good, title_guard_passed="true"),
            "panel_missing": without(good, "panel"),
            "panel_not_dict": with_fields(good, panel=[60, 791]),
            "panel_left_missing": with_panel(good, left=UNSET),
            "panel_inverted": with_panel(good, left=800),
            "panel_beyond_frame": with_panel(good, right=1300, left=1300 - EXPANDED_WIDTH),
            "panel_negative": with_panel(good, left=-5),
            "panel_wrong_width": with_panel(good, right=791 + 5),
            "panel_nan": with_panel(good, left=float("nan")),
            "panel_inf": with_panel(good, right=float("inf"), left=0),
            "panel_string": with_panel(good, left="60"),
            "panel_bool": with_panel(good, left=True),
            "button_missing": without(good, "button"),
            "button_not_dict": with_fields(good, button=[]),
            "box_missing": with_button(good, box=UNSET),
            "box_short": with_button(good, box=[512, 495, 192]),
            "box_zero_width": with_button(good, box=[512, 495, 0, 50]),
            "box_negative_height": with_button(good, box=[512, 495, 192, -50]),
            "box_off_frame": with_button(good, box=[1200, 495, 192, 50]),
            "box_nan": with_button(good, box=[float("nan"), 495, 192, 50]),
            "box_string": with_button(good, box=["512", 495, 192, 50]),
        }
        for label, evidence in cases.items():
            with self.subTest(case=label):
                result, harness, controller, order, _sleeps = self._flow(evidence=evidence)
                self.assertIs(result, False)
                self.assertEqual(harness.frame_calls, 0)
                self.assertEqual(order, [])
                self.assertEqual(controller.posts, [])

    # --------------------------------------------- fresh independent observation
    def test_a_stable_but_different_slot_is_refused(self) -> None:
        result, harness, controller, order, _sleeps = self._flow(
            slot=1, frames=[SLOT_FRAMES[2], SLOT_FRAMES[2]] + [SLOT_FRAMES[2]] * 4)
        self.assertIs(result, False)
        self.assertEqual(controller.posts, [])
        self.assertEqual(harness.frame_calls, 2)
        self.assertEqual(order, ["frame", "ocr", "frame", "ocr"])

    def test_geometry_drift_in_the_supplied_evidence_is_refused(self) -> None:
        shifted_panel = with_panel(evidence_for(1), left=60 + SLOT_PITCH,
                                   right=791 + SLOT_PITCH)
        shifted_button = with_button(evidence_for(1),
                                     box=[BUTTON_BOX[1][0] - 10, BUTTON_BOX[1][1],
                                          BUTTON_BOX[1][2], BUTTON_BOX[1][3]])
        for label, evidence in {"panel_drift": shifted_panel,
                                "button_drift": shifted_button}.items():
            with self.subTest(case=label):
                result, harness, controller, _order, _sleeps = self._flow(evidence=evidence)
                self.assertIs(result, False)
                self.assertEqual(controller.posts, [])
                self.assertEqual(harness.frame_calls, 2)

    def test_a_verified_attack_page_is_refused(self) -> None:
        for frames in ([SLOT_FRAMES[1]], [SLOT_FRAMES[1]] * 2):
            with self.subTest(frames=len(frames)):
                result, _harness, controller, _order, _sleeps = self._flow(
                    frames=frames, title_rows=[title_row(UNSUPPORTED_PAGE_TITLE)])
                self.assertIs(result, False)
                self.assertEqual(controller.posts, [])

    def test_an_unstable_or_blind_current_page_is_refused(self) -> None:
        cases = {
            "blank": ([BLANK] * MAX_SAMPLES, None),
            "alternating": ([SLOT_FRAMES[1], SLOT_FRAMES[2]] * 2, None),
            "single_valid_frame": ([SLOT_FRAMES[1], BLANK, BLANK, BLANK], None),
            "low_confidence_title": ([SLOT_FRAMES[1]] * MAX_SAMPLES,
                                     [title_row(DEFENSE_PAGE_TITLE, confidence=0.4)]),
            "no_title_rows": ([SLOT_FRAMES[1]] * MAX_SAMPLES, []),
            "conflicting_titles": ([SLOT_FRAMES[1]] * MAX_SAMPLES,
                                   [title_row(DEFENSE_PAGE_TITLE, box=(70, 100, 40, 30)),
                                    title_row(UNSUPPORTED_PAGE_TITLE, box=(120, 110, 40, 30))]),
            "title_outside_region": ([SLOT_FRAMES[1]] * MAX_SAMPLES,
                                     [title_row(DEFENSE_PAGE_TITLE, box=(700, 400, 80, 30))]),
        }
        for label, (frames, rows) in cases.items():
            with self.subTest(case=label):
                result, _harness, controller, _order, _sleeps = self._flow(
                    frames=frames, title_rows=rows)
                self.assertIs(result, False)
                self.assertEqual(controller.posts, [])

    # ------------------------------------------------------- pre-click re-check
    def test_a_last_frame_in_another_slot_is_not_clicked(self) -> None:
        result, harness, controller, _order, _sleeps = self._flow(
            frames=[SLOT_FRAMES[1], SLOT_FRAMES[1], SLOT_FRAMES[3]])
        self.assertIs(result, False)
        self.assertEqual(harness.frame_calls, 3)
        self.assertEqual(controller.posts, [])

    def test_a_last_frame_without_a_locatable_slot_is_not_clicked(self) -> None:
        result, harness, controller, _order, _sleeps = self._flow(
            frames=[SLOT_FRAMES[1], SLOT_FRAMES[1], BLANK])
        self.assertIs(result, False)
        self.assertEqual(harness.frame_calls, 3)
        self.assertEqual(controller.posts, [])

    def test_a_last_frame_with_a_moved_button_is_not_clicked(self) -> None:
        result, harness, controller, _order, _sleeps = self._flow(
            frames=[SLOT_FRAMES[1], SLOT_FRAMES[1], off_grid_button_frame(1)])
        self.assertIs(result, False)
        self.assertEqual(harness.frame_calls, 3)
        self.assertEqual(controller.posts, [])

    def test_button_label_must_be_the_whole_string_with_a_trustworthy_score(self) -> None:
        left, top, width, height = BUTTON_BOX[1]
        inside = [left + 30, top + 8, width - 60, height - 16]
        cases = {
            "substring": [{"text": "选择车辆并确认", "confidence": 0.99, "box": inside}],
            "prefix": [{"text": "选", "confidence": 0.99, "box": inside}],
            "garage_title": [{"text": SELECTION_PAGE_TITLE, "confidence": 0.99,
                              "box": inside}],
            "blank": [{"text": "   ", "confidence": 0.99, "box": inside}],
            "not_a_string": [{"text": 7, "confidence": 0.99, "box": inside}],
            "low_confidence": [{"text": "选择车辆", "confidence": 0.89, "box": inside}],
            "floor_confidence": [{"text": "选择车辆", "confidence": 0.90, "box": inside}],
            "over_range": [{"text": "选择车辆", "confidence": 1.01, "box": inside}],
            "nan": [{"text": "选择车辆", "confidence": float("nan"), "box": inside}],
            "inf": [{"text": "选择车辆", "confidence": float("inf"), "box": inside}],
            "bool": [{"text": "选择车辆", "confidence": True, "box": inside}],
            "outside_box": [{"text": "选择车辆", "confidence": 0.99,
                             "box": [left - 400, top, width, height]}],
            "malformed_box": [{"text": "选择车辆", "confidence": 0.99, "box": [left, top]}],
            "not_a_dict": ["选择车辆"],
            "no_rows": [],
            "both_labels": [{"text": "选择车辆", "confidence": 0.99, "box": inside},
                            {"text": "更换车辆", "confidence": 0.99, "box": inside}],
        }
        expected = {"floor_confidence": True}
        for label, rows in cases.items():
            with self.subTest(case=label):
                result, _harness, controller, _order, _sleeps = self._flow(button_rows=rows)
                self.assertIs(result, expected.get(label, False))
                self.assertEqual(len(controller.posts), 1 if label in expected else 0)

    # ---------------------------------------------------------------- the click
    def test_a_failed_click_is_not_retried_and_does_not_sample_arrival(self) -> None:
        result, harness, controller, _order, _sleeps = self._flow(
            controller=_Controller([], succeeded=False))
        self.assertIs(result, False)
        self.assertEqual(controller.posts, [click_point(1)])
        self.assertEqual(harness.frame_calls, 3)

    def test_a_raising_click_is_not_retried_and_does_not_sample_arrival(self) -> None:
        result, harness, controller, _order, _sleeps = self._flow(
            controller=_Controller([], error=RuntimeError("controller gone")))
        self.assertIs(result, False)
        self.assertEqual(controller.posts, [click_point(1)])
        self.assertEqual(harness.frame_calls, 3)

    # --------------------------------------------------------------- the arrival
    def test_a_single_garage_title_frame_is_not_arrival(self) -> None:
        result, harness, controller, _order, _sleeps = self._flow(
            arrival_rows=[[arrival_row()], []])
        self.assertIs(result, False)
        self.assertEqual(controller.posts, [click_point(1)])
        self.assertEqual(harness.arrival_calls, ARRIVAL_SAMPLES)
        self.assertEqual(harness.frame_calls, 3 + ARRIVAL_SAMPLES)

    def test_two_consecutive_garage_titles_are_required(self) -> None:
        cases = {
            "second_and_third": [[], [arrival_row()], [arrival_row()]],
            "fourth_and_fifth_after_bad": [[arrival_row()], [], [arrival_row()],
                                           [arrival_row()]],
        }
        for label, rows in cases.items():
            with self.subTest(case=label):
                result, harness, controller, _order, _sleeps = self._flow(arrival_rows=rows)
                self.assertIs(result, True)
                self.assertEqual(len(controller.posts), 1)
                self.assertLessEqual(harness.arrival_calls, ARRIVAL_SAMPLES)

    def test_the_arrival_budget_is_six_samples_and_exhausts_to_false(self) -> None:
        result, harness, controller, _order, sleeps = self._flow(arrival_rows=[[]])
        self.assertIs(result, False)
        self.assertEqual(harness.arrival_calls, 6)
        self.assertEqual(harness.frame_calls, 3 + 6)
        self.assertEqual(controller.posts, [click_point(1)])
        self.assertEqual(set(sleeps), {ARRIVAL_INTERVAL})
        self.assertGreaterEqual(len(sleeps), ARRIVAL_SAMPLES - 1)

    def test_arrival_requires_a_whole_string_confident_title_in_its_region(self) -> None:
        cases = {
            "longer_text": [arrival_row(text="车辆选择中")],
            "shorter_text": [arrival_row(text="车辆")],
            "low_confidence": [arrival_row(confidence=0.89)],
            "over_range": [arrival_row(confidence=1.5)],
            "nan": [arrival_row(confidence=float("nan"))],
            "bool": [arrival_row(confidence=True)],
            "outside_region": [arrival_row(box=(600, 400, 180, 40))],
            "malformed_box": [{"text": SELECTION_PAGE_TITLE, "confidence": 0.99,
                               "box": [50, 70]}],
            "not_a_dict": ["车辆选择"],
        }
        for label, rows in cases.items():
            with self.subTest(case=label):
                result, harness, _controller, _order, _sleeps = self._flow(arrival_rows=[rows])
                self.assertIs(result, False)
                self.assertEqual(harness.arrival_calls, ARRIVAL_SAMPLES)

    def test_a_wrongly_sized_arrival_frame_is_refused_not_scaled(self) -> None:
        small = np.zeros((360, 640, 3), dtype=np.uint8)
        result, harness, controller, _order, _sleeps = self._flow(
            frames=[SLOT_FRAMES[1]] * 3 + [small] * ARRIVAL_SAMPLES)
        self.assertIs(result, False)
        self.assertEqual(harness.arrival_calls, 0)
        self.assertEqual(harness.ocr_rois[-1], BUTTON_BOX[1])
        self.assertEqual(len(harness.ocr_rois), 4)
        self.assertEqual(controller.posts, [click_point(1)])

    # ------------------------------------------------ integration with real 05F
    def _with_05f(self, frames: list, scan_result: dict, expected_slot: int = 1):
        order: list = []
        controller = _Controller(order)
        harness = _Harness(order, frames, slot=expected_slot)
        scan_calls: list = []

        def scan_stub(*args, **kwargs):
            scan_calls.append({"args": args, "kwargs": kwargs})
            return scan_result

        with mock.patch.object(duel_slot_entry, "frame_of", harness.frame_of), \
                mock.patch.object(duel_slot_entry, "ocr_roi", harness.ocr_roi), \
                mock.patch.object(duel_slot_selection, "frame_of", harness.frame_of), \
                mock.patch.object(duel_slot_selection, "ocr_roi", harness.ocr_roi), \
                mock.patch.object(duel_slot_selection, "scan", scan_stub), \
                mock.patch.object(duel_slot_entry.time, "sleep"), \
                mock.patch.object(duel_slot_selection.time, "sleep"):
            report = select_vehicle_for_slot(
                _Context(controller), request(expected_slot=expected_slot),
                enter_defense_slot_selection, catalog=CATALOG, confirmed_owned_ids=OWNED)
        return report, harness, controller, scan_calls

    def test_real_05f_locate_only_succeeds_through_the_real_entry_callback(self) -> None:
        report, harness, controller, scan_calls = self._with_05f(
            [SLOT_FRAMES[1]] * 8, detail_report())
        self.assertEqual(report["status"], STATUS_LOCATED)
        self.assertTrue(report["entry_attempted"])
        self.assertFalse(report["selection_attempted"])
        self.assertFalse(report["starts_race"])
        self.assertFalse(report["assignment_complete"])
        self.assertIsNone(report["after"])
        self.assertEqual(len(scan_calls), 1)
        self.assertIs(scan_calls[0]["kwargs"]["choose"], False)
        self.assertEqual(controller.posts, [click_point(1)])
        self.assertEqual(harness.frame_calls, 7)

    def test_real_05f_entry_false_never_scans(self) -> None:
        report, harness, controller, scan_calls = self._with_05f(
            [SLOT_FRAMES[1], SLOT_FRAMES[1], SLOT_FRAMES[1], SLOT_FRAMES[1], BLANK],
            detail_report())
        self.assertEqual(report["status"], STATUS_ENTRY_FAILED)
        self.assertEqual(report["reason"], "entry_returned_false")
        self.assertTrue(report["entry_attempted"])
        self.assertFalse(report["selection_attempted"])
        self.assertFalse(report["starts_race"])
        self.assertEqual(scan_calls, [])
        self.assertEqual(controller.posts, [])
        self.assertEqual(harness.frame_calls, 5)

    # ------------------------------------------------------------ static gates
    def test_module_stays_offline_and_avoids_navigation_nodes(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        absolute: set[str] = set()
        relative: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                absolute.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    relative.add(node.module or "")
                elif node.module:
                    absolute.add(node.module.split(".")[0])
        self.assertEqual(absolute, {"__future__", "time", "typing"})
        self.assertEqual(relative, {"duel_lineup_slot", "duel_slot_selection",
                                    "selection_runtime"})

        called: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    called.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called.add(func.attr)
        self.assertEqual(called & {"open", "run_task", "post_swipe", "post_screencap",
                                   "post_long_click", "post_key_press", "imread",
                                   "imwrite", "imdecode", "imencode", "urlopen",
                                   "eval", "exec", "compile"}, set())
        self.assertIn("post_click", called)

        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertEqual(names & {"Controller", "adb", "requests", "socket", "subprocess",
                                  "Path", "os", "json", "logging", "sys"}, set())
        for banned in ("run_task", "post_swipe", "防守", "花都", "铁塔", "季风", "岩石",
                       "defense_setup", "对决_"):
            self.assertNotIn(banned, source)

    def test_imported_fixtures_really_come_from_the_real_observers(self) -> None:
        for slot in range(1, 6):
            with self.subTest(slot=slot):
                report = REPORTS[slot]
                self.assertEqual(report["page"], "duel_lineup")
                self.assertEqual(report["expanded_slot"], slot)
                self.assertEqual(report["page_title"], DEFENSE_PAGE_TITLE)
                self.assertEqual(report["verification_basis"], "geometry_and_title")
                self.assertTrue(report["title_guard_passed"])
                self.assertEqual(evidence_for(slot)["expanded_slot"], slot)

    def test_the_callback_is_a_plain_bool_and_never_a_truthy_payload(self) -> None:
        result, _harness, _controller, _order, _sleeps = self._flow()
        self.assertIsInstance(result, bool)
        refused, *_ = self._flow(evidence=None)
        self.assertIs(refused, False)


if __name__ == "__main__":
    unittest.main()