from __future__ import annotations

import sys
import unittest
from pathlib import Path

from maa.resource import Resource
from maa.tasker import Tasker


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "tools"))

from ma9_agent.account_conflict import account_conflict_from_ocr  # noqa: E402
from probe_duel_vehicle_selection import SavedImageController  # noqa: E402
from probe_vehicle_fields import read_image, recognize_roi  # noqa: E402
from ma9_agent.duel_vehicle_screen import normalize  # noqa: E402


def words(*texts: str) -> list[dict]:
    return [{"text": text, "confidence": .95} for text in texts]


class AccountConflictTests(unittest.TestCase):
    def test_requires_title_and_other_device_message(self) -> None:
        found = account_conflict_from_ocr(words("检测到并行存取行为", "该账号从另一台设备登录。"))
        self.assertTrue(found["detected"])
        self.assertEqual(found["recommended_action"], "stop_current_task")
        self.assertFalse(account_conflict_from_ocr(words("检测到并行存取行为"))["detected"])
        self.assertFalse(account_conflict_from_ocr(words("该账号从另一台设备登录"))["detected"])

    def test_low_confidence_text_is_ignored(self) -> None:
        result = account_conflict_from_ocr([
            {"text": "检测到并行存取行为", "confidence": .4},
            {"text": "该账号从另一台设备登录。", "confidence": .95},
        ])
        self.assertFalse(result["detected"])

    @unittest.skipUnless(
        (ROOT / "captures/duel_account_kicked.png").is_file()
        and (ROOT / "captures/duel_selection_live/duel_d_start.png").is_file(),
        "local live-game screenshots are intentionally not distributed",
    )
    def test_saved_conflict_and_car_selection_screens(self) -> None:
        positive = normalize(read_image(ROOT / "captures/duel_account_kicked.png"))
        negative = normalize(read_image(ROOT / "captures/duel_selection_live/duel_d_start.png"))
        resource = Resource()
        self.assertTrue(resource.post_bundle(ROOT / "assets/resource").wait().succeeded)
        controller = SavedImageController(positive)
        self.assertTrue(controller.post_connection().wait().succeeded)
        tasker = Tasker()
        self.assertTrue(tasker.bind(resource, controller))
        self.assertTrue(account_conflict_from_ocr(
            recognize_roi(tasker, positive, (140, 200, 1000, 330)))["detected"])
        self.assertFalse(account_conflict_from_ocr(
            recognize_roi(tasker, negative, (140, 200, 1000, 330)))["detected"])


if __name__ == "__main__":
    unittest.main()
