"""Generate read-only car-name recognitions from approved rotation and existing list templates."""

from __future__ import annotations

import json
from pathlib import Path

from check_daily_navigation import hit, read_image


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    rotation = json.loads((ROOT / "data/generated/champion_rotation.json").read_text(encoding="utf-8"))
    template_root = ROOT / "assets/resource/image/navigation/loop"
    nodes = {}
    available = []
    for group in rotation["groups"]:
        for vehicle in group["vehicles"]:
            vehicle_id = vehicle["catalog_id"]
            if not (template_root / f"{vehicle_id}_list.png").is_file():
                continue
            name = f"多人选车_车型_{vehicle_id}"
            nodes[name] = {
                "recognition": "TemplateMatch",
                "template": f"navigation/loop/{vehicle_id}_list.png",
                "roi": [0, 190, 1280, 480],
                "threshold": 0.9,
                "action": "DoNothing",
                "next": [],
            }
            available.append((vehicle["title"], name))
    assert available
    for title, name in available:
        sources = sorted((ROOT / "captures").glob(f"多人游戏_选车_*_{title}完整可见_仅拥有*.png"))
        assert sources, f"missing template verification: {title}"
        assert any(hit(nodes[name], read_image(source)) for source in sources), title
    output = ROOT / "assets/resource/pipeline/vehicle_recognition.json"
    output.write_text(json.dumps(nodes, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"PASS {len(available)} read-only vehicle recognitions")


if __name__ == "__main__":
    main()
