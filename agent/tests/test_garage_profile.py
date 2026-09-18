from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.garage_profile import empty_profile, merge_owned_survey, owned_vehicle_ids, set_owned
from ma9_agent.models import League, Rect, VehicleObservation
from ma9_agent.vehicle_selector import VehicleSelector


class GarageProfileTest(unittest.TestCase):
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
