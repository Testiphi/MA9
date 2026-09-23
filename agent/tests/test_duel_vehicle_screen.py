from __future__ import annotations

import unittest
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_selection import plan_live_weak_defense
from ma9_agent.duel_vehicle_screen import read_visible_cards


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


if __name__ == "__main__":
    unittest.main()
