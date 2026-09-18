from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from check_daily_navigation import hit, read_image


class VehicleLocationPipelineTest(unittest.TestCase):
    def test_detail_guard_distinguishes_saved_detail_and_list_screens(self) -> None:
        guard = json.loads((ROOT / "assets/resource/pipeline/runtime_agent.json").read_text(encoding="utf-8"))[
            "多人运行时_车辆详情通用"]
        details = sorted((ROOT / "captures").glob("多人游戏_车辆详情_*.png"))
        lists = sorted((ROOT / "captures").glob("多人游戏_选车_*.png"))
        self.assertGreaterEqual(len(details), 30)
        self.assertTrue(all(hit(guard, read_image(path)) for path in details))
        self.assertFalse(any(hit(guard, read_image(path)) for path in lists))


if __name__ == "__main__":
    unittest.main()
