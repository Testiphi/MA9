from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.vehicle_recognizer import VehicleCandidate, available_candidates, recognize_visible


class VehicleRecognizerTest(unittest.TestCase):
    def test_reports_template_coverage_without_requiring_game_unlocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = root / "resource/image/navigation/loop"
            images.mkdir(parents=True)
            (images / "car_found_list.png").touch()
            rotation = {"groups": [{"league": "黄金", "vehicles": [
                {"catalog_id": "car_found", "title": "Found"},
                {"catalog_id": "car_missing", "title": "Missing"},
            ]}]}
            available, missing = available_candidates(root, rotation)
            self.assertEqual([candidate.name for candidate in available], ["Found"])
            self.assertEqual(missing, ["Missing"])
            account_available, account_missing = available_candidates(root, rotation, {"car_missing"})
            self.assertEqual(account_available, [])
            self.assertEqual(account_missing, ["Missing"])

    def test_visible_name_near_left_edge_is_never_suggested_for_click(self) -> None:
        candidates = [VehicleCandidate("left", "Left", "黄金"), VehicleCandidate("middle", "Middle", "黄金")]

        class FakeContext:
            def run_recognition(self, entry, frame):
                self.last_frame = frame
                box = (180, 320, 55, 20) if entry.endswith("left") else (490, 330, 60, 20)
                return SimpleNamespace(hit=True, box=box)

        frame = object()
        context = FakeContext()
        result = recognize_visible(context, frame, candidates)
        self.assertIs(context.last_frame, frame)
        self.assertFalse(result[0]["safe_to_click"])
        self.assertIsNone(result[0]["suggested_body_point"])
        self.assertTrue(result[1]["safe_to_click"])
        self.assertEqual(result[1]["suggested_body_point"], [300, 270])


if __name__ == "__main__":
    unittest.main()
