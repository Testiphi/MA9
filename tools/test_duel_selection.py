"""Focused checks for the Duel reference importer and five-car allocator."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "tools"))

from import_duel_selection_data import build  # noqa: E402
from ma9_agent.duel_selection import plan_attack, plan_weak_defense  # noqa: E402


CATALOG = {"vehicles": [
    {"id": name, "title": name, "class": "D" if name in "abcde" else "S"}
    for name in "abcdef"
]}


def reference(groups: list[list[str]]) -> dict:
    return {"tracks": [
        {"big": "Map", "small": str(index), "zones": {"五区": choices, "四区": choices}}
        for index, choices in enumerate(groups, 1)
    ]}


class DuelSelectionTests(unittest.TestCase):
    def test_allocator_uses_distinct_cars_and_best_available_tradeoff(self) -> None:
        data = reference([["a", "b"], ["a", "c"], ["b", "d"], ["c", "e"], ["a", "f"]])
        plan = plan_attack([("Map", str(index)) for index in range(1, 6)],
                           "五区", set("abcdef"), data, CATALOG)
        self.assertTrue(plan["complete"])
        for scheme in plan["plans"]:
            chosen = [slot["vehicle_id"] for slot in scheme["slots"]]
            self.assertEqual(len(chosen), len(set(chosen)))
            self.assertEqual(len(chosen), 5)

    def test_unknown_and_empty_tracks_are_reported_without_a_startable_plan(self) -> None:
        data = reference([["a"], ["a"], [], ["c"], ["d"]])
        plan = plan_attack([("Map", "1"), ("Map", "2"), ("Map", "3"),
                            ("Map", "4"), ("Unknown", "5")],
                           "五区", set("abcd"), data, CATALOG)
        self.assertFalse(plan["complete"])
        self.assertEqual(plan["filled_slots"], 2)
        self.assertEqual({gap["reason"] for gap in plan["gaps"]},
                         {"no_auto_candidates", "unknown_track", "mutual_exclusion_shortage"})

    def test_same_car_on_every_track_reports_mutual_exclusion_shortage(self) -> None:
        data = reference([["a"]] * 5)
        plan = plan_attack([("Map", str(index)) for index in range(1, 6)],
                           "五区", {"a"}, data, CATALOG)
        self.assertFalse(plan["complete"])
        self.assertEqual(plan["filled_slots"], 1)
        self.assertEqual([gap["reason"] for gap in plan["gaps"]],
                         ["mutual_exclusion_shortage"] * 4)

    def test_weak_defense_uses_five_lowest_owned_d_cars(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            csv_path = Path(temporary) / "scores.csv"
            csv_path.write_text("title,score\na,10\nb,20\nc,30\nd,40\ne,50\nf,1\n",
                                encoding="utf-8")
            result = plan_weak_defense(CATALOG, set("abcdef"), csv_path)
        self.assertTrue(result["complete"])
        self.assertEqual([slot["vehicle_id"] for slot in result["slots"]], list("abcde"))

    def test_real_source_maps_all_automatic_nicknames_to_ma9_ids(self) -> None:
        catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))
        source = ROOT.parent / "MutualExclusionAllocator" / "repo"
        if not source.is_dir():
            self.skipTest("source checkout is not installed")
        imported, report = build(source, catalog)
        self.assertEqual(report["unresolved_aliases"], [])
        self.assertEqual(report["tracks"], 83)
        self.assertEqual(report["automatic_candidates"], 622)
        self.assertEqual(len(imported["tracks"]), 83)
        generated = json.loads((ROOT / "data/generated/duel_auto_candidates.json").read_text(
            encoding="utf-8"))
        self.assertEqual(generated, imported)


if __name__ == "__main__":
    unittest.main()
