"""Controlled tests for the read-only Duel lineup five-map reader.

Every frame here is synthesised in-process from the published lineup geometry
and every OCR row is a frozen literal: no account screenshot, no capture
fixture, no OCR engine, no device and no filesystem access.  The native 1280x720
replay lives in the 05O private evidence directory instead.

Two calibration facts are locked from the committed code rather than restated:
the geometry constants come from ``duel_lineup_slot`` (the slot observer) and the
reference matching is delegated to ``duel_map_screen.read_five_tracks``.  The
tests assert the *reason* the new layer exists: the committed parser publishes an
x-sorted ordinal that renumbers when a cell is unreadable, so the five maps are
placed into the observer's real cell spans here.

Nothing in this module grants permission: ``maps_verified`` means "five maps and
their real slot ordinals were read", never "a click is allowed".
"""

from __future__ import annotations

import ast
import copy
import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent import duel_lineup_maps as maps_module
from ma9_agent.duel_lineup_maps import (AMBIGUITY_MARGIN, LINEUP_TITLE_ROI,
                                        MAP_ROI, MAX_ATTEMPTS, MAX_TIMEOUT,
                                        PAIR_X_TOLERANCE, ROW_TOP_RANGE,
                                        observe_lineup_maps,
                                        read_stable_lineup_maps)
from ma9_agent.duel_lineup_slot import (BUTTON_CENTER_BASE, EXPANDED_WIDTH,
                                        PANEL_RIGHT_BASE, SLOT_PITCH,
                                        STRIP_LEFT, SUPPORTED_SIZE,
                                        observe_lineup_slot)
from ma9_agent.duel_map_screen import read_five_tracks

MODULE_PATH = Path(__file__).resolve().parents[1] / "ma9_agent/duel_lineup_maps.py"
MAP_SCREEN_PATH = Path(__file__).resolve().parents[1] / "ma9_agent/duel_map_screen.py"
DEFENSE_PATH = Path(__file__).resolve().parents[1] / "ma9_agent/duel_defense_setup.py"

BACKGROUND = (60, 25, 45)
PANEL_COLOR = (200, 90, 140)
BUTTON_COLOR = (20, 240, 180)

#: A small stand-in reference table.  ``花都疾驰`` deliberately owns two entries
#: so the tests can build a near neighbour without inventing a match.
PAIRS = [
    ("花都疾驰", "铁塔飞跃"),
    ("热带天堂", "地狱谷"),
    ("季风秘境", "碎石山路"),
    ("海港博物馆", "海洋爆冲"),
    ("古老斗技场", "旧时风情"),
]
PAIR_SIX = {"big": "明珠港口", "small": "东方巴黎"}
TABLE = {"tracks": [{"big": big, "small": small} for big, small in PAIRS]}

#: Distinguishes "argument omitted" from an explicit ``None`` reference.
DEFAULT = object()

QUALIFIER_ROW = {"text": "资格赛", "box": [62, 90, 101, 39], "confidence": 0.99982}
CHALLENGE_ROW = {"text": "挑战", "box": [62, 86, 74, 44], "confidence": 0.999099}
GARAGE_ROW = {"text": "车辆选择", "box": [62, 90, 100, 39], "confidence": 0.999}


def blank_frame(width: int = 1280, height: int = 720) -> np.ndarray:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :] = BACKGROUND
    return frame


def panel_span(slot: int) -> tuple[int, int]:
    right = PANEL_RIGHT_BASE + SLOT_PITCH * (slot - 1)
    return right - EXPANDED_WIDTH, right


def lineup_frame(slot: int) -> np.ndarray:
    """The published geometry: one bright expanded panel and one green button."""
    frame = blank_frame()
    left, right = panel_span(slot)
    frame[210:545, left:right + 1] = PANEL_COLOR
    center = BUTTON_CENTER_BASE + SLOT_PITCH * (slot - 1)
    bx = int(round(center - 192 / 2))
    frame[495:545, bx:bx + 192] = BUTTON_COLOR
    return frame


def cell_spans(slot: int) -> list[dict]:
    """Independent re-derivation of the five cell spans for ``slot`` expanded."""
    right = PANEL_RIGHT_BASE + SLOT_PITCH * (slot - 1)
    left = right - EXPANDED_WIDTH
    cells = []
    for index in range(1, 6):
        if index == slot:
            span = (left, right)
        elif index < slot:
            cell_left = STRIP_LEFT + SLOT_PITCH * (index - 1)
            span = (cell_left, cell_left + SLOT_PITCH - 1)
        else:
            cell_left = right + 1 + SLOT_PITCH * (index - slot - 1)
            span = (cell_left, cell_left + SLOT_PITCH - 1)
        cells.append({"slot": index, "left": span[0], "right": span[1],
                      "expanded": index == slot})
    return cells


def map_row(text: str, center: float, top: int, width: int = 60) -> dict:
    return {"text": text, "box": [int(round(center - width / 2)), top, width, 35],
            "confidence": 0.99}


def pair_rows(slot: int, index: int, *, pair_index: int | None = None,
              big_center: float | None = None,
              small_center: float | None = None, width: int | None = None) -> list[dict]:
    """The two map lines of cell ``index``; ``pair_index`` picks which pair."""
    cell = cell_spans(slot)[index - 1]
    center = (cell["left"] + cell["right"]) / 2
    size = width if width is not None else (120 if cell["expanded"] else 60)
    big, small = PAIRS[(index if pair_index is None else pair_index) - 1]
    return [map_row(big, center if big_center is None else big_center, 216, size),
            map_row(small, center if small_center is None else small_center, 250, size)]


def lineup_rows(slot: int, *, title: dict | None = QUALIFIER_ROW,
                skip: set[int] | None = None) -> list[dict]:
    rows = [] if title is None else [dict(title)]
    for index in range(1, 6):
        if skip and index in skip:
            continue
        rows.extend(pair_rows(slot, index))
    return rows


class LineupMapsTest(unittest.TestCase):
    def assert_refused(self, report: dict, reason: str) -> None:
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["tracks"], [])
        self.assertEqual(report["reason"], reason)

    def observe(self, frame, rows, reference=DEFAULT):
        return observe_lineup_maps(
            frame, ocr=rows, reference=TABLE if reference is DEFAULT else reference)

    # ------------------------------------------------------- slot alignment
    def test_each_expanded_slot_maps_the_five_pairs_to_its_own_slots(self) -> None:
        for slot in range(1, 6):
            with self.subTest(slot=slot):
                report = self.observe(lineup_frame(slot), lineup_rows(slot))
                self.assertTrue(report["maps_verified"])
                self.assertEqual(report["status"], "verified")
                self.assertEqual(report["reason"], "lineup_maps_verified")
                self.assertEqual(report["expanded_slot"], slot)
                self.assertEqual(report["page_title"], "资格赛")
                self.assertEqual([row["slot"] for row in report["tracks"]],
                                 [1, 2, 3, 4, 5])
                self.assertEqual([(row["big"], row["small"]) for row in report["tracks"]],
                                 PAIRS)
                self.assertEqual(report["evidence"]["slots_present"], [1, 2, 3, 4, 5])
                self.assertEqual(report["evidence"]["slots_missing"], [])

    def test_a_track_carries_both_line_boxes_and_the_cell_it_belongs_to(self) -> None:
        report = self.observe(lineup_frame(3), lineup_rows(3))
        cells = cell_spans(3)
        for row in report["tracks"]:
            with self.subTest(slot=row["slot"]):
                cell = cells[row["slot"] - 1]
                self.assertEqual(row["cell"], cell)
                self.assertTrue(cell["left"] <= row["big_center_x"] <= cell["right"])
                self.assertTrue(cell["left"] <= row["small_center_x"] <= cell["right"])
                for box in (row["big_box"], row["small_box"]):
                    self.assertEqual(len(box), 4)
                self.assertEqual(row["confidence"], 1.0)

    def test_the_committed_parser_renumbers_but_this_layer_does_not(self) -> None:
        # The whole reason for the new layer: with cell 3 unreadable the
        # committed parser publishes slots 1..4, which would silently shift the
        # 4th and 5th maps forward.  The new layer keeps the real 1,2,4,5.
        rows = lineup_rows(3, skip={3})
        committed = read_five_tracks(rows, TABLE)
        self.assertEqual([row["slot"] for row in committed["tracks"]], [1, 2, 3, 4])
        report = self.observe(lineup_frame(3), rows)
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["status"], "partial")
        self.assertEqual([row["slot"] for row in report["tracks"]], [1, 2, 4, 5])
        self.assertEqual(report["evidence"]["slots_present"], [1, 2, 4, 5])
        self.assertEqual(report["evidence"]["slots_missing"], [3])

    def test_a_missing_map_leaves_a_hole_instead_of_shifting_slots(self) -> None:
        for missing in range(1, 6):
            with self.subTest(missing=missing):
                report = self.observe(lineup_frame(2),
                                      lineup_rows(2, skip={missing}))
                self.assertFalse(report["maps_verified"])
                self.assertEqual(report["reason"], "maps_incomplete")
                self.assertNotIn(missing, report["evidence"]["slots_present"])
                self.assertEqual(report["evidence"]["slots_missing"], [missing])
                self.assertNotIn(missing,
                                 [row["slot"] for row in report["tracks"]])

    def test_four_groups_are_partial_never_complete(self) -> None:
        rows = lineup_rows(1)[:-2]
        report = self.observe(lineup_frame(1), rows)
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["status"], "partial")
        self.assertEqual([row["slot"] for row in report["tracks"]], [1, 2, 3, 4])

    def test_a_missing_small_line_drops_that_map_only(self) -> None:
        rows = [row for row in lineup_rows(4)
                if row["text"] != PAIRS[2][1]]
        report = self.observe(lineup_frame(4), rows)
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["evidence"]["slots_missing"], [3])
        self.assertEqual([row["slot"] for row in report["tracks"]], [1, 2, 4, 5])

    def test_a_pair_whose_lines_straddle_two_cells_is_refused(self) -> None:
        # Big line inside cell 2, small line inside cell 3: the parser grouped
        # them, the geometry says they belong to different slots.
        rows = [dict(QUALIFIER_ROW)]
        rows.extend(pair_rows(3, 1))
        rows.extend(pair_rows(3, 2, big_center=286.0, small_center=289.0))
        rows.extend(pair_rows(3, 3))
        rows.extend(pair_rows(3, 4))
        rows.extend(pair_rows(3, 5))
        report = self.observe(lineup_frame(3), rows)
        self.assertFalse(report["maps_verified"])
        rejected = report["evidence"]["rejected_tracks"]
        # The straddling small line is also a third candidate in cell 3, so
        # its otherwise valid pair is conservatively withheld from partials.
        self.assertEqual({row["reject"] for row in rejected},
                         {"pair_spans_cells", "map_cell_candidates_conflict"})
        self.assertEqual(sorted(row["slot"] for row in report["tracks"]),
                         [1, 4, 5])
        self.assertEqual(report["evidence"]["slots_missing"], [2, 3])

    def test_a_pair_whose_lines_drift_apart_in_one_cell_is_refused(self) -> None:
        rows = [dict(QUALIFIER_ROW)]
        for index in range(1, 6):
            if index == 2:
                rows.extend(pair_rows(3, 2, small_center=230.5 + PAIR_X_TOLERANCE + 10))
            else:
                rows.extend(pair_rows(3, index))
        report = self.observe(lineup_frame(3), rows)
        self.assertFalse(report["maps_verified"])
        self.assertEqual([row["reject"] for row in report["evidence"]["rejected_tracks"]],
                         ["pair_lines_disagree"])
        self.assertEqual(report["evidence"]["slots_missing"], [2])

    def test_a_map_read_outside_every_cell_is_refused(self) -> None:
        rows = lineup_rows(3)
        extra = PAIR_SIX
        rows.append(map_row(extra["big"], 20.0, 216))
        rows.append(map_row(extra["small"], 20.0, 250))
        report = self.observe(lineup_frame(3), rows, reference={"tracks": [
            *[{"big": big, "small": small} for big, small in PAIRS], extra]})
        self.assertFalse(report["maps_verified"])
        self.assertEqual([row["reject"] for row in report["evidence"]["rejected_tracks"]],
                         ["map_outside_slot_cells"])
        self.assertEqual([row["slot"] for row in report["tracks"]], [1, 2, 3, 4, 5])
        self.assertEqual(report["reason"], "maps_incomplete")

    def test_the_same_map_on_two_cells_is_refused(self) -> None:
        rows = [dict(QUALIFIER_ROW)]
        for index in range(1, 6):
            rows.extend(pair_rows(1, index,
                                  pair_index=2 if index in (2, 4) else index))
        report = self.observe(lineup_frame(1), rows)
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["reason"], "duplicate_maps")
        self.assertEqual(report["status"], "partial")
        self.assertEqual([row["slot"] for row in report["tracks"]], [1, 2, 3, 4, 5])
        observed = [(row["big"], row["small"]) for row in report["tracks"]]
        self.assertEqual(observed.count(PAIRS[1]), 2)

    # --------------------------------------------- same-cell candidate audit
    def conflicting_rows(self, *, text: str = "完全不同赛道", top: int = 270):
        """``lineup_rows(3)`` plus a second *small* candidate in cell 1.

        The extra row copies cell 1's small line, changes its text and moves it
        lower - still inside the ``200..275`` band.  The committed parser reads
        only a group's first two rows, so before the cell audit this candidate
        was silently discarded and the frame still reported five verified maps.
        """
        rows = lineup_rows(3)
        extra = copy.deepcopy(rows[2])            # cell 1's small map line
        extra["text"] = text
        extra["box"][1] = top
        rows.append(extra)
        return rows

    def conflicting_table(self, small: str = "完全不同赛道") -> dict:
        return {"tracks": [*TABLE["tracks"],
                           {"big": PAIRS[0][0], "small": small}]}

    def test_a_conflicting_second_small_map_line_in_one_cell_is_refused(self):
        report = self.observe(lineup_frame(3), self.conflicting_rows(),
                              reference=self.conflicting_table())
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["reason"], "map_row_conflict")
        self.assertEqual(report["expanded_slot"], 3)
        # The refused cell is not re-numbered: the other four keep real slots.
        self.assertEqual([row["slot"] for row in report["tracks"]], [2, 3, 4, 5])
        self.assertEqual(report["evidence"]["slots_missing"], [1])
        rejected = report["evidence"]["rejected_tracks"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["reject"], "map_cell_candidates_conflict")
        self.assertEqual(rejected[0]["slot"], 1)
        self.assertEqual([row["text"] for row in rejected[0]["cell_rows"]],
                         [PAIRS[0][0], PAIRS[0][1], "完全不同赛道"])

    def test_a_conflicting_second_big_map_line_in_one_cell_is_refused(self):
        # The same omission with a *big* map name as the discarded row: the cell
        # audit refuses on the row set, not on which side the extra line is.
        report = self.observe(lineup_frame(3), self.conflicting_rows(text=PAIRS[1][0]),
                              reference=self.conflicting_table())
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["reason"], "map_row_conflict")
        self.assertEqual([row["slot"] for row in report["tracks"]], [2, 3, 4, 5])
        self.assertEqual([row["text"] for row
                          in report["evidence"]["rejected_tracks"][0]["cell_rows"]],
                         [PAIRS[0][0], PAIRS[0][1], PAIRS[1][0]])

    def test_the_verdict_of_a_conflicting_cell_ignores_the_row_input_order(self):
        rows = self.conflicting_rows()
        reports = [self.observe(lineup_frame(3), rows,
                                reference=self.conflicting_table()),
                   self.observe(lineup_frame(3), list(reversed(rows)),
                                reference=self.conflicting_table())]
        for report in reports:
            self.assertFalse(report["maps_verified"])
            self.assertEqual(report["reason"], "map_row_conflict")
            self.assertEqual([row["slot"] for row in report["tracks"]],
                             [2, 3, 4, 5])

    def test_every_row_in_the_wide_geometry_cell_is_audited(self):
        # Slot 3 spans x=288..1019.  A second row 70 px from the selected
        # pair forms an isolated parser x-group, yet remains in that same cell.
        cell = cell_spans(3)[2]
        center = (cell["left"] + cell["right"]) / 2
        for text, top in (("完全不同赛道", 270), ("完全不同地图", 202)):
            with self.subTest(text=text):
                rows = lineup_rows(3)
                rows.append(map_row(text, center + 70, top))
                report = self.observe(lineup_frame(3), rows)
                self.assertFalse(report["maps_verified"])
                self.assertEqual(report["reason"], "map_row_conflict")
                self.assertEqual([row["slot"] for row in report["tracks"]],
                                 [1, 2, 4, 5])
                self.assertEqual(report["evidence"]["slots_missing"], [3])
                conflicts = [row for row in report["evidence"]["rejected_tracks"]
                             if row["reject"] == "map_cell_candidates_conflict"]
                self.assertEqual(len(conflicts), 1)
                self.assertEqual(conflicts[0]["slot"], 3)
                self.assertIn(text, [row["text"] for row in conflicts[0]["cell_rows"]])

    def test_parser_x_group_boundary_does_not_change_the_cell_verdict(self):
        cell = cell_spans(3)[2]
        center = (cell["left"] + cell["right"]) / 2
        for delta in (54, 55, 70):
            with self.subTest(delta=delta):
                rows = lineup_rows(3)
                extra = map_row("完全不同赛道", center + delta, 270)
                original_center = rows[5]["box"][0] + rows[5]["box"][2] / 2
                extra["box"][0] = int(original_center + delta - extra["box"][2] / 2)
                rows.append(extra)
                parser = read_five_tracks(rows, TABLE)
                self.assertEqual(parser["observed_groups"],
                                 5 if delta == 54 else 6)
                report = self.observe(lineup_frame(3), rows)
                self.assertFalse(report["maps_verified"])
                self.assertEqual(report["reason"], "map_row_conflict")
                self.assertEqual(report["evidence"]["slots_missing"], [3])

    def test_rows_excluded_from_the_map_band_do_not_create_a_conflict(self):
        cell = cell_spans(3)[2]
        center = (cell["left"] + cell["right"]) / 2 + 70
        rows = lineup_rows(3)
        rows.extend([map_row("完全不同地图", center, 199),
                     map_row("完全不同赛道", center, 276),
                     map_row("选择车辆", center, 250),
                     map_row("English", center, 250)])
        faint = map_row("完全不同赛道", center, 250)
        faint["confidence"] = 0.69
        rows.append(faint)
        report = self.observe(lineup_frame(3), rows)
        self.assertTrue(report["maps_verified"])
        self.assertEqual(report["evidence"]["slots_missing"], [])

    def test_an_equal_height_pair_leaves_the_cell_unresolved(self):
        # Two map lines at one height cannot be ordered into big/small; both
        # insertion orders must refuse rather than let the sort order decide.
        for order in ((0, 1), (1, 0)):
            with self.subTest(order=order):
                rows = [dict(QUALIFIER_ROW)]
                for index in range(1, 6):
                    lines = pair_rows(3, index)
                    if index == 1:
                        flat = [map_row(row["text"], row["box"][0] + 30, 250)
                                for row in lines]
                        lines = [flat[position] for position in order]
                    rows.extend(lines)
                report = self.observe(lineup_frame(3), rows)
                self.assertFalse(report["maps_verified"])
                self.assertEqual([row["slot"] for row in report["tracks"]],
                                 [2, 3, 4, 5])
                self.assertEqual(report["evidence"]["slots_missing"], [1])

    def test_an_exact_duplicate_map_line_is_deduped_not_refused(self):
        # A legitimate OCR repeat is the *same physical line*: identical text and
        # identical box.  It is collapsed, so it can neither block the read nor
        # be miscounted as a second candidate.
        rows = lineup_rows(3)
        rows.append(copy.deepcopy(rows[2]))       # cell 1's small line, again
        report = self.observe(lineup_frame(3), rows)
        self.assertTrue(report["maps_verified"])
        self.assertEqual(report["evidence"]["duplicate_rows"], 1)
        self.assertEqual([row["slot"] for row in report["tracks"]], [1, 2, 3, 4, 5])

    def test_the_same_text_at_a_different_height_is_a_candidate_not_a_repeat(self):
        # De-duplication is by physical line, never by text alone: the same name
        # printed at two heights is two candidates and must be refused.
        rows = lineup_rows(3)
        near = copy.deepcopy(rows[2])
        near["box"][1] = 270                      # same text, different line
        rows.append(near)
        report = self.observe(lineup_frame(3), rows)
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["reason"], "map_row_conflict")
        self.assertEqual([row["slot"] for row in report["tracks"]], [2, 3, 4, 5])

    def test_a_non_lineup_page_with_a_conflicting_cell_is_still_refused(self):
        # The cell audit never overrides the page gate: off the lineup page the
        # verdict stays the page-level refusal, with no map rows reported.
        rows = [dict(GARAGE_ROW)] + self.conflicting_rows()[1:]
        report = self.observe(lineup_frame(3), rows,
                              reference=self.conflicting_table())
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["reason"], "lineup_page_unverified")
        self.assertEqual(report["tracks"], [])
        self.assertIsNone(report["expanded_slot"])

    # ------------------------------------------------- reference uniqueness
    def test_a_reference_that_lists_the_same_pair_twice_is_refused(self) -> None:
        table = {"tracks": [*TABLE["tracks"], dict(TABLE["tracks"][2])]}
        report = self.observe(lineup_frame(1), lineup_rows(1), reference=table)
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["reason"], "reference_ambiguous")
        rejected = report["evidence"]["rejected_tracks"]
        self.assertEqual([row["reject"] for row in rejected],
                         ["reference_match_ambiguous"])
        self.assertEqual(rejected[0]["margin"], 0.0)
        self.assertEqual(rejected[0]["observed"], list(PAIRS[2]))

    def test_a_near_neighbour_candidate_is_refused(self) -> None:
        table = {"tracks": [*TABLE["tracks"],
                            {"big": "花都疾驰", "small": "铁塔飞越"}]}
        report = self.observe(lineup_frame(1), lineup_rows(1), reference=table)
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["reason"], "reference_ambiguous")
        rejected = report["evidence"]["rejected_tracks"]
        self.assertEqual(rejected[0]["observed"], list(PAIRS[0]))
        self.assertEqual(rejected[0]["runner_up"], ["花都疾驰", "铁塔飞越"])
        self.assertLess(rejected[0]["margin"], AMBIGUITY_MARGIN)

    def test_a_candidate_below_the_parser_thresholds_does_not_block(self) -> None:
        table = {"tracks": [*TABLE["tracks"],
                            {"big": "花都疾驰", "small": "飞沙走石"}]}
        report = self.observe(lineup_frame(1), lineup_rows(1), reference=table)
        self.assertTrue(report["maps_verified"])
        self.assertEqual(report["tracks"][0]["margin"], None)
        self.assertEqual(report["tracks"][0]["runner_up"], None)

    def test_the_verdict_never_depends_on_the_directory_order(self) -> None:
        decoy = {"big": "花都疾驰", "small": "铁塔飞越"}
        first = {"tracks": [decoy, *TABLE["tracks"]]}
        last = {"tracks": [*TABLE["tracks"], decoy]}
        one = self.observe(lineup_frame(1), lineup_rows(1), reference=last)
        two = self.observe(lineup_frame(1), lineup_rows(1), reference=first)
        for report in (one, two):
            self.assertFalse(report["maps_verified"])
            self.assertEqual(report["reason"], "reference_ambiguous")
            self.assertEqual(report["evidence"]["rejected_tracks"][0]["margin"], 0.25)

    # -------------------------------------------------------- page identity
    def test_the_challenge_page_is_an_unsupported_environment(self) -> None:
        rows = [dict(CHALLENGE_ROW)] + lineup_rows(1)[1:]
        report = self.observe(lineup_frame(1), rows)
        self.assertEqual(report["status"], "unsupported_environment")
        self.assertEqual(report["reason"], "challenge_page_unsupported")
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["tracks"], [])
        self.assertEqual(report["expanded_slot"], 1)
        self.assertEqual(report["page_title"], "挑战")

    def test_the_garage_title_is_still_veto_evidence(self) -> None:
        report = self.observe(lineup_frame(1),
                              [dict(GARAGE_ROW)] + lineup_rows(1)[1:])
        self.assert_refused(report, "lineup_page_unverified")
        self.assertIn("车辆选择",
                      report["evidence"]["observer"]["title_conflicts"])

    def test_a_missing_or_conflicting_title_is_refused(self) -> None:
        without = self.observe(lineup_frame(1), lineup_rows(1, title=None))
        self.assert_refused(without, "lineup_page_unverified")
        self.assertNotEqual(without["page_title"], "资格赛")
        conflict = self.observe(lineup_frame(1),
                                [dict(QUALIFIER_ROW), dict(CHALLENGE_ROW)]
                                + lineup_rows(1)[1:])
        self.assert_refused(conflict, "lineup_page_unverified")
        self.assertEqual(conflict["evidence"]["observer"]["reason"],
                         "page_title_conflict")

    def test_an_unsupported_size_is_refused_without_being_rescaled(self) -> None:
        for size in ((640, 360), (1920, 1080), (1280, 719)):
            with self.subTest(size=size):
                frame = np.zeros((size[1], size[0], 3), dtype=np.uint8)
                report = self.observe(frame, lineup_rows(1))
                self.assert_refused(report, "unsupported_size")
                self.assertIsNone(report["expanded_slot"])

    def test_a_bad_reference_table_fails_closed_before_the_frame(self) -> None:
        bad = [None, {}, {"tracks": []}, {"tracks": None}, {"tracks": [{}]},
               {"tracks": [{"big": "甲"}]}, {"tracks": [{"big": "", "small": "乙"}]},
               {"tracks": [{"big": "甲", "small": "   "}]}, {"tracks": ["甲"]},
               {"tracks": "甲"}, 0, "tracks"]
        for reference in bad:
            with self.subTest(reference=reference):
                # ``object()`` is not even a frame: the table must be refused
                # first, so a broken table can never reach image code.
                report = observe_lineup_maps(object(), ocr=[], reference=reference)
                self.assert_refused(report, "reference_invalid")
                self.assertEqual(report["evidence"]["reference_tracks"], 0)
        self.assertIsNone(maps_module._normalize_reference([("甲", "乙")]))
        self.assertEqual(maps_module._normalize_reference(TABLE), PAIRS)
        self.assertEqual(maps_module._normalize_reference(TABLE["tracks"]), PAIRS)

    def test_a_bare_list_reference_is_accepted(self) -> None:
        report = observe_lineup_maps(lineup_frame(1), ocr=lineup_rows(1),
                                     reference=[{"big": big, "small": small}
                                                for big, small in PAIRS])
        self.assertTrue(report["maps_verified"])

    def test_malformed_rows_never_raise_and_are_counted(self) -> None:
        junk = [{"text": "甲", "box": [1, 2]},
                {"text": "乙", "box": None, "confidence": 0.9},
                {"text": "丙", "box": [1, 200, 10], "confidence": "0.9"},
                {"text": None, "box": [1, 200, 10, 10], "confidence": 0.9},
                {"text": "丁", "box": [1, 200, float("nan"), 10],
                 "confidence": float("inf")},
                "not a row", None, 7]
        report = self.observe(lineup_frame(2), lineup_rows(2) + junk)
        self.assertTrue(report["maps_verified"])
        self.assertEqual(report["evidence"]["malformed_rows"], len(junk))
        empty = self.observe(lineup_frame(2), [dict(QUALIFIER_ROW)] + junk)
        self.assert_refused(empty, "maps_incomplete")
        self.assertEqual(empty["evidence"]["map_rows"], 0)
        self.assertEqual(empty["evidence"]["malformed_rows"], len(junk))

    def test_malformed_frames_raise_instead_of_reporting_maps(self) -> None:
        for frame in (None, [[1, 2, 3]], "frame"):
            with self.subTest(frame=type(frame).__name__):
                with self.assertRaises((TypeError, ValueError)):
                    self.observe(frame, lineup_rows(1))
        with self.assertRaises(ValueError):
            self.observe(np.zeros((720, 1280), dtype=np.uint8), lineup_rows(1))

    # ------------------------------------------------------ purity and shape
    def test_the_observation_is_pure_and_does_not_mutate_its_inputs(self) -> None:
        rows = lineup_rows(3)
        table = copy.deepcopy(TABLE)
        frame = lineup_frame(3)
        before_rows, before_table = copy.deepcopy(rows), copy.deepcopy(table)
        first = self.observe(frame, rows)
        again = self.observe(frame, rows)
        self.assertEqual(first, again)
        self.assertEqual(rows, before_rows)
        self.assertEqual(table, before_table)

    def test_the_reported_shape_carries_no_execution_permission(self) -> None:
        reports = [self.observe(lineup_frame(1), lineup_rows(1)),
                   self.observe(blank_frame(), lineup_rows(1)),
                   observe_lineup_maps(object(), ocr=[], reference={})]
        for report in reports:
            with self.subTest(reason=report["reason"]):
                self.assertEqual(
                    set(report),
                    {"status", "maps_verified", "expanded_slot", "page_title",
                     "tracks", "reason", "evidence", "read_only",
                     "selection_attempted", "starts_race"})
                self.assertTrue(report["read_only"])
                self.assertFalse(report["selection_attempted"])
                self.assertFalse(report["starts_race"])
                for banned in ("can_click", "action_ready", "allowed", "authorized",
                               "clickable", "expected_slot", "slot"):
                    self.assertNotIn(banned, report)

    def test_a_refusal_keeps_the_real_slot_evidence(self) -> None:
        report = self.observe(lineup_frame(4), lineup_rows(4, skip={2}))
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["expanded_slot"], 4)
        self.assertEqual(report["page_title"], "资格赛")
        self.assertEqual([row["slot"] for row in report["tracks"]], [1, 3, 4, 5])
        self.assertEqual(report["evidence"]["observer"]["reason"], "verified")
        self.assertEqual(len(report["evidence"]["observer"]["cells"]), 5)


class StableLineupMapsTest(unittest.TestCase):
    """The clock and the OCR/capture boundary are the only things faked."""

    def setUp(self) -> None:
        self.case = {"frames": [], "rows": {}}

    def source(self):
        case = self.case

        def frame_of(context):
            index = min(case["called"], len(case["frames"]) - 1)
            case["called"] += 1
            return case["frames"][index]

        def ocr_roi(context, frame, roi):
            case["ocr"].append((roi, id(frame)))
            left, top, width, height = roi
            rows = case["rows"].get(id(frame), [])
            return [row for row in rows
                    if isinstance(row.get("box"), list) and len(row["box"]) >= 4
                    and left <= row["box"][0] + row["box"][2] / 2 <= left + width
                    and top <= row["box"][1] + row["box"][3] / 2 <= top + height]

        return frame_of, ocr_roi

    def register(self, slot: int, **kwargs):
        frame = lineup_frame(slot)
        rows = lineup_rows(slot, **kwargs)
        self.case["frames"].append(frame)
        self.case["rows"][id(frame)] = rows
        return frame

    def run_reader(self, *, attempts=6, timeout=30.0, interval=0.0,
                   reference=DEFAULT, frames=None):
        self.case["called"] = 0
        self.case["ocr"] = []
        if frames is not None:
            self.case["frames"] = frames
        frame_of, ocr_roi = self.source()
        with mock.patch.object(maps_module, "frame_of", side_effect=frame_of), \
             mock.patch.object(maps_module, "ocr_roi", side_effect=ocr_roi), \
             mock.patch.object(maps_module, "sleep", return_value=None):
            return read_stable_lineup_maps(
                object(), TABLE if reference is DEFAULT else reference,
                attempts=attempts, timeout=timeout, interval=interval)

    # ------------------------------------------------------------ positives
    def test_two_identical_frames_confirm_and_stop_early(self) -> None:
        self.register(3)
        self.register(3)
        report = self.run_reader(attempts=6)
        self.assertTrue(report["maps_verified"])
        self.assertTrue(report["stable"])
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["reason"], "stable_lineup_maps_verified")
        self.assertEqual(report["samples"], 2)
        self.assertEqual(self.case["called"], 2)
        self.assertEqual([row["slot"] for row in report["tracks"]], [1, 2, 3, 4, 5])
        self.assertEqual(report["expanded_slot"], 3)

    def test_a_swapped_slot_rebreaks_the_pair_then_reconfirms(self) -> None:
        self.register(1)
        self.register(5)
        self.register(5)
        report = self.run_reader()
        self.assertTrue(report["maps_verified"])
        self.assertEqual(report["samples"], 3)
        self.assertEqual(report["expanded_slot"], 5)

    def test_small_box_jitter_does_not_break_the_same_semantics(self) -> None:
        first = self.register(2)
        second = self.register(2)
        self.case["rows"][id(second)] = [
            {**row, "box": [row["box"][0] + 2, row["box"][1], row["box"][2], row["box"][3]]}
            for row in self.case["rows"][id(second)]]
        self.case["frames"] = [first, second]
        report = self.run_reader()
        self.assertTrue(report["maps_verified"])
        self.assertEqual(report["samples"], 2)

    def test_the_same_frame_feeds_both_ocr_regions(self) -> None:
        self.register(4)
        self.register(4)
        report = self.run_reader()
        self.assertTrue(report["maps_verified"])
        self.assertEqual(self.case["called"], 2)
        self.assertEqual(len(self.case["ocr"]), 4)
        self.assertEqual([roi for roi, _ in self.case["ocr"]],
                         [LINEUP_TITLE_ROI, MAP_ROI, LINEUP_TITLE_ROI, MAP_ROI])
        self.assertEqual(self.case["ocr"][0][1], self.case["ocr"][1][1])
        self.assertEqual(self.case["ocr"][2][1], self.case["ocr"][3][1])

    def test_duplicate_rows_from_both_regions_are_merged_once(self) -> None:
        frame = lineup_frame(1)
        rows = lineup_rows(1)
        self.case["frames"] = [frame, frame]
        self.case["rows"][id(frame)] = rows
        self.case["called"] = 0
        self.case["ocr"] = []

        def ocr_roi(context, image, roi):
            self.case["ocr"].append((roi, id(image)))
            return list(rows)          # a backend that ignores the ROI and repeats

        with mock.patch.object(maps_module, "frame_of", return_value=frame), \
             mock.patch.object(maps_module, "ocr_roi", side_effect=ocr_roi), \
             mock.patch.object(maps_module, "sleep", return_value=None):
            report = read_stable_lineup_maps(object(), TABLE, attempts=2)
        self.assertTrue(report["maps_verified"])
        self.assertEqual(len(report["tracks"]), 5)

    # ------------------------------------------------------------ negatives
    def test_alternating_slots_never_confirm(self) -> None:
        for _ in range(2):
            self.register(1)
            self.register(5)
        report = self.run_reader(attempts=4)
        self.assertFalse(report["maps_verified"])
        self.assertFalse(report["stable"])
        self.assertEqual(report["status"], "unverified")
        self.assertEqual(report["samples"], 4)
        self.assertEqual(report["reason"], "lineup_maps_unstable")
        self.assertEqual(report["latest"]["reason"], "lineup_maps_verified")
        self.assertEqual(report["latest"]["expanded_slot"], 5)

    def test_a_conflicting_cell_never_confirms_over_two_frames(self):
        # Two *independent* frames carrying the same second candidate are not an
        # agreement on the maps: the cell never resolves, so the pair is broken
        # on every sample and the reader stays unverified.
        table = {"tracks": [*TABLE["tracks"],
                            {"big": PAIRS[0][0], "small": "完全不同赛道"}]}
        rows = lineup_rows(3)
        extra = copy.deepcopy(rows[2])
        extra["text"] = "完全不同赛道"
        extra["box"][1] = 270
        rows.append(extra)
        frame = lineup_frame(3)
        self.case["rows"][id(frame)] = rows
        report = self.run_reader(attempts=3, reference=table, frames=[frame, frame])
        self.assertFalse(report["maps_verified"])
        self.assertFalse(report["stable"])
        self.assertEqual(report["status"], "unverified")
        self.assertEqual(report["reason"], "lineup_maps_unstable")
        self.assertEqual(report["samples"], 3)
        self.assertEqual(report["latest"]["reason"], "map_row_conflict")
        self.assertEqual([row["slot"] for row in report["latest"]["tracks"]],
                         [2, 3, 4, 5])
        self.assertTrue(report["read_only"])
        self.assertFalse(report["selection_attempted"])
        self.assertFalse(report["starts_race"])

    def test_an_isolated_x_group_in_the_same_cell_never_confirms(self):
        cell = cell_spans(3)[2]
        center = (cell["left"] + cell["right"]) / 2
        rows = lineup_rows(3)
        rows.append(map_row("完全不同地图", center + 70, 202))
        frames = [lineup_frame(3), lineup_frame(3)]
        for frame in frames:
            self.case["rows"][id(frame)] = rows
        report = self.run_reader(attempts=2, frames=frames)
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["samples"], 2)
        self.assertEqual(report["latest"]["reason"], "map_row_conflict")
        self.assertEqual([row["slot"] for row in report["latest"]["tracks"]],
                         [1, 2, 4, 5])

    def test_the_attempt_budget_caps_the_samples(self) -> None:
        for slot in (1, 2, 3, 4, 5):
            self.register(slot)
        report = self.run_reader(attempts=3)
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["samples"], 3)
        self.assertEqual(self.case["called"], 3)

    def test_a_challenge_page_never_confirms(self) -> None:
        for _ in range(2):
            self.register(1, title=CHALLENGE_ROW)
        report = self.run_reader(attempts=2)
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["samples"], 2)
        self.assertEqual(report["reason"], "challenge_page_unsupported")
        self.assertEqual(report["tracks"], [])

    def test_an_observation_error_is_recorded_and_breaks_the_pair(self) -> None:
        self.register(1)              # sample 1
        self.register(2)              # sample 3
        self.register(2)              # sample 4
        calls = {"n": 0}
        frame_of, ocr_roi = self.source()

        def exploding_frame_of(context):
            calls["n"] += 1
            if calls["n"] == 2:       # sample 2 fails while capturing
                raise RuntimeError("capture failed")
            return frame_of(context)

        self.case["called"] = 0
        self.case["ocr"] = []
        with mock.patch.object(maps_module, "frame_of", side_effect=exploding_frame_of), \
             mock.patch.object(maps_module, "ocr_roi", side_effect=ocr_roi), \
             mock.patch.object(maps_module, "sleep", return_value=None):
            report = read_stable_lineup_maps(object(), TABLE, attempts=4)
        self.assertTrue(report["maps_verified"])
        self.assertEqual(report["samples"], 4)
        self.assertEqual(report["error_count"], 1)
        self.assertEqual(len(report["errors"]), 1)
        self.assertIn("capture failed", report["errors"][0])
        self.assertEqual(report["expanded_slot"], 2)

    def test_a_bad_reference_fails_closed_before_any_capture(self) -> None:
        self.register(1)
        for reference in (None, {}, {"tracks": []}, {"tracks": [{}]}):
            with self.subTest(reference=reference):
                report = self.run_reader(reference=reference)
                self.assertFalse(report["maps_verified"])
                self.assertEqual(report["reason"], "reference_invalid")
                self.assertEqual(report["samples"], 0)
                self.assertEqual(self.case["called"], 0)
                self.assertEqual(self.case["ocr"], [])

    # ---------------------------------------------------------- parameters
    def test_parameters_are_validated_before_the_context_is_touched(self) -> None:
        self.register(1)
        bad = [{"attempts": True}, {"attempts": 1}, {"attempts": MAX_ATTEMPTS + 1},
               {"attempts": 10.0}, {"attempts": "10"}, {"attempts": None},
               {"timeout": True}, {"timeout": 0}, {"timeout": -1.0},
               {"timeout": MAX_TIMEOUT + 1}, {"timeout": float("inf")},
               {"timeout": float("nan")}, {"timeout": "30"},
               {"interval": True}, {"interval": -0.1}, {"interval": 1.5},
               {"interval": float("inf")}, {"interval": "0.3"}]
        for kwargs in bad:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError) as caught:
                    self.run_reader(**kwargs)
                self.assertTrue(str(caught.exception))
                self.assertEqual(self.case["called"], 0)
                self.assertEqual(self.case["ocr"], [])

    def test_the_deadline_is_created_once_and_gates_new_captures(self) -> None:
        for slot in (1, 2, 3, 4, 5):
            self.register(slot)
        clock = {"calls": 0}

        def fake_monotonic():
            clock["calls"] += 1
            return 0.0 if clock["calls"] <= 3 else 999.0

        frame_of, ocr_roi = self.source()
        self.case["called"] = 0
        self.case["ocr"] = []
        with mock.patch.object(maps_module, "monotonic", side_effect=fake_monotonic), \
             mock.patch.object(maps_module, "frame_of", side_effect=frame_of), \
             mock.patch.object(maps_module, "ocr_roi", side_effect=ocr_roi), \
             mock.patch.object(maps_module, "sleep", return_value=None):
            report = read_stable_lineup_maps(object(), TABLE, attempts=5,
                                             timeout=30.0, interval=0.0)
        self.assertFalse(report["maps_verified"])
        # One sample was taken, then the single deadline stopped the second
        # capture; a per-sample deadline would have kept going to five.
        self.assertEqual(report["samples"], 1)
        self.assertEqual(self.case["called"], 1)
        self.assertGreaterEqual(report["elapsed_seconds"], report["budget"]["timeout"])

    def test_the_reader_reports_its_budget_and_latest_evidence(self) -> None:
        for _ in range(3):
            self.register(2, skip={3})
            self.register(5, skip={3})
        report = self.run_reader(attempts=6, timeout=7.5, interval=0.1)
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["budget"], {"attempts": 6, "timeout": 7.5,
                                            "interval": 0.1,
                                            "max_recorded_errors": 10})
        self.assertEqual(report["samples"], 6)
        self.assertEqual(report["latest"]["status"], "partial")
        self.assertEqual(report["latest"]["expanded_slot"], 5)
        self.assertEqual(report["latest"]["reason"], "maps_incomplete")
        self.assertEqual(report["latest"]["evidence"]["slots_missing"], [3])
        self.assertTrue(report["latest"]["read_only"])
        self.assertTrue(report["read_only"])
        self.assertFalse(report["selection_attempted"])
        self.assertFalse(report["starts_race"])
        for banned in ("can_click", "action_ready", "allowed", "authorized"):
            self.assertNotIn(banned, report)

    def test_a_refusal_never_leaves_a_verified_result_behind(self) -> None:
        self.register(3)
        report = self.run_reader(attempts=2, frames=[])
        self.assertFalse(report["maps_verified"])
        self.assertFalse(report["stable"])
        self.assertEqual(report["tracks"], [])
        self.assertIsNone(report["expanded_slot"])


class ReaderHygieneTest(unittest.TestCase):
    def test_the_module_stays_off_device_and_off_disk(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported, {"__future__", "collections", "time", "typing",
                                    "duel_lineup_slot", "duel_map_screen",
                                    "selection_runtime"})

        forbidden_calls = {
            "scan", "assign_visible", "run_task", "post_click", "post_swipe",
            "post_screencap", "post_connection", "plan_attack", "enter_slot",
            "open", "print", "input", "glob", "listdir", "walk", "makedirs",
            "remove", "rmtree", "rename", "read_text", "write_text",
            "read_bytes", "write_bytes", "imread", "imwrite", "imdecode",
            "fromfile", "tofile", "load", "loads", "save",
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
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertEqual(names & {"Controller", "tasker", "adb", "controller",
                                  "Path"}, set())

    def test_the_production_map_and_defense_modules_are_untouched(self) -> None:
        screen = inspect.signature(read_five_tracks)
        self.assertEqual(list(screen.parameters), ["ocr", "reference"])
        source = MAP_SCREEN_PATH.read_text(encoding="utf-8")
        self.assertNotIn("duel_lineup_maps", source)
        defense = DEFENSE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("duel_lineup_maps", defense)
        self.assertIn("def _read_tracks(context: Any, reference: dict[str, Any], *,",
                      defense)
        signature = inspect.signature(observe_lineup_slot)
        self.assertEqual(list(signature.parameters), ["frame", "ocr"])

    def test_only_the_guarded_read_only_action_wires_the_map_reader(self) -> None:
        # The separately authorised GUI entry may call the isolated wrapper.
        # Other actions and the production defense path must stay independent.
        root = MODULE_PATH.parents[2]
        action_tree = ast.parse((root / "agent/runtime_action.py")
                                .read_text(encoding="utf-8"))
        actions = [node for node in action_tree.body if isinstance(node, ast.ClassDef)]
        wired = [node for node in actions if node.name == "DuelLineupMapsTestAction"]
        self.assertEqual(len(wired), 1)
        imports = [node for node in ast.walk(action_tree)
                   if isinstance(node, ast.ImportFrom)
                   and node.module and "duel_lineup_maps" in node.module]
        self.assertEqual(len(imports), 1)
        self.assertIn(imports[0], ast.walk(wired[0]))
        self.assertEqual(imports[0].module, "ma9_agent.duel_lineup_maps_test")
        self.assertEqual([(alias.name, alias.asname) for alias in imports[0].names],
                         [("run_lineup_maps_test", None)])
        calls = [node for node in ast.walk(action_tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id == "run_lineup_maps_test"]
        self.assertEqual(len(calls), 1)
        run = next(node for node in wired[0].body
                   if isinstance(node, ast.FunctionDef) and node.name == "run")
        self.assertTrue(any(isinstance(node, ast.Delete)
                            and any(isinstance(target, ast.Name) and target.id == "argv"
                                    for target in node.targets)
                            for node in ast.walk(run)))
        self.assertTrue(any(isinstance(node, ast.Try) and calls[0] in ast.walk(node)
                            for node in ast.walk(run)))
        self.assertEqual([ast.unparse(arg) for arg in calls[0].args],
                         ["context", "find_project_root()"])
        self.assertEqual(calls[0].keywords, [])
        self.assertNotIn("read_stable_lineup_maps",
                         (root / "agent/runtime_action.py").read_text(encoding="utf-8"))
        self.assertNotIn("duel_lineup_maps",
                         DEFENSE_PATH.read_text(encoding="utf-8"))

    def test_the_row_band_mirrors_the_committed_parser(self) -> None:
        source = MAP_SCREEN_PATH.read_text(encoding="utf-8")
        self.assertIn("200 <= row[\"box\"][1] <= 275", source)
        self.assertIn("row[\"confidence\"] >= .70", source)
        self.assertIn('row["text"] not in {"为该赛道", "选择车辆"}', source)
        self.assertEqual(ROW_TOP_RANGE, (200, 275))
        self.assertEqual(len(SUPPORTED_SIZE), 2)


if __name__ == "__main__":
    unittest.main()
