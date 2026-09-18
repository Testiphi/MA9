"""Generate map-name-independent templates for Duel qualifier defense slots."""

import json
from pathlib import Path

from PIL import Image

from check_daily_navigation import hit, read_image, score


ROOT = Path(__file__).resolve().parents[1]
IMAGE_ROOT = ROOT / "assets/resource/image/navigation/duel"
CAPTURE = "多人游戏_对决_资格赛_防守_第{slot}赛道展开_未选车.png"
READY = "多人游戏_对决_资格赛_防守_第1赛道展开_已选车_可开始.png"
BUTTONS = [(501, 494), (613, 494), (728, 492), (842, 495), (957, 492)]


def crop(source, name, box):
    with Image.open(ROOT / "captures" / source) as image:
        assert image.size == (1280, 720), (source, image.size)
        image.convert("RGB").crop(box).save(IMAGE_ROOT / f"{name}.png")


def template(name, roi):
    return {
        "recognition": "TemplateMatch",
        "template": f"navigation/duel/{name}.png",
        "roi": roi,
        "threshold": 0.9,
    }


def main():
    IMAGE_ROOT.mkdir(parents=True, exist_ok=True)
    crop(CAPTURE.format(slot=1), "defense_qualifier_title", (70, 93, 153, 125))
    page = template("defense_qualifier_title", [62, 86, 110, 52])
    for slot in (1, 5):
        crop(CAPTURE.format(slot=slot), f"defense_auto_select_{slot}", (140, 641, 247, 680))
    auto_select = {
        "recognition": "TemplateMatch",
        "template": [f"navigation/duel/defense_auto_select_{slot}.png" for slot in (1, 5)],
        "roi": [130, 630, 130, 60],
        "threshold": 0.9,
    }

    nodes = {
        "对决_防守状态识别入口": {
            "recognition": "DirectHit", "action": "DoNothing", "timeout": 60000,
            "next": ["对决_防守_已选车可开始", *[f"对决_防守_第{slot}赛道展开未选车" for slot in range(1, 6)],
                     "对决_防守_页面已到达"],
        }
    }
    for slot, (x, y) in enumerate(BUTTONS, start=1):
        source = CAPTURE.format(slot=slot)
        key = f"defense_select_{slot}"
        # Only the fixed lime button and its label are used. Map names, map
        # emblems, routes, season countdown and assigned car art are excluded.
        crop(source, key, (x + 52, y + 10, x + 144, y + 42))
        nodes[f"对决_防守_第{slot}赛道展开未选车"] = {
            "recognition": "And",
            "all_of": [page, template(key, [x + 38, y - 4, 122, 62])],
            "action": "DoNothing", "next": [],
        }

    # Avoid the animated outer border: live MuMu capture differs from the
    # saved image there, while the orange centre and label stay stable.
    crop(READY, "defense_ready_start", (1020, 641, 1210, 692))
    nodes["对决_防守_已选车可开始"] = {
        "recognition": "And",
        "all_of": [page, template("defense_ready_start", [980, 625, 280, 80])],
        "action": "DoNothing", "next": [],
    }
    # Covers partially assigned lineups that cannot match the six specific
    # captures, without matching the earlier weekly qualification intro.
    nodes["对决_防守_页面已到达"] = {
        "recognition": "And", "all_of": [page, auto_select],
        "action": "DoNothing", "next": [],
    }
    path = ROOT / "assets/resource/pipeline/duel_defense.json"
    path.write_text(json.dumps(nodes, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")

    cases = {CAPTURE.format(slot=slot): f"对决_防守_第{slot}赛道展开未选车"
             for slot in range(1, 6)}
    cases.update({
        READY: "对决_防守_已选车可开始",
        "多人游戏_对决_首次进入_资格赛.png": None,
        "多人游戏_对决_主页卡片.png": None,
        "多人游戏_经典系列赛_首页_白金.png": None,
        "多人游戏_选车_白金起点_仅拥有开启.png": None,
    })
    choices = nodes["对决_防守状态识别入口"]["next"]
    specific = choices[:-1]
    report = []
    for source, expected in cases.items():
        image = read_image(ROOT / "captures" / source)
        matches = [name for name in specific if hit(nodes[name], image)]
        assert matches == ([] if expected is None else [expected]), (source, matches, expected)
        first = next((name for name in choices if hit(nodes[name], image)), None)
        assert first == expected, (source, first, expected)
        assert hit(nodes[choices[-1]], image) == (expected is not None), source
        if expected is not None:
            # Both expanded and collapsed large/small map labels sit above
            # the action buttons. Their content must not affect slot state.
            masked = image.copy()
            masked[210:310, 60:1250] = 0
            assert [name for name in specific if hit(nodes[name], masked)] == [expected], source
        report.append({"screenshot": source, "first_match": first, "specific_matches": matches,
                       "scores": {name: round(score(nodes[name], image), 4) for name in choices}})
        print(f"PASS {source}: {matches}")
    partial = read_image(ROOT / "captures" / CAPTURE.format(slot=1)).copy()
    partial[490:550, 490:710] = 0
    assert next(name for name in choices if hit(nodes[name], partial)) == choices[-1]
    (ROOT / "captures/duel_defense_check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS five defense slots and ready state; recognition only")


if __name__ == "__main__":
    main()
