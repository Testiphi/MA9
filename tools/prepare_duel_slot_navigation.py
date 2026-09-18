"""Generate independent navigation tasks for all five Duel qualifier tracks."""

import json
from pathlib import Path

from check_daily_navigation import hit, read_image


ROOT = Path(__file__).resolve().parents[1]
CAPTURE = "多人游戏_对决_资格赛_防守_第{slot}赛道展开_未选车.png"
READY = "多人游戏_对决_资格赛_防守_第1赛道展开_已选车_可开始.png"
# Top-left corners of the lime select/change-car buttons in 1280x720.
BUTTONS = [(501, 494), (613, 494), (728, 492), (842, 495), (957, 492)]


def expanded(slot):
    x, y = BUTTONS[slot - 1]
    return {
        "recognition": "And",
        "all_of": [
            {
                "recognition": "TemplateMatch",
                "template": "navigation/duel/defense_qualifier_title.png",
                "roi": [62, 86, 110, 52],
                "threshold": 0.9,
            },
            {
                "recognition": "ColorMatch",
                # The button is wider than the 113-pixel gap between slots.
                # Its centre is the small area not shared with either neighbour.
                "roi": [x + 88, y + 8, 20, 13],
                "method": 4,  # BGR screenshot to RGB
                "lower": [180, 240, 0],
                "upper": [210, 255, 40],
                "count": 120,
            },
        ],
    }


def collapsed_x(current, target):
    return 7 + 113 * target if target < current else 620 + 113 * target


def main():
    nodes = {}
    for slot in range(1, 6):
        nodes[f"对决_防守_第{slot}赛道已展开"] = {
            **expanded(slot), "action": "DoNothing", "next": [],
        }
        x, y = BUTTONS[slot - 1]
        nodes[f"对决_防守_第{slot}赛道点击选择车辆"] = {
            **expanded(slot), "action": "Click", "target": [x + 95, y + 25],
            "max_hit": 1, "post_delay": 500, "next": [],
        }
        for current in range(1, 6):
            if current == slot:
                continue
            nodes[f"对决_防守_从第{current}切到第{slot}赛道"] = {
                **expanded(current), "action": "Click",
                "target": [collapsed_x(current, slot), 350],
                "max_hit": 1, "post_delay": 500,
                "next": [f"对决_防守_第{slot}赛道已展开"],
            }
            nodes[f"对决_防守_从第{current}切到第{slot}赛道并选车"] = {
                **expanded(current), "action": "Click",
                "target": [collapsed_x(current, slot), 350],
                "max_hit": 1, "post_delay": 500,
                "next": [f"对决_防守_第{slot}赛道点击选择车辆"],
            }
        nodes[f"对决_防守_查看第{slot}赛道"] = {
            "recognition": "DirectHit", "action": "DoNothing", "timeout": 60000,
            "next": [f"对决_防守_第{slot}赛道已展开", *[
                f"对决_防守_从第{current}切到第{slot}赛道"
                for current in range(1, 6) if current != slot
            ]],
        }
        nodes[f"对决_防守_进入第{slot}赛道选车"] = {
            "recognition": "DirectHit", "action": "DoNothing", "timeout": 60000,
            "next": [f"对决_防守_第{slot}赛道点击选择车辆", *[
                f"对决_防守_从第{current}切到第{slot}赛道并选车"
                for current in range(1, 6) if current != slot
            ]],
        }

    path = ROOT / "assets/resource/pipeline/duel_slot_navigation.json"
    path.write_text(json.dumps(nodes, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")

    cases = [CAPTURE.format(slot=slot) for slot in range(1, 6)] + [READY]
    for source in cases:
        image = read_image(ROOT / "captures" / source)
        current = 1 if source == READY else cases.index(source) + 1
        matches = [slot for slot in range(1, 6) if hit(nodes[f"对决_防守_第{slot}赛道已展开"], image)]
        assert matches == [current], (source, matches)
        for target in range(1, 6):
            view = nodes[f"对决_防守_查看第{target}赛道"]["next"]
            choose = nodes[f"对决_防守_进入第{target}赛道选车"]["next"]
            expected_view = (f"对决_防守_第{target}赛道已展开" if target == current
                             else f"对决_防守_从第{current}切到第{target}赛道")
            expected_choose = (f"对决_防守_第{target}赛道点击选择车辆" if target == current
                               else f"对决_防守_从第{current}切到第{target}赛道并选车")
            assert next(name for name in view if hit(nodes[name], image)) == expected_view
            assert next(name for name in choose if hit(nodes[name], image)) == expected_choose
            if target != current:
                assert 75 <= collapsed_x(current, target) <= 1200
        print(f"PASS {source}: expanded track {current}; all five destinations")
    for source in ("多人游戏_对决_主页卡片.png", "多人游戏_对决_首次进入_资格赛.png",
                   "多人游戏_经典系列赛_首页_白金.png"):
        image = read_image(ROOT / "captures" / source)
        assert not any(hit(nodes[f"对决_防守_第{slot}赛道已展开"], image)
                       for slot in range(1, 6)), source
    print("PASS Duel track navigation; game clicks not device-tested")


if __name__ == "__main__":
    main()
