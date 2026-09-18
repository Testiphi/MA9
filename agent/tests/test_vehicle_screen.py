from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.models import League
from ma9_agent.vehicle_screen import match_vehicle


class VehicleScreenTest(unittest.TestCase):
    def test_unique_model_line_survives_misread_brand(self) -> None:
        catalog = [
            {"id": "praga", "title": "Praga Bohema", "league": "黄金"},
            {"id": "other", "title": "Other Bohema", "league": "白银"},
        ]
        words = [
            {"text": "Proqo", "confidence": .895, "box": [332, 327, 35, 11]},
            {"text": "BOHEMA", "confidence": .992, "box": [334, 339, 69, 18]},
        ]
        self.assertEqual(match_vehicle(words, catalog, League.GOLD)["id"], "praga")
        self.assertIsNone(match_vehicle(words, catalog, League.BRONZE))


if __name__ == "__main__":
    unittest.main()
