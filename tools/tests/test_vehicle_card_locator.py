from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from probe_vehicle_fields import match_catalog, read_image, selected_league  # noqa: E402
from vehicle_card_locator import detect_list_cards  # noqa: E402
from collect_vehicle_scan import is_detail, is_list  # noqa: E402
from vehicle_scan_merge import merge_vehicle_records  # noqa: E402


class VehicleCardLocatorTest(unittest.TestCase):
    def test_existing_selection_screens_have_complete_cards(self) -> None:
        captures = list((ROOT / "captures").glob("多人游戏_选车*.png"))
        self.assertGreaterEqual(len(captures), 40)
        for path in captures:
            with self.subTest(image=path.name):
                boxes = detect_list_cards(read_image(path))
                self.assertTrue(boxes)
                for x, y, width, height in boxes:
                    self.assertGreater(x, 0)
                    self.assertLess(x + width, 1280)
                    self.assertIn(y, (195, 432))
                    self.assertEqual(height, 227)

    def test_roman_numeral_ocr_matches_catalog_name(self) -> None:
        catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))["vehicles"]
        ocr = [{"text": "FORD", "confidence": .97, "box": [0, 0, 40, 15]},
               {"text": "GT MK ⅡI", "confidence": .88, "box": [0, 16, 80, 15]}]
        result = match_catalog(ocr, catalog)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Ford GT MK II")

    def test_stylized_praga_wordmark_matches_catalog(self) -> None:
        catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))["vehicles"]
        ocr = [{"text": "Proqo", "confidence": .855, "box": [0, 0, 33, 11]},
               {"text": "R1", "confidence": .994, "box": [0, 13, 22, 16]}]
        self.assertEqual(match_catalog(ocr, catalog, "青铜")["name"], "Praga R1")

    def test_short_model_name_uses_selected_league_only_when_unique(self) -> None:
        catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))["vehicles"]
        ocr = [{"text": "TECHRULES", "confidence": .995, "box": [0, 0, 60, 12]},
               {"text": "AT96", "confidence": .998, "box": [0, 15, 50, 18]}]
        self.assertIsNone(match_catalog(ocr, catalog))
        self.assertEqual(match_catalog(ocr, catalog, "钻石")["name"], "Techrules AT96 Track Version")
        self.assertEqual(match_catalog(ocr, catalog, "精英")["name"], "Techrules AT96 Dragon Boat Edition")
        self.assertIsNone(match_catalog(ocr, catalog, "白金"))

    def test_selected_league_reads_survey_screen(self) -> None:
        image = read_image(ROOT / "captures/多人游戏_选车_黄金_Nissan Z GT4完整可见_仅拥有开启.png")
        self.assertEqual(selected_league(image), "黄金")

    def test_input_guards_reject_the_wrong_screen(self) -> None:
        list_image = read_image(ROOT / "captures/多人游戏_选车_黄金_Nissan Z GT4完整可见_仅拥有开启.png")
        detail_image = read_image(ROOT / "captures/多人游戏_车辆详情_Nissan Z GT4_可开始_TouchDrive开.png")
        self.assertTrue(is_list(list_image))
        self.assertFalse(is_detail(list_image))
        self.assertTrue(is_detail(detail_image))
        self.assertFalse(is_list(detail_image))

    def test_merge_keeps_gold_state_and_exposes_conflicting_fuel(self) -> None:
        vehicle = {"id": "car_1", "name": "Car", "class": "D", "catalog_league": "青铜", "confidence": 1.0}
        records = [
            {"screen": "list", "source": "list.png", "card": [200, 195, 453, 227],
             "values": {"vehicle": vehicle, "fully_upgraded": True, "fuel": [4, 4]}},
            {"screen": "detail", "source": "detail.png",
             "values": {"vehicle": vehicle, "fully_upgraded": None, "fuel": [0, 4], "stars_lit": 3}},
        ]
        result = merge_vehicle_records(records)["vehicles"]["car_1"]
        self.assertIs(result["values"]["fully_upgraded"], True)
        self.assertEqual(result["values"]["stars_lit"], 3)
        self.assertIsNone(result["values"]["fuel"])
        self.assertEqual(result["conflicts"]["fuel"], [[4, 4], [0, 4]])


if __name__ == "__main__":
    unittest.main()
