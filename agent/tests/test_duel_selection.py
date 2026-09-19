from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_selection import plan_live_weak_defense


class DuelLiveDefenseSelectionTest(unittest.TestCase):
    def test_repairs_clipped_rating_among_weakest_cars(self) -> None:
        tracks = {"complete": True, "tracks": [
            {"big": "Map", "small": str(index)} for index in range(1, 6)]}
        scan = {"status": "edge_reached", "vehicles": [
            {"vehicle": {"id": name, "title": name}, "class": "D",
             "performance": [score, None]}
            for name, score in zip("abcdefg", [2200, 1827, 1814, 1738, 1683, 662, 1546])
        ]}

        plan = plan_live_weak_defense(tracks, scan)

        self.assertEqual([slot["vehicle_id"] for slot in plan["slots"]], list("gfedc"))
        self.assertEqual([slot["performance"] for slot in plan["slots"]],
                         [1546, 1662, 1683, 1738, 1814])
        self.assertTrue(plan["slots"][1]["rating_repaired"])


if __name__ == "__main__":
    unittest.main()
