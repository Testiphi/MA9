from __future__ import annotations

import json
import unittest
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_selection import plan_live_weak_defense
from ma9_agent.duel_vehicle_screen import (read_clipped_candidate, read_visible_cards,
                                           rolling_identity, _name_bands)
from ma9_agent.vehicle_screen import _key, match_vehicle

#: The shipped full catalog, used as read-only input by the tail-rejection test.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


# Verbatim OCR output of the frozen live frame recorded at
# 2026-09-22 23:18:23.444 in
# E:/hzz/work/MA9-evidence/20260922-231746-ordering-handoff/maafw.log
# (the run that aborted with "D-class ratings contradict the game's ordering").
# Selection rule: every item whose box falls inside one of the two row name
# bands (y 323-358 and 550-585) or inside one of the four cards' performance
# ROI. Those are the only boxes read_visible_cards consults, so the subset is
# behaviourally equivalent to the full recorded call.
_RECORDED_PAGE = [
    {"text": "62.64", "confidence": .996, "box": [38, 323, 112, 31]},
    {"text": "HYUNDAI", "confidence": .997, "box": [188, 329, 97, 26]},
    {"text": "IONIQ 5 N", "confidence": .926, "box": [190, 350, 90, 23]},
    {"text": "INFINIT", "confidence": .912, "box": [628, 334, 65, 19]},
    {"text": "PROJECT", "confidence": .990, "box": [625, 349, 85, 22]},
    {"text": "BLACK S", "confidence": .972, "box": [712, 350, 82, 22]},
    {"text": "Praga", "confidence": .956, "box": [189, 557, 72, 27]},
    {"text": "R1", "confidence": .996, "box": [189, 578, 28, 21]},
    {"text": "PEUGEOT", "confidence": .993, "box": [628, 557, 96, 26]},
    {"text": "SR1", "confidence": .993, "box": [626, 578, 40, 21]},
    {"text": "290.7", "confidence": .998, "box": [33, 190, 113, 32]},
    {"text": "@71.54", "confidence": .877, "box": [32, 231, 117, 36]},
    {"text": "2.559", "confidence": .878, "box": [186, 194, 108, 47]},
    {"text": "2.559/2,624", "confidence": .946, "box": [188, 423, 189, 43]},
    {"text": "2.371", "confidence": .915, "box": [620, 186, 112, 56]},
    {"text": "2307", "confidence": .864, "box": [625, 423, 103, 44]},
]

_RECORDED_CATALOG = [
    {"id": "glickenhaus", "title": "Glickenhaus 004C", "class": "D"},
    {"id": "giulia", "title": "Alfa Romeo Giulia GTAm", "class": "D"},
    {"id": "ginetta", "title": "Ginetta G60", "class": "D"},
    {"id": "countach", "title": "Lamborghini Countach 25th Anniversary", "class": "D"},
    {"id": "ioniq", "title": "Hyundai IONIQ 5 N", "class": "D"},
    {"id": "praga", "title": "Praga R1", "class": "D"},
    {"id": "infiniti", "title": "Infiniti Project Black S", "class": "D"},
    {"id": "peugeot", "title": "Peugeot SR1", "class": "D"},
    {"id": "supra", "title": "Toyota GR Supra Racing Concept", "class": "D"},
    {"id": "i8", "title": "BMW i8 Roadster", "class": "D"},
    {"id": "leaf", "title": "Nissan Leaf Nismo RC", "class": "D"},
    {"id": "etense", "title": "DS Automobiles DS E-Tense", "class": "D"},
    {"id": "emira", "title": "Lotus Emira", "class": "D"},
    {"id": "csl", "title": "BMW 3.0 CSL Hommage", "class": "D"},
    {"id": "xlsport", "title": "Volkswagen XL Sport Concept", "class": "D"},
    {"id": "xbow", "title": "KTM X-Bow GTX", "class": "D"},
    {"id": "challenger", "title": "Dodge Challenger SRT8", "class": "D"},
    {"id": "camaro", "title": "Chevrolet Camaro LT", "class": "D"},
    {"id": "porsche", "title": "Porsche 911 Carrera RS 3.8", "class": "D"},
    {"id": "z4", "title": "BMW Z4 LCI E89", "class": "D"},
    {"id": "lancer", "title": "Mitsubishi Lancer Evolution", "class": "D"},
]

# Ratings exactly as the frozen report recorded them, in list order.
_RECORDED_RATINGS = [
    ("glickenhaus", 2840, None), ("giulia", 2803, 2895), ("ginetta", 2632, None),
    ("countach", 2613, None), ("ioniq", 7154, None), ("praga", 2559, 2624),
    ("infiniti", 2371, None), ("peugeot", 2307, None), ("supra", 2124, 2124),
    ("i8", 2122, None), ("leaf", 2101, None), ("etense", 976, None),
    ("emira", 1834, 1834), ("csl", 1827, None), ("xlsport", 1814, None),
    ("xbow", 1738, None), ("challenger", 1683, None), ("camaro", 1546, None),
    ("porsche", 1516, 1516), ("z4", 1476, None), ("lancer", 1381, None),
]


def _recorded_scan(replacements: dict[str, int] | None = None) -> dict:
    overrides = replacements or {}
    titles = {row["id"]: row["title"] for row in _RECORDED_CATALOG}
    return {
        "status": "class_ladder_complete",
        "vehicles": [
            {"vehicle": {"id": vehicle_id, "title": titles[vehicle_id], "confidence": 1.0},
             "class": "D",
             "performance": [overrides.get(vehicle_id, rating), maximum],
             "page": 1}
            for vehicle_id, rating, maximum in _RECORDED_RATINGS
        ],
    }


class DuelVehicleScreenTest(unittest.TestCase):
    @staticmethod
    def _name_words():
        return [
            {"text": "CHEVROLET", "confidence": .99, "box": [100, 325, 110, 20]},
            {"text": "CAMARO LT", "confidence": .99, "box": [100, 345, 115, 20]},
        ]

    @staticmethod
    def _catalog():
        return [{"id": "camaro", "title": "Chevrolet Camaro LT", "class": "D"}]

    def test_retry_ocr_accepts_current_only_rating(self) -> None:
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        catalog = self._catalog()
        words = self._name_words()

        cards = read_visible_cards(
            image,
            words,
            catalog,
            retry_ocr=lambda _roi: [
                {"text": "1,546", "confidence": .99, "box": [0, 0, 80, 25]},
            ],
        )

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["vehicle"]["id"], "camaro")
        self.assertEqual(cards[0]["performance"], [1546, None])

    def test_clear_four_digit_current_rating_avoids_retry_ocr(self) -> None:
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        for rating in ("1,546", "1.546"):
            with self.subTest(rating=rating):
                words = [*self._name_words(),
                         {"text": rating, "confidence": .99, "box": [110, 205, 80, 25]}]
                retries = []
                cards = read_visible_cards(image, words, self._catalog(),
                                           retry_ocr=lambda roi: retries.append(roi) or [])
                self.assertEqual(cards[0]["performance"], [1546, None])
                self.assertEqual(retries, [])

    def test_ambiguous_or_possibly_clipped_current_rating_still_retries(self) -> None:
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        for name, ratings in (
                ("multiple", ["546", "1,546"]),
                ("possibly_clipped", ["546"]),
                ("incomplete", ["1,5"]),
        ):
            with self.subTest(name=name):
                words = [*self._name_words(),
                         *[{"text": value, "confidence": .99,
                            "box": [110 + 82 * index, 205, 75, 25]}
                           for index, value in enumerate(ratings)]]
                retries = []
                cards = read_visible_cards(image, words, self._catalog(),
                                           retry_ocr=lambda roi: retries.append(roi) or [])
                self.assertEqual(len(retries), 1)
                if name == "incomplete":
                    self.assertIsNone(cards[0]["performance"])
                else:
                    self.assertEqual(cards[0]["performance"], [546, None])

    def test_noncanonical_or_low_conflicting_values_do_not_take_fast_path(self) -> None:
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        cases = (
            ("decimal_speed", [("270.1", .99)], [2701, None]),
            ("incomplete_fraction", [("1546/??", .99)], [1546, None]),
            ("low_conflict", [("1,546", .99), ("1,547", .5)], [1546, None]),
        )
        for name, readings, expected in cases:
            with self.subTest(name=name):
                words = [*self._name_words(),
                         *[{"text": value, "confidence": confidence,
                            "box": [110 + 82 * index, 205, 75, 25]}
                           for index, (value, confidence) in enumerate(readings)]]
                retries = []
                cards = read_visible_cards(image, words, self._catalog(),
                                           retry_ocr=lambda roi: retries.append(roi) or [])
                self.assertEqual(cards[0]["performance"], expected)
                self.assertEqual(len(retries), 1)

    def test_recorded_statistic_cannot_move_a_card_edge_or_fake_a_rating(self) -> None:
        """The frozen 23:18:23.444 frame must read 2559, never 7154.

        The last statistic of the partly visible column on the left sits at the
        same height as this row's model line. It entered the name band as
        "62.64", merged into IONIQ's group, and pulled the card's left edge
        150 px leftwards; the performance ROI then also covered the
        neighbouring "290.7" and "@71.54" statistics, and the digits-only
        fallback fabricated 7154. The garage ordering guard rejected that
        reading, so the whole run stopped before any car was assigned.
        """
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        cards = {row["vehicle"]["id"]: row for row in read_visible_cards(
            image, _RECORDED_PAGE, _RECORDED_CATALOG)}

        self.assertEqual(cards["ioniq"]["card"][0], 184)
        self.assertEqual(cards["ioniq"]["target"], [369, 273])
        self.assertEqual(cards["ioniq"]["performance"], [2559, None])
        self.assertNotIn(7154, [row["performance"][0] for row in cards.values()])
        # The neighbouring cards keep the geometry and ratings they already had.
        self.assertEqual(cards["praga"]["card"][0], 185)
        self.assertEqual(cards["praga"]["performance"], [2559, 2624])
        self.assertEqual(cards["infiniti"]["performance"], [2371, None])
        self.assertEqual(cards["peugeot"]["performance"], [2307, None])

    def test_recorded_garage_reaches_a_five_car_plan_once_the_frame_is_reread(self) -> None:
        """End to end over the frozen garage: the frame drives the plan.

        The ratings fed to the planner are the ones this module produces from
        the recorded frame, not literals, so the whole chain
        frame -> read_visible_cards -> plan is exercised. The frozen report's
        own reading of 7154 stays as the negative control that proves the
        ordering guard was not weakened.
        """
        tracks = {"complete": True,
                  "tracks": [{"big": "大地图", "small": f"小地图{index}"}
                             for index in range(1, 6)]}
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        reread = {row["vehicle"]["id"]: row["performance"][0]
                  for row in read_visible_cards(
                      image, _RECORDED_PAGE, _RECORDED_CATALOG)}
        recorded = {vehicle_id: rating for vehicle_id, rating, _maximum
                    in _RECORDED_RATINGS}
        self.assertEqual(
            {key: value for key, value in reread.items() if value != recorded[key]},
            {"ioniq": 2559})

        with self.assertRaises(ValueError) as raised:
            plan_live_weak_defense(tracks, _recorded_scan())
        self.assertEqual(str(raised.exception),
                         "D-class ratings contradict the game's ordering")

        plan = plan_live_weak_defense(tracks, _recorded_scan(reread))
        self.assertTrue(plan["complete"])
        self.assertFalse(plan["starts_race"])
        self.assertEqual(plan["classes_used"], ["D"])
        self.assertEqual([slot["performance"] for slot in plan["slots"]],
                         [1381, 1476, 1516, 1546, 1683])
        self.assertEqual(len({slot["vehicle_id"] for slot in plan["slots"]}), 5)


# Name-band OCR of the two frozen "FE3 fully visible" frames in
# E:/hzz/work/MA9/MA9-evidence/20260925-fe3-full-intake/native-results.json
# (real MaaFW native OCR).  Only the two name bands are kept: they are the only
# boxes read_visible_cards consults for identity, and the black placeholder
# frame keeps this a text-only reading, never a star or pixel claim.  The card
# of Formula E Gen 3 EVO Championship Edition is *fully visible* at x 690/694 in
# both frames; only its scrolling name never reads whole.
_ROLLING_FRAME_A = [
    {"text": "GLICKENHAUS", "confidence": .996, "box": [258, 330, 142, 23]},
    {"text": "007S", "confidence": .971, "box": [256, 350, 56, 23]},
    {"text": "FORMU", "confidence": .989, "box": [698, 333, 66, 20]},
    {"text": "GEN 3 EVO CHAMPION", "confidence": .931, "box": [698, 350, 196, 22]},
    {"text": "FERRARI", "confidence": .979, "box": [1133, 329, 89, 24]},
    {"text": "ENZO FERRARI", "confidence": .965, "box": [1132, 350, 132, 22]},
    {"text": "MCLAREN", "confidence": .936, "box": [256, 556, 101, 26]},
    {"text": "650S GT3", "confidence": .966, "box": [256, 578, 94, 22]},
    {"text": "LEXUS", "confidence": .995, "box": [694, 558, 74, 22]},
    {"text": "ELECTRIFIED SPORT t", "confidence": .931, "box": [704, 578, 192, 22]},
    {"text": "RAESR", "confidence": .984, "box": [1133, 558, 75, 22]},
    {"text": "TACHYON SPEED", "confidence": .960, "box": [1132, 578, 147, 22]},
]
_ROLLING_FRAME_B = [
    {"text": "GLICKENHAUS", "confidence": .995, "box": [258, 330, 142, 23]},
    {"text": "007S", "confidence": .971, "box": [256, 350, 56, 23]},
    {"text": "FORMU", "confidence": .989, "box": [697, 332, 72, 22]},
    {"text": "V 3 EV0 CHAMPIONSH", "confidence": .930, "box": [694, 350, 199, 22]},
    {"text": "FERRARI", "confidence": .979, "box": [1133, 329, 89, 24]},
    {"text": "ENZO FERRARI", "confidence": .961, "box": [1132, 350, 132, 22]},
    {"text": "MCLAREN", "confidence": .936, "box": [256, 556, 101, 26]},
    {"text": "650S GT3", "confidence": .966, "box": [256, 578, 94, 22]},
    {"text": "LEXUS", "confidence": .993, "box": [694, 557, 72, 22]},
    {"text": "ELECTRIFIED SPOI", "confidence": .985, "box": [733, 578, 161, 22]},
    {"text": "RAESR", "confidence": .984, "box": [1132, 558, 76, 22]},
    {"text": "TACHYON SPEED", "confidence": .957, "box": [1132, 578, 147, 22]},
]
# The clipped right-edge card of the real 11:55:52.818 page of the slot-3 scan
# (the page after which the fling lost the car), and of 11:55:55.256, whose
# fragments of the same car never reach the minimum evidence.
_ROLLING_EDGE_DECIDES = [
    {"text": "FORMU", "confidence": .993, "box": [1077, 332, 72, 22]},
    {"text": "J CHAMPIONSHIP EDIT", "confidence": .947, "box": [1073, 350, 201, 22]},
]
_ROLLING_EDGE_TOO_SHORT = [
    {"text": "FORMULAE", "confidence": .989, "box": [990, 332, 116, 22]},
    {"text": "P EDITION", "confidence": .956, "box": [988, 350, 88, 22]},
    {"text": "GEN 3 EV", "confidence": .931, "box": [1109, 350, 80, 22]},
]

_ROLLING_CATALOG = [
    {"id": "fe3", "title": "Formula E Gen 3 EVO Championship Edition", "class": "A"},
    {"id": "fe2", "title": "Formula E Gen 2 Asphalt Edition", "class": "B"},
    {"id": "glickenhaus007", "title": "Glickenhaus 007S", "class": "A"},
    {"id": "mclaren650", "title": "McLaren 650S GT3", "class": "A"},
    {"id": "lexus", "title": "Lexus Electrified Sport Concept", "class": "A"},
    {"id": "raesr", "title": "Raesr Tachyon Speed", "class": "A"},
    {"id": "ferrari_enzo", "title": "Ferrari Enzo Ferrari", "class": "A"},
    {"id": "nevera", "title": "Rimac Nevera", "class": "S"},
    {"id": "nevera_r", "title": "Rimac Nevera R", "class": "R"},
    {"id": "glickenhaus004", "title": "Glickenhaus 004C", "class": "D"},
    {"id": "praga", "title": "Praga R1", "class": "D"},
    {"id": "nissan370", "title": "Nissan 370Z Nismo", "class": "C"},
    {"id": "ginetta", "title": "Ginetta G60", "class": "D"},
]


class DuelRollingNameTest(unittest.TestCase):
    """The scrolling-name fallback and the clipped right-edge candidate."""

    def test_recorded_scrolling_frames_resolve_fe3_and_keep_their_neighbours(self) -> None:
        """Both frozen frames must read FE3, and nothing else may move.

        ``match_vehicle`` scores the visible ``FORMU`` + ``GEN 3 EVO CHAMPION``
        at .777, just under its .78 gate, which is why the live run never saw
        the car.  The fallback resolves it from the fragment itself; the three
        cards that were already exact keep their exact reading.
        """
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        for name, rows, left in (("frame_a", _ROLLING_FRAME_A, 694),
                                 ("frame_b", _ROLLING_FRAME_B, 690)):
            with self.subTest(frame=name):
                cards = {row["vehicle"]["id"]: row for row in read_visible_cards(
                    image, rows, _ROLLING_CATALOG)}
                self.assertEqual(set(cards), {"fe3", "glickenhaus007", "mclaren650",
                                              "lexus"})
                self.assertEqual(cards["fe3"]["card"][:2], [left, 168])
                self.assertEqual(cards["fe3"]["vehicle"]["identity_basis"],
                                 "rolling_fragment")
                self.assertEqual(cards["fe3"]["vehicle"]["title"],
                                 "Formula E Gen 3 EVO Championship Edition")
                for neighbour in ("glickenhaus007", "mclaren650", "lexus"):
                    self.assertEqual(cards[neighbour]["identity_basis"], "title")

    def test_clipped_right_edge_card_is_reported_only_when_its_name_decides(self) -> None:
        """The clipped card is offered for a re-position, never for a click.

        Its geometry stays outside the complete-card bound, so the caller can
        only use it to ask for one more observation.
        """
        decided = read_clipped_candidate(_ROLLING_EDGE_DECIDES, _ROLLING_CATALOG)
        self.assertEqual(decided["vehicle"]["id"], "fe3")
        self.assertTrue(decided["clipped"])
        self.assertEqual(decided["visible_name"], ["J CHAMPIONSHIP EDIT", "FORMU"])
        self.assertGreaterEqual(decided["card"][0], 1069)
        self.assertGreater(decided["card"][0] + decided["card"][2], 1295)
        self.assertEqual(read_clipped_candidate(_ROLLING_EDGE_TOO_SHORT,
                                               _ROLLING_CATALOG), None)
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.assertEqual(read_visible_cards(image, _ROLLING_EDGE_DECIDES,
                                            _ROLLING_CATALOG), [])

    def test_clipped_candidate_offers_no_click_target(self) -> None:
        """The clipped record is explicitly non-clickable; full cards are not.

        Real call premise: ``read_clipped_candidate`` resolves a right-edge card
        only so the scan can trade one bounded re-position for a full read, so
        its row must not carry the ``target`` key that a caller could click.
        The complete-card rows keep their existing format -- this test reads the
        same frozen frames through both helpers and compares the two shapes.
        """
        decided = read_clipped_candidate(_ROLLING_EDGE_DECIDES, _ROLLING_CATALOG)
        self.assertTrue(decided["clipped"])
        self.assertEqual(decided["vehicle"]["id"], "fe3")
        self.assertIn("card", decided)
        self.assertIn("vehicle", decided)
        self.assertNotIn("target", decided)

        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        rows = {row["vehicle"]["id"]: row for row in read_visible_cards(
            image, _ROLLING_FRAME_A, _ROLLING_CATALOG)}
        self.assertIn("target", rows["fe3"])
        self.assertEqual(rows["fe3"]["target"], [694 + 185, 168 + 105])

    def test_scrolling_name_negatives_never_decide(self) -> None:
        """Every documented undecidable fragment shape must stay unresolved."""
        cases = {
            # A near name of the same family stays itself, and never becomes FE3.
            "fe2_stays_gen2": ([("FORMULA E", .99, [100, 325, 110, 20]),
                                ("GEN 2 ASPHALT EDITION", .97, [100, 345, 200, 20])],
                               "fe2"),
            "model_tail_too_short": ([("FORMULA E", .99, [100, 325, 110, 20]),
                                      ("GEN 3 EV", .98, [100, 345, 80, 20])], None),
            "generic_word_only": ([("FORMULA E", .99, [100, 325, 110, 20]),
                                   ("EDITION", .97, [100, 345, 80, 20])], None),
            "brand_line_only": ([("FORMULA E", .99, [100, 325, 110, 20]),
                                 ("GEN 3", .97, [100, 345, 60, 20])], None),
            # Text of another card can never join this card's identity block.
            "cross_card_mix": ([("FORMU", .99, [100, 325, 66, 20]),
                                ("TACHYON SPEED", .97, [520, 345, 152, 22])], None),
            "brand_contradicts_model": ([("FORMU", .99, [100, 325, 66, 20]),
                                         ("650S GT3", .97, [100, 345, 95, 22])], None),
            "low_confidence_fragment": ([("FORMU", .99, [100, 325, 66, 20]),
                                         ("GEN 3 EVO CHAMPION", .80,
                                          [100, 345, 196, 22])], None),
            # Short names keep going through the exact matcher, never this rule.
            "nevera_without_suffix": ([("RIMAC", .99, [100, 325, 60, 20]),
                                       ("NEVERA", .97, [100, 345, 70, 20])], None),
            "digit_name_370z": ([("NISSAN", .99, [100, 325, 66, 20]),
                                 ("370Z NISMO", .97, [100, 345, 110, 20])], None),
            "four_digit_name_004c": ([("GLICKENHAUS", .99, [100, 325, 120, 20]),
                                      ("004C", .97, [100, 345, 50, 20])], None),
            "one_letter_suffix_r1": ([("PRAGA", .99, [100, 325, 60, 20]),
                                      ("R1", .97, [100, 345, 30, 20])], None),
        }
        for name, (rows, expected) in cases.items():
            with self.subTest(case=name):
                resolved = rolling_identity(
                    [{"text": text, "confidence": confidence, "box": box}
                     for text, confidence, box in rows], _ROLLING_CATALOG)
                self.assertEqual(resolved["id"] if resolved else None, expected)

    def test_scrolling_name_positives_follow_the_recorded_fragments(self) -> None:
        """Each evidenced fragment shape resolves, and only to its own car."""
        head = [("FORMU", .99, [100, 325, 66, 20])]
        cases = {
            "head_fragment": ([*head, ("GEN 3 EVO CHAMPION", .93, [100, 345, 196, 22])],
                              "fe3"),
            "wrapped_tail": ([("FORMULAE", .99, [100, 325, 90, 20]),
                              ("J CHAMPIONSHIP EDIT", .95, [100, 345, 201, 22])], "fe3"),
            "ocr_reads_zero": ([*head, ("V 3 EV0 CHAMPIONSH", .93,
                                        [100, 345, 199, 22])], "fe3"),
            "gen2_keeps_its_own_reading": ([("FORMULA E", .99, [100, 325, 110, 20]),
                                            ("GEN 2 ASPHALT EDITION", .97,
                                             [100, 345, 200, 20])], "fe2"),
        }
        for name, (rows, expected) in cases.items():
            with self.subTest(case=name):
                resolved = rolling_identity(
                    [{"text": text, "confidence": confidence, "box": box}
                     for text, confidence, box in rows], _ROLLING_CATALOG)
                self.assertEqual(resolved["id"], expected)

    def test_one_extra_candidate_rejects_the_rolling_reading(self) -> None:
        """Uniqueness is over the whole catalog, and a twin removes the match."""
        rows = [{"text": "FORMU", "confidence": .99, "box": [100, 325, 66, 20]},
                {"text": "GEN 3 EVO CHAMPION", "confidence": .93, "box": [100, 345, 196, 22]}]
        twin = [{"id": "twin", "title": "Formula E Gen 3 EVO Championship Edition RS",
                 "class": "B"}]
        self.assertEqual(rolling_identity(rows, _ROLLING_CATALOG)["id"], "fe3")
        self.assertIsNone(rolling_identity(rows, _ROLLING_CATALOG + twin))

    def test_third_identity_line_rejects_the_rolling_reading(self) -> None:
        """Fragments of two pages must never be combined into one identity."""
        rows = [{"text": "FORMU", "confidence": .99, "box": [100, 325, 66, 20]},
                {"text": "GEN 3 EVO CHAMPION", "confidence": .93, "box": [100, 345, 196, 22]},
                {"text": "TACHYON SPEED", "confidence": .97, "box": [100, 468, 152, 22]}]
        self.assertIsNone(rolling_identity(rows, _ROLLING_CATALOG))


class DuelRollingTailTest(unittest.TestCase):
    """A long fragment is matched whole, never as an unexplained prefix."""

    @staticmethod
    def _real_catalog() -> list[dict]:
        return json.loads((_PROJECT_ROOT / "data" / "generated" /
                           "vehicle_catalog.json").read_text(encoding="utf8"))["vehicles"]

    def test_contradictory_long_tail_is_rejected_over_the_real_catalog(self) -> None:
        """Synthetic contradictory name over the real catalog and matchers.

        Real call premise: the two words are the shape the live OCR produces for
        a scrolling Duel name -- a truncated brand line and then a model line --
        and both readings are high confidence.  Both go through the real
        :func:`vehicle_screen.match_vehicle` and the real :func:`rolling_identity`
        over the shipped ``data/generated/vehicle_catalog.json`` with no
        hand-picked catalog and no stubbed matcher.  ``CHAMPIONSHIP EDITION``
        aligns inside the Gen 3 car's name, but ``UNRELATEDZZZZZZZZ`` is a tail
        that name cannot explain: a long fragment whose tail is unexplained is a
        contradiction, not a short match, so both matchers must return ``None``.
        This is a synthetic name, not a device reading.
        """
        catalog = self._real_catalog()
        words = [
            {"text": "FORMU", "confidence": .99, "box": [100, 330, 80, 20]},
            {"text": "CHAMPIONSHIP EDITION UNRELATEDZZZZZZZZ", "confidence": .99,
             "box": [100, 350, 210, 20]},
        ]
        self.assertIsNone(match_vehicle(words, catalog))
        self.assertIsNone(rolling_identity(words, catalog))
        # The Gen 3 car is in the catalog and its key does contain the fragment
        # prefix, so the rejection is the tail rule and not a missing entry.
        gen3 = next(row for row in catalog
                    if row["title"] == "Formula E Gen 3 EVO Championship Edition")
        self.assertIn("championshipedition", _key(gen3["title"]))

    def test_recorded_rolling_fragments_still_resolve_after_the_tail_rule(self) -> None:
        """The full-consumption rule keeps the evidenced recorded shapes.

        Real call premise: the same two recorded high-confidence fragments the
        module already resolves -- ``FORMU`` + ``GEN 3 EVO CHAMPION`` and the
        wrapped ``FORMULAE`` + ``J CHAMPIONSHIP EDIT`` -- are matched whole after
        the one allowed leading character, so requiring the whole fragment does
        not cost the positives.  Text-only reading of the frozen OCR rows.
        """
        cases = {
            "head_fragment": [("FORMU", .99, [100, 325, 66, 20]),
                              ("GEN 3 EVO CHAMPION", .93, [100, 345, 196, 22])],
            "wrapped_tail": [("FORMULAE", .99, [100, 325, 90, 20]),
                             ("J CHAMPIONSHIP EDIT", .95, [100, 345, 201, 22])],
        }
        for name, rows in cases.items():
            with self.subTest(case=name):
                resolved = rolling_identity(
                    [{"text": text, "confidence": confidence, "box": box}
                     for text, confidence, box in rows], _ROLLING_CATALOG)
                self.assertEqual(resolved["id"], "fe3")


class DuelFamilyIdentityTest(unittest.TestCase):
    """A scrolling common prefix cannot choose a shorter family member."""

    CATALOG = [
        {"id": "anniversary", "title": "Ford Mustang RTR Spec 5 10th Anniv.", "class": "B"},
        {"id": "fd", "title": "Ford Mustang RTR Spec 5-FD", "class": "S"},
    ]

    def _read(self, brand: str, model: str, catalog=None):
        words = [{"text": brand, "confidence": .97, "box": [396, 558, 62, 24]},
                 {"text": model, "confidence": .96, "box": [400, 578, 190, 22]}]
        return read_visible_cards(np.zeros((720, 1280, 3), dtype=np.uint8),
                                  words, catalog or self.CATALOG)

    def test_common_prefix_is_ambiguous_and_anniversary_tail_is_unique(self):
        for model in ("MUSTANG RTR", "MUSTANG RTR SPEC 5", "MUSTANG RTR SF"):
            with self.subTest(model=model):
                self.assertEqual(self._read("FORD", model), [])
        for model in ("SPEC 5 10TH ANNIV.", "JSTANG RTR SPEC 5 11"):
            with self.subTest(model=model):
                self.assertEqual(self._read("FORD", model)[0]["vehicle"]["id"],
                                 "anniversary")

    def test_full_fd_stays_fd_and_unknown_tail_does_not_complete(self):
        self.assertEqual(self._read("FORD", "MUSTANG RTR SPEC 5-FD")
                         [0]["vehicle"]["id"], "fd")
        self.assertEqual(self._read("FORD", "MUSTANG RTR SPEC 5 UNKNOWN"), [])

    def test_neighbour_statistic_cannot_choose_fd_from_ambiguous_ford_name(self):
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        neighbour = {"text": "18", "confidence": .99, "box": [0, 552, 24, 28]}
        brand = {"text": "FORD", "confidence": .99, "box": [64, 560, 62, 19]}
        for model in (
            {"text": "MUSTANG RTR SPEC !", "confidence": .99,
             "box": [69, 578, 196, 22]},
            {"text": "USTANG RTR SPEC 5 1", "confidence": .99,
             "box": [64, 578, 201, 22]},
        ):
            with self.subTest(model=model["text"]):
                clean = read_visible_cards(image, [brand, model], self.CATALOG)
                self.assertEqual(clean, [])
                for text in ("18", "58.18", "58,18", "58 18", "18.0", "18%"):
                    with self.subTest(neighbour=text):
                        noisy = read_visible_cards(image, [{**neighbour, "text": text}, brand, model],
                                                   self.CATALOG)
                        self.assertEqual(noisy, clean)

        complete = {"text": "MUSTANG RTR SPEC 5-FD", "confidence": .99,
                    "box": [64, 578, 201, 22]}
        clean = read_visible_cards(image, [brand, complete], self.CATALOG)
        noisy = read_visible_cards(image, [neighbour, brand, complete], self.CATALOG)
        self.assertEqual(noisy, clean)
        self.assertEqual(noisy[0]["vehicle"]["id"], "fd")

    def test_digits_inside_name_band_are_retained(self):
        brand = {"text": "PORSCHE", "confidence": .99, "box": [64, 560, 92, 19]}
        for model in ("911", "918", "004C", "G60", "911.5"):
            with self.subTest(model=model):
                number = {"text": model, "confidence": .99,
                          "box": [64, 578, 50, 22]}
                bands = _name_bands([brand, number], 395)
                self.assertEqual([item["text"] for item in bands[0][1]],
                                 ["PORSCHE", model])

        crossing = {"text": "918", "confidence": .99,
                    "box": [58, 578, 3, 22]}
        bands = _name_bands([brand, crossing], 395)
        self.assertEqual(bands[0][0], 60)
        self.assertIn(crossing, bands[0][1])

    def test_short_name_and_unanchored_brand_keep_generic_match(self):
        self.assertEqual(self._read("RIMAC", "NEVERA", [
            {"id": "nevera", "title": "Rimac Nevera", "class": "S"}])
                         [0]["vehicle"]["id"], "nevera")

    def test_complete_short_title_survives_a_longer_edition(self):
        catalog = [
            {"id": "short", "title": "W Motors Lykan Hypersport", "class": "S"},
            {"id": "edition", "title": "W Motors Lykan Hypersport Neon Edition", "class": "S"},
        ]
        self.assertEqual(self._read("W MOTORS", "LYKAN HYPERSPORT", catalog)
                         [0]["vehicle"]["id"], "short")
        self.assertEqual(self._read("W MOTORS", "LYKAN HYPERSPORT NEON EDITION",
                                    catalog)[0]["vehicle"]["id"], "edition")
        self.assertEqual(self._read("W MOTORS", "LYKAN HYPERSPORT EXTRA EDITION",
                                    catalog), [])


if __name__ == "__main__":
    unittest.main()
