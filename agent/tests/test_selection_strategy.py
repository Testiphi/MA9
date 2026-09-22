from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.selection_strategy import LEAGUES, default_priorities, load_strategy, new_strategy, planned_vehicles, vehicle_index
from ma9_agent.models import League


class SelectionStrategyTest(unittest.TestCase):
    def test_league_keys_fallback_and_version_are_strict(self) -> None:
        self.assertEqual(LEAGUES, tuple(rank.label for rank in League))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "strategy.json"
            self.assertIsNone(load_strategy(path, self.catalog, self.rotation, self.garage))
            for change in ("missing", "extra", "version", "fallback", "no_garage"):
                strategy = new_strategy(self.catalog, self.rotation, self.garage)
                self.assertEqual(set(strategy), {"schema_version", "fallback", "priorities"})
                if change == "missing":
                    del strategy["priorities"]["传奇"]
                elif change == "extra":
                    strategy["priorities"]["不存在"] = []
                elif change == "version":
                    strategy["schema_version"] = 2
                elif change == "fallback":
                    strategy["fallback"] = "forward"
                path.write_text(json.dumps(strategy), encoding="utf-8")
                garage = None if change == "no_garage" else self.garage
                with self.subTest(change=change), self.assertRaises(ValueError):
                    load_strategy(path, self.catalog, self.rotation, garage)

    def test_default_ownership_filter_and_approved_league_override(self) -> None:
        self.assertEqual(default_priorities(self.rotation)["黄金"], ["gold", "silver", "bronze"])
        self.assertEqual(default_priorities(self.rotation, set())["黄金"], [])
        self.assertEqual(default_priorities(self.rotation, {"silver"})["黄金"], ["silver"])
        self.catalog["vehicles"][1]["league"] = "传奇"
        self.assertEqual(vehicle_index(self.catalog, self.rotation)["silver"]["league"], "白银")
        self.assertEqual(self.catalog["vehicles"][1]["league"], "传奇")
        self.assertEqual([v["catalog_id"] for v in planned_vehicles("白银", self.catalog, self.rotation)],
                         ["silver", "bronze"])

    def setUp(self) -> None:
        self.catalog = {"vehicles": [
            {"id": "bronze", "title": "Bronze Car", "league": "青铜"},
            {"id": "silver", "title": "Silver Car", "league": "白银"},
            {"id": "gold", "title": "Gold Car", "league": "黄金"},
            {"id": "other", "title": "Other Silver Car", "league": "白银"},
        ]}
        self.rotation = {"groups": [
            {"league": "青铜", "vehicles": [{"catalog_id": "bronze", "order": 1}]},
            {"league": "白银", "vehicles": [{"catalog_id": "silver", "order": 1}]},
            {"league": "黄金", "vehicles": [{"catalog_id": "gold", "order": 1}]},
        ]}
        self.garage = {"vehicles": {
            "bronze": {"owned": True}, "silver": {"owned": True},
            "gold": {"owned": False}, "other": {"owned": True}}}

    def test_account_priority_can_prefer_lower_league_and_empty_means_fallback(self) -> None:
        strategy = new_strategy(self.catalog, self.rotation, self.garage)
        self.assertEqual(strategy["priorities"]["黄金"], ["silver", "bronze", "other"])
        strategy["priorities"]["黄金"] = ["bronze", "silver"]
        strategy["priorities"]["白银"] = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "selection_strategy.json"
            path.write_text(json.dumps(strategy), encoding="utf-8")
            loaded = load_strategy(path, self.catalog, self.rotation, self.garage)
        self.assertEqual([car["catalog_id"] for car in planned_vehicles("黄金", self.catalog, self.rotation, loaded)],
                         ["bronze", "silver"])
        self.assertEqual(planned_vehicles("白银", self.catalog, self.rotation, loaded), [])

    def test_rejects_unknown_unowned_duplicate_and_incompatible(self) -> None:
        strategy = new_strategy(self.catalog, self.rotation, self.garage)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "selection_strategy.json"
            for bad in (["missing"], ["gold"], ["bronze", "bronze"]):
                strategy["priorities"]["黄金"] = bad
                path.write_text(json.dumps(strategy), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_strategy(path, self.catalog, self.rotation, self.garage)
            self.garage["vehicles"]["gold"]["owned"] = True
            strategy["priorities"]["白银"] = ["gold"]
            strategy["priorities"]["黄金"] = []
            path.write_text(json.dumps(strategy), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_strategy(path, self.catalog, self.rotation, self.garage)

    def test_default_uses_approved_order_when_no_account_file(self) -> None:
        self.assertEqual(len(LEAGUES), 9)
        self.assertEqual([car["catalog_id"] for car in planned_vehicles("黄金", self.catalog, self.rotation, None)],
                         ["gold", "silver", "bronze"])


if __name__ == "__main__":
    unittest.main()
