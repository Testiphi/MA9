"""Read a saved Duel selection screenshot without connecting to the game."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maa.controller import CustomController
from maa.resource import Resource
from maa.tasker import Tasker

from probe_vehicle_fields import read_image, recognize_roi


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
from ma9_agent.duel_vehicle_screen import normalize, read_visible_cards  # noqa: E402


class SavedImageController(CustomController):
    def __init__(self, image):
        self.image = image
        super().__init__()

    def connect(self): return True
    def request_uuid(self): return "saved-duel-image"
    def start_app(self, intent): return False
    def stop_app(self, intent): return False
    def screencap(self): return self.image
    def click(self, x, y): return False
    def swipe(self, x1, y1, x2, y2, duration): return False
    def touch_down(self, contact, x, y, pressure): return False
    def touch_move(self, contact, x, y, pressure): return False
    def touch_up(self, contact): return False
    def click_key(self, keycode): return False
    def input_text(self, value): return False
    def key_down(self, keycode): return False
    def key_up(self, keycode): return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    image = normalize(read_image(args.image))
    resource = Resource()
    if not resource.post_bundle(ROOT / "assets/resource").wait().succeeded:
        raise RuntimeError("MAA resource load failed")
    controller = SavedImageController(image)
    if not controller.post_connection().wait().succeeded:
        raise RuntimeError("saved image controller failed")
    tasker = Tasker()
    if not tasker.bind(resource, controller):
        raise RuntimeError("MAA tasker bind failed")
    ocr = recognize_roi(tasker, image, (0, 120, 1280, 500))
    catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(
        encoding="utf-8"))["vehicles"]
    cards = read_visible_cards(image, ocr, catalog,
                               retry_ocr=lambda roi: recognize_roi(tasker, image, roi))
    report = {"source": str(args.image), "cards": cards,
              "fully_visible_cards": len(cards)}
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
