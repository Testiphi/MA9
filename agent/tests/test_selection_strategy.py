from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.selection_strategy import LEAGUES, load_strategy, new_strategy, planned_vehicles


class SelectionStrategyTest(unittest.TestCase):
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
