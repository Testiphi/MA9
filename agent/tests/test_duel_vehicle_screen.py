from __future__ import annotations

import unittest
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_vehicle_screen import read_visible_cards


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


if __name__ == "__main__":
    unittest.main()
