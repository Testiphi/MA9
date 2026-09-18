"""Generate Duel entry branches, including a zero-progress qualifier restart."""

import copy
import json
from pathlib import Path

import cv2
from PIL import Image

from check_daily_navigation import hit, read_image, score


ROOT = Path(__file__).resolve().parents[1]
IMAGE_ROOT = ROOT / "assets/resource/image/navigation/duel"
HOME = "多人游戏_对决_主页卡片.png"
QUALIFIER = "多人游戏_对决_首次进入_资格赛.png"
FAILED_ZERO = "多人游戏_对决_资格赛_中断_五图零成绩.png"
RESTART_CONFIRM = "多人游戏_对决_资格赛_中断_重开确认.png"
RESTART_READY = "多人游戏_对决_资格赛_重开后_第1赛道未选车.png"
SPECS = {
    # Keep text-only crops: the rank badge and season timer change over time.
    "home_duel_title": (HOME, (891, 391, 963, 433), [880, 380, 105, 65]),
    "qualifier_title": (QUALIFIER, (300, 151, 393, 190), [285, 140, 125, 65]),
    "qualifier_button": (QUALIFIER, (1042, 650, 1155, 705), [1025, 640, 145, 75]),
    # The five zero results are verified separately before spending one ticket.
    "qualifier_failed_title": (FAILED_ZERO, (78, 94, 219, 124), [70, 88, 165, 50]),
    "qualifier_zero_time": (FAILED_ZERO, (154, 238, 265, 255), [140, 230, 140, 35]),
    "qualifier_restart_button": (FAILED_ZERO, (888, 647, 1084, 684), [870, 630, 230, 75]),
    "qualifier_restart_popup_title": (RESTART_CONFIRM, (570, 177, 718, 215), [550, 160, 190, 70]),
    "qualifier_restart_popup_button": (RESTART_CONFIRM, (527, 540, 733, 580), [500, 520, 265, 80]),
}


def template(key, roi=None):
    return {
        "recognition": "TemplateMatch",
        "template": f"navigation/duel/{key}.png",
        "roi": roi or SPECS[key][2],
        "threshold": 0.9,
    }


def main():
    IMAGE_ROOT.mkdir(parents=True, exist_ok=True)
    for key, (source, box, _) in SPECS.items():
        with Image.open(ROOT / "captures" / source) as image:
            assert image.size == (1280, 720), (source, image.size)
            image.convert("RGB").crop(box).save(IMAGE_ROOT / f"{key}.png")

    home = json.loads((ROOT / "assets/resource/pipeline/home_navigation.json").read_text(encoding="utf-8"))
    selected = copy.deepcopy(home["主页_多人游戏_已选中"])
    selected.pop("action", None)
    selected.pop("next", None)
    switch = copy.deepcopy(home["主页_多人游戏_切换"])
    switch["next"] = ["对决_点击首页卡片"]
    defense = json.loads((ROOT / "assets/resource/pipeline/duel_defense.json").read_text(encoding="utf-8"))
    defense_states = defense["对决_防守状态识别入口"]["next"]
    zero_rois = [[x, 230, 140, 35] for x in (140, 374, 608, 842, 1076)]
    interrupted_states = ["对决_确认重开资格赛", "对决_重开零进度资格赛"]
    pipeline = {
        "对决_资格赛入口": {
            "recognition": "DirectHit", "action": "DoNothing", "timeout": 60000,
            "next": [*interrupted_states, *defense_states, "对决_点击资格赛",
                     "对决_点击首页卡片", "对决_切换多人标签"],
        },
        "对决_切换多人标签": switch,
        "对决_点击首页卡片": {
            "recognition": "And", "all_of": [selected, template("home_duel_title")],
            "action": "Click", "target": [930, 330], "max_hit": 1,
            "post_delay": 800, "timeout": 60000,
            "next": [*interrupted_states, *defense_states, "对决_点击资格赛"],
        },
        "对决_重开零进度资格赛": {
            "recognition": "And",
            "all_of": [template("qualifier_failed_title"),
                       template("qualifier_restart_button"),
                       *(template("qualifier_zero_time", roi) for roi in zero_rois)],
            "action": "Click", "target": [970, 665], "max_hit": 1,
            "post_delay": 500, "timeout": 60000,
            "next": ["对决_确认重开资格赛"],
        },
        "对决_确认重开资格赛": {
            "recognition": "And",
            "all_of": [template("qualifier_restart_popup_title"),
                       template("qualifier_restart_popup_button")],
            "action": "Click", "target": [635, 558], "max_hit": 1,
            "post_delay": 700, "timeout": 60000,
            "next": ["对决_防守状态识别入口"],
        },
        "对决_点击资格赛": {
            "recognition": "And", "all_of": [template("qualifier_title"), template("qualifier_button")],
            "action": "Click", "target": [1100, 680], "max_hit": 1,
            "post_delay": 500, "timeout": 60000,
            "next": ["对决_防守状态识别入口"],
        },
    }
    path = ROOT / "assets/resource/pipeline/duel_navigation.json"
    path.write_text(json.dumps(pipeline, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")

    cases = {
        HOME: "对决_点击首页卡片",
        QUALIFIER: "对决_点击资格赛",
        FAILED_ZERO: "对决_重开零进度资格赛",
        RESTART_CONFIRM: "对决_确认重开资格赛",
        RESTART_READY: "对决_防守_第1赛道展开未选车",
        "多人游戏_主页选中_白金.png": "对决_点击首页卡片",
        "多人游戏_主页选中_无奖励.png": "对决_点击首页卡片",
        "多人游戏_经典系列赛_首页_白金.png": None,
        "多人游戏_选车_白金起点_仅拥有开启.png": None,
        "多人游戏_结算_成绩.png": None,
    }
    cases.update({
        f"多人游戏_对决_资格赛_防守_第{slot}赛道展开_未选车.png": f"对决_防守_第{slot}赛道展开未选车"
        for slot in range(1, 6)
    })
    cases["多人游戏_对决_资格赛_防守_第1赛道展开_已选车_可开始.png"] = "对决_防守_已选车可开始"
    candidates = pipeline["对决_资格赛入口"]["next"][:-1]
    recognition = {**defense, **pipeline}
    report = []
    for source, expected in cases.items():
        image = read_image(ROOT / "captures" / source)
        matches = [name for name in candidates if hit(recognition[name], image)]
        assert (matches[0] if matches else None) == expected, (source, matches, expected)
        report.append({
            "screenshot": source,
            "matches": matches,
            "first_match": matches[0] if matches else None,
        })
        print(f"PASS {source}: {matches}")
    # A spent ticket must require five independently visible zero records.
    failed_image = read_image(ROOT / "captures" / FAILED_ZERO)
    for index, (x, y, w, h) in enumerate(zero_rois, start=1):
        altered = failed_image.copy()
        cv2.rectangle(altered, (x, y), (x + w, y + h), (65, 30, 42), -1)
        assert not hit(pipeline["对决_重开零进度资格赛"], altered), index
    (ROOT / "captures/duel_navigation_check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS independent Duel entry; clicks not device-tested")


if __name__ == "__main__":
    main()
