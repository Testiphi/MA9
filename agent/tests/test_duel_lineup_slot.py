"""Controlled tests for the read-only Duel lineup slot observer.

Every frame here is synthesised in-process from the published geometry: no
account screenshot, no capture fixture and no device is used.  The fixed
1280x720 sample replay lives in the 05E private evidence directory instead.
"""

from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_lineup_slot import (BUTTON_CENTER_BASE, BUTTON_COLOR_LOWER,
                                        EXPANDED_WIDTH, LINEUP_TITLE_ROI,
                                        PANEL_RIGHT_BASE, SLOT_PITCH, STRIP_LEFT,
                                        SUPPORTED_SIZE, observe_lineup_slot)

MODULE_PATH = Path(__file__).resolve().parents[1] / "ma9_agent/duel_lineup_slot.py"

BACKGROUND = (60, 25, 45)
PANEL_COLOR = (200, 90, 140)
BUTTON_COLOR = (20, 240, 180)
MARKER_COLOR = (210, 60, 160)


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


def collapsed_centers(slot: int, panel_right: int) -> list[int]:
    centers = [STRIP_LEFT + SLOT_PITCH / 2 + SLOT_PITCH * (index - 1)
               for index in range(1, slot)]
    centers += [panel_right + SLOT_PITCH / 2 + SLOT_PITCH * (index - slot - 1)
                for index in range(slot + 1, 6)]
    return centers


def lineup_frame(slot: int, *, markers: bool = True, panel_top: int = 210,
                 panel_bottom: int = 545, shift: int = 0) -> np.ndarray:
    """Draw the five-cell lineup: one bright expanded panel, four markers."""
    frame = blank_frame()
    left, right = panel_span(slot, shift=shift)
    frame[panel_top:panel_bottom, left:right + 1] = PANEL_COLOR
    if markers:
        for center in collapsed_centers(slot, right):
            x = int(round(center))
            frame[220:530, x - 10:x + 10] = MARKER_COLOR
    bx, by, bw, bh = button_box(slot)
    frame[by:by + bh, bx:bx + bw] = BUTTON_COLOR
    return frame


def ocr_row(text: str, box: list[int] | None = None) -> dict:
    row: dict = {"text": text, "confidence": 0.99}
    if box is not None:
        row["box"] = box
    return row


class LineupSlotObserverTest(unittest.TestCase):
    def assert_refused(self, report: dict, reason: str) -> None:
        self.assertIsNone(report["expanded_slot"])
        self.assertFalse(report["slot_verified"])
        self.assertEqual(report["reason"], reason)

    # ---------------------------------------------------------------- positives
    def test_each_slot_is_read_from_its_own_geometry(self) -> None:
        for slot in range(1, 6):
            with self.subTest(slot=slot):
                report = observe_lineup_slot(lineup_frame(slot))
                self.assertEqual(report["page"], "duel_lineup")
                self.assertEqual(report["reason"], "verified")
                self.assertTrue(report["slot_verified"])
                self.assertEqual(report["expanded_slot"], slot)
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

    def test_assigned_collapsed_cells_without_markers_still_verify(self) -> None:
        # 09-style frame: every other car is already placed, so the collapsed
        # cells carry no marker.  The panel edge plus the button still decide.
        report = observe_lineup_slot(lineup_frame(1, markers=False))
        self.assertEqual(report["expanded_slot"], 1)
        self.assertEqual(report["evidence"]["collapsed_markers"], [])
        self.assertFalse(report["evidence"]["collapsed_markers_present"])

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
    def test_qualifier_and_challenge_titles_confirm_the_page(self) -> None:
        x, y, _width, _height = LINEUP_TITLE_ROI
        for title in ("资格赛", "挑战"):
            with self.subTest(title=title):
                report = observe_lineup_slot(
                    lineup_frame(4), ocr=[ocr_row(title, [x + 10, y + 20, 80, 30])])
                self.assertEqual(report["expanded_slot"], 4)
                self.assertEqual(report["page_title"], title)
                self.assertTrue(report["ocr_used"])

    def test_garage_title_is_not_a_lineup_page(self) -> None:
        x, y, _width, _height = LINEUP_TITLE_ROI
        report = observe_lineup_slot(
            lineup_frame(1), ocr=[ocr_row("车辆选择", [x - 5, y + 10, 90, 30])])
        self.assert_refused(report, "page_title_conflict")
        self.assertEqual(report["page_title"], "车辆选择")

    def test_map_names_cannot_verify_the_page_or_the_slot(self) -> None:
        x, y, _width, _height = LINEUP_TITLE_ROI
        rows = [
            ocr_row("花都疾驰", [x + 100, y + 60, 80, 25]),
            ocr_row("铁塔飞跃", [x + 100, y + 90, 80, 25]),
        ]
        report = observe_lineup_slot(lineup_frame(2), ocr=rows)
        self.assert_refused(report, "page_title_missing")
        self.assertIsNone(report["page_title"])

    def test_ocr_rows_without_a_box_are_ignored(self) -> None:
        report = observe_lineup_slot(lineup_frame(2), ocr=[ocr_row("资格赛")])
        self.assert_refused(report, "page_title_missing")

    def test_empty_ocr_evidence_refuses_rather_than_guesses(self) -> None:
        self.assert_refused(observe_lineup_slot(lineup_frame(1), ocr=[]),
                            "page_title_missing")

    def test_ocr_outside_the_title_region_is_ignored(self) -> None:
        # A "资格赛" string far from the title region must not confirm the page.
        report = observe_lineup_slot(
            lineup_frame(1), ocr=[ocr_row("资格赛", [900, 640, 90, 30])])
        self.assert_refused(report, "page_title_missing")

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

    def test_module_stays_offline_and_off_device(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported, {"__future__", "cv2", "numpy", "typing"})

        forbidden_calls = {"open", "print", "scan", "assign_visible", "Controller",
                           "post_click", "post_swipe", "run_task"}
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
            source_names & {"Controller", "tasker", "adb", "controller"}, set())


if __name__ == "__main__":
    unittest.main()
