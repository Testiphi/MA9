from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.garage_profile import empty_profile, load_profile, save_profile, merge_owned_survey, owned_vehicle_ids, set_owned
from ma9_agent.models import League, Rect, VehicleObservation
from ma9_agent.vehicle_selector import VehicleSelector


class GarageProfileTest(unittest.TestCase):
    def test_profile_shape_missing_path_version_and_atomic_save(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "account" / "garage.json"
            profile = load_profile(path)
            self.assertEqual(profile, {"schema_version": 1, "updated_at": None, "coverage": {}, "vehicles": {}})
            replace = Path.replace
            replaced = []

            def record_replace(source, destination):
                self.assertEqual(source, path.with_suffix(".json.tmp"))
                self.assertEqual(json.loads(source.read_text(encoding="utf-8")), profile)
                replaced.append(destination)
                return replace(source, destination)

            with patch.object(Path, "replace", record_replace):
                for _ in range(2):
                    save_profile(path, profile)
            self.assertEqual(replaced, [path, path])
            self.assertEqual(load_profile(path), profile)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])
            for version in (0, 2, "1", None):
                path.write_text(json.dumps({**profile, "schema_version": version}), encoding="utf-8")
                with self.subTest(version=version), self.assertRaises(ValueError):
                    load_profile(path)

    def test_partial_scan_preserves_existing_unseen_ownership(self) -> None:
        for owned in (True, False):
            profile = empty_profile()
            profile["vehicles"]["other"] = {"owned": owned, "ownership_source": "only_owned_scan"}
            before = profile["vehicles"]["other"].copy()
            merge_owned_survey(profile, self.survey, self.records, self.catalog)
            self.assertEqual(profile["vehicles"]["other"], before)
        for value in (None, "off", True, "unknown"):
            with self.subTest(filter=value), self.assertRaises(ValueError):
                merge_owned_survey(empty_profile(), {"owned_filter": value}, [], self.catalog)

    def test_manual_ownership_and_removal(self) -> None:
        profile = empty_profile()
        set_owned(profile, self.catalog["owned"], True)
        self.assertTrue(profile["updated_at"])
        self.assertEqual(profile["vehicles"]["owned"]["ownership_source"], "manual")
        merge_owned_survey(profile, self.survey, self.records, self.catalog)
        self.assertEqual(profile["vehicles"]["owned"]["ownership_source"], "manual")
        set_owned(profile, self.catalog["owned"], None)
        self.assertNotIn("owned", profile["vehicles"])
        set_owned(profile, self.catalog["owned"], None)

    def test_coverage_requires_boundary_and_complete_recognition(self) -> None:
        for status in ("edge_reached", "league_boundary", "page_limit", "ocr_incomplete"):
            for recognized in (0, 1):
                survey = {"owned_filter": "on", "leagues": {"黄金": {
                    "status": status, "pages": 1, "cards": 1, "recognized": recognized}}}
                profile = merge_owned_survey(empty_profile(), survey, [], self.catalog)
                self.assertEqual(profile["coverage"]["黄金"]["complete"],
                                 status in {"edge_reached", "league_boundary"} and recognized == 1)

    def setUp(self) -> None:
        self.catalog = {
            "owned": {"id": "owned", "title": "Owned Car"},
            "other": {"id": "other", "title": "Other Car"},
        }
        self.survey = {"owned_filter": "on", "leagues": {
            "黄金": {"status": "page_limit", "pages": 1, "cards": 1, "recognized": 1},
        }}
        self.records = [{"values": {"vehicle": {"id": "owned"}}}]

    def test_partial_only_owned_scan_keeps_unseen_unknown(self) -> None:
        profile = merge_owned_survey(empty_profile(), self.survey, self.records, self.catalog, "2026-09-16T00:00:00Z")
        self.assertEqual(owned_vehicle_ids(profile), {"owned"})
        self.assertNotIn("other", profile["vehicles"])
        self.assertFalse(profile["coverage"]["黄金"]["complete"])

    def test_unfiltered_scan_cannot_assert_ownership_and_manual_choice_survives_rescan(self) -> None:
        with self.assertRaises(ValueError):
            merge_owned_survey(empty_profile(), {**self.survey, "owned_filter": "off"},
                               self.records, self.catalog)
        profile = empty_profile()
        set_owned(profile, self.catalog["owned"], False)
        merge_owned_survey(profile, self.survey, self.records, self.catalog, "2026-09-16T00:00:00Z")
        self.assertIs(profile["vehicles"]["owned"]["owned"], False)

    def test_selector_restricts_priority_to_account_garage(self) -> None:
        groups = [{"league": "黄金", "vehicles": [
            {"catalog_id": "owned", "order": 1}, {"catalog_id": "other", "order": 2},
        ]}]
        selector = VehicleSelector.from_rotation(League.GOLD, groups, {"owned"})
        item = VehicleObservation("other", "Other Car", League.GOLD, Rect(100, 200, 600, 300),
                                  owned=True, unlocked=True, fuel=5)
        self.assertIn("not_recommended", selector.rejection_reasons(item))


if __name__ == "__main__":
    unittest.main()
