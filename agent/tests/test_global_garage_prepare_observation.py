"""Offline tests for the global-garage prepare Observation adapter (05AK-B).

Two fixture kinds, always labelled:

* real frames read-only from ``captures/global_garage`` (tests skip with an
  explicit reason when that user directory is absent) and a real-OCR
  transcription of the two panel frames from the 05AJ evidence replay
  (``MA9-evidence/20260928-05AJ-root-takeover/final-real-ocr-replay.json``);
* synthetic frames/OCR built in-memory (panel cells, section badges, dotted
  dividers, shifted lists) -- they are counterexamples and rule probes, never
  real switch positives.

Planner integration tests consume the adapter's Observations directly; the
synthetic ActionResult receipts used to reach later planner phases are marked
as such and produce no production receipt claim.

Real-frame fixture location (05AK-B1): a lane worktree is itself a full
checkout and also carries the orchestration marker, so the sample set is
found by walking the test file's ancestors for a marker root that ALSO has
``captures/global_garage`` (the user's untracked samples live only in the
true MA9 root).  Both a root checkout (``MA9/agent/tests/...``) and a nested
worktree (``MA9/MA9-worktrees/<lane>/agent/tests/...``) therefore resolve to
the same sample set.  An explicit environment path may override it:
``MA9_CAPTURES_GLOBAL_GARAGE`` (the directory itself) or ``MA9_ROOT`` (the
MA9 root).  No disk-wide search is performed; when no samples are reachable
the real-frame tests skip with an explicit reason.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent import global_garage_prepare_plan as plan
from ma9_agent import global_garage_prepare_observation as adapter

MA9_MARKER = Path("agent") / "orchestration" / "state.json"


def _resolve_ma9_root(start: Path) -> Path | None:
    """Nearest ancestor of ``start`` holding the MA9 orchestration marker."""
    for base in start.resolve().parents:
        if (base / MA9_MARKER).is_file():
            return base
    return None


def _find_captures(start: Path) -> Path:
    """Nearest marker ancestor of ``start`` that also carries the samples."""
    for base in start.resolve().parents:
        if (base / MA9_MARKER).is_file() and (base / "captures" / "global_garage").is_dir():
            return base / "captures" / "global_garage"
    return start.resolve().parent / "captures_unreachable"


def _captures_dir() -> Path:
    """Locate captures/global_garage; explicit env paths take precedence."""
    env_dir = os.environ.get("MA9_CAPTURES_GLOBAL_GARAGE")
    if env_dir:
        return Path(env_dir)
    env_root = os.environ.get("MA9_ROOT")
    if env_root:
        return Path(env_root) / "captures" / "global_garage"
    return _find_captures(Path(__file__))


CAPTURES = _captures_dir()
SID = "sess-obs"
HAVE_CAPTURES = CAPTURES.is_dir()


def imread_unicode(path: Path) -> np.ndarray:
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


def real(name: str) -> np.ndarray:
    return imread_unicode(CAPTURES / name)


def ocr_item(text: str, box, confidence: float = .95) -> dict:
    """Build an OCR item, preserving huge ints and NaN/inf floats verbatim."""
    cleaned = []
    for v in box:
        if isinstance(v, int) and not isinstance(v, bool):
            cleaned.append(v)
        elif isinstance(v, float) and math.isfinite(v) and v.is_integer():
            cleaned.append(int(v))
        else:
            cleaned.append(v)
    return {"text": text, "confidence": confidence, "box": cleaned}


# Real-OCR transcription of the two panel frames (05AJ replay, source SHA
# 8f4bcd13... is the iPad frame; the panel records carry per-file SHA256 in
# the replay file; labels transcribed verbatim with original boxes).
PANEL_OCR_OFF = [
    ocr_item("筛选条件", [50, 83, 120, 41], 1.0),
    ocr_item("排序方式", [52, 266, 120, 37], 1.0),
    ocr_item("升序", [52, 299, 44, 25], 1.0),
    ocr_item("品牌", [64, 125, 64, 41], 1.0),
    ocr_item("已拥有", [64, 194, 82, 34], .996),
    ocr_item("星级", [58, 330, 68, 43], 1.0),
    ocr_item("性能分", [64, 399, 81, 35], 1.0),
    ocr_item("完成", [177, 586, 64, 37], 1.0),
    ocr_item("ACURA", [450, 194, 98, 24], .999),
]
PANEL_OCR_ON = [
    ocr_item("筛选条件", [50, 83, 120, 41], 1.0),
    ocr_item("排序方式", [52, 266, 118, 37], 1.0),
    ocr_item("升序", [52, 299, 44, 25], 1.0),
    ocr_item("品牌", [64, 125, 62, 41], 1.0),
    ocr_item("已拥有", [64, 194, 82, 34], .996),
    ocr_item("星级", [61, 334, 64, 36], 1.0),
    ocr_item("性能分", [64, 399, 81, 35], 1.0),
    ocr_item("完成", [177, 586, 64, 37], 1.0),
    ocr_item("ACURA", [450, 194, 99, 24], .999),
]


# --------------------------------------------------------------------------- #
# synthetic frame builders
# --------------------------------------------------------------------------- #
def panel_frame(checked: str | None = None, flat: str | None = None,
                covered: str | None = None) -> np.ndarray:
    """A synthetic filter panel; cells mirror the real calibrated ROIs.

    ``checked``/``flat``/``covered`` pick one control cell (brand/stars/
    performance/owned) to fill yellow-green / flatten / cover.
    """
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    image[:, :] = (30, 35, 25)                     # darkened backdrop ring
    image[52:668, 37:1243] = (60, 70, 55)          # panel body + border
    cells = dict(adapter.CONTROL_ROIS)
    cells["owned"] = (314, 188, 47, 48)
    for name, (x, y, w, h) in cells.items():
        if flat == name:
            image[y:y + h, x:x + w] = (100, 100, 100)
            continue
        if covered == name:
            image[y:y + h, x:x + w] = (60, 70, 55)
            continue
        image[y:y + h, x:x + w] = (140, 150, 130)  # bright outline
        interior = (44, 190, 150) if checked == name else (40, 45, 35)
        image[y + 5:y + h - 5, x + 5:x + w - 5] = interior
    return image


def list_frame(card_x: int = 219, badge_letter: str = "D", badge_center: int = 158,
               dots: bool = True, cards: bool = True, top_button: bool = False
               ) -> np.ndarray:
    """A synthetic garage list with calibrated D-start geometry."""
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    image[:, :] = (18, 18, 18)
    image[86:142, 100:1216] = (147, 155, 161)      # bright distinct header
    if cards:
        for top, bottom in ((225, 423), (441, 640)):
            for x in (card_x, card_x + 414, card_x + 828):
                image[top:bottom, x:x + 399] = (150, 150, 150)
                image[top:bottom, x + 10:x + 389:20] = (55, 55, 55)
    if top_button:                                  # top D jump button, not the rail
        image[96:144, 733:789] = (200, 200, 200)
        cv2.putText(image, "D", (745, 136), cv2.FONT_HERSHEY_SIMPLEX, 1.1,
                    (0, 0, 0), 3, cv2.LINE_AA)
    if dots:
        for y in range(225, 640, 8):
            image[y:y + 4, badge_center - 1:badge_center + 2] = (220, 220, 220)
    if badge_letter:
        bx, by = badge_center - 24, 408
        image[by:by + 48, bx:bx + 48] = (210, 210, 210)
        cv2.putText(image, badge_letter, (bx + 6, by + 38), cv2.FONT_HERSHEY_SIMPLEX,
                    1.1, (0, 0, 0), 3, cv2.LINE_AA)
    return image


def rail_background(sample: np.ndarray) -> np.ndarray:
    """Mean rail colour of a real list frame, used by ablation fills."""
    return sample[560:620, 110:200].reshape(-1, 3).mean(axis=0).astype(np.uint8)


def observe(image, ocr=None, sid=SID, fid=1):
    return adapter.observe(image, ocr, session_id=sid, frame_id=fid)


# --------------------------------------------------------------------------- #
# case 1: real-frame acceptance with per-field independent reasons
# --------------------------------------------------------------------------- #
@unittest.skipUnless(HAVE_CAPTURES, "captures/global_garage not present (read-only user data)")
class RealFrameAcceptanceTest(unittest.TestCase):
    def test_panel_off(self):
        result = observe(real("筛选面板_已拥有关闭.png"), PANEL_OCR_OFF, fid=2)
        o = result.observation
        self.assertEqual(o.page, plan.FILTER_PANEL)
        self.assertEqual(o.owned_filter, plan.OFF)
        self.assertTrue(o.other_filters_clear)
        self.assertIsNone(o.at_d_start)
        d = result.diagnostics
        self.assertEqual(d["owned_filter"]["reasons"], ["checkbox_outline_visible_and_empty"])
        self.assertIn("all_controls_unselected_default_ascending_sort",
                      d["other_filters_clear"]["reasons"])
        self.assertEqual(d["at_d_start"]["reasons"],
                         ["at_d_start_only_judgeable_on_a_confirmed_garage_list"])

    def test_panel_on(self):
        result = observe(real("筛选面板_已拥有开启.png"), PANEL_OCR_ON, fid=3)
        o = result.observation
        self.assertEqual(o.page, plan.FILTER_PANEL)
        self.assertEqual(o.owned_filter, plan.ON)
        self.assertTrue(o.other_filters_clear)
        self.assertIsNone(o.at_d_start)
        self.assertEqual(d_field := result.diagnostics["owned_filter"]["reasons"],
                         ["checkbox_filled_yellow_green"])

    def test_d_start_true(self):
        result = observe(real("切换已拥有后_D级最左端.png"), fid=4)
        o = result.observation
        self.assertEqual(o.page, plan.GARAGE_LIST)
        self.assertTrue(o.at_d_start)
        self.assertEqual(o.owned_filter, plan.UNKNOWN_FILTER)
        self.assertIsNone(o.other_filters_clear)
        self.assertIn("d_marker_divider_and_first_column_all_confirmed",
                      result.diagnostics["at_d_start"]["reasons"])

    def test_random_position_not_true(self):
        result = observe(real("刚进入全局车库_随机位置.png"), fid=5)
        self.assertIs(result.observation.at_d_start, False)
        self.assertIn("list_scrolled_left_of_start",
                      result.diagnostics["at_d_start"]["reasons"])

    def test_r_page_not_true(self):
        result = observe(real("仅拥有R级页面.png"), fid=6)
        self.assertIs(result.observation.at_d_start, False)

    def test_s_page_not_true(self):
        result = observe(real("仅拥有S级页面.png"), fid=7)
        self.assertIs(result.observation.at_d_start, False)

    def test_r_section_marker_is_definite_non_d_start(self):
        # 仅拥有切换前.png shows a start-like layout with an R section marker.
        result = observe(real("仅拥有切换前.png"), fid=8)
        self.assertIs(result.observation.at_d_start, False)
        self.assertIn("non_d_section_marker_visible",
                      result.diagnostics["at_d_start"]["reasons"])

    def test_scrolled_variants_are_definite_false(self):
        for name, fid in (("仅拥有切换后.png", 9), ("升星就绪.png", 10),
                          ("未拥有_图纸_F5.png", 11), ("未拥有_钥匙_腾风龙舟版.png", 12)):
            with self.subTest(frame=name):
                result = observe(real(name), fid=fid)
                self.assertEqual(result.observation.page, plan.GARAGE_LIST)
                self.assertIs(result.observation.at_d_start, False)

    def test_home_maps_to_other_with_positive_evidence(self):
        result = observe(real("主页面.png"), fid=13)
        self.assertEqual(result.observation.page, plan.OTHER_PAGE)
        self.assertEqual(result.diagnostics["page"]["reason"],
                         "home_page_evidence_mapped_to_other")

    def test_ipad_reference_frame_is_unsupported_unknown(self):
        result = observe(real("已可解锁_银电_r兔_ipadpro比例.png"), fid=14)
        self.assertEqual(result.observation.page, plan.UNKNOWN_PAGE)
        self.assertFalse(result.diagnostics["page"]["supported"])
        self.assertEqual(result.observation.owned_filter, plan.UNKNOWN_FILTER)
        self.assertIsNone(result.observation.other_filters_clear)
        self.assertIsNone(result.observation.at_d_start)

    def test_observations_are_wellformed_for_the_planner(self):
        for name in ("筛选面板_已拥有关闭.png", "切换已拥有后_D级最左端.png",
                     "刚进入全局车库_随机位置.png", "主页面.png"):
            with self.subTest(frame=name):
                o = observe(real(name), PANEL_OCR_OFF, fid=20).observation
                state, _ = plan.start(SID, 0.0)
                _, decision = plan.step(state, o, 0.0)
                self.assertNotEqual(decision.reason, "malformed_page")


# --------------------------------------------------------------------------- #
# case 2: degenerate, occluded, wrong-size, wrong-page frames
# --------------------------------------------------------------------------- #
class DegenerateFrameTest(unittest.TestCase):
    def test_flat_frames_stay_unknown(self):
        for name, fill in (("grey", 50), ("black", 0), ("white", 255)):
            with self.subTest(frame=name):
                image = np.full((720, 1280, 3), fill, np.uint8)
                o = observe(image, fid=1).observation
                self.assertEqual(o.page, plan.UNKNOWN_PAGE)
                self.assertEqual(o.owned_filter, plan.UNKNOWN_FILTER)
                self.assertIsNone(o.other_filters_clear)
                self.assertIsNone(o.at_d_start)

    def test_non_native_size_is_unknown(self):
        image = np.zeros((719, 1279, 3), np.uint8)
        result = observe(image, PANEL_OCR_OFF, fid=1)
        self.assertEqual(result.observation.page, plan.UNKNOWN_PAGE)
        self.assertFalse(result.diagnostics["page"]["supported"])

    def test_occluded_owned_cell_is_unknown(self):
        image = panel_frame(covered="owned")
        result = observe(image, PANEL_OCR_OFF, fid=1)
        self.assertEqual(result.observation.owned_filter, plan.UNKNOWN_FILTER)
        self.assertIn("checkbox_body_not_confirmed",
                      result.diagnostics["owned_filter"]["reasons"])

    def test_list_frame_asking_for_panel_fields_is_unknown(self):
        result = observe(list_frame(), PANEL_OCR_OFF, fid=1)
        self.assertEqual(result.observation.owned_filter, plan.UNKNOWN_FILTER)
        self.assertIsNone(result.observation.other_filters_clear)

    def test_top_d_button_alone_is_not_a_start(self):
        # Top D jump button retained, list content/markers removed.
        result = observe(list_frame(cards=False, dots=False, badge_letter=None,
                                    top_button=True), fid=1)
        self.assertIsNot(result.observation.at_d_start, True)

    def test_injected_d_text_cannot_create_a_start(self):
        synthetic_d = [ocr_item("D", [140, 410, 30, 30], .99),
                       ocr_item("D", [745, 100, 30, 40], .99)]
        result = observe(list_frame(badge_letter=None, dots=False), synthetic_d, fid=1)
        self.assertIsNot(result.observation.at_d_start, True)
        if HAVE_CAPTURES:
            random_frame = observe(real("刚进入全局车库_随机位置.png"), synthetic_d, fid=2)
            self.assertIs(random_frame.observation.at_d_start, False)


# --------------------------------------------------------------------------- #
# case 3: anchor ablation on the real D-start frame
# --------------------------------------------------------------------------- #
@unittest.skipUnless(HAVE_CAPTURES, "captures/global_garage not present (read-only user data)")
class AnchorAblationTest(unittest.TestCase):
    def test_marker_covered_is_not_true(self):
        image = real("切换已拥有后_D级最左端.png").copy()
        image[390:480, 100:210] = rail_background(image)
        result = observe(image, fid=1)
        self.assertIsNot(result.observation.at_d_start, True)
        self.assertIn("d_marker_missing", result.diagnostics["at_d_start"]["reasons"])

    def test_divider_dots_covered_is_not_true(self):
        image = real("切换已拥有后_D级最左端.png").copy()
        colour = rail_background(image)
        image[225:400, 148:170] = colour
        image[460:640, 148:170] = colour
        result = observe(image, fid=1)
        self.assertIsNot(result.observation.at_d_start, True)
        self.assertIn("divider_dots_not_confirmed",
                      result.diagnostics["at_d_start"]["reasons"])

    def test_first_column_boundary_covered_is_not_true(self):
        image = real("切换已拥有后_D级最左端.png").copy()
        image[222:643, 212:300] = rail_background(image)
        result = observe(image, fid=1)
        self.assertIsNot(result.observation.at_d_start, True)
        self.assertIn("first_column_geometry_not_confirmed",
                      result.diagnostics["at_d_start"]["reasons"])

    def test_content_shifted_with_top_nav_kept_is_not_true(self):
        image = real("切换已拥有后_D级最左端.png").copy()
        image[150:680] = np.roll(image[150:680], -60, axis=1)
        result = observe(image, fid=1)
        self.assertEqual(result.observation.page, plan.GARAGE_LIST)
        self.assertIs(result.observation.at_d_start, False)


# --------------------------------------------------------------------------- #
# case 4: non-owned control conflicts and occlusions (synthetic panels)
# --------------------------------------------------------------------------- #
class ControlConflictTest(unittest.TestCase):
    def test_each_checked_control_blocks_clear(self):
        for name in ("brand", "stars", "performance"):
            with self.subTest(control=name):
                result = observe(panel_frame(checked=name), PANEL_OCR_OFF, fid=1)
                self.assertIs(result.observation.other_filters_clear, False)
                self.assertIn(f"control_checked:{name}",
                              result.diagnostics["other_filters_clear"]["reasons"])

    def test_occluded_or_flattened_control_is_unknown_not_clear(self):
        for kind in ("covered", "flat"):
            for name in ("brand", "stars", "performance"):
                with self.subTest(kind=kind, control=name):
                    image = panel_frame(**{kind: name})
                    result = observe(image, PANEL_OCR_OFF, fid=1)
                    self.assertIsNone(result.observation.other_filters_clear)
                    self.assertIn(f"control_state_unknown:{name}",
                                  result.diagnostics["other_filters_clear"]["reasons"])

    def test_synthetic_panel_positive_is_reported_from_synthetic_pixels(self):
        # The three unchecked cells plus the transcribed 升序 label confirm the
        # synthetic-panel layout; this is a rule probe, not a real switch frame.
        result = observe(panel_frame(), PANEL_OCR_OFF, fid=1)
        self.assertTrue(result.observation.other_filters_clear)


# --------------------------------------------------------------------------- #
# case 5: OCR robustness
# --------------------------------------------------------------------------- #
class OcrRobustnessTest(unittest.TestCase):
    def test_missing_ocr_leaves_sort_unknown_but_owned_readable(self):
        if HAVE_CAPTURES:
            result = observe(real("筛选面板_已拥有关闭.png"), None, fid=1)
            self.assertEqual(result.observation.owned_filter, plan.OFF)
        result = observe(panel_frame(), None, fid=2)
        self.assertIsNone(result.observation.other_filters_clear)
        self.assertIn("sort_direction_unknown",
                      result.diagnostics["other_filters_clear"]["reasons"])

    def test_low_confidence_direction_is_unknown(self):
        ocr = [ocr_item("升序", [52, 299, 44, 25], .5)]
        self.assertIsNone(observe(panel_frame(), ocr, fid=1).observation.other_filters_clear)

    def test_nan_and_infinite_confidences_are_rejected(self):
        ocr = [ocr_item("升序", [52, 299, 44, 25], float("nan")),
               ocr_item("升序", [52, 299, 44, 25], float("inf"))]
        result = observe(panel_frame(), ocr, fid=1)
        self.assertEqual(result.diagnostics["ocr"]["items_rejected"], 2)
        self.assertIsNone(result.observation.other_filters_clear)

    def test_direction_outside_roi_is_ignored(self):
        ocr = [ocr_item("升序", [800, 500, 44, 25], .99)]
        self.assertIsNone(observe(panel_frame(), ocr, fid=1).observation.other_filters_clear)

    def test_contradictory_direction_readings_are_unknown(self):
        ocr = [ocr_item("升序", [52, 299, 44, 25], .99),
               ocr_item("降序", [54, 300, 42, 24], .98)]
        result = observe(panel_frame(), ocr, fid=1)
        self.assertIsNone(result.observation.other_filters_clear)
        self.assertIn("sort_direction_readings_conflict",
                      result.diagnostics["other_filters_clear"]["reasons"])

    def test_duplicate_consistent_direction_stands(self):
        ocr = [ocr_item("升序", [52, 299, 44, 25], .99),
               ocr_item("升序", [52, 299, 44, 25], .99)]
        self.assertTrue(observe(panel_frame(), ocr, fid=1).observation.other_filters_clear)

    def test_descending_direction_is_a_definite_conflict(self):
        ocr = [ocr_item("降序", [52, 299, 44, 25], 1.0)]
        result = observe(panel_frame(), ocr, fid=1)
        self.assertIs(result.observation.other_filters_clear, False)
        self.assertIn("sort_direction_not_default_ascending",
                      result.diagnostics["other_filters_clear"]["reasons"])

    def test_malformed_ocr_items_are_counted_not_trusted(self):
        ocr = ["升序", {"text": "升序"}, {"text": "升序", "confidence": .9, "box": [1, 2]},
               {"text": "升序", "confidence": .9, "box": [52, 299, 44, 25]}]
        result = observe(panel_frame(), ocr, fid=1)
        self.assertEqual(result.diagnostics["ocr"]["items_rejected"], 3)
        self.assertTrue(result.observation.other_filters_clear)

    def test_isolated_sort_text_does_not_leak_across_pages(self):
        result = observe(list_frame(), PANEL_OCR_OFF, fid=1)
        self.assertIsNone(result.observation.other_filters_clear)


# --------------------------------------------------------------------------- #
# synthetic D-start geometry matrix
# --------------------------------------------------------------------------- #
class SyntheticMarkerTest(unittest.TestCase):
    def test_synthetic_d_start_layout_is_true(self):
        result = observe(list_frame(), fid=1)
        self.assertIs(result.observation.at_d_start, True)

    def test_each_non_d_letter_is_definite_false(self):
        for letter in ("R", "B", "C", "S", "A", "P"):
            with self.subTest(letter=letter):
                result = observe(list_frame(badge_letter=letter), fid=1)
                self.assertIs(result.observation.at_d_start, False)
                self.assertIn("non_d_section_marker_visible",
                              result.diagnostics["at_d_start"]["reasons"])

    def test_displaced_d_marker_is_not_true(self):
        result = observe(list_frame(badge_center=128), fid=1)
        self.assertIsNot(result.observation.at_d_start, True)
        self.assertIn("d_marker_not_at_calibrated_position",
                      result.diagnostics["at_d_start"]["reasons"])

    def test_d_marker_without_divider_is_not_true(self):
        result = observe(list_frame(dots=False), fid=1)
        self.assertIsNot(result.observation.at_d_start, True)
        self.assertIn("divider_dots_not_confirmed",
                      result.diagnostics["at_d_start"]["reasons"])

    def test_scrolled_cards_are_definite_false(self):
        result = observe(list_frame(card_x=120), fid=1)
        self.assertIs(result.observation.at_d_start, False)
        self.assertIn("list_scrolled_left_of_start",
                      result.diagnostics["at_d_start"]["reasons"])

    def test_unreadable_marker_letter_is_unknown(self):
        image = list_frame()
        image[408:456, 134:182] = (210, 210, 210)   # blank badge: no glyph
        result = observe(image, fid=1)
        self.assertIsNone(result.observation.at_d_start)
        self.assertIn("d_marker_letter_unreadable",
                      result.diagnostics["at_d_start"]["reasons"])


# --------------------------------------------------------------------------- #
# case 6: contract, purity, session/frame validation
# --------------------------------------------------------------------------- #
class ContractTest(unittest.TestCase):
    @unittest.skipUnless(HAVE_CAPTURES, "captures/global_garage not present (read-only user data)")
    def test_inputs_are_not_mutated_and_output_is_deterministic(self):
        image = real("切换已拥有后_D级最左端.png")
        before = image.copy()
        ocr = [dict(item) for item in PANEL_OCR_OFF]
        first = observe(image, ocr, fid=1)
        self.assertTrue(np.array_equal(image, before))
        self.assertEqual(ocr, PANEL_OCR_OFF)
        second = observe(image, [dict(item) for item in PANEL_OCR_OFF], fid=1)
        self.assertEqual(first, second)

    def test_invalid_session_id_rejected(self):
        image = np.zeros((720, 1280, 3), np.uint8)
        for bad in ("", "   ", None, 1, True):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ValueError):
                    adapter.observe(image, None, session_id=bad, frame_id=1)

    def test_invalid_frame_id_rejected(self):
        image = np.zeros((720, 1280, 3), np.uint8)
        for bad in (-1, True, 1.0, "3", None):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ValueError):
                    adapter.observe(image, None, session_id=SID, frame_id=bad)

    def test_non_ndarray_image_rejected(self):
        with self.assertRaises(ValueError):
            adapter.observe([[0]], None, session_id=SID, frame_id=1)

    def test_results_are_offline_only_and_jsonable(self):
        for image in (panel_frame(), list_frame()):
            result = observe(image, PANEL_OCR_OFF, fid=1)
            self.assertFalse(result.executable)
            self.assertTrue(result.offline_only)
            self.assertFalse(result.diagnostics["executable"])
            self.assertTrue(result.diagnostics["offline_only"])
            json.dumps(result.diagnostics)

    def test_no_click_targets_or_receipts_in_output(self):
        result = observe(panel_frame(), PANEL_OCR_OFF, fid=1)
        blob = json.dumps(result.diagnostics)
        for banned in ("click", "tap", "action_id", "receipt"):
            self.assertNotIn(banned, blob)


# --------------------------------------------------------------------------- #
# case 7: planner integration through adapter output
# --------------------------------------------------------------------------- #
def O(frame, page, owned="unknown", clear=None, d=None, sid=SID):
    return plan.Observation(session_id=sid, frame_id=frame, page=page,
                            owned_filter=owned, other_filters_clear=clear, at_d_start=d)


def R(action_id, ok=True, sid=SID):
    # Synthetic planner-contract receipt; unit-test scaffolding only.
    return plan.ActionResult(session_id=sid, action_id=action_id, ok=ok)


def drive_to_d_start():
    """Planner state after the off-chain prefix (synthetic events, marked)."""
    state, _ = plan.start(SID, 0.0)
    for event in (O(1, plan.GARAGE_LIST), R(1),
                  O(2, plan.FILTER_PANEL, owned=plan.OFF, clear=True), R(2),
                  O(3, plan.FILTER_PANEL, owned=plan.ON, clear=True), R(3),
                  O(4, plan.GARAGE_LIST), R(4),
                  O(5, plan.FILTER_PANEL, owned=plan.ON, clear=True), R(5)):
        state, _ = plan.step(state, event, 0.0)
    return state


def drive_to_panel():
    state, _ = plan.start(SID, 0.0)
    for event in (O(1, plan.GARAGE_LIST), R(1)):
        state, _ = plan.step(state, event, 0.0)
    return state


@unittest.skipUnless(HAVE_CAPTURES, "captures/global_garage not present (read-only user data)")
class PlannerIntegrationTest(unittest.TestCase):
    def test_unknown_other_filters_waits(self):
        state = drive_to_panel()
        observation = observe(panel_frame(), None, fid=2).observation
        _, decision = plan.step(state, observation, 0.0)
        self.assertEqual(decision.kind, plan.WAIT)
        self.assertEqual(decision.reason, "other_filters_clear_unknown")

    def test_definite_conflict_blocks(self):
        state = drive_to_panel()
        observation = observe(panel_frame(checked="stars"), PANEL_OCR_OFF, fid=2).observation
        _, decision = plan.step(state, observation, 0.0)
        self.assertEqual(decision.kind, plan.BLOCKED)
        self.assertEqual(decision.reason, "other_filters_not_clear")

    def test_two_fresh_d_frames_reach_ready(self):
        state = drive_to_d_start()
        frame = real("切换已拥有后_D级最左端.png")
        state, decision = plan.step(state, observe(frame, fid=6).observation, 0.0)
        self.assertEqual(decision.kind, plan.WAIT)
        self.assertEqual(decision.reason, "awaiting_second_d_start_frame")
        state, decision = plan.step(state, observe(frame, fid=7).observation, 0.0)
        self.assertEqual(decision.kind, plan.READY)
        self.assertFalse(decision.executable)

    def test_stale_frame_id_does_not_advance(self):
        state = drive_to_d_start()
        frame = real("切换已拥有后_D级最左端.png")
        state, _ = plan.step(state, observe(frame, fid=6).observation, 0.0)
        _, decision = plan.step(state, observe(frame, fid=6).observation, 0.0)
        self.assertEqual(decision.kind, plan.WAIT)
        self.assertEqual(decision.reason, "stale_frame_ignored")

    def test_unknown_page_between_d_frames_resets_accumulation(self):
        state = drive_to_d_start()
        frame = real("切换已拥有后_D级最左端.png")
        grey = np.full((720, 1280, 3), 50, np.uint8)
        state, _ = plan.step(state, observe(frame, fid=6).observation, 0.0)
        state, _ = plan.step(state, observe(grey, fid=7).observation, 0.0)
        state, decision = plan.step(state, observe(frame, fid=8).observation, 0.0)
        self.assertEqual(decision.kind, plan.WAIT)
        state, decision = plan.step(state, observe(frame, fid=9).observation, 0.0)
        self.assertEqual(decision.kind, plan.READY)

    def test_replayed_duplicate_file_with_new_frame_ids_is_caller_trusted(self):
        # Documented trust boundary: the same pixels read twice with distinct
        # frame_ids are accepted as fresh by the planner (stable-page sampling
        # is legitimate); detecting a *replayed file* is the caller contract,
        # not something offline pixels can prove.
        state = drive_to_d_start()
        frame = real("仅拥有R级页面.png")
        state, decision = plan.step(state, observe(frame, fid=6).observation, 0.0)
        self.assertEqual(decision.kind, plan.ACTION)
        self.assertEqual(decision.intent, plan.JUMP_D_SECTION)
        self.assertFalse(decision.executable)
        # A fresh observation can advance bounded navigation only after its
        # synthetic caller receipt; identical pixels are not a stale frame id.
        state, _ = plan.step(state, R(decision.action_id), 0.0)
        state, decision = plan.step(state, observe(frame, fid=7).observation, 0.0)
        self.assertEqual(decision.kind, plan.ACTION)
        self.assertEqual(decision.intent, plan.SWIPE_TO_ORIGIN)
        self.assertEqual(state.last_frame_id, 7)
        self.assertFalse(decision.executable)
        self.assertNotEqual(decision.reason, "stale_frame_ignored")


# --------------------------------------------------------------------------- #
# case 8: positives exist and gaps are delivered as gaps
# --------------------------------------------------------------------------- #
class EvidenceCompletenessTest(unittest.TestCase):
    @unittest.skipUnless(HAVE_CAPTURES, "captures/global_garage not present (read-only user data)")
    def test_real_positives_exist(self):
        self.assertTrue(observe(real("切换已拥有后_D级最左端.png"), fid=1)
                        .observation.at_d_start)
        self.assertTrue(observe(real("筛选面板_已拥有关闭.png"), PANEL_OCR_OFF, fid=2)
                        .observation.other_filters_clear)
        self.assertEqual(observe(real("筛选面板_已拥有开启.png"), PANEL_OCR_ON, fid=3)
                         .observation.owned_filter, plan.ON)

    def test_missing_evidence_is_reported_as_gap_not_relaxed(self):
        result = observe(panel_frame(), None, fid=1)
        reasons = result.diagnostics["other_filters_clear"]["reasons"]
        self.assertIn("sort_direction_unknown", reasons)
        self.assertIsNone(result.observation.other_filters_clear)


# --------------------------------------------------------------------------- #
# 05AK-B1 repair regressions (root review F1-F4).  These were written first
# and must fail on the pre-repair implementation.
# --------------------------------------------------------------------------- #
class OcrSanitationRegressionTest(unittest.TestCase):
    """F1: only finite in-unit confidences and in-frame positive boxes count."""

    def test_confidence_outside_unit_interval_rejected(self):
        for bad in (2, -0.1, 1.5, 10**1000, -(10**1000)):
            with self.subTest(confidence=repr(bad)):
                ocr = [ocr_item("升序", [52, 299, 44, 25], bad)]
                result = observe(panel_frame(), ocr, fid=1)
                self.assertIsNone(result.observation.other_filters_clear)
                self.assertEqual(result.diagnostics["ocr"]["items_rejected"], 1)

    def test_malformed_or_out_of_frame_boxes_rejected(self):
        boxes = ([96, 299, -44, 25], [52, 299, 0, 25], [52, 299, 44, 0],
                 [-566, -48, 1280, 720], [52, -5, 44, 25], [1230, 299, 60, 25],
                 [52, 700, 44, 30], [10**1000, 299, 44, 25],
                 [float("nan"), 299, 44, 25], [52, 299, float("inf"), 25])
        for box in boxes:
            with self.subTest(box=box):
                ocr = [ocr_item("升序", box, .99)]
                result = observe(panel_frame(), ocr, fid=1)
                self.assertIsNone(result.observation.other_filters_clear)
                self.assertEqual(result.diagnostics["ocr"]["items_rejected"], 1)

    def test_sort_label_box_must_fully_inside_roi(self):
        # Centres fall inside the label ROI but the box crosses an edge.
        for box in ([36, 299, 44, 25], [100, 299, 44, 25],
                    [52, 284, 44, 25], [52, 318, 44, 25]):
            with self.subTest(box=box):
                ocr = [ocr_item("升序", box, .99)]
                result = observe(panel_frame(), ocr, fid=1)
                self.assertIsNone(result.observation.other_filters_clear)

    @unittest.skipUnless(HAVE_CAPTURES, "captures/global_garage not present (read-only user data)")
    def test_invalid_evidence_cannot_create_clear_on_real_panel(self):
        frame = real("筛选面板_已拥有关闭.png")
        for confidence, box in ((2, [52, 299, 44, 25]), (.99, [96, 299, -44, 25]),
                                (.99, [-566, -48, 1280, 720]),
                                (10**1000, [52, 299, 44, 25])):
            with self.subTest(confidence=confidence, box=box):
                ocr = [dict(text="升序", confidence=confidence, box=box)]
                result = observe(frame, ocr, fid=1)
                self.assertIsNone(result.observation.other_filters_clear)
                self.assertEqual(result.diagnostics["ocr"]["items_rejected"], 1)

    def test_wellformed_label_still_confirms(self):
        ocr = [ocr_item("升序", [52, 299, 44, 25], .99)]
        self.assertTrue(observe(panel_frame(), ocr, fid=1)
                        .observation.other_filters_clear)


@unittest.skipUnless(HAVE_CAPTURES, "captures/global_garage not present (read-only user data)")
class InteriorEvidenceRegressionTest(unittest.TestCase):
    """F2: unchecked needs a provably empty interior, not just 'no green'."""

    @staticmethod
    def tick(image, cell, colour):
        x, y, _w, _h = cell
        cv2.line(image, (x + 8, y + 21), (x + 18, y + 31), colour, 4)
        cv2.line(image, (x + 18, y + 31), (x + 38, y + 8), colour, 4)

    def test_marks_inside_controls_are_unknown_not_unchecked(self):
        for name, cell in adapter.CONTROL_ROIS.items():
            for label, colour in (("white_tick", (240, 240, 240)),
                                  ("red_tick", (0, 0, 255)),
                                  ("dim_grey_mark", (110, 110, 110))):
                with self.subTest(control=name, mark=label):
                    image = real("筛选面板_已拥有关闭.png").copy()  # synthetic mutation
                    self.tick(image, cell, colour)
                    result = observe(image, PANEL_OCR_OFF, fid=1)
                    control = result.diagnostics["other_filters_clear"]["controls"][name]
                    self.assertEqual(control["state"], "unknown")
                    self.assertIn(control["reason"],
                                  ("unexplained_interior_content", "control_body_ambiguous"))
                    self.assertIsNone(result.observation.other_filters_clear)

    def test_partial_pollution_is_unknown(self):
        image = real("筛选面板_已拥有关闭.png").copy()
        x, y, _w, _h = adapter.CONTROL_ROIS["brand"]
        cv2.circle(image, (x + 24, y + 24), 3, (230, 230, 230), -1)
        result = observe(image, PANEL_OCR_OFF, fid=1)
        control = result.diagnostics["other_filters_clear"]["controls"]["brand"]
        self.assertEqual(control["state"], "unknown")
        self.assertIsNone(result.observation.other_filters_clear)

    def test_real_empty_cells_carry_empty_interior_evidence(self):
        result = observe(real("筛选面板_已拥有关闭.png"), PANEL_OCR_OFF, fid=1)
        for name, control in result.diagnostics["other_filters_clear"]["controls"].items():
            self.assertEqual(control["state"], "unchecked", name)
            self.assertLessEqual(control["interior_max_gray"], 90, name)
            self.assertLessEqual(control["interior_std"], 8.0, name)
        self.assertTrue(result.observation.other_filters_clear)


class RootResolutionRegressionTest(unittest.TestCase):
    """F3: fixture path must work from a root checkout and a nested worktree."""

    def test_marker_resolution_for_both_layouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            (root / "agent" / "orchestration").mkdir(parents=True)
            (root / "agent" / "orchestration" / "state.json").write_text("{}", encoding="utf-8")
            root_checkout = root / "agent" / "tests" / "test_x.py"
            self.assertEqual(_resolve_ma9_root(root_checkout), root)
            worktree = root / "MA9-worktrees" / "lane" / "agent" / "tests" / "test_x.py"
            self.assertEqual(_resolve_ma9_root(worktree), root)
            # Negative case outside any MA9 checkout (the temp dir itself sits
            # inside the real MA9 tree and would inherit its marker).
            nowhere = Path.home() / "ma9-absent-marker-probe" / "test_x.py"
            self.assertIsNone(_resolve_ma9_root(nowhere))

    def test_sample_resolution_prefers_marker_root_with_captures(self):
        # A worktree is itself a full checkout and carries the marker too; the
        # samples live at the outer marker root, and both layouts agree there.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            (root / "agent" / "orchestration").mkdir(parents=True)
            (root / "agent" / "orchestration" / "state.json").write_text("{}", encoding="utf-8")
            samples = root / "captures" / "global_garage"
            samples.mkdir(parents=True)
            root_checkout = root / "agent" / "tests" / "test_x.py"
            self.assertEqual(_find_captures(root_checkout), samples)
            worktree = root / "MA9-worktrees" / "lane" / "agent" / "tests" / "test_x.py"
            self.assertEqual(_find_captures(worktree), samples)

    def test_this_file_resolves_to_a_marker_root(self):
        self.assertIsNotNone(_resolve_ma9_root(Path(__file__)))

    def test_env_override_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["MA9_CAPTURES_GLOBAL_GARAGE"] = tmp
            try:
                self.assertEqual(_captures_dir(), Path(tmp))
            finally:
                del os.environ["MA9_CAPTURES_GLOBAL_GARAGE"]
            os.environ["MA9_ROOT"] = tmp
            try:
                self.assertEqual(_captures_dir(), Path(tmp) / "captures" / "global_garage")
            finally:
                del os.environ["MA9_ROOT"]

    def test_lane_layout_uses_the_same_samples_without_skip(self):
        # In the lane worktree (and after merge, in the root checkout) the
        # resolution must reach the real sample set: no silent skip.
        if not HAVE_CAPTURES:
            self.skipTest("captures unreachable from this checkout")
        marker_roots = [base for base in Path(__file__).resolve().parents
                        if (base / MA9_MARKER).is_file()]
        self.assertIn(CAPTURES.parent.parent, marker_roots)


class ImageEntryValidationRegressionTest(unittest.TestCase):
    """F4: HxWx3 uint8 at the entry point; malformed input raises ValueError."""

    def test_malformed_images_raise_value_error(self):
        cases = [np.zeros((720, 1280), np.uint8),
                 np.zeros((720, 1280, 4), np.uint8),
                 np.zeros((1280,), np.uint8),
                 np.zeros((720, 1280, 3), np.float32),
                 np.zeros((0, 0, 3), np.uint8)]
        for image in cases:
            with self.subTest(shape=image.shape, dtype=image.dtype):
                with self.assertRaises(ValueError):
                    adapter.observe(image, None, session_id=SID, frame_id=1)

    def test_valid_non_native_bgr_stays_documented_unknown(self):
        result = observe(np.zeros((1668, 2420, 3), np.uint8), None, fid=1)
        self.assertEqual(result.observation.page, plan.UNKNOWN_PAGE)
        self.assertFalse(result.diagnostics["page"]["supported"])


@unittest.skipUnless(HAVE_CAPTURES, "captures/global_garage not present")
class RootInteriorCoverageTest(unittest.TestCase):
    def test_dark_colour_ticks_do_not_establish_empty_controls(self):
        cells = dict(adapter.CONTROL_ROIS, owned=(314, 188, 47, 48))
        for name, (x, y, w, h) in cells.items():
            for colour in ((255, 0, 0), (0, 0, 0), (90, 9, 0)):
                for thickness in (2, 3, 4):
                    with self.subTest(cell=name, colour=colour, thickness=thickness):
                        image = real("筛选面板_已拥有关闭.png").copy()
                        cv2.line(image, (x+8, y+21), (x+18, y+31), colour, thickness)
                        cv2.line(image, (x+18, y+31), (x+38, y+8), colour, thickness)
                        result = observe(image, PANEL_OCR_OFF)
                        if name == "owned":
                            self.assertEqual(result.observation.owned_filter, plan.UNKNOWN_FILTER)
                        else:
                            self.assertIsNone(result.observation.other_filters_clear)

    def test_only_corner_is_excluded_not_entire_bottom_and_right_strips(self):
        for control, (x, y, w, h) in adapter.CONTROL_ROIS.items():
            for region in ((x + 37, y + 11, x + 39, y + 26),
                           (x + 11, y + 37, x + 24, y + 39)):
                with self.subTest(control=control, region=region):
                    image = real("筛选面板_已拥有关闭.png").copy()
                    x0, y0, x1, y1 = region
                    image[y0:y1, x0:x1] = 240
                    self.assertIsNone(observe(image, PANEL_OCR_OFF).observation.other_filters_clear)

    def test_owned_unexplained_tick_is_unknown_at_adapter_boundary(self):
        image = real("筛选面板_已拥有关闭.png").copy()
        cv2.line(image, (322, 209), (332, 219), (240, 240, 240), 4)
        cv2.line(image, (332, 219), (352, 196), (240, 240, 240), 4)
        result = observe(image, PANEL_OCR_OFF)
        self.assertEqual(result.observation.owned_filter, plan.UNKNOWN_FILTER)


if __name__ == "__main__":
    unittest.main()
