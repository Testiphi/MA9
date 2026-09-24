"""Offline tests for the thin single-slot defence selection adapter.

Every test uses an in-process fake context, stubbed capture/OCR and stubbed
``scan`` plus an injected entry callback: no device, no ADB, no real frame
source and no account data.  ``observe_lineup_slot`` itself is **never** stubbed,
so the synthetic lineup frames are really interpreted by the production
observer; only the frame source (``frame_of``), the OCR rows (``ocr_roi``) and
the reused ``scan`` are replaced, exactly as the prompt allows.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_lineup_slot import (BUTTON_CENTER_BASE, EXPANDED_WIDTH,
                                        LINEUP_TITLE_ROI, LINEUP_TITLES,
                                        PANEL_RIGHT_BASE, SLOT_PITCH)
from ma9_agent import duel_slot_selection
from ma9_agent.duel_slot_selection import (DEFENSE_PAGE_TITLE, MAX_SAMPLES,
                                           STATUS_ASSIGNED, STATUS_ASSIGNMENT_UNVERIFIED,
                                           STATUS_ENTRY_ERROR, STATUS_ENTRY_FAILED,
                                           STATUS_ENTRY_MISSING, STATUS_LINEUP_UNSTABLE,
                                           STATUS_LOCATED, STATUS_SCAN_INCOMPLETE,
                                           STATUS_SLOT_MISMATCH, STATUS_UNSUPPORTED,
                                           UNSUPPORTED_PAGE_TITLE, SlotSelectionRequest,
                                           select_vehicle_for_slot)

MODULE_PATH = Path(__file__).resolve().parents[1] / "ma9_agent/duel_slot_selection.py"

BACKGROUND = (60, 25, 45)
PANEL_COLOR = (200, 90, 140)
BUTTON_COLOR = (20, 240, 180)
BUTTON_WIDTH = 192
BUTTON_HEIGHT = 50

CATALOG = [
    {"id": "car-d", "title": "Car D", "class": "D"},
    {"id": "car-d2", "title": "Car D2", "class": "D"},
    {"id": "car-c", "title": "Car C", "class": "C"},
]
OWNED = ("car-d", "car-d2", "car-c")


def blank_frame() -> np.ndarray:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[:, :] = BACKGROUND
    return frame


def lineup_frame(slot: int) -> np.ndarray:
    """Draw one bright expanded cell on the published 114 px slot grid."""
    frame = blank_frame()
    right = PANEL_RIGHT_BASE + SLOT_PITCH * (slot - 1)
    left = right - EXPANDED_WIDTH
    frame[210:545, left:right + 1] = PANEL_COLOR
    center = BUTTON_CENTER_BASE + SLOT_PITCH * (slot - 1)
    bx = int(round(center - BUTTON_WIDTH / 2))
    frame[495:495 + BUTTON_HEIGHT, bx:bx + BUTTON_WIDTH] = BUTTON_COLOR
    return frame


SLOT_FRAMES = {slot: lineup_frame(slot) for slot in range(1, 6)}
BLANK = blank_frame()


def title_row(text: str, confidence: float = 0.99,
              box: tuple[int, int, int, int] = (70, 100, 80, 30)) -> dict:
    return {"text": text, "confidence": confidence, "box": list(box)}


def request(**overrides) -> SlotSelectionRequest:
    base = {"expected_slot": 1, "target_id": "car-d", "vehicle_class": "D",
            "account_key": "trace-account-1", "choose": False}
    base.update(overrides)
    return SlotSelectionRequest(**base)


def detail_report(target: str = "car-d", status: str = "detail_verified") -> dict:
    return {
        "status": status,
        "pages": 1,
        "vehicles": [],
        "assignment_complete": status == "assigned",
        "detail_vehicle": {"id": target, "title": target, "confidence": 1.0},
        "selected_card": {"vehicle": {"id": target, "title": target, "confidence": 1.0}},
    }


def assigned_report(target: str = "car-d") -> dict:
    return detail_report(target, status="assigned")


_UNSET = object()


class _Entry:
    def __init__(self, result=True, error=None, order=None):
        self.result = result
        self.error = error
        self.order = order
        self.calls = []

    def __call__(self, context, evidence):
        if self.order is not None:
            self.order.append("entry")
        self.calls.append(evidence)
        if self.error is not None:
            raise self.error
        return self.result


class _Harness:
    """Fake frame source + OCR rows; records the call order of every stage."""

    def __init__(self, frames, rows, order):
        self.frames = list(frames)
        self.rows = rows
        self.order = order
        self.frame_calls = 0
        self.ocr_rois = []

    def frame_of(self, _context):
        index = self.frame_calls
        self.frame_calls += 1
        self.order.append("frame")
        return self.frames[index] if index < len(self.frames) else self.frames[-1]

    def ocr_roi(self, _context, _frame, roi):
        self.order.append("ocr")
        self.ocr_rois.append(roi)
        return list(self.rows)


class SlotSelectionAdapterTest(unittest.TestCase):
    def _flow(self, req, *, frames, rows=None, scan_result=None, enter=_UNSET,
              catalog=None, owned=OWNED):
        order: list[str] = []
        harness = _Harness(frames, rows if rows is not None else [title_row(DEFENSE_PAGE_TITLE)],
                           order)
        entry = _Entry(order=order) if enter is _UNSET else enter
        scan_calls: list[dict] = []

        def scan_stub(context, vehicle_class, catalog_arg, **kwargs):
            order.append("scan")
            scan_calls.append({"context": context, "vehicle_class": vehicle_class,
                               "catalog": catalog_arg, **kwargs})
            return scan_result

        with mock.patch.object(duel_slot_selection, "frame_of", harness.frame_of), \
                mock.patch.object(duel_slot_selection, "ocr_roi", harness.ocr_roi), \
                mock.patch.object(duel_slot_selection, "scan", scan_stub), \
                mock.patch.object(duel_slot_selection.time, "sleep"):
            report = select_vehicle_for_slot(
                object(), req, entry, catalog=CATALOG if catalog is None else catalog,
                confirmed_owned_ids=owned)
        return report, order, scan_calls, entry, harness

    # ------------------------------------------------------------ happy paths
    def test_each_slot_orders_pre_entry_scan_post_and_keeps_same_slot(self) -> None:
        for slot in range(1, 6):
            with self.subTest(slot=slot):
                frames = [SLOT_FRAMES[slot]] * 4
                report, order, scan_calls, entry, harness = self._flow(
                    request(expected_slot=slot, choose=True), frames=frames,
                    scan_result=assigned_report())
                self.assertEqual(report["status"], STATUS_ASSIGNED)
                self.assertTrue(report["assignment_complete"])
                self.assertTrue(report["entry_attempted"])
                self.assertTrue(report["selection_attempted"])
                self.assertFalse(report["starts_race"])
                self.assertEqual(report["before"]["expanded_slot"], slot)
                self.assertEqual(report["after"]["expanded_slot"], slot)
                self.assertEqual(order, ["frame", "ocr", "frame", "ocr", "entry", "scan",
                                         "frame", "ocr", "frame", "ocr"])
                self.assertEqual(len(scan_calls), 1)
                self.assertIs(scan_calls[0]["choose"], True)
                self.assertEqual(len(entry.calls), 1)
                self.assertEqual(entry.calls[0]["expanded_slot"], slot)
                self.assertEqual(harness.ocr_rois, [LINEUP_TITLE_ROI] * 4)

    def test_every_slot_also_works_in_the_locate_only_default(self) -> None:
        for slot in range(1, 6):
            with self.subTest(slot=slot):
                report, order, scan_calls, _entry, _harness = self._flow(
                    request(expected_slot=slot), frames=[SLOT_FRAMES[slot]] * 2,
                    scan_result=detail_report())
                self.assertEqual(report["status"], STATUS_LOCATED)
                self.assertFalse(report["assignment_complete"])
                self.assertFalse(report["selection_attempted"])
                self.assertIsNone(report["after"])
                self.assertFalse(report["starts_race"])
                self.assertEqual(order, ["frame", "ocr", "frame", "ocr", "entry", "scan"])
                self.assertIs(scan_calls[0]["choose"], False)

    def test_pre_evidence_is_produced_by_the_real_observer(self) -> None:
        report, *_ = self._flow(request(expected_slot=3), frames=[SLOT_FRAMES[3]] * 2,
                                scan_result=detail_report())
        evidence = report["before"]
        self.assertEqual(evidence["verification_basis"], "geometry_and_title")
        self.assertTrue(evidence["title_guard_passed"])
        self.assertEqual(evidence["page_title"], DEFENSE_PAGE_TITLE)
        self.assertEqual(evidence["panel"]["right"],
                         PANEL_RIGHT_BASE + SLOT_PITCH * 2)
        self.assertEqual(evidence["panel"]["right"] - evidence["panel"]["left"],
                         EXPANDED_WIDTH)
        self.assertEqual(evidence["consecutive"], 2)
        self.assertEqual(evidence["samples"], 2)

    def test_expected_slot_is_never_handed_to_the_observer(self) -> None:
        real = duel_slot_selection.observe_lineup_slot
        seen: list[dict] = []

        def spy(frame, **kwargs):
            seen.append(kwargs)
            return real(frame, **kwargs)

        with mock.patch.object(duel_slot_selection, "observe_lineup_slot", spy), \
                mock.patch.object(duel_slot_selection, "frame_of",
                                  lambda _c: SLOT_FRAMES[1]), \
                mock.patch.object(duel_slot_selection, "ocr_roi",
                                  lambda *a: [title_row(DEFENSE_PAGE_TITLE)]), \
                mock.patch.object(duel_slot_selection, "scan",
                                  lambda *a, **k: detail_report()), \
                mock.patch.object(duel_slot_selection.time, "sleep"):
            select_vehicle_for_slot(object(), request(), _Entry(), catalog=CATALOG,
                                    confirmed_owned_ids=OWNED)
        self.assertTrue(seen)
        for kwargs in seen:
            self.assertEqual(set(kwargs), {"ocr"})

    def test_request_optionals_reach_the_scan_unchanged(self) -> None:
        report, _order, scan_calls, _entry, _harness = self._flow(
            request(expected_slot=2, choose=True, expected_performance=1381,
                    expected_stars=4, page_hint=3, max_pages=10),
            frames=[SLOT_FRAMES[2]] * 4, scan_result=assigned_report())
        self.assertEqual(report["status"], STATUS_ASSIGNED)
        call = scan_calls[0]
        self.assertEqual(call["vehicle_class"], "D")
        self.assertEqual(call["target_id"], "car-d")
        self.assertIs(call["choose"], True)
        self.assertEqual(call["max_pages"], 10)
        self.assertEqual(call["expected_performance"], 1381)
        self.assertEqual(call["expected_stars"], 4)
        self.assertEqual(call["page_hint"], 3)
        self.assertEqual(report["request"]["page_hint"], 3)

    # --------------------------------------------------- pre-slot refusals
    def test_single_valid_frame_is_not_enough(self) -> None:
        report, order, scan_calls, entry, _harness = self._flow(
            request(), frames=[SLOT_FRAMES[1], BLANK, BLANK, BLANK],
            scan_result=detail_report())
        self.assertEqual(report["status"], STATUS_LINEUP_UNSTABLE)
        self.assertEqual(order, ["frame", "ocr"] * MAX_SAMPLES)
        self.assertEqual(entry.calls, [])
        self.assertEqual(scan_calls, [])

    def test_alternating_slots_are_never_stable(self) -> None:
        report, _order, scan_calls, entry, _harness = self._flow(
            request(), frames=[SLOT_FRAMES[1], SLOT_FRAMES[2],
                               SLOT_FRAMES[1], SLOT_FRAMES[2]],
            scan_result=detail_report())
        self.assertEqual(report["status"], STATUS_LINEUP_UNSTABLE)
        self.assertEqual(entry.calls, [])
        self.assertEqual(scan_calls, [])

    def test_low_confidence_title_is_not_evidence(self) -> None:
        report, _order, _scan, entry, _harness = self._flow(
            request(), frames=[SLOT_FRAMES[1]] * 4,
            rows=[title_row(DEFENSE_PAGE_TITLE, confidence=0.4)],
            scan_result=detail_report())
        self.assertEqual(report["status"], STATUS_LINEUP_UNSTABLE)
        self.assertEqual(entry.calls, [])

    def test_geometry_only_frame_without_a_title_is_refused(self) -> None:
        report, _order, _scan, entry, _harness = self._flow(
            request(), frames=[SLOT_FRAMES[1]] * 4, rows=[],
            scan_result=detail_report())
        self.assertEqual(report["status"], STATUS_LINEUP_UNSTABLE)
        self.assertEqual(entry.calls, [])

    def test_conflicting_titles_are_refused(self) -> None:
        report, _order, _scan, entry, _harness = self._flow(
            request(), frames=[SLOT_FRAMES[1]] * 4,
            rows=[title_row(DEFENSE_PAGE_TITLE, box=(70, 100, 40, 30)),
                  title_row(UNSUPPORTED_PAGE_TITLE, box=(120, 110, 40, 30))],
            scan_result=detail_report())
        self.assertEqual(report["status"], STATUS_LINEUP_UNSTABLE)
        self.assertEqual(entry.calls, [])

    def test_a_frame_without_a_locatable_slot_is_refused(self) -> None:
        report, _order, _scan, entry, _harness = self._flow(
            request(), frames=[BLANK] * 4, scan_result=detail_report())
        self.assertEqual(report["status"], STATUS_LINEUP_UNSTABLE)
        self.assertEqual(entry.calls, [])

    def test_sample_budget_is_bounded_and_not_shared_between_calls(self) -> None:
        unstable, order, _scan, _entry, harness = self._flow(
            request(), frames=[BLANK] * 8, scan_result=detail_report())
        self.assertEqual(unstable["status"], STATUS_LINEUP_UNSTABLE)
        self.assertEqual(harness.frame_calls, MAX_SAMPLES)
        self.assertEqual(order, ["frame", "ocr"] * MAX_SAMPLES)

        # A fresh call must not inherit the previous call's sample count and
        # must be able to accept a slot immediately.
        stable, _order2, _scan2, _entry2, harness2 = self._flow(
            request(), frames=[SLOT_FRAMES[1]] * 2, scan_result=detail_report())
        self.assertEqual(stable["status"], STATUS_LOCATED)
        self.assertEqual(stable["before"]["samples"], 2)
        self.assertEqual(harness2.frame_calls, 2)

    # ------------------------------------------------------ environment guard
    def test_stable_wrong_slot_is_a_mismatch_without_entry(self) -> None:
        report, order, scan_calls, entry, _harness = self._flow(
            request(expected_slot=1), frames=[SLOT_FRAMES[2]] * 2,
            scan_result=detail_report())
        self.assertEqual(report["status"], STATUS_SLOT_MISMATCH)
        self.assertEqual(report["reason"], "observed_2_expected_1")
        self.assertEqual(order, ["frame", "ocr", "frame", "ocr"])
        self.assertEqual(entry.calls, [])
        self.assertEqual(scan_calls, [])

    def test_verified_attack_page_is_unsupported_and_never_entered(self) -> None:
        rows = [title_row(UNSUPPORTED_PAGE_TITLE)]
        for frames in ([SLOT_FRAMES[1]], [SLOT_FRAMES[1]] * 2):
            with self.subTest(frames=len(frames)):
                report, _order, scan_calls, entry, _harness = self._flow(
                    request(expected_slot=1), frames=frames, rows=rows,
                    scan_result=assigned_report())
                self.assertEqual(report["status"], STATUS_UNSUPPORTED)
                self.assertEqual(report["reason"], "attack_page_title")
                self.assertEqual(entry.calls, [])
                self.assertEqual(scan_calls, [])
                self.assertFalse(report["starts_race"])

    def test_title_constants_match_the_observer_contract(self) -> None:
        self.assertIn(DEFENSE_PAGE_TITLE, LINEUP_TITLES)
        self.assertIn(UNSUPPORTED_PAGE_TITLE, LINEUP_TITLES)
        self.assertNotEqual(DEFENSE_PAGE_TITLE, UNSUPPORTED_PAGE_TITLE)

    # -------------------------------------------------- request validation
    def test_invalid_requests_are_rejected_before_any_context_call(self) -> None:
        cases = {
            "slot_zero": request(expected_slot=0),
            "slot_six": request(expected_slot=6),
            "slot_float": request(expected_slot=1.0),
            "slot_bool": request(expected_slot=True),
            "choose_int": request(choose=1),
            "account_blank": request(account_key="  "),
            "account_not_str": request(account_key=7),
            "target_blank": request(target_id=""),
            "class_unknown": request(vehicle_class="Z"),
            "class_type": request(vehicle_class=None),
            "max_pages_zero": request(max_pages=0),
            "max_pages_big": request(max_pages=51),
            "max_pages_type": request(max_pages="5"),
            "perf_low": request(expected_performance=99),
            "perf_type": request(expected_performance="1381"),
            "stars_zero": request(expected_stars=0),
            "stars_seven": request(expected_stars=7),
            "hint_zero": request(page_hint=0),
            "hint_over": request(page_hint=99, max_pages=10),
        }
        for label, req in cases.items():
            with self.subTest(case=label):
                order: list[str] = []
                harness = _Harness([SLOT_FRAMES[1]] * 2, [title_row(DEFENSE_PAGE_TITLE)], order)
                entry = _Entry(order=order)
                scan_calls: list = []
                with mock.patch.object(duel_slot_selection, "frame_of", harness.frame_of), \
                        mock.patch.object(duel_slot_selection, "ocr_roi", harness.ocr_roi), \
                        mock.patch.object(duel_slot_selection, "scan",
                                          lambda *a, **k: scan_calls.append(a)), \
                        mock.patch.object(duel_slot_selection.time, "sleep"):
                    with self.assertRaises(ValueError):
                        select_vehicle_for_slot(object(), req, entry, catalog=CATALOG,
                                                confirmed_owned_ids=OWNED)
                self.assertEqual(order, [])
                self.assertEqual(entry.calls, [])
                self.assertEqual(scan_calls, [])

    def test_unowned_or_mismatched_targets_are_rejected(self) -> None:
        cases = {
            "not_owned": (request(), CATALOG, ("car-d2",)),
            "absent": (request(target_id="ghost"), CATALOG, OWNED),
            "class_mismatch": (request(target_id="car-c"), CATALOG, OWNED),
        }
        for label, (req, catalog, owned) in cases.items():
            with self.subTest(case=label):
                with mock.patch.object(duel_slot_selection, "frame_of") as frame_of:
                    with self.assertRaises(ValueError):
                        select_vehicle_for_slot(object(), req, None, catalog=catalog,
                                                confirmed_owned_ids=owned)
                frame_of.assert_not_called()

    def test_non_request_object_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            select_vehicle_for_slot(object(), {"expected_slot": 1}, None,
                                    catalog=CATALOG, confirmed_owned_ids=OWNED)

    # --------------------------------------------------------- entry gating
    def test_entry_false_or_error_or_missing_stops_before_scan(self) -> None:
        cases = [
            ("missing", None, STATUS_ENTRY_MISSING, False),
            ("false", _Entry(result=False), STATUS_ENTRY_FAILED, True),
            ("exception", _Entry(error=RuntimeError("boom")), STATUS_ENTRY_ERROR, True),
            ("non_bool", _Entry(result="yes"), STATUS_ENTRY_FAILED, True),
        ]
        for label, entry, status, attempted in cases:
            with self.subTest(case=label):
                report, _order, scan_calls, _entry, _harness = self._flow(
                    request(), frames=[SLOT_FRAMES[1]] * 2, scan_result=assigned_report(),
                    enter=entry)
                self.assertEqual(report["status"], status)
                self.assertEqual(scan_calls, [])
                self.assertIs(report["entry_attempted"], attempted)
                self.assertIsNone(report["scan_report"])
                self.assertFalse(report["starts_race"])

    def test_scan_exception_is_reported_and_never_a_success(self) -> None:
        def exploding(*_args, **_kwargs):
            raise RuntimeError("device gone")

        with mock.patch.object(duel_slot_selection, "frame_of",
                               lambda _c: SLOT_FRAMES[1]), \
                mock.patch.object(duel_slot_selection, "ocr_roi",
                                  lambda *a: [title_row(DEFENSE_PAGE_TITLE)]), \
                mock.patch.object(duel_slot_selection, "scan", exploding), \
                mock.patch.object(duel_slot_selection.time, "sleep"):
            located = select_vehicle_for_slot(object(), request(), _Entry(),
                                              catalog=CATALOG, confirmed_owned_ids=OWNED)
            selected = select_vehicle_for_slot(
                object(), request(choose=True), _Entry(), catalog=CATALOG,
                confirmed_owned_ids=OWNED)
        self.assertEqual(located["status"], STATUS_SCAN_INCOMPLETE)
        self.assertEqual(located["reason"], "scan_error:RuntimeError")
        self.assertFalse(located["selection_attempted"])
        self.assertEqual(selected["status"], STATUS_ASSIGNMENT_UNVERIFIED)
        self.assertTrue(selected["selection_attempted"])

    # ------------------------------------------------ locate-only behaviour
    def test_locate_only_never_claims_an_assignment(self) -> None:
        for scan_result in ({"status": "target_not_found", "assignment_complete": False},
                            {"status": "occupied_elsewhere", "assignment_complete": False},
                            assigned_report()):
            with self.subTest(scan=scan_result["status"]):
                report, _order, scan_calls, _entry, _harness = self._flow(
                    request(choose=False), frames=[SLOT_FRAMES[1]] * 2,
                    scan_result=scan_result)
                self.assertEqual(report["status"], STATUS_SCAN_INCOMPLETE)
                self.assertFalse(report["assignment_complete"])
                self.assertFalse(report["selection_attempted"])
                self.assertIsNone(report["after"])
                self.assertIs(scan_calls[0]["choose"], False)
                self.assertNotEqual(report["status"], STATUS_ASSIGNED)
                self.assertEqual(report["scan_report"], scan_result)

    def test_locate_only_requires_target_evidence_not_just_the_status(self) -> None:
        report, _order, _scan, _entry, _harness = self._flow(
            request(choose=False), frames=[SLOT_FRAMES[1]] * 2,
            scan_result=detail_report(target="car-d2"))
        self.assertEqual(report["status"], STATUS_SCAN_INCOMPLETE)

    # ------------------------------------------------ choose=True behaviour
    def test_choose_requires_target_evidence_from_the_scan(self) -> None:
        report, order, scan_calls, entry, _harness = self._flow(
            request(choose=True), frames=[SLOT_FRAMES[1]] * 4,
            scan_result=assigned_report(target="car-d2"))
        self.assertEqual(report["status"], STATUS_ASSIGNMENT_UNVERIFIED)
        self.assertEqual(report["reason"], "target_evidence_mismatch")
        self.assertTrue(report["selection_attempted"])
        self.assertFalse(report["assignment_complete"])
        self.assertIsNone(report["after"])
        self.assertEqual(order, ["frame", "ocr", "frame", "ocr", "entry", "scan"])
        self.assertEqual(len(scan_calls), 1)
        self.assertEqual(len(entry.calls), 1)

    def test_bare_assigned_status_without_evidence_is_not_success(self) -> None:
        report, _order, _scan, _entry, _harness = self._flow(
            request(choose=True), frames=[SLOT_FRAMES[1]] * 4,
            scan_result={"status": "assigned", "assignment_complete": True})
        self.assertEqual(report["status"], STATUS_ASSIGNMENT_UNVERIFIED)
        self.assertEqual(report["reason"], "target_evidence_mismatch")

    def test_choose_scan_failure_is_unverified_with_attempt_recorded(self) -> None:
        report, _order, _scan, _entry, _harness = self._flow(
            request(choose=True), frames=[SLOT_FRAMES[1]] * 2,
            scan_result={"status": "target_not_found", "assignment_complete": False})
        self.assertEqual(report["status"], STATUS_ASSIGNMENT_UNVERIFIED)
        self.assertEqual(report["reason"], "assignment_not_confirmed")
        self.assertTrue(report["selection_attempted"])
        self.assertEqual(report["scan_report"]["status"], "target_not_found")

    def test_return_to_a_different_slot_is_unverified_and_side_effect_kept(self) -> None:
        report, order, scan_calls, entry, _harness = self._flow(
            request(choose=True), frames=[SLOT_FRAMES[1]] * 2 + [SLOT_FRAMES[4]] * 2,
            scan_result=assigned_report())
        self.assertEqual(report["status"], STATUS_ASSIGNMENT_UNVERIFIED)
        self.assertEqual(report["reason"], "after_slot_mismatch")
        self.assertTrue(report["selection_attempted"])
        self.assertFalse(report["assignment_complete"])
        self.assertEqual(report["after"]["expanded_slot"], 4)
        self.assertEqual(len(scan_calls), 1)
        self.assertEqual(len(entry.calls), 1)
        self.assertEqual(order[-2:], ["frame", "ocr"])

    def test_unstable_return_page_is_unverified(self) -> None:
        report, _order, _scan, _entry, _harness = self._flow(
            request(choose=True), frames=[SLOT_FRAMES[1]] * 2 + [BLANK] * 2,
            scan_result=assigned_report())
        self.assertEqual(report["status"], STATUS_ASSIGNMENT_UNVERIFIED)
        self.assertEqual(report["reason"], "after_lineup_unstable")
        self.assertTrue(report["selection_attempted"])

    def test_unstable_return_page_reports_the_attempt_without_correction(self) -> None:
        report, order, scan_calls, entry, _harness = self._flow(
            request(choose=True), frames=[SLOT_FRAMES[1]] * 2 + [SLOT_FRAMES[3], BLANK],
            scan_result=assigned_report())
        self.assertEqual(report["status"], STATUS_ASSIGNMENT_UNVERIFIED)
        self.assertEqual(report["reason"], "after_lineup_unstable")
        self.assertEqual(len(scan_calls), 1)
        self.assertEqual(len(entry.calls), 1)
        self.assertNotIn("click", "".join(order))

    # -------------------------------------------------------- report shape
    def test_report_is_image_free_and_always_declares_no_race_start(self) -> None:
        report, *_ = self._flow(request(expected_slot=2, choose=True),
                                frames=[SLOT_FRAMES[2]] * 4,
                                scan_result=assigned_report())
        self.assertEqual(
            set(report),
            {"account_key", "request", "status", "reason", "starts_race",
             "entry_attempted", "selection_attempted", "assignment_complete",
             "before", "after", "scan_report"})
        self.assertIs(report["starts_race"], False)
        self.assertEqual(report["account_key"], "trace-account-1")

        def walk(value):
            self.assertNotIsInstance(value, np.ndarray)
            if isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    walk(item)

        walk(report)

    def test_module_stays_offline_and_map_free(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        absolute_imports: set[str] = set()
        relative_imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                absolute_imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    relative_imports.add(node.module or "")
                elif node.module:
                    absolute_imports.add(node.module.split(".")[0])
        self.assertEqual(absolute_imports, {"__future__", "time", "dataclasses", "typing"})
        self.assertEqual(relative_imports,
                         {"duel_lineup_slot", "duel_vehicle_runtime", "selection_runtime"})

        forbidden_calls = {"open", "run_task", "post_click", "post_swipe",
                           "imread", "imwrite", "imdecode", "imencode", "urlopen"}
        called: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    called.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called.add(func.attr)
        self.assertEqual(called & forbidden_calls, set())
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertEqual(names & {"Controller", "tasker", "adb", "requests", "socket",
                                  "subprocess", "Path"}, set())
        for banned in ("防守", "花都", "铁塔", "季风", "岩石", "defense_setup"):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()