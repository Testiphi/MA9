"""Focused offline tests for the Duel candidate preview."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_map_candidates import preview_lineup_candidates

_CLI_PATH = Path(__file__).resolve().parents[2] / "tools" / "preview_duel_map_candidates.py"
_CLI_SPEC = importlib.util.spec_from_file_location("preview_duel_map_candidates", _CLI_PATH)
if _CLI_SPEC is None or _CLI_SPEC.loader is None:
    raise ImportError(f"cannot load CLI module from {_CLI_PATH}")
cli = importlib.util.module_from_spec(_CLI_SPEC)
_CLI_SPEC.loader.exec_module(cli)


PAIRS = [(f"大图{i}", f"小图{i}") for i in range(1, 6)]


def fixture_data():
    report = {
        "status": "verified", "maps_verified": True, "stable": True,
        "read_only": True, "selection_attempted": False, "starts_race": False,
        "page_title": "资格赛", "samples": 2, "expanded_slot": 3,
        "tracks": [{"slot": slot, "big": big, "small": small}
                   for slot, (big, small) in reversed(list(enumerate(PAIRS, 1)))],
    }
    reference = {"schema_version": 1, "candidate_tier": "自动", "tracks": []}
    catalog = {"schema_version": 1, "vehicles": []}
    for index, (big, small) in enumerate(PAIRS, 1):
        five, four = f"five-{index}", f"four-{index}"
        reference["tracks"].append({"big": big, "small": small,
                                    "zones": {"五区": [five], "四区": [four]}})
        catalog["vehicles"].extend([
            {"id": five, "title": f"五区车辆{index}", "class": "S"},
            {"id": four, "title": f"四区车辆{index}", "class": "A"},
        ])
    return report, reference, catalog


class CandidateProjectionTest(unittest.TestCase):
    def test_real_slots_zones_ranks_and_inputs_are_preserved(self):
        report, reference, catalog = fixture_data()
        reference["tracks"][0]["zones"]["五区"] = ["five-1", "five-1-second", "five-1-third"]
        reference["tracks"][1]["zones"]["四区"].append("five-1")
        catalog["vehicles"].extend([
            {"id": "five-1-second", "title": "五区车辆1次选", "class": "A"},
            {"id": "five-1-third", "title": "五区车辆1三选", "class": "B"},
        ])
        before = copy.deepcopy((report, reference, catalog))
        result = preview_lineup_candidates(report, reference, catalog)
        self.assertEqual((report, reference, catalog), before)
        self.assertEqual([row["slot"] for row in result["slots"]], [1, 2, 3, 4, 5])
        self.assertEqual([row["map"] for row in result["slots"]],
                         [{"big": big, "small": small} for big, small in PAIRS])
        for index, row in enumerate(result["slots"], 1):
            self.assertEqual(row["zones"]["五区"]["candidates"][0], {
                "rank": 1, "vehicle_id": f"five-{index}", "title": f"五区车辆{index}",
                "class": "S", "ownership": "unknown", "availability": "unknown"})
            self.assertEqual(row["zones"]["四区"]["candidates"][0]["vehicle_id"],
                             f"four-{index}")
            self.assertIsNone(row["zones"]["五区"]["gap"])
        self.assertEqual([candidate["rank"] for candidate in result["slots"][0]["zones"]["五区"]["candidates"]],
                         [1, 2, 3])
        self.assertIs(result["read_only"], True)
        self.assertIs(result["selection_attempted"], False)
        self.assertIs(result["starts_race"], False)

    def test_unknown_map_and_empty_zone_are_explicit_gaps(self):
        report, reference, catalog = fixture_data()
        next(track for track in report["tracks"] if track["slot"] == 1)["big"] = "未知大图"
        reference["tracks"][1]["zones"]["五区"] = []
        result = preview_lineup_candidates(report, reference, catalog)
        self.assertEqual(result["slots"][0]["zones"]["五区"],
                         {"candidates": [], "gap": "unknown_map"})
        self.assertEqual(result["slots"][1]["zones"]["五区"],
                         {"candidates": [], "gap": "no_candidates"})

    def test_bad_reports_reference_schema_and_unknown_ids_are_rejected(self):
        report, reference, catalog = fixture_data()
        cases = []
        for field, value in [("status", "partial"), ("maps_verified", 1),
                             ("stable", False), ("read_only", False),
                             ("selection_attempted", True), ("starts_race", True),
                             ("page_title", "挑战"), ("samples", 1),
                             ("samples", True), ("expanded_slot", True)]:
            bad = copy.deepcopy(report)
            bad[field] = value
            cases.append((bad, reference, catalog))
        bad = copy.deepcopy(report)
        bad["tracks"][0]["slot"] = bad["tracks"][1]["slot"]
        cases.append((bad, reference, catalog))
        bad = copy.deepcopy(reference)
        bad["schema_version"] = True
        cases.append((report, bad, catalog))
        bad = copy.deepcopy(reference)
        bad["tracks"] = []
        cases.append((report, bad, catalog))
        bad = copy.deepcopy(reference)
        bad["tracks"].append(copy.deepcopy(bad["tracks"][0]))
        cases.append((report, bad, catalog))
        bad = copy.deepcopy(reference)
        bad["tracks"][0]["zones"]["五区"].append("missing-id")
        cases.append((report, bad, catalog))
        for bad_report, bad_reference, bad_catalog in cases:
            with self.subTest(case=len(cases)):
                with self.assertRaises(ValueError):
                    preview_lineup_candidates(bad_report, bad_reference, bad_catalog)

    def test_duplicate_catalog_ids_and_candidate_ids_are_rejected(self):
        report, reference, catalog = fixture_data()
        reference["tracks"][0]["zones"]["五区"] = ["five-1", "five-1"]
        with self.assertRaisesRegex(ValueError, "duplicate vehicle id"):
            preview_lineup_candidates(report, reference, catalog)
        reference, catalog = fixture_data()[1:]
        catalog["vehicles"].append(copy.deepcopy(catalog["vehicles"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate catalog vehicle"):
            preview_lineup_candidates(report, reference, catalog)


class CandidateCliTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "package"
        (self.root / "debug").mkdir(parents=True)
        (self.root / "data/generated").mkdir(parents=True)
        (self.root / ".ma9-portable-root").write_text("", encoding="utf-8")
        report, reference, catalog = fixture_data()
        self.report_path = self.root / "debug/source-report.json"
        report["runtime_root"] = str(self.root.resolve())
        report["report_file"] = str(self.report_path.resolve())
        report["account_key"] = "fixture-account"
        self.report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        (self.root / "data/generated/duel_auto_candidates.json").write_text(
            json.dumps(reference, ensure_ascii=False), encoding="utf-8")
        (self.root / "data/generated/vehicle_catalog.json").write_text(
            json.dumps(catalog, ensure_ascii=False), encoding="utf-8")

    def test_two_runs_create_distinct_json_and_matching_markdown(self):
        first = cli.create_preview(str(self.root), str(self.report_path))
        second = cli.create_preview(str(self.root), str(self.report_path))
        self.assertNotEqual(first, second)
        for json_path, md_path in (first, second):
            document = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = md_path.read_text(encoding="utf-8")
            for slot in document["slots"]:
                self.assertIn(f"## 槽位 {slot['slot']}：", markdown)
                for zone, zone_result in slot["zones"].items():
                    self.assertIn(f"### {zone}", markdown)
                    for candidate in zone_result["candidates"]:
                        self.assertIn(f"| {candidate['rank']} | {candidate['title']} | "
                                      f"{candidate['class']} | 未知 | 未知 |", markdown)
            self.assertTrue(document["metadata"]["snapshot_not_live"])
            self.assertEqual(document["metadata"]["account_key"], "fixture-account")
            self.assertIn(document["metadata"]["source_report_sha256"], markdown)

    def test_cross_root_report_and_resolved_debug_escape_fail_before_reads(self):
        outside_report = Path(self.temp.name) / "outside.json"
        outside_report.write_text("{}", encoding="utf-8")
        with patch.object(cli, "_load_json") as reads:
            with self.assertRaisesRegex(ValueError, "inside --root/debug"):
                cli.create_preview(str(self.root), str(outside_report))
            reads.assert_not_called()

        escaped_root = Path(self.temp.name) / "escaped-package"
        escaped_root.mkdir()
        (escaped_root / ".ma9-portable-root").write_text("", encoding="utf-8")
        outside_debug = Path(self.temp.name) / "outside-debug"
        outside_debug.mkdir()
        escaped_report = outside_debug / "source.json"
        escaped_report.write_text("{}", encoding="utf-8")
        resolve = cli._canonical

        def canonical_with_debug_escape(path, *, strict=True):
            if Path(path) == escaped_root / "debug":
                return outside_debug
            return resolve(path, strict=strict)

        with patch.object(cli, "_load_json") as reads:
            with patch.object(cli, "_canonical", side_effect=canonical_with_debug_escape):
                with self.assertRaisesRegex(ValueError, "inside --root/debug"):
                    cli.create_preview(str(escaped_root), str(escaped_report))
            reads.assert_not_called()


if __name__ == "__main__":
    unittest.main()
