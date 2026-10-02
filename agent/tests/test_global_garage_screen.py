"""Offline tests for the global-garage current-page parser (05AJ).

Synthetic, de-identified fixtures plus injected OCR observations only: no
device, no local absolute path, no OCR engine.  The real 13-frame replay and the
human transcription live in the 05AJ evidence directory.  Several tests below
are the counterexamples raised by the 05AJ root review; they drive the production
entry points and would fail if the defect returned.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.global_garage_screen import (
    PAGE_FILTER_PANEL,
    PAGE_GARAGE_LIST,
    PAGE_HOME,
    PAGE_UNKNOWN,
    PAGE_UNSUPPORTED,
    card_coverage,
    classify_page,
    detect_card_boxes,
    normalize,
    read_card,
    read_owned_filter,
    read_page,
    resolve_identity,
)


CARD = [40, 225, 420, 198]
CARD_RIGHT = [464, 225, 420, 198]
GOLD_BGR = (40, 190, 230)


def frame(kind: str, checked: bool = False) -> np.ndarray:
    """One synthetic 1280x720 frame carrying a calibrated page signature."""
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    if kind == PAGE_GARAGE_LIST:
        image[:, :] = (18, 18, 18)
        image[86:142, 100:1216] = (147, 155, 161)          # bright, distinct header
        for x, y, w, h in (CARD, CARD_RIGHT):
            image[y:y + h, x:x + w] = (150, 150, 150)
            image[y:y + h, x + 10:x + w - 10:20] = (55, 55, 55)   # card texture
    elif kind == PAGE_HOME:
        image[:, :] = (40, 40, 40)
        image[295:305, ::7] = (200, 200, 200)
    elif kind == PAGE_FILTER_PANEL:
        image[:, :] = (30, 35, 25)                          # darkened backdrop ring
        image[52:668, 37:1243] = (60, 70, 55)               # panel body + border
        image[188:236, 314:361] = (140, 150, 130)           # checkbox outline
        image[193:231, 319:356] = (40, 45, 35)              # empty interior
        if checked:
            image[193:231, 319:356] = (44, 190, 150)        # yellow-green check fill
    return image


def item(text: str, box, confidence: float = .95) -> dict:
    return {"text": text, "confidence": confidence, "box": [int(v) for v in box]}


def name_item(box, text: str, confidence: float = .95, line: int = 0) -> dict:
    x, y, w, _h = box
    return item(text, [x + w - 120, y + 112 + line * 22, min(112, max(40, len(text) * 8)), 18],
                confidence)


def badge_item(box, label: str, confidence: float = .95) -> dict:
    x, y, w, _h = box
    return item(label, [x + w - 114, y + 92, 16, 22], confidence)


def status_item(box, text: str, confidence: float = .95) -> dict:
    x, y, _w, _h = box
    return item(text, [x + 20, y + 70, max(80, len(text) * 14), 22], confidence)


def field_item(box, text: str, region: str) -> dict:
    x, y, w, h = box
    where = {
        "performance": [x + 20, y + 32, 110, 20],
        "blueprint": [x + w - 118, y + 156, 96, 22],
        "fuel": [x + 8, y + 162, 44, 22],
    }[region]
    return item(text, where)


def paint_stars(image: np.ndarray, box, count: int) -> None:
    x, y = box[0], box[1]
    for index in range(count):
        cx = int(round(x + 14 + 16.6 * index))
        cy = y + 16
        image[cy - 5:cy + 6, cx - 5:cx + 6] = GOLD_BGR


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from walk(value)


CATALOG = [
    {"id": "nevera", "title": "Rimac Nevera", "class": "S", "league": "传奇"},
    {"id": "nevera-r", "title": "Rimac Nevera R", "class": "R", "league": "传奇"},
    {"id": "zagato", "title": "Aston Martin DBS GT Zagato", "class": "A", "league": "翡翠"},
    {"id": "918", "title": "Porsche 918 Spyder", "class": "S", "league": "翡翠"},
    {"id": "918-asphalt", "title": "Porsche 918 Spyder Asphalt Edition", "class": "S",
     "league": "精英"},
]


class PageKindTest(unittest.TestCase):
    def test_calibrated_pages_and_mutual_negatives(self) -> None:
        cases = {PAGE_HOME: frame(PAGE_HOME), PAGE_GARAGE_LIST: frame(PAGE_GARAGE_LIST),
                 PAGE_FILTER_PANEL: frame(PAGE_FILTER_PANEL)}
        for expected, image in cases.items():
            got = classify_page(image)["page"]
            self.assertEqual(got, expected)
            for other in set(cases) - {expected}:
                self.assertNotEqual(got, other)

    def test_flat_grey_and_plain_white_are_unknown(self) -> None:
        for name, image in (("grey50", np.full((720, 1280, 3), 50, np.uint8)),
                            ("white255", np.full((720, 1280, 3), 255, np.uint8)),
                            ("black", np.zeros((720, 1280, 3), np.uint8))):
            with self.subTest(frame=name):
                self.assertEqual(classify_page(image)["page"], PAGE_UNKNOWN)
                self.assertEqual(read_owned_filter(image)["state"], "unknown")

    def test_page_is_not_decided_by_name_size_or_hash(self) -> None:
        image = frame(PAGE_GARAGE_LIST)
        self.assertEqual(classify_page(image.copy())["page"], PAGE_GARAGE_LIST)
        self.assertEqual(classify_page(frame(PAGE_HOME), [item("车库等级", [100, 100, 40, 20])])["page"],
                         PAGE_HOME)


class OwnedFilterTest(unittest.TestCase):
    def test_checkbox_three_states(self) -> None:
        self.assertEqual(read_owned_filter(frame(PAGE_FILTER_PANEL, checked=True))["state"], "on")
        off = read_owned_filter(frame(PAGE_FILTER_PANEL, checked=False))
        self.assertEqual(off["state"], "off")
        self.assertEqual(off["reasons"], ["checkbox_outline_visible_and_empty"])

    def test_absent_checkbox_body_is_unknown_not_off(self) -> None:
        # A panel-shaped frame whose checkbox cell is flat must not read as "off".
        flat = frame(PAGE_FILTER_PANEL, checked=False)
        flat[188:236, 314:361] = (60, 70, 55)
        result = read_owned_filter(flat)
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["reasons"], ["checkbox_body_not_confirmed"])

    def test_non_panel_frames_never_report_on(self) -> None:
        for kind in (PAGE_HOME, PAGE_GARAGE_LIST):
            self.assertEqual(read_owned_filter(frame(kind))["state"], "unknown")
        bright = frame(PAGE_GARAGE_LIST)
        bright[188:236, 314:361] = (44, 190, 150)
        self.assertEqual(read_owned_filter(bright)["state"], "unknown")


class GeometryTest(unittest.TestCase):
    def test_detected_boxes_mark_edge_clipping(self) -> None:
        image = frame(PAGE_GARAGE_LIST)
        image[225:423, 900:1280] = (150, 150, 150)
        image[441:640, 0:400] = (150, 150, 150)
        boxes = detect_card_boxes(image)
        self.assertTrue(any(box["clipped_right"] for box in boxes))
        self.assertTrue(any(box["clipped_left"] for box in boxes))

    def test_flat_frame_yields_no_invented_cards(self) -> None:
        self.assertEqual(detect_card_boxes(frame(PAGE_HOME)), [])

    def test_narrow_clipped_card_is_kept_and_flagged_uncertain(self) -> None:
        image = frame(PAGE_GARAGE_LIST)
        image[225:423, 1060:1280] = (150, 150, 150)        # visible part of an edge card
        boxes = [box for box in detect_card_boxes(image) if box["row"] == 0]
        narrow = [box for box in boxes if box["geometry_uncertain"]]
        self.assertTrue(narrow, "a clipped narrow card must not be silently dropped")
        self.assertTrue(any(box["clipped_right"] for box in narrow))

    def test_dark_region_becomes_a_coverage_gap(self) -> None:
        image = frame(PAGE_GARAGE_LIST)
        image[:, :] = (18, 18, 18)
        image[86:142, 100:1216] = (147, 155, 161)
        image[225:423, 40:440] = (150, 150, 150)           # one bright card only
        image[225:423, 460:1200] = (22, 22, 22)            # dark, dropped cards
        coverage = card_coverage(image)
        row0 = coverage["rows"][0]
        self.assertEqual(len(row0["cards"]), 1)
        self.assertTrue(row0["unresolved"])
        self.assertTrue(any(region["kind"] == "possible_dark_or_clipped_card"
                            for region in row0["unresolved"]))
        self.assertGreater(coverage["unresolved_count"], 0)

    def test_provided_boxes_keep_clipping_flags(self) -> None:
        page = read_page(frame(PAGE_GARAGE_LIST), [], CATALOG,
                         card_boxes=[[0, 225, 420, 198], [1100, 225, 420, 198]])
        self.assertEqual(len(page["cards"]), 2)
        self.assertTrue(page["cards"][0]["clipped"]["left"])
        self.assertTrue(page["cards"][1]["clipped"]["right"])


class IdentityTest(unittest.TestCase):
    def _resolve(self, name: str, badge: str | None, **kwargs):
        ocr = [name_item(CARD, name)]
        if badge:
            ocr.insert(0, badge_item(CARD, badge))
        return read_card(frame(PAGE_GARAGE_LIST), ocr, CATALOG, CARD, **kwargs)

    def test_complete_name_plus_matching_badge_is_unique(self) -> None:
        card = self._resolve("ASTON MARTIN DBS GT ZAGATO", "A")
        self.assertEqual(card["identity_status"], "unique")
        self.assertEqual(card["candidate"]["id"], "zagato")

    def test_different_class_sibling_is_excluded_by_the_badge(self) -> None:
        card = self._resolve("RIMAC NEVERA", "S")
        self.assertEqual(card["identity_status"], "unique")
        self.assertEqual(card["candidate"]["id"], "nevera")
        self.assertIn("class_badge_excluded_differently_classed_siblings", card["identity_reasons"])

    def test_same_class_sibling_keeps_the_reading_ambiguous(self) -> None:
        card = self._resolve("PORSCHE 918 SPYDER", "S")
        self.assertEqual(card["identity_status"], "ambiguous")
        self.assertIn("name_is_prefix_of_longer_title", card["identity_reasons"])

    def test_ocr_typo_cannot_escape_the_family_gate(self) -> None:
        clean = resolve_identity("Porsche 918 Spyder", "S", CATALOG)
        typo = resolve_identity("Porsche 918 Spyderr", "S", CATALOG)
        self.assertEqual(clean["status"], "ambiguous")
        self.assertEqual(typo["status"], clean["status"])
        self.assertIsNone(typo.get("candidate"))

    def test_lower_quality_input_never_raises_confirmation(self) -> None:
        family = [{"id": "base", "title": "W Motors Lykan Hypersport", "class": "S"},
                  {"id": "neon", "title": "W Motors Lykan Hypersport Neon Edition", "class": "S"}]
        for reading in ("W Motors Lykan Hypersport", "W Motors Lykan Hypersporx",
                        "W Motors Lykan Hypersp"):
            with self.subTest(reading=reading):
                self.assertEqual(resolve_identity(reading, "S", family)["status"], "ambiguous")

    def test_full_long_name_resolves_to_the_variant(self) -> None:
        card = self._resolve("PORSCHE 918 SPYDER ASPHALT EDITION", "S")
        self.assertEqual(card["identity_status"], "unique")
        self.assertEqual(card["candidate"]["id"], "918-asphalt")

    def test_missing_badge_letter_is_not_taken_from_the_catalog(self) -> None:
        card = self._resolve("ASTON MARTIN DBS GT ZAGATO", None)
        self.assertEqual(card["identity_status"], "ambiguous")
        self.assertIn("class_badge_unobserved", card["identity_reasons"])

    def test_badge_outside_roi_or_low_confidence_is_not_evidence(self) -> None:
        # Root counterexample: a "D" at the card's left edge with confidence .01.
        ocr = [name_item(CARD, "GINETTA G60"), item("D", [50, 260, 18, 20], .01)]
        catalog = [{"id": "g60", "title": "Ginetta G60", "class": "D", "league": "x"}]
        card = read_card(frame(PAGE_GARAGE_LIST), ocr, catalog, CARD)
        self.assertIsNone(card["class_observation"]["value"])
        self.assertNotEqual(card["identity_status"], "unique")
        # A correct box but a low confidence is still not evidence.
        low = read_card(frame(PAGE_GARAGE_LIST),
                        [name_item(CARD, "GINETTA G60"), badge_item(CARD, "D", .1)],
                        catalog, CARD)
        self.assertIsNone(low["class_observation"]["value"])
        self.assertNotEqual(low["identity_status"], "unique")

    def test_conflicting_badge_letters_yield_no_class(self) -> None:
        ocr = [name_item(CARD, "GINETTA G60"), badge_item(CARD, "D"), badge_item(CARD, "S")]
        catalog = [{"id": "g60", "title": "Ginetta G60", "class": "D", "league": "x"}]
        card = read_card(frame(PAGE_GARAGE_LIST), ocr, catalog, CARD)
        self.assertIsNone(card["class_observation"]["value"])
        self.assertIn("conflicting_class_badge_letters", card["conflicts"])

    def test_class_badge_conflict_stays_unresolved(self) -> None:
        card = self._resolve("ASTON MARTIN DBS GT ZAGATO", "B")
        self.assertEqual(card["identity_status"], "ambiguous")
        self.assertIn("class_badge_disagrees_with_catalog", card["identity_reasons"])

    def test_clipped_geometry_never_confirms_an_identity(self) -> None:
        # Root counterexample: the same card, clipped, must not stay unique.
        catalog = [{"id": "g60", "title": "Ginetta G60", "class": "D", "league": "x"}]
        ocr = [badge_item(CARD, "D"), name_item(CARD, "GINETTA G60")]
        clean = read_card(frame(PAGE_GARAGE_LIST), ocr, catalog, CARD)
        page = read_page(frame(PAGE_GARAGE_LIST), ocr, catalog,
                         card_boxes=[{"box": CARD, "clipped_left": True}])
        clipped = page["cards"][0]
        self.assertEqual(clean["identity_status"], "unique")
        self.assertNotEqual(clipped["identity_status"], "unique")
        self.assertIsNone(clipped["candidate"])
        self.assertIn("card_geometry_clipped_no_complete_name_evidence", clipped["identity_reasons"])

    def test_out_of_bounds_geometry_never_confirms_an_identity(self) -> None:
        catalog = [{"id": "g60", "title": "Ginetta G60", "class": "D", "league": "x"}]
        page = read_page(frame(PAGE_GARAGE_LIST),
                         [name_item([0, 225, 420, 198], "GINETTA G60"), badge_item([0, 225, 420, 198], "D")],
                         catalog, card_boxes=[[-40, 225, 420, 198]])
        self.assertNotEqual(page["cards"][0]["identity_status"], "unique")
        self.assertTrue(page["cards"][0]["out_of_bounds"])

    def test_similar_model_names_across_brands_stay_unresolved(self) -> None:
        catalog = [{"id": "praga", "title": "Praga Bohema", "class": "A", "league": "x"},
                   {"id": "other", "title": "Other Bohema", "class": "A", "league": "x"}]
        bare = read_card(frame(PAGE_GARAGE_LIST),
                         [badge_item(CARD, "A"), name_item(CARD, "BOHEMA")], catalog, CARD)
        self.assertNotEqual(bare["identity_status"], "unique")
        full = read_card(frame(PAGE_GARAGE_LIST),
                         [badge_item(CARD, "A"), name_item(CARD, "PRAGA BOHEMA")], catalog, CARD)
        self.assertEqual(full["identity_status"], "unique")
        self.assertEqual(full["candidate"]["id"], "praga")

    def test_empty_catalog_and_empty_name_do_not_guess(self) -> None:
        empty = read_card(frame(PAGE_GARAGE_LIST), [name_item(CARD, "RIMAC NEVERA")], [], CARD)
        self.assertEqual(empty["identity_status"], "unknown")
        self.assertIn("empty_catalog", empty["identity_reasons"])
        blank = read_card(frame(PAGE_GARAGE_LIST), [item("...", [CARD[0] + 300, 340, 40, 18])],
                          CATALOG, CARD)
        self.assertEqual(blank["identity_status"], "unknown")
        self.assertIn("no_readable_complete_name", blank["identity_reasons"])

    def test_duplicate_titles_are_not_forced_to_one(self) -> None:
        catalog = [{"id": "one", "title": "Example Car", "class": "S", "league": "x"},
                   {"id": "two", "title": "Example Car", "class": "S", "league": "x"}]
        card = read_card(frame(PAGE_GARAGE_LIST),
                         [badge_item(CARD, "S"), name_item(CARD, "EXAMPLE CAR")], catalog, CARD)
        self.assertEqual(card["identity_status"], "ambiguous")
        self.assertIsNone(card["candidate"])


class StarsTest(unittest.TestCase):
    def test_gold_components_without_total_slot_evidence_stay_unknown(self) -> None:
        for count in (1, 3, 6):
            with self.subTest(count=count):
                image = frame(PAGE_GARAGE_LIST)
                paint_stars(image, CARD, count)
                card = read_card(image, [name_item(CARD, "ASTON MARTIN DBS GT ZAGATO")], CATALOG, CARD)
                self.assertIsNone(card["stars"])
                self.assertEqual(card["stars_unknown_reason"], "star_total_slots_unverified")

    def test_gold_background_or_solid_banner_is_unknown(self) -> None:
        # Root counterexample: a solid coloured band must not become six stars.
        image = frame(PAGE_GARAGE_LIST)
        x, y, _w, _h = CARD
        image[y + 6:y + 26, x:x + 130] = GOLD_BGR
        card = read_card(image, [name_item(CARD, "ASTON MARTIN DBS GT ZAGATO")], CATALOG, CARD)
        self.assertIsNone(card["stars"])
        self.assertEqual(card["stars_unknown_reason"], "star_row_background_not_separable")

    def test_wide_gold_bar_is_not_a_star(self) -> None:
        image = frame(PAGE_GARAGE_LIST)
        x, y, _w, _h = CARD
        image[y + 11:y + 22, x + 14:x + 44] = GOLD_BGR      # 30 px wide bar, not a star
        card = read_card(image, [name_item(CARD, "ASTON MARTIN DBS GT ZAGATO")], CATALOG, CARD)
        self.assertIsNone(card["stars"])
        self.assertEqual(card["stars_unknown_reason"], "star_row_glyph_too_wide_for_a_star")

    def test_glyph_outside_the_six_slots_is_unknown(self) -> None:
        image = frame(PAGE_GARAGE_LIST)
        x, y, _w, _h = CARD
        image[y + 11:y + 22, x + 105:x + 116] = GOLD_BGR    # beyond the sixth slot
        card = read_card(image, [name_item(CARD, "ASTON MARTIN DBS GT ZAGATO")], CATALOG, CARD)
        self.assertIsNone(card["stars"])

    def test_banner_hides_stars_without_changing_ownership(self) -> None:
        image = frame(PAGE_GARAGE_LIST)
        x, y, _w, _h = CARD
        image[y + 6:y + 26, x:x + 130] = (180, 80, 220)
        card = read_card(image, [badge_item(CARD, "A"), name_item(CARD, "ASTON MARTIN DBS GT ZAGATO")],
                         CATALOG, CARD)
        self.assertIsNone(card["stars"])
        self.assertEqual(card["owned"], "unknown")


class StatusTest(unittest.TestCase):
    def test_upgrade_ready_and_unlockable_stay_separate(self) -> None:
        base = [badge_item(CARD, "A")]
        upgrade = read_card(frame(PAGE_GARAGE_LIST),
                            base + [name_item(CARD, "ASTON MARTIN DBS GT ZAGATO"),
                                    status_item(CARD, "升星就绪")], CATALOG, CARD)
        unlock = read_card(frame(PAGE_GARAGE_LIST),
                           base + [name_item(CARD, "ASTON MARTIN DBS GT ZAGATO"),
                                   status_item(CARD, "已可解锁")], CATALOG, CARD)
        self.assertEqual(upgrade["explicit_state"], "upgrade_ready")
        self.assertEqual(unlock["explicit_state"], "unlockable")
        self.assertEqual(unlock["owned"], "not_owned")
        self.assertNotEqual(upgrade["explicit_state"], unlock["explicit_state"])

    def test_key_card_and_dark_card_are_not_owned(self) -> None:
        keyed = read_card(frame(PAGE_GARAGE_LIST),
                          [badge_item(CARD, "A"), name_item(CARD, "ASTON MARTIN DBS GT ZAGATO"),
                           status_item(CARD, "你需要钥匙"), status_item(CARD, "才能永久解锁这辆车")],
                          CATALOG, CARD)
        self.assertEqual(keyed["explicit_state"], "key_required")
        self.assertEqual(keyed["owned"], "not_owned")
        dark = frame(PAGE_GARAGE_LIST)
        x, y, w, h = CARD
        dark[y:y + h, x:x + w] = (12, 12, 12)
        dim = read_card(dark, [badge_item(CARD, "A"), name_item(CARD, "ASTON MARTIN DBS GT ZAGATO")],
                        CATALOG, CARD)
        self.assertEqual(dim["owned"], "unknown")
        self.assertNotEqual(dim["owned"], "owned")


class FieldsTest(unittest.TestCase):
    def test_thousands_separators_and_single_value_performance(self) -> None:
        cases = [("4,185/4,185", [4185, 4185]), ("5,368/5,664", [5368, 5664]),
                 ("1,381", [1381, None]), ("4,471/4,471", [4471, 4471])]
        for text, expected in cases:
            with self.subTest(text=text):
                card = read_card(frame(PAGE_GARAGE_LIST),
                                 [name_item(CARD, "ASTON MARTIN DBS GT ZAGATO"),
                                  field_item(CARD, text, "performance")], CATALOG, CARD)
                self.assertEqual(card["performance"], expected)

    def test_blueprint_and_fuel_are_never_performance(self) -> None:
        ocr = [name_item(CARD, "ASTON MARTIN DBS GT ZAGATO"),
               field_item(CARD, "32/85", "blueprint"),
               field_item(CARD, "3/3", "fuel")]
        card = read_card(frame(PAGE_GARAGE_LIST), ocr, CATALOG, CARD)
        self.assertIsNone(card["performance"])
        self.assertEqual(card["blueprints"], [32, 85])
        self.assertEqual(card["fuel"], 3)

    def test_blueprint_max_marker_is_recorded(self) -> None:
        ocr = [field_item(CARD, "最高", "blueprint")]
        card = read_card(frame(PAGE_GARAGE_LIST), ocr, CATALOG, CARD)
        self.assertTrue(card["blueprint_maxed"])
        self.assertIsNone(card["blueprints"])

    def test_blueprint_may_exceed_its_target(self) -> None:
        card = read_card(frame(PAGE_GARAGE_LIST),
                         [field_item(CARD, "30/27", "blueprint")], CATALOG, CARD)
        self.assertEqual(card["blueprints"], [30, 27])


class PageLevelTest(unittest.TestCase):
    def test_declared_filter_conflict_is_reported_not_owned(self) -> None:
        declared = {"state": "on", "source": "previous_verified_filter_session"}
        ocr = [badge_item(CARD, "A"), name_item(CARD, "ASTON MARTIN DBS GT ZAGATO"),
               status_item(CARD, "已可解锁")]
        page = read_page(frame(PAGE_GARAGE_LIST), ocr, CATALOG,
                         card_boxes=[CARD], declared_owned_filter=declared)
        card = page["cards"][0]
        self.assertIn("declared_owned_filter_conflicts_with_not_owned_evidence", card["conflicts"])
        self.assertNotEqual(card["owned"], "owned")

    def test_declared_filter_assumption_is_labelled(self) -> None:
        ocr = [badge_item(CARD, "A"), name_item(CARD, "ASTON MARTIN DBS GT ZAGATO")]
        page = read_page(frame(PAGE_GARAGE_LIST), ocr, CATALOG, card_boxes=[CARD],
                         declared_owned_filter={"state": "on", "source": "prior_session"})
        self.assertEqual(page["cards"][0]["owned"], "owned")
        self.assertTrue(any("prior_session" in reason for reason in page["cards"][0]["owned_reasons"]))
        plain = read_page(frame(PAGE_GARAGE_LIST), ocr, CATALOG, card_boxes=[CARD])
        self.assertEqual(plain["cards"][0]["owned"], "unknown")

    def test_non_monotonic_performance_does_not_reject_the_page(self) -> None:
        ocr = [badge_item(CARD, "A"), name_item(CARD, "ASTON MARTIN DBS GT ZAGATO"),
               field_item(CARD, "1,381", "performance"),
               badge_item(CARD_RIGHT, "S"), name_item(CARD_RIGHT, "PORSCHE 918 SPYDER ASPHALT EDITION"),
               field_item(CARD_RIGHT, "5,368/5,664", "performance")]
        page = read_page(frame(PAGE_GARAGE_LIST), ocr, CATALOG, card_boxes=[CARD, CARD_RIGHT])
        self.assertEqual(page["page"], PAGE_GARAGE_LIST)
        self.assertEqual([card["performance"] for card in page["cards"]],
                         [[1381, None], [5368, 5664]])

    def test_placeholder_is_not_a_vehicle(self) -> None:
        page = read_page(frame(PAGE_GARAGE_LIST), [status_item(CARD, "新车型即将推出")],
                         CATALOG, card_boxes=[CARD])
        self.assertEqual(page["cards"], [])
        self.assertEqual(len(page["placeholders"]), 1)

    def test_repeated_identical_frames_are_deterministic_not_doubled(self) -> None:
        ocr = [badge_item(CARD, "A"), name_item(CARD, "ASTON MARTIN DBS GT ZAGATO")]
        image = frame(PAGE_GARAGE_LIST)
        first = read_page(image, ocr, CATALOG, card_boxes=[CARD])
        second = read_page(image, ocr, CATALOG, card_boxes=[CARD])
        self.assertEqual(first, second)
        self.assertEqual(len(first["cards"]), 1)

    def test_cards_are_not_read_outside_a_list_page(self) -> None:
        ocr = [badge_item(CARD, "A"), name_item(CARD, "ASTON MARTIN DBS GT ZAGATO")]
        for kind in (PAGE_HOME, PAGE_FILTER_PANEL):
            page = read_page(frame(kind), ocr, CATALOG, card_boxes=[CARD])
            self.assertEqual(page["page"], kind)
            self.assertEqual(page["cards"], [])

    def test_list_page_reports_coverage(self) -> None:
        page = read_page(frame(PAGE_GARAGE_LIST), [], CATALOG, card_boxes=[CARD])
        self.assertIsNotNone(page["coverage"])
        self.assertIn("rows", page["coverage"])


class AspectRatioTest(unittest.TestCase):
    def test_ipad_ratio_reference_is_unsupported(self) -> None:
        ipad = np.zeros((1668, 2420, 3), dtype=np.uint8)
        with self.assertRaises(ValueError):
            normalize(ipad)
        page = read_page(ipad, [name_item([100, 100, 420, 198], "RIMAC NEVERA")], CATALOG)
        self.assertEqual(page["page"], PAGE_UNSUPPORTED)
        self.assertFalse(page["supported"])
        self.assertEqual(page["cards"], [])

    def test_non_16_9_is_rejected_not_stretched(self) -> None:
        for width, height in ((800, 600), (1310, 720), (720, 1280)):
            with self.subTest(size=(width, height)), self.assertRaises(ValueError):
                normalize(np.zeros((height, width, 3), dtype=np.uint8))


class ExecutableBoundaryTest(unittest.TestCase):
    def test_every_output_is_non_executable(self) -> None:
        ocr = [badge_item(CARD, "A"), name_item(CARD, "ASTON MARTIN DBS GT ZAGATO"),
               status_item(CARD, "已可解锁")]
        payloads = [classify_page(frame(PAGE_GARAGE_LIST)),
                    read_owned_filter(frame(PAGE_FILTER_PANEL, checked=True)),
                    card_coverage(frame(PAGE_GARAGE_LIST)),
                    read_card(frame(PAGE_GARAGE_LIST), ocr, CATALOG, CARD),
                    read_page(frame(PAGE_GARAGE_LIST), ocr, CATALOG, card_boxes=[CARD]),
                    read_page(np.zeros((1668, 2420, 3), np.uint8), ocr, CATALOG)]
        for payload in payloads:
            self.assertIs(payload["executable"], False)
            for node in walk(payload):
                self.assertNotIn("target", node)
                if "executable" in node:
                    self.assertIs(node["executable"], False)


class RootEvidenceBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.catalog = [{"id": "g60", "title": "Ginetta G60", "class": "D"}]
        self.ocr = [name_item(CARD, "GINETTA G60"), badge_item(CARD, "D")]

    def test_uncertain_geometry_vetoes_unique_even_when_text_is_good(self):
        result = read_page(frame(PAGE_GARAGE_LIST), self.ocr, self.catalog,
                           card_boxes=[{"box": CARD, "geometry_uncertain": True}])
        card = result["cards"][0]
        self.assertNotEqual(card["identity_status"], "unique")
        self.assertIsNone(card["candidate"])
        self.assertIn("card_geometry_uncertain", card["identity_reasons"])
        clear = read_page(frame(PAGE_GARAGE_LIST), self.ocr, self.catalog, card_boxes=[CARD])
        self.assertEqual(clear["cards"][0]["candidate"]["id"], "g60")

    def test_state_noise_does_not_create_ownership(self):
        for confidence in (.01, .849, True, 2, "0.99", None):
            with self.subTest(confidence=confidence):
                rows = self.ocr + [status_item(CARD, "升星就绪", confidence)]
                card = read_card(frame(PAGE_GARAGE_LIST), rows, self.catalog, CARD)
                self.assertEqual(card["owned"], "unknown")
        card = read_card(frame(PAGE_GARAGE_LIST),
                         self.ocr + [status_item(CARD, "升星就绪", .95)], self.catalog, CARD)
        self.assertEqual(card["explicit_state"], "upgrade_ready")
        self.assertEqual(card["owned"], "owned")

    def test_isolated_ocr_cannot_promote_an_unverified_page(self):
        for confidence in (.01, .99):
            for label in ("已拥有", "筛选条件", "车库等级 仓库"):
                parsed = read_page(np.zeros((720, 1280, 3), np.uint8),
                                   [item(label, [1, 1, 100, 20], confidence)], [])
                self.assertEqual(parsed["page"], PAGE_UNKNOWN)
                self.assertEqual(parsed["owned_filter"]["state"], "unknown")

    def test_larger_same_aspect_frame_is_rejected_not_partially_rescaled(self):
        parsed = read_page(np.zeros((1440, 2560, 3), np.uint8), self.ocr, self.catalog)
        self.assertEqual(parsed["page"], PAGE_UNSUPPORTED)
        self.assertFalse(parsed["supported"])
        self.assertEqual(parsed["cards"], [])

    def test_invalid_badge_confidence_cannot_confirm(self):
        for confidence in (True, 2, "0.99", None):
            with self.subTest(confidence=confidence):
                card = read_card(frame(PAGE_GARAGE_LIST),
                                 [name_item(CARD, "GINETTA G60"), badge_item(CARD, "D", confidence)],
                                 self.catalog, CARD)
                self.assertIsNone(card["class_observation"]["value"])
                self.assertIsNone(card["candidate"])


class StaticNameAndDarkBorderTest(unittest.TestCase):
    def test_caller_page_label_cannot_turn_home_into_a_filter_panel(self):
        self.assertEqual(read_owned_filter(frame(PAGE_HOME), page=PAGE_FILTER_PANEL)["state"], "unknown")

    def test_low_confidence_numeric_fields_are_not_promoted(self):
        rows = [field_item(CARD, "4,000/4,500", "performance"),
                field_item(CARD, "最高", "blueprint"), field_item(CARD, "3/3", "fuel")]
        for row in rows:
            row["confidence"] = .01
        card = read_card(frame(PAGE_GARAGE_LIST), rows, [], CARD)
        self.assertIsNone(card["performance"])
        self.assertIsNone(card["fuel"])
        self.assertFalse(card["blueprint_maxed"])

    @staticmethod
    def _scene(rendered="BASE", reported="BASE"):
        # Independent synthetic typography: the OCR string and rendered pixels
        # can disagree while retaining exactly the same detection box.
        image = frame(PAGE_GARAGE_LIST)
        x, y, w, _ = CARD
        left, top = x + w - 126, y + 110
        cv2.rectangle(image, (left, top), (left + 105, top + 33), (245, 245, 245), -1)
        cv2.putText(image, "MAKER", (left + 7, top + 10), cv2.FONT_HERSHEY_SIMPLEX,
                    .3, (20, 20, 20), 1, cv2.LINE_AA)
        for index, character in enumerate(rendered.replace(" ", "")):
            cv2.putText(image, character, (left + 7 + index * 10, top + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, .35, (20, 20, 20), 1, cv2.LINE_AA)
        rows = [item("MAKER", [left + 5, top + 1, 45, 11], .99),
                item(reported, [left + 5, top + 15, 96, 16], .99),
                badge_item(CARD, "S", .99)]
        catalog = [{"id": "base", "title": "Maker BASE", "class": "S"},
                   {"id": "tail", "title": "Maker BASE TAIL", "class": "S"}]
        return image, rows, catalog

    def test_complete_static_short_title_has_independent_pixel_evidence(self):
        image, rows, catalog = self._scene()
        card = read_page(image, rows, catalog, card_boxes=[CARD])["cards"][0]
        self.assertEqual(card["identity_status"], "unique")
        self.assertEqual(card["candidate"]["id"], "base")
        self.assertTrue(card["name_completeness_evidence"]["complete"])

    def test_omitted_suffix_with_unchanged_wide_ocr_box_stays_ambiguous(self):
        image, rows, catalog = self._scene(rendered="BASE TAIL", reported="BASE")
        card = read_page(image, rows, catalog, card_boxes=[CARD])["cards"][0]
        self.assertNotEqual(card["identity_status"], "unique")
        self.assertIsNone(card["candidate"])

    def test_glyph_proof_cannot_override_uncertain_geometry_or_low_confidence(self):
        image, rows, catalog = self._scene()
        card = read_page(image, rows, catalog,
                         card_boxes=[{"box": CARD, "geometry_uncertain": True}])["cards"][0]
        self.assertIsNone(card["candidate"])
        rows[1]["confidence"] = .75
        card = read_page(image, rows, catalog, card_boxes=[CARD])["cards"][0]
        self.assertIsNone(card["candidate"])

    def test_dark_body_does_not_erase_a_card_with_paired_borders(self):
        image = frame(PAGE_GARAGE_LIST)
        image[225:423] = (18, 18, 18)  # Isolate this card from the fixture's neighbour.
        x, y, w, h = CARD
        image[y:y+h, x:x+w] = (12, 12, 12)
        cv2.rectangle(image, (x, y), (x+w-1, y+h-1), (200, 120, 30), 1)
        boxes = detect_card_boxes(image)
        self.assertTrue(any(abs(b["box"][0]-x) <= 2 and abs(b["box"][2]-w) <= 2
                            and not b["geometry_uncertain"] for b in boxes))
        image[y+h-1, x:x+w] = (12, 12, 12)
        boxes = detect_card_boxes(image)
        self.assertFalse(any(abs(b["box"][0]-x) <= 2 and abs(b["box"][2]-w) <= 2
                             and not b["geometry_uncertain"] for b in boxes))


class LowBrandModelEvidenceTest(unittest.TestCase):
    @staticmethod
    def _scene():
        image = frame(PAGE_GARAGE_LIST)
        x, y, w, _ = CARD
        left, top = x + w - 126, y + 110
        cv2.rectangle(image, (left, top), (left + 105, top + 33), (245, 245, 245), -1)
        # Fourteen separate model glyphs, drawn independently from injected OCR.
        for offset in range(14):
            cv2.putText(image, "H", (left + 7 + offset * 6, top + 26),
                        cv2.FONT_HERSHEY_SIMPLEX, .25, (20, 20, 20), 1, cv2.LINE_AA)
        rows = [item("DO06E", [left + 5, top + 1, 33, 11], .651142),
                item("CHALLENGER SRT8", [left + 5, top + 15, 96, 13], .959318),
                badge_item(CARD, "D", .99)]
        catalog = [{"id": "car", "title": "Dodge Challenger SRT8", "class": "D"}]
        return image, rows, catalog

    def test_low_brand_is_corroboration_with_confidence_cap_and_raw_text(self):
        image, rows, catalog = self._scene()
        card = read_card(image, rows, catalog, CARD)
        self.assertEqual(card["identity_status"], "unique")
        self.assertEqual(card["candidate"]["basis"], "exact_model_with_brand_corroboration")
        self.assertEqual(card["candidate"]["confidence"], .651142)
        self.assertEqual(card["name_text"], ["DO06E", "CHALLENGER SRT8"])
        self.assertTrue(card["name_completeness_evidence"]["complete"])

    def test_wrong_brand_same_model_other_brand_near_model_and_prefix_are_unresolved(self):
        for case in ("wrong_brand", "other_brand", "near_model", "longer_model"):
            with self.subTest(case=case):
                image, rows, catalog = self._scene()
                if case == "wrong_brand":
                    rows[0]["text"] = "HONDA"
                else:
                    title = {"other_brand": "Honda Challenger SRT8",
                             "near_model": "Dodge Challenger SRT9",
                             "longer_model": "Dodge Challenger SRT8 Edition"}[case]
                    catalog.append({"id": "other", "title": title, "class": "C"})
                card = read_card(image, rows, catalog, CARD)
                self.assertNotEqual(card["identity_status"], "unique")
                self.assertIsNone(card["candidate"])

    def test_class_geometry_missing_brand_and_incomplete_model_cannot_confirm(self):
        for case in ("class", "clipped", "uncertain", "missing_brand", "pixel_suffix", "model_confidence"):
            with self.subTest(case=case):
                image, rows, catalog = self._scene()
                kwargs = {}
                if case == "class":
                    rows[-1]["text"] = "C"
                elif case == "clipped":
                    kwargs["clipped_right"] = True
                elif case == "uncertain":
                    kwargs["geometry_uncertain"] = True
                elif case == "missing_brand":
                    rows.pop(0)
                elif case == "pixel_suffix":
                    rows[1]["text"] = "CHALLENGER SRT"
                else:
                    rows[1]["confidence"] = .8
                card = read_card(image, rows, catalog, CARD, **kwargs)
                self.assertNotEqual(card["identity_status"], "unique")
                self.assertIsNone(card["candidate"])


class SimilarSiblingGuardTest(unittest.TestCase):
    def test_exact_same_class_one_letter_siblings_stay_ambiguous(self):
        for first, second, grade in (("Glickenhaus 003S", "Glickenhaus 007S", "A"),
                                      ("Ford GT MK II", "Ford GT MK IV", "B")):
            catalog = [{"id": "first", "title": first, "class": grade},
                       {"id": "second", "title": second, "class": grade}]
            for title in (first, second):
                result = resolve_identity(title, grade, catalog)
                self.assertEqual(result["status"], "ambiguous")
                self.assertNotIn("candidate", result)
                self.assertEqual(set(result["candidates"]), {"first", "second"})

    def test_independent_class_still_separates_different_class_siblings(self):
        catalog = [{"id": "a", "title": "Maker BASE", "class": "A"},
                   {"id": "s", "title": "Maker TASE", "class": "S"}]
        self.assertEqual(resolve_identity("Maker BASE", "A", catalog)["candidate"]["id"], "a")

    def test_pixel_completeness_cannot_override_similar_sibling_guard(self):
        image, rows, catalog = StaticNameAndDarkBorderTest._scene()
        catalog.append({"id": "near", "title": "Maker TASE", "class": "S"})
        card = read_page(image, rows, catalog, card_boxes=[CARD])["cards"][0]
        self.assertTrue(card["name_completeness_evidence"]["complete"])
        self.assertEqual(card["identity_status"], "ambiguous")
        self.assertIsNone(card["candidate"])
        self.assertIn("same_class_one_character_sibling", card["identity_reasons"])

    def test_class_filtered_prefix_exit_also_applies_sibling_guard(self):
        catalog = [{"id": "base", "title": "Maker BASE", "class": "S"},
                   {"id": "tail", "title": "Maker BASE EDITION", "class": "R"},
                   {"id": "near", "title": "Maker TASE", "class": "S"}]
        result = resolve_identity("Maker BASE", "S", catalog)
        self.assertEqual(result["status"], "ambiguous")
        self.assertNotIn("candidate", result)


class CardPixelBadgeTest(unittest.TestCase):
    @staticmethod
    def _scene(letter="D", hole=True):
        image = frame(PAGE_GARAGE_LIST)
        x, y, w, _ = CARD
        left, top = x+w-118, y+89
        image[top:top+20, left:left+21] = (65, 0, 230)
        # Independent small badge typography; no OCR-generated pixels.
        if letter == "D":
            image[top+4:top+17, left+5:left+15] = 245
            image[top+4:top+6, left+14] = (65, 0, 230)
            image[top+16, left+14] = (65, 0, 230)
            if hole:
                image[top+6:top+15, left+8:left+13] = (65, 0, 230)
        else:
            cv2.putText(image, letter, (left+3, top+17), cv2.FONT_HERSHEY_SIMPLEX,
                        .5, (245, 245, 245), 2)
        return image

    def test_low_confidence_d_has_independent_badge_evidence(self):
        catalog = [{"id": "bmw", "title": "BMW Z4 LCI E89", "class": "D"}]
        rows = [name_item(CARD, "BMW Z4 LCI E89"), badge_item(CARD, "D", .542415)]
        card = read_page(self._scene(), rows, catalog, card_boxes=[CARD])["cards"][0]
        self.assertEqual(card["candidate"]["id"], "bmw")
        self.assertEqual(card["class_observation"]["source"], "pixel_badge")
        self.assertIsNone(card["class_observation"]["confidence"])
        clipped = read_card(self._scene(), rows, catalog, CARD, clipped_right=True)
        self.assertIsNone(clipped["candidate"])

    def test_antialiased_cap_keeps_the_uninterrupted_vertical_stem(self):
        image = self._scene()
        left, top = CARD[0]+CARD[2]-118, CARD[1]+89
        # A faint cap protrudes left, while the actual stem is one white column.
        image[top+4:top+17, left+5] = (65, 0, 230)
        image[top+5, left+5] = 181
        image[top+6:top+15, left+7] = (65, 0, 230)
        catalog = [{"id": "ktm", "title": "KTM X-BOW GTX", "class": "D"}]
        rows = [name_item(CARD, "KTM X-BOW GTX"), badge_item(CARD, "□", .360813)]
        card = read_card(image, rows, catalog, CARD)
        self.assertEqual(card["candidate"]["id"], "ktm")
        self.assertEqual(card["class_observation"]["evidence"]["left_stem_column_offset"], 1)
        # Break only the geometric straight stem, leaving the enclosed counter
        # intact by stepping the ink one column left at that row.
        image[top+10, left+6] = (65, 0, 230)
        image[top+9:top+12, left+5] = 245
        self.assertIsNone(read_card(image, rows, catalog, CARD)["candidate"])

    def test_independent_d_excludes_cross_class_longer_title(self):
        catalog = [{"id": "base", "title": "Nissan 370Z NISMO", "class": "D"},
                   {"id": "long", "title": "Nissan 370Z NISMO Edition", "class": "C"}]
        rows = [name_item(CARD, "NISSAN 370ZNISM0"), badge_item(CARD, "D", .459462)]
        card = read_card(self._scene(), rows, catalog, CARD)
        self.assertEqual(card["candidate"]["id"], "base")
        self.assertEqual(card["identity_basis"], "fuzzy_full_name")
        self.assertIn("class_badge_excluded_differently_classed_siblings", card["identity_reasons"])
        catalog[1]["class"] = "D"
        self.assertIsNone(read_card(self._scene(), rows, catalog, CARD)["candidate"])

    def test_background_missing_counter_and_non_d_cannot_supply_class(self):
        catalog = [{"id": "base", "title": "Maker BASE", "class": "D"}]
        rows = [name_item(CARD, "MAKER BASE")]
        for image in (frame(PAGE_GARAGE_LIST), self._scene(hole=False), self._scene("B"),
                      self._scene("O")):
            card = read_card(image, rows, catalog, CARD)
            self.assertIsNone(card["class_observation"]["value"])
            self.assertIsNone(card["candidate"])
        for badges in ([badge_item(CARD, "C")], [badge_item(CARD, "C"), badge_item(CARD, "D")]):
            card = read_card(self._scene(), rows+badges, catalog, CARD)
            self.assertIsNone(card["candidate"])
            self.assertEqual(card["class_observation"]["source"], "ocr_badge")


if __name__ == "__main__":
    unittest.main()
