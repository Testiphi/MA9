"""生成黄金定位、TouchDrive 开启任务并检查所有现有截图。"""
import copy
import json
from pathlib import Path
from PIL import Image
from check_daily_navigation import read_image, hit

ROOT = Path(__file__).resolve().parents[1]
DETAIL = "多人游戏_车辆详情_Ferrari J50_可开始_TouchDrive"
SPECS = {
    "touchdrive_label": (DETAIL + "开.png", (821, 615, 957, 642), [812, 607, 155, 43]),
    "detail_upgrade": (DETAIL + "开.png", (157, 628, 218, 669), [147, 616, 82, 65]),
    "detail_start": (DETAIL + "开.png", (1077, 632, 1139, 669), [1067, 619, 82, 65]),
    "touchdrive_on": (DETAIL + "开.png", (823, 654, 956, 686), [815, 648, 148, 43]),
    "touchdrive_off": (DETAIL + "关.png", (823, 654, 956, 686), [815, 648, 148, 43]),
    "gold_selected": ("多人游戏_选车_黄金起点_仅拥有开启.png", (643, 92, 700, 135), [637, 85, 70, 54]),
}

def main():
    output = ROOT / "assets/resource/image/navigation/vehicle"
    output.mkdir(parents=True, exist_ok=True)
    for name, (source, box, _) in SPECS.items():
        with Image.open(ROOT / "captures" / source) as image:
            assert image.size == (1280, 720), (source, image.size)
            image.convert("RGB").crop(box).save(output / f"{name}.png")

    def template(name):
        return {"recognition": "TemplateMatch", "template": f"navigation/vehicle/{name}.png", "roi": SPECS[name][2], "threshold": 0.9}

    def detail(state):
        return {"recognition": "And", "all_of": [template("touchdrive_label"), template("detail_upgrade"), template("detail_start"), template(state)]}

    # 复用纯识别部分，不改变已实测的多人准备任务。
    multiplayer = json.loads((ROOT / "assets/resource/pipeline/multiplayer_navigation.json").read_text(encoding="utf-8"))
    selection = multiplayer["多人准备_仅拥有已开启"]["all_of"]
    enable_owned = copy.deepcopy(multiplayer["多人准备_开启仅拥有"])
    enable_owned["next"] = ["黄金定位_点击黄金"]
    intro_start = copy.deepcopy(multiplayer["多人准备_介绍页开始"])
    intro_start["next"] = ["黄金定位_点击黄金", "黄金定位_开启仅拥有"]
    pipeline = {
        "TouchDrive_确认入口": {
            "recognition": "DirectHit", "action": "DoNothing", "timeout": 10000,
            "next": ["TouchDrive_已开启", "TouchDrive_点击开"],
        },
        "TouchDrive_已开启": {**detail("touchdrive_on"), "action": "DoNothing", "next": []},
        "TouchDrive_点击开": {
            **detail("touchdrive_off"), "action": "Click", "target": [853, 670], "max_hit": 1,
            "post_delay": 300, "timeout": 10000, "next": ["TouchDrive_已开启"],
        },
        "黄金定位_入口": {
            "recognition": "DirectHit", "action": "DoNothing", "timeout": 60000,
            "next": ["黄金定位_点击黄金", "黄金定位_开启仅拥有", "黄金定位_介绍页开始"],
        },
        "黄金定位_开启仅拥有": enable_owned,
        "黄金定位_介绍页开始": intro_start,
        "黄金定位_点击黄金": {
            "recognition": "And", "all_of": selection, "action": "Click", "target": [671, 107],
            "max_hit": 1, "post_delay": 500, "timeout": 10000,
            "next": ["黄金定位_已选中"],
        },
        "黄金定位_已选中": {
            "recognition": "And", "all_of": [*selection, template("gold_selected")],
            "action": "DoNothing", "next": [],
        },
    }
    path = ROOT / "assets/resource/pipeline/vehicle_controls.json"
    path.write_text(json.dumps(pipeline, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    pipeline = json.loads(path.read_text(encoding="utf-8"))
    report = []
    for source in sorted((ROOT / "captures").glob("*.png")):
        image = read_image(source)
        td = [name for name in pipeline["TouchDrive_确认入口"]["next"] if hit(pipeline[name], image)]
        expected_td = ["TouchDrive_已开启"] if source.name == DETAIL + "开.png" else ["TouchDrive_点击开"] if source.name == DETAIL + "关.png" else []
        assert td == expected_td, (source.name, td, expected_td)
        is_owned_selection = "_选车_" in source.name and "仅拥有开启" in source.name
        assert hit(pipeline["黄金定位_点击黄金"], image) == is_owned_selection, source.name
        is_gold = is_owned_selection and "_黄金" in source.name
        assert hit(pipeline["黄金定位_已选中"], image) == is_gold, source.name
        report.append({"screenshot": source.name, "touchdrive_matches": td, "can_locate_gold": is_owned_selection, "gold_selected": is_gold})
        print(f"PASS {source.name}")
    (ROOT / "captures/vehicle_controls_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    # 纳入真实失败现场，检查首次动作分支，而不只检查模板源图。
    failure_dir = ROOT / "debug/on_error"
    failures = {
        "2026.09.15-19.48.14.704_黄金定位_入口.png": "黄金定位_介绍页开始",
        "2026.09.15-19.48.48.177_黄金定位_入口.png": "黄金定位_开启仅拥有",
        "2026.09.15-19.49.32.868_黄金定位_入口.png": "黄金定位_开启仅拥有",
    }
    for name, expected in failures.items():
        source = failure_dir / name
        if not source.exists():
            continue
        image = read_image(source)
        matches = [node for node in pipeline["黄金定位_入口"]["next"] if hit(pipeline[node], image)]
        assert matches == [expected], (name, matches, expected)
        print(f"PASS failure screenshot {name}: {matches}")
    for source in (ROOT / "captures").glob("*.png"):
        image = read_image(source)
        matches = [node for node in pipeline["黄金定位_入口"]["next"] if hit(pipeline[node], image)]
        expected = ["黄金定位_点击黄金"] if "_选车_" in source.name and "仅拥有开启" in source.name else ["黄金定位_开启仅拥有"] if "_选车_" in source.name and "仅拥有关闭" in source.name else ["黄金定位_介绍页开始"] if source.name == "多人游戏_经典系列赛_进入后.png" else []
        assert matches == expected, (source.name, matches, expected)
    print(f"PASS {len(report)} screenshot checks; device execution not tested")

if __name__ == "__main__":
    main()
