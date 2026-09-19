from __future__ import annotations

import unittest
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_vehicle_screen import read_visible_cards


class DuelVehicleScreenTest(unittest.TestCase):
    def test_retry_ocr_accepts_current_only_rating(self) -> None:
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        catalog = [{"id": "camaro", "title": "Chevrolet Camaro LT", "class": "D"}]
        words = [
            {"text": "CHEVROLET", "confidence": .99, "box": [100, 325, 110, 20]},
            {"text": "CAMARO LT", "confidence": .99, "box": [100, 345, 115, 20]},
        ]

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


if __name__ == "__main__":
    unittest.main()
