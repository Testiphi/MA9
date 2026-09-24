"""Controlled tests for the read-only Duel lineup slot observer.

Every frame here is synthesised in-process from the published geometry: no
account screenshot, no capture fixture and no device is used.  The fixed
1280x720 sample replay lives in the 05E1 private evidence directory instead.

Two calibration facts are locked from committed resources rather than restated:
the *title region* must equal the ROI of the already-committed same-page
``TemplateMatch`` in ``assets/resource/pipeline/duel_slot_navigation.json``, and
the geometry constants are exercised through the public observer only.

The observer reports a *verification basis*, never an execution permission:
``slot_verified`` means "the calibrated layout was found", and the caller must
add its own page-provenance, settle-frame and entry/return evidence before any
selection action.  No ``can_click``/``action_ready`` field exists by design.
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import inspect
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_lineup_slot import (BASIS_GEOMETRY_AND_TITLE,
                                        BASIS_GEOMETRY_ONLY, BASIS_REJECTED,
                                        BUTTON_CENTER_BASE, BUTTON_COLOR_LOWER,
                                        EXPANDED_WIDTH, LINEUP_TITLE_ROI,
                                        PANEL_RIGHT_BASE, SLOT_PITCH,
                                        SELECTION_PAGE_TITLE, STRIP_LEFT,
                                        SUPPORTED_SIZE, TITLE_CONFIDENCE_FLOOR,
                                        observe_lineup_slot)

MODULE_PATH = Path(__file__).resolve().parents[1] / "ma9_agent/duel_lineup_slot.py"
PIPELINE_PATH = (Path(__file__).resolve().parents[2]
                 / "assets/resource/pipeline/duel_slot_navigation.json")

BACKGROUND = (60, 25, 45)
PANEL_COLOR = (200, 90, 140)
BUTTON_COLOR = (20, 240, 180)
MARKER_COLOR = (210, 60, 160)

#: Centre of an inside-the-region title glyph box used by most title tests.
TITLE_CENTER = (100, 110)


def blank_frame(width: int = 1280, height: int = 720) -> np.ndarray:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :] = BACKGROUND
    return frame


def panel_span(slot: int, *, shift: int = 0, width: int | None = None) -> tuple[int, int]:
    right = PANEL_RIGHT_BASE + SLOT_PITCH * (slot - 1) + shift
    return right - EXPANDED_WIDTH, right


def button_box(slot: int, *, width: int = 192, height: int = 50) -> tuple[int, int, int, int]:
    center = BUTTON_CENTER_BASE + SLOT_PITCH * (slot - 1)
    left = int(round(center - width / 2))
    return left, 495, width, height


def marker_centers(slot: int, panel_right: int, *, only: list[int] | None = None) -> list[int]:
    """x-centre of each collapsed cell; ``only`` selects a subset of slots."""
    mapping: dict[int, float] = {}
    for index in range(1, 6):
        if index == slot:
            continue
        if index < slot:
            mapping[index] = STRIP_LEFT + SLOT_PITCH / 2 + SLOT_PITCH * (index - 1)
        else:
            mapping[index] = panel_right + SLOT_PITCH / 2 + SLOT_PITCH * (index - slot - 1)
    keys = sorted(mapping) if only is None else sorted(only)
    return [mapping[index] for index in keys]


def collapsed_centers(slot: int, panel_right: int) -> list[int]:
    return marker_centers(slot, panel_right)


def lineup_frame(slot: int, *, markers: bool = True, marker_slots: list[int] | None = None,
                 panel_top: int = 210, panel_bottom: int = 545,
                 shift: int = 0) -> np.ndarray:
    """Draw the five-cell lineup: one bright expanded panel, optional markers."""
    frame = blank_frame()
    left, right = panel_span(slot, shift=shift)
    frame[panel_top:panel_bottom, left:right + 1] = PANEL_COLOR
    if markers:
        for center in marker_centers(slot, right, only=marker_slots):
            x = int(round(center))
            frame[220:530, x - 10:x + 10] = MARKER_COLOR
    bx, by, bw, bh = button_box(slot)
    frame[by:by + bh, bx:bx + bw] = BUTTON_COLOR
    return frame


def title_box(center_x: int = TITLE_CENTER[0], center_y: int = TITLE_CENTER[1],
              width: int = 80, height: int = 30) -> list[int]:
    return [center_x - width // 2, center_y - height // 2, width, height]


def ocr_row(text: str, box: list | None = None, confidence: object = 0.99) -> dict:
    row: dict = {"text": text, "confidence": confidence}
    if box is not None:
        row["box"] = box
    return row


class LineupSlotObserverTest(unittest.TestCase):
    def assert_refused(self, report: dict, reason: str) -> None:
        self.assertIsNone(report["expanded_slot"])
        self.assertFalse(report["slot_verified"])
        self.assertEqual(report["reason"], reason)
        self.assertEqual(report["verification_basis"], BASIS_REJECTED)
        self.assertFalse(report["title_guard_passed"])

    def assert_accepted(self, report: dict, slot: int, basis: str) -> None:
        self.assertEqual(report["expanded_slot"], slot)
        self.assertTrue(report["slot_verified"])
        self.assertEqual(report["reason"], "verified")
        self.assertEqual(report["verification_basis"], basis)

    # ---------------------------------------------------------------- positives
    def test_each_slot_is_read_from_its_own_geometry(self) -> None:
        for slot in range(1, 6):
            with self.subTest(slot=slot):
                report = observe_lineup_slot(lineup_frame(slot))
                self.assertEqual(report["page"], "duel_lineup")
                self.assert_accepted(report, slot, BASIS_GEOMETRY_ONLY)
                self.assertEqual(report["evidence"]["slot_from_panel"], slot)
                self.assertEqual(report["evidence"]["slot_from_button"], slot)
                self.assertEqual(report["evidence"]["size"], list(SUPPORTED_SIZE))

    def test_five_cells_and_panel_geometry_are_reported(self) -> None:
        report = observe_lineup_slot(lineup_frame(3))
        evidence = report["evidence"]
        cells = evidence["cells"]
        self.assertEqual([row["slot"] for row in cells], [1, 2, 3, 4, 5])
        self.assertEqual([row["expanded"] for row in cells],
                         [False, False, True, False, False])
        self.assertEqual(cells[2]["left"], evidence["panel"]["left"])
        self.assertEqual(cells[2]["right"], evidence["panel"]["right"])
        self.assertEqual(evidence["panel"]["right"] - evidence["panel"]["left"],
                         EXPANDED_WIDTH)
        self.assertEqual(evidence["pitch"], SLOT_PITCH)

    def test_all_markers_are_mapped_onto_collapsed_cells(self) -> None:
        report = observe_lineup_slot(lineup_frame(2))
        markers = report["evidence"]["collapsed_markers"]
        self.assertEqual(sorted(row["slot"] for row in markers), [1, 3, 4, 5])
        for row in markers:
            self.assertLessEqual(abs(row["offset"]), 1.0)

    # -------------------------------------------- verification basis & markers
    def test_geometry_only_stays_observable_without_any_marker(self) -> None:
        # 09-style and "already selected" style frames: every other car is
        # placed, so no collapsed cell carries a marker.  Two real no-marker
        # shapes must stay observable, and must declare *what* they verified.
        for slot in (1, 4):
            with self.subTest(slot=slot):
                report = observe_lineup_slot(lineup_frame(slot, markers=False))
                self.assert_accepted(report, slot, BASIS_GEOMETRY_ONLY)
                self.assertFalse(report["title_guard_passed"])
                self.assertIsNone(report["page_title"])
                self.assertFalse(report["ocr_used"])
                self.assertEqual(report["evidence"]["collapsed_markers"], [])
                self.assertFalse(report["evidence"]["collapsed_markers_present"])

    def test_strict_title_upgrades_the_basis_to_geometry_and_title(self) -> None:
        for title in ("资格赛", "挑战"):
            with self.subTest(title=title):
                report = observe_lineup_slot(
                    lineup_frame(4),
                    ocr=[ocr_row(title, title_box(), 0.99)])
                self.assert_accepted(report, 4, BASIS_GEOMETRY_AND_TITLE)
                self.assertTrue(report["title_guard_passed"])
                self.assertEqual(report["page_title"], title)
                self.assertTrue(report["ocr_used"])

    def test_no_title_means_geometry_only_never_a_title_basis(self) -> None:
        report = observe_lineup_slot(lineup_frame(2))
        self.assertNotEqual(report["verification_basis"], BASIS_GEOMETRY_AND_TITLE)
        self.assertFalse(report["title_guard_passed"])

    def test_partial_markers_keep_the_corroboration_semantics(self) -> None:
        # A collapsed marker is corroboration: present ones are reported and
        # mapped, missing ones are not required.
        report = observe_lineup_slot(lineup_frame(3, marker_slots=[1, 5]))
        self.assert_accepted(report, 3, BASIS_GEOMETRY_ONLY)
        markers = report["evidence"]["collapsed_markers"]
        self.assertEqual(sorted(row["slot"] for row in markers), [1, 5])
        self.assertTrue(report["evidence"]["collapsed_markers_present"])

    def test_missing_markers_are_not_an_assigned_lineup_failure(self) -> None:
        # Losing all four markers must read as "no corroboration", never as a
        # failure of an already-assigned lineup.
        report = observe_lineup_slot(lineup_frame(5, markers=False))
        self.assert_accepted(report, 5, BASIS_GEOMETRY_ONLY)
        self.assertEqual(report["evidence"]["collapsed_markers"], [])
        self.assertNotIn("assigned", report["reason"])
        self.assertNotIn("marker", report["reason"])

    # ------------------------------------------------------------------ refusals
    def test_unsupported_sizes_are_refused_without_rescaling(self) -> None:
        for size in ((1920, 1080), (2560, 1440), (1280, 719), (1279, 720), (720, 1280)):
            with self.subTest(size=size):
                frame = blank_frame(*size)
                frame[210:545, 60:792] = PANEL_COLOR
                bx, by, bw, bh = button_box(1)
                if frame.shape[1] > bx + bw:
                    frame[by:by + bh, bx:bx + bw] = BUTTON_COLOR
                report = observe_lineup_slot(frame)
                self.assert_refused(report, "unsupported_size")
                self.assertEqual(report["evidence"]["size"], list(size))
                self.assertEqual(report["evidence"]["supported"], list(SUPPORTED_SIZE))

    def test_blank_and_other_pages_have_no_expanded_slot(self) -> None:
        plain = observe_lineup_slot(blank_frame())
        self.assert_refused(plain, "no_expanded_button")
        self.assertEqual(plain["page"], "not_lineup")

        # A green control outside the lineup button band (vehicle detail page):
        detail = blank_frame()
        detail[625:690, 1045:1235] = BUTTON_COLOR
        self.assert_refused(observe_lineup_slot(detail), "no_expanded_button")

    def test_two_expanded_buttons_are_ambiguous(self) -> None:
        frame = lineup_frame(1)
        # A second, non-adjacent expanded selection button: the geometry can no
        # longer name one expanded cell.
        frame[495:545, 90:282] = BUTTON_COLOR
        report = observe_lineup_slot(frame)
        self.assert_refused(report, "multiple_expanded_buttons")
        self.assertEqual(report["page"], "ambiguous")
        self.assertEqual(report["evidence"]["button_candidates"], 2)

    def test_button_without_a_bright_panel_is_refused(self) -> None:
        frame = lineup_frame(1)
        left, right = panel_span(1)
        frame[210:545, left:right + 1] = BACKGROUND
        bx, by, bw, bh = button_box(1)
        frame[by:by + bh, bx:bx + bw] = BUTTON_COLOR
        self.assert_refused(observe_lineup_slot(frame), "expanded_panel_unverified")

    def test_panel_edge_far_from_button_is_refused(self) -> None:
        frame = lineup_frame(1)
        bx, by, bw, bh = button_box(1)
        frame[by:by + bh, bx:bx + bw] = BUTTON_COLOR
        # Blank the section between the button and the panel edge.
        frame[210:545, bx + bw + 20:792] = BACKGROUND
        self.assert_refused(observe_lineup_slot(frame), "expanded_panel_unverified")

    def test_panel_boundary_off_the_slot_grid_is_a_conflict(self) -> None:
        report = observe_lineup_slot(lineup_frame(1, shift=45))
        self.assert_refused(report, "slot_geometry_conflict")
        self.assertEqual(report["page"], "ambiguous")

    def test_marker_off_the_collapsed_grid_is_a_conflict(self) -> None:
        frame = lineup_frame(1)
        frame[220:530, 1225:1245] = MARKER_COLOR
        report = observe_lineup_slot(frame)
        self.assert_refused(report, "collapsed_marker_conflict")
        self.assertIn("collapsed_cell_centers", report["evidence"])

    # ------------------------------------------------------------- page title
    def test_title_region_matches_the_committed_pipeline_roi(self) -> None:
        self.assertEqual(tuple(LINEUP_TITLE_ROI), (62, 86, 110, 52))
        pipeline = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))
        rois = [
            rule["roi"]
            for node in pipeline.values() if isinstance(node, dict)
            for rule in node.get("all_of", []) if isinstance(rule, dict)
            if str(rule.get("template", "")).endswith("defense_qualifier_title.png")
        ]
        self.assertGreaterEqual(len(rois), 5)
        for roi in rois:
            self.assertEqual(roi, list(LINEUP_TITLE_ROI))

    def test_qualifier_and_challenge_titles_confirm_the_page(self) -> None:
        for title in ("资格赛", "挑战"):
            with self.subTest(title=title):
                report = observe_lineup_slot(
                    lineup_frame(4), ocr=[ocr_row(title, title_box())])
                self.assert_accepted(report, 4, BASIS_GEOMETRY_AND_TITLE)
                self.assertEqual(report["page_title"], title)
                self.assertTrue(report["title_guard_passed"])
                self.assertEqual(report["evidence"]["title_conflicts"], [])

    def test_garage_title_is_still_veto_evidence(self) -> None:
        report = observe_lineup_slot(
            lineup_frame(1), ocr=[ocr_row(SELECTION_PAGE_TITLE, title_box())])
        self.assert_refused(report, "page_title_conflict")
        self.assertEqual(report["page"], "not_lineup")
        self.assertEqual(report["page_title"], SELECTION_PAGE_TITLE)
        self.assertEqual(report["evidence"]["title_conflicts"], [SELECTION_PAGE_TITLE])

    def test_substring_titles_cannot_confirm_the_page(self) -> None:
        # Only the whole stripped string may confirm; no substring/prefix pass.
        for text in ("好友挑战", "每日挑战次数:3", "资格赛奖励", "挑战赛", "资格",
                     "今日挑战", "挑战资格赛", "资格赛挑战"):
            with self.subTest(text=text):
                report = observe_lineup_slot(
                    lineup_frame(2), ocr=[ocr_row(text, title_box())])
                self.assert_refused(report, "page_title_missing")
                self.assertIsNone(report["page_title"])

    def test_whitespace_only_padding_is_accepted_as_whole_string(self) -> None:
        report = observe_lineup_slot(
            lineup_frame(2), ocr=[ocr_row("  挑战  ", title_box())])
        self.assert_accepted(report, 2, BASIS_GEOMETRY_AND_TITLE)
        self.assertEqual(report["page_title"], "挑战")

    def test_confidence_floor_and_validity_are_enforced(self) -> None:
        below = TITLE_CONFIDENCE_FLOOR - 0.01
        cases: list[tuple[str, dict, bool]] = [
            ("at_floor", ocr_row("资格赛", title_box(), TITLE_CONFIDENCE_FLOOR), True),
            ("above_floor", ocr_row("资格赛", title_box(), 0.995), True),
            ("below_floor", ocr_row("资格赛", title_box(), below), False),
            ("zero", ocr_row("资格赛", title_box(), 0.0), False),
            ("negative", ocr_row("资格赛", title_box(), -0.1), False),
            ("above_one", ocr_row("资格赛", title_box(), 1.5), False),
            ("nan", ocr_row("资格赛", title_box(), float("nan")), False),
            ("inf", ocr_row("资格赛", title_box(), float("inf")), False),
            ("none", ocr_row("资格赛", title_box(), None), False),
            ("bool_true", ocr_row("资格赛", title_box(), True), False),
            ("string", ocr_row("资格赛", title_box(), "0.99"), False),
            ("missing", {"text": "资格赛", "box": title_box()}, False),
        ]
        for label, row, accepted in cases:
            with self.subTest(confidence=label):
                report = observe_lineup_slot(lineup_frame(1), ocr=[row])
                if accepted:
                    self.assert_accepted(report, 1, BASIS_GEOMETRY_AND_TITLE)
                    self.assertTrue(report["title_guard_passed"])
                else:
                    self.assert_refused(report, "page_title_missing")

    def test_two_different_titles_in_the_region_conflict(self) -> None:
        report = observe_lineup_slot(
            lineup_frame(3),
            ocr=[ocr_row("资格赛", title_box(90, 105)),
                 ocr_row("挑战", title_box(130, 120))])
        self.assert_refused(report, "page_title_conflict")
        self.assertEqual(report["page"], "ambiguous")
        self.assertIsNone(report["page_title"])
        self.assertEqual(report["evidence"]["title_conflicts"], ["资格赛", "挑战"])

    def test_repeated_identical_title_is_not_a_conflict(self) -> None:
        report = observe_lineup_slot(
            lineup_frame(3),
            ocr=[ocr_row("挑战", title_box(90, 105)),
                 ocr_row("挑战", title_box(130, 120)),
                 ocr_row("挑战", title_box(100, 110))])
        self.assert_accepted(report, 3, BASIS_GEOMETRY_AND_TITLE)
        self.assertEqual(report["page_title"], "挑战")
        self.assertEqual(report["evidence"]["title_conflicts"], [])

    def test_low_confidence_duplicate_cannot_create_a_conflict(self) -> None:
        # The second title is below the floor, so it is not evidence at all.
        report = observe_lineup_slot(
            lineup_frame(3),
            ocr=[ocr_row("挑战", title_box(90, 105)),
                 ocr_row("资格赛", title_box(130, 120), 0.42)])
        self.assert_accepted(report, 3, BASIS_GEOMETRY_AND_TITLE)
        self.assertEqual(report["page_title"], "挑战")
        self.assertEqual(report["evidence"]["title_conflicts"], [])

    def test_substring_veto_text_is_not_a_veto(self) -> None:
        # A veto needs the same strict whole-string + confidence rule; a
        # substring must not silently veto, and with no legal title the result
        # still refuses.
        report = observe_lineup_slot(
            lineup_frame(1), ocr=[ocr_row("返回车辆选择", title_box())])
        self.assert_refused(report, "page_title_missing")
        self.assertEqual(report["evidence"]["title_conflicts"], [])

    def test_map_names_cannot_verify_the_page_or_the_slot(self) -> None:
        rows = [
            ocr_row("花都疾驰", title_box(140, 120, 80, 25)),
            ocr_row("铁塔飞跃", title_box(150, 130, 80, 25)),
        ]
        report = observe_lineup_slot(lineup_frame(2), ocr=rows)
        self.assert_refused(report, "page_title_missing")
        self.assertIsNone(report["page_title"])
        self.assertEqual(report["evidence"]["title_conflicts"], [])

    def test_ocr_rows_without_a_box_are_ignored(self) -> None:
        report = observe_lineup_slot(lineup_frame(2), ocr=[ocr_row("资格赛")])
        self.assert_refused(report, "page_title_missing")
        self.assertEqual(report["evidence"]["title_rows"]["invalid"], 1)

    def test_empty_ocr_evidence_refuses_rather_than_guesses(self) -> None:
        self.assert_refused(observe_lineup_slot(lineup_frame(1), ocr=[]),
                            "page_title_missing")

    def test_ocr_outside_the_title_region_is_ignored(self) -> None:
        # A "资格赛" string far from the title region must not confirm the page.
        report = observe_lineup_slot(
            lineup_frame(1), ocr=[ocr_row("资格赛", title_box(240, 110))])
        self.assert_refused(report, "page_title_missing")
        self.assertEqual(report["evidence"]["title_rows"]["outside_region"], 1)

    def test_text_inside_the_former_wide_region_is_now_outside(self) -> None:
        # The region was narrowed to the committed pipeline ROI (62,86,110,52);
        # a box centred at x=240 was inside the old 250-wide band and must no
        # longer count.
        for center in ((198, 110), (240, 110), (76, 170), (100, 60)):
            with self.subTest(center=center):
                report = observe_lineup_slot(
                    lineup_frame(1), ocr=[ocr_row("资格赛", title_box(*center))])
                self.assert_refused(report, "page_title_missing")
                self.assertEqual(report["evidence"]["title_rows"]["outside_region"], 1)

    # ------------------------------------------------- unusable OCR entries
    def test_unusable_boxes_and_rows_are_ignored_without_crashing(self) -> None:
        bad_rows: list[object] = [
            ocr_row("资格赛", None),                       # no box
            {"text": "资格赛"},                             # box key missing
            ocr_row("资格赛", "not-a-box"),                 # non-numeric box
            ocr_row("资格赛", [1, 2]),                      # too short
            ocr_row("资格赛", [70, 100, 0, 30]),            # zero width
            ocr_row("资格赛", [70, 100, 80, 0]),            # zero height
            ocr_row("资格赛", [70, 100, -80, 30]),          # negative width
            ocr_row("资格赛", [float("nan"), 100, 80, 30]),  # NaN origin
            ocr_row("资格赛", [70, float("inf"), 80, 30]),   # Inf origin
            ocr_row("资格赛", [70, 100, float("nan"), 30]),  # NaN width
            ocr_row("资格赛", ["a", 100, 80, 30]),           # non-numeric element
            ocr_row("资格赛", {"x": 70, "y": 100}),          # mapping, not a box
            ocr_row(123, title_box()),                      # non-string text
            ocr_row("", title_box()),                       # empty text
            ocr_row(None, title_box()),                     # missing text
            {"box": title_box(), "confidence": 0.99},       # text key missing
            "not-a-row",                                    # not a mapping
            None,                                           # not a mapping
            42,                                             # not a mapping
        ]
        for index, row in enumerate(bad_rows):
            with self.subTest(row=index):
                try:
                    report = observe_lineup_slot(lineup_frame(1), ocr=[row])
                except Exception as error:  # noqa: BLE001 - failure message aid
                    self.fail(f"bad OCR row {index} crashed the observer: {error!r}")
                self.assert_refused(report, "page_title_missing")
                self.assertEqual(report["evidence"]["title_rows"]["invalid"], 1)
                self.assertEqual(report["evidence"]["title_rows"]["in_region"], 0)
                self.assertEqual(report["evidence"]["title_region_matches"], [])

    def test_bad_rows_do_not_mask_a_valid_title(self) -> None:
        report = observe_lineup_slot(
            lineup_frame(5),
            ocr=["junk", ocr_row("资格赛", title_box(), 0.97), {"text": "x"}])
        self.assert_accepted(report, 5, BASIS_GEOMETRY_AND_TITLE)
        self.assertEqual(report["page_title"], "资格赛")
        counts = report["evidence"]["title_rows"]
        self.assertEqual(counts["supplied"], 3)
        self.assertEqual(counts["invalid"], 2)
        self.assertEqual(counts["in_region"], 1)
        self.assertEqual(counts["supplied"],
                         counts["invalid"] + counts["outside_region"] + counts["in_region"])

    def test_non_iterable_ocr_evidence_is_treated_as_absent(self) -> None:
        # An unsafe container must not take the observer down either.
        for value in (7, 7.5, object()):
            with self.subTest(ocr=type(value).__name__):
                report = observe_lineup_slot(lineup_frame(1), ocr=value)
                self.assert_refused(report, "page_title_missing")

    # ------------------------------------- title evidence survives early exits
    def test_geometry_early_exit_still_reports_a_title_conflict(self) -> None:
        report = observe_lineup_slot(
            blank_frame(),
            ocr=[ocr_row("资格赛", title_box(90, 105)),
                 ocr_row("挑战", title_box(130, 120))])
        self.assert_refused(report, "no_expanded_button")
        self.assertEqual(report["evidence"]["title_conflicts"], ["资格赛", "挑战"])
        self.assertIsNone(report["page_title"])

    def test_geometry_early_exit_still_reports_a_veto_title(self) -> None:
        report = observe_lineup_slot(
            blank_frame(), ocr=[ocr_row(SELECTION_PAGE_TITLE, title_box())])
        self.assert_refused(report, "no_expanded_button")
        self.assertEqual(report["page_title"], SELECTION_PAGE_TITLE)
        self.assertEqual(report["evidence"]["title_conflicts"], [SELECTION_PAGE_TITLE])

    def test_geometry_conflict_exit_keeps_the_detected_title_conflict(self) -> None:
        report = observe_lineup_slot(
            lineup_frame(1, shift=45),
            ocr=[ocr_row("资格赛", title_box(90, 105)),
                 ocr_row("挑战", title_box(130, 120))])
        self.assert_refused(report, "slot_geometry_conflict")
        self.assertEqual(report["evidence"]["title_conflicts"], ["资格赛", "挑战"])

    def test_unsupported_size_still_reports_title_evidence(self) -> None:
        report = observe_lineup_slot(
            blank_frame(1920, 1080), ocr=[ocr_row(SELECTION_PAGE_TITLE, title_box())])
        self.assert_refused(report, "unsupported_size")
        self.assertEqual(report["evidence"]["title_conflicts"], [SELECTION_PAGE_TITLE])

    def test_early_exit_without_ocr_reports_an_empty_conflict_list(self) -> None:
        report = observe_lineup_slot(blank_frame())
        self.assertEqual(report["evidence"]["title_conflicts"], [])
        self.assertEqual(report["evidence"]["title_region_matches"], [])

    def test_plain_run_always_carries_an_empty_conflict_list(self) -> None:
        report = observe_lineup_slot(lineup_frame(2))
        self.assertEqual(report["evidence"]["title_conflicts"], [])

    # ----------------------------------------------------------- determinism
    def test_repeated_calls_are_deterministic_and_stateless(self) -> None:
        frames = [lineup_frame(slot) for slot in (1, 5, 3, 1)]
        reports = [observe_lineup_slot(frame) for frame in frames]
        self.assertEqual([row["expanded_slot"] for row in reports], [1, 5, 3, 1])
        self.assertEqual(reports[0], reports[3])
        again = observe_lineup_slot(frames[1])
        self.assertEqual(again, reports[1])
        snapshot = frames[0].copy()
        self.assertTrue(np.array_equal(snapshot, frames[0]))

    def test_input_frame_is_not_mutated(self) -> None:
        frame = lineup_frame(5)
        before = frame.copy()
        observe_lineup_slot(frame)
        self.assertTrue(np.array_equal(frame, before))

    # --------------------------------------------------------------- contracts
    def test_no_expected_slot_channel_exists(self) -> None:
        parameters = list(inspect.signature(observe_lineup_slot).parameters)
        self.assertEqual(parameters, ["frame", "ocr"])
        with self.assertRaises(TypeError):
            observe_lineup_slot(lineup_frame(1), expected_slot=1)  # type: ignore[call-arg]

    def test_malformed_frames_raise_instead_of_returning_a_slot(self) -> None:
        with self.assertRaises(TypeError):
            observe_lineup_slot([[0] * 3])  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            observe_lineup_slot(np.zeros((720, 1280), dtype=np.uint8))
        with self.assertRaises(ValueError):
            observe_lineup_slot(np.zeros((720, 1280, 3), dtype=np.float32))

    def test_result_reason_matches_slot_verified(self) -> None:
        verified = observe_lineup_slot(lineup_frame(1))
        self.assertTrue(verified["slot_verified"])
        self.assertEqual(verified["reason"], "verified")
        refused = observe_lineup_slot(blank_frame())
        self.assertFalse(refused["slot_verified"])

    def test_no_execution_permission_field_exists(self) -> None:
        # slot_verified is *not* an action authorisation: the report declares a
        # verification basis and nothing that a click could be gated on.
        for report in (observe_lineup_slot(lineup_frame(1)),
                       observe_lineup_slot(lineup_frame(1),
                                           ocr=[ocr_row("挑战", title_box())]),
                       observe_lineup_slot(blank_frame())):
            with self.subTest(basis=report["verification_basis"]):
                self.assertEqual(
                    set(report),
                    {"page", "expanded_slot", "slot_verified", "verification_basis",
                     "title_guard_passed", "reason", "page_title", "ocr_used", "evidence"})
                for banned in ("can_click", "action_ready", "click_allowed", "allowed",
                               "authorized", "may_click", "executable", "safe_to_act"):
                    self.assertNotIn(banned, report)

    # ----------------------------------------------------- offline/off-device
    def test_module_stays_offline_and_off_device(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported, {"__future__", "cv2", "numpy", "typing"})

        forbidden_calls = {
            # device / agent surface
            "scan", "assign_visible", "Controller", "post_click", "post_swipe", "run_task",
            # console and filesystem
            "open", "print", "input", "glob", "listdir", "walk", "makedirs", "remove",
            "rmtree", "rename", "read_text", "write_text", "read_bytes", "write_bytes",
            # image / array file I/O (the 05ER finding F7 gap)
            "imread", "imreadmulti", "imwrite", "imdecode", "imencode", "fromfile",
            "tofile", "load", "loads", "loadtxt", "savetxt", "save", "savez",
            "savez_compressed", "genfromtxt", "VideoCapture", "VideoWriter", "FileStorage",
        }
        called: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    called.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called.add(func.attr)
        self.assertEqual(called & forbidden_calls, set())
        source_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertEqual(
            source_names & {"Controller", "tasker", "adb", "controller", "Path"}, set())

    def test_normal_observation_never_touches_a_capture_or_io_api(self) -> None:
        # Behavioural complement to the AST gate: patch the common I/O entry
        # points so any use raises, then observe a normal frame.
        blocked: list[tuple[object, str]] = [
            (builtins, "open"),
            (np, "fromfile"), (np, "load"), (np, "loadtxt"), (np, "save"),
            (np, "savetxt"), (np, "savez"), (np, "genfromtxt"),
        ]
        try:
            import cv2
        except ImportError:  # pragma: no cover - cv2 is a hard dependency
            self.skipTest("cv2 unavailable")
        blocked += [(cv2, name) for name in
                    ("imread", "imreadmulti", "imwrite", "imdecode", "imencode",
                     "VideoCapture", "VideoWriter", "FileStorage")]

        with contextlib.ExitStack() as stack:
            used: list[str] = []
            patches = []
            for module, name in blocked:
                if not hasattr(module, name):
                    continue

                def explode(*args, _name=name, **kwargs):
                    used.append(_name)
                    raise AssertionError(f"observer used forbidden I/O API {_name}")

                patches.append(stack.enter_context(
                    mock.patch.object(module, name, side_effect=explode)))
            report = observe_lineup_slot(lineup_frame(2))
            self.assert_accepted(report, 2, BASIS_GEOMETRY_ONLY)
            with_title = observe_lineup_slot(
                lineup_frame(2), ocr=[ocr_row("资格赛", title_box())])
            self.assert_accepted(with_title, 2, BASIS_GEOMETRY_AND_TITLE)
            for patch in patches:
                self.assertFalse(patch.called)
            self.assertEqual(used, [])


if __name__ == "__main__":
    unittest.main()
