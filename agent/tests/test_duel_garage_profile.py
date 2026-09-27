from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_garage_profile import (atomic_json, empty_profile,
                                           load_profile, merge_class)


class DuelGarageProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = {"one": {"id": "one", "title": "One", "class": "R"},
                        "old": {"id": "old", "title": "Old", "class": "S"}}
        self.profile = empty_profile(self.root, "account")

    def test_positive_merge_keeps_old_and_manual_and_raw_stars(self):
        self.profile["vehicles"]["old"] = {
            "id": "old", "title": "Old", "class": "S", "owned": False,
            "ownership_source": "manual", "stars_status": "confirmed",
            "manual": {"note": "keep"},
        }
        self.profile["vehicles"]["one"] = {
            "id": "one", "title": "One", "class": "R", "owned": False,
            "ownership_source": "manual", "stars_status": "unknown",
            "manual": {"note": "keep"},
        }
        merge_class(self.profile, "R", {"status": "class_boundary", "pages": 1,
            "scan_complete": True, "vehicles": [{"vehicle": {"id": "one"},
            "class": "R", "stars_lit": 3, "star_slots": 6, "page": 1}]},
            self.catalog, "run", "now", "frames.jsonl")
        self.assertFalse(self.profile["vehicles"]["one"]["owned"])
        self.assertEqual(self.profile["vehicles"]["one"]["manual"], {"note": "keep"})
        self.assertIn("old", self.profile["vehicles"])
        self.assertEqual(self.profile["vehicles"]["one"]["stars_status"], "unverified")
        self.assertEqual(self.profile["vehicles"]["one"]["star_observations"][0]["stars_lit"], 3)
        self.assertFalse(self.profile["coverage_complete"])
        self.assertFalse(self.profile["allocation_ready"])

    def test_load_rejects_foreign_account_and_unknown_id(self):
        path = self.root / "duel_garage.json"
        atomic_json(path, self.profile)
        with self.assertRaises(ValueError):
            load_profile(path, self.root, "other", self.catalog)
        self.profile["vehicles"]["unknown"] = {"id": "unknown"}
        atomic_json(path, self.profile)
        with self.assertRaises(ValueError):
            load_profile(path, self.root, "account", self.catalog)

    def test_unknown_star_is_not_zero(self):
        merge_class(self.profile, "R", {"status": "page_limit", "pages": 1,
            "scan_complete": False, "vehicles": [{"vehicle": {"id": "one"},
            "class": "R", "stars_lit": None, "star_slots": None, "page": 1}]},
            self.catalog, "run", "now", "frames.jsonl")
        item = self.profile["vehicles"]["one"]
        self.assertEqual(item["stars_status"], "unknown")
        self.assertIsNone(item["star_observations"][0]["stars_lit"])
        self.assertTrue(item["owned"])
        self.assertEqual(item["ownership_status"], "provisional")

    def test_atomic_json_does_not_delete_colliding_temporary_file(self):
        path = self.root / "duel_garage.json"
        collision = path.with_name(path.name + ".fixed.tmp")
        collision.write_text("someone else's work", encoding="utf-8")
        with patch("ma9_agent.duel_garage_profile.uuid4",
                   return_value=type("Id", (), {"hex": "fixed"})()):
            with self.assertRaises(FileExistsError):
                atomic_json(path, self.profile)
        self.assertEqual(collision.read_text(encoding="utf-8"), "someone else's work")
        self.assertFalse(path.exists())

    def test_malformed_existing_evidence_rejected(self):
        path = self.root / "duel_garage.json"
        self.profile["vehicles"]["one"] = {
            "id": "one", "title": "One", "class": "R", "owned": True,
            "stars_status": "confirmed", "star_observations": {"bad": "shape"}}
        atomic_json(path, self.profile)
        with self.assertRaises(ValueError):
            load_profile(path, self.root, "account", self.catalog)

    def test_malformed_star_history_rejected_before_use(self):
        path = self.root / "duel_garage.json"
        self.profile["vehicles"]["one"] = {
            "id": "one", "title": "One", "class": "R", "owned": True,
            "stars_status": "unverified", "star_observations": [1]}
        atomic_json(path, self.profile)
        with self.assertRaises(ValueError):
            load_profile(path, self.root, "account", self.catalog)
        for reading in ({"stars_lit": True, "star_slots": 6},
                        {"stars_lit": 5, "star_slots": 4},
                        {"stars_lit": 1, "star_slots": None}):
            self.profile["vehicles"]["one"]["star_observations"] = [reading]
            atomic_json(path, self.profile)
            with self.assertRaises(ValueError):
                load_profile(path, self.root, "account", self.catalog)

    def test_owned_rejects_numeric_boolean_impostors(self):
        path = self.root / "duel_garage.json"
        entry = {"id": "one", "title": "One", "class": "R",
                 "stars_status": "unknown", "star_observations": []}
        self.profile["vehicles"]["one"] = entry
        for invalid in (0, 1):
            entry["owned"] = invalid
            atomic_json(path, self.profile)
            with self.assertRaises(ValueError):
                load_profile(path, self.root, "account", self.catalog)


if __name__ == "__main__":
    unittest.main()
