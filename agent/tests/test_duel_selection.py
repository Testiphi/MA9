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

    def test_requested_class_shortage_falls_back_without_duplicates(self) -> None:
        tracks = {"complete": True, "tracks": [
            {"big": "Map", "small": str(index)} for index in range(1, 6)]}
        cards = []
        for vehicle_class, ratings in (("R", [5300, 5100]),
                                       ("S", [4900, 4700, 4500, 4300])):
            cards.extend({
                "vehicle": {"id": f"{vehicle_class}{rating}",
                            "title": f"{vehicle_class}{rating}"},
                "class": vehicle_class,
                "performance": [rating, None],
                "stars_lit": None,
            } for rating in ratings)
        scan = {"status": "class_ladder_complete", "scan_complete": True,
                "vehicles": cards}

        plan = plan_live_weak_defense(tracks, scan, vehicle_class="R")

        self.assertTrue(plan["complete"])
        self.assertEqual(plan["classes_used"], ["R", "S"])
        self.assertEqual([slot["class"] for slot in plan["slots"]],
                         ["R", "R", "S", "S", "S"])
        self.assertEqual([slot["performance"] for slot in plan["slots"]],
                         [5100, 5300, 4300, 4500, 4700])
        self.assertEqual(len({slot["vehicle_id"] for slot in plan["slots"]}), 5)


if __name__ == "__main__":
    unittest.main()
