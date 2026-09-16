"""从已检查的原图生成经典系列赛选车入口，并离线检查页面分支。"""
import copy
import json
from pathlib import Path
from PIL import Image
from check_daily_navigation import read_image, hit

ROOT = Path(__file__).resolve().parents[1]
IMAGE_ROOT = ROOT / "assets/resource/image"
PAGE_LOAD_TIMEOUT_MS = 60000
SPECS = {
    "classic_card": ("多人游戏_主页选中_无奖励.png", (264, 401, 448, 466), [250, 390, 220, 85]),
    "classic_start": ("多人游戏_经典系列赛_首页_黄金.png", (1091, 638, 1151, 665), [1070, 625, 100, 50]),
    "selection_title": ("多人游戏_选车_青铜起点_仅拥有关闭.png", (100, 83, 230, 113), [90, 75, 150, 45]),
    "selection_tools": ("多人游戏_选车_青铜起点_仅拥有关闭.png", (1045, 83, 1093, 131), [1040, 78, 60, 60]),
    "league_icons": ("多人游戏_选车_青铜起点_仅拥有关闭.png", (541, 90, 1021, 123), [532, 82, 498, 50]),
    "league_icons_gold": ("多人游戏_选车_黄金起点_仅拥有开启.png", (541, 90, 1021, 123), [532, 82, 498, 50]),
    "owned_off": ("多人游戏_选车_青铜起点_仅拥有关闭.png", (1105, 83, 1154, 131), [1100, 78, 59, 60]),
    "owned_on": ("多人游戏_选车_青铜起点_仅拥有开启.png", (1105, 83, 1154, 131), [1100, 78, 59, 60]),
}

def main():
    output = IMAGE_ROOT / "navigation/multiplayer"
    output.mkdir(parents=True, exist_ok=True)
    for key, (source, box, _) in SPECS.items():
        with Image.open(ROOT / "captures" / source) as image:
            assert image.size == (1280, 720), (source, image.size)
            image.convert("RGB").crop(box).save(output / f"{key}.png")

    def template(key):
        paths = ["navigation/multiplayer/league_icons.png", "navigation/multiplayer/league_icons_gold.png"] if key == "league_icons" else f"navigation/multiplayer/{key}.png"
        return {"recognition": "TemplateMatch", "template": paths,
                "roi": SPECS[key][2], "threshold": 0.9}

    def selection(key):
        return {"recognition": "And", "all_of": [template("selection_title"), template("selection_tools"), template(key)]}

    home = json.loads((ROOT / "assets/resource/pipeline/home_navigation.json").read_text(encoding="utf-8"))
    selected = copy.deepcopy(home["主页_多人游戏_已选中"])
    selected.pop("action")
    selected.pop("next")
    switch = copy.deepcopy(home["主页_多人游戏_切换"])
    switch["next"] = ["多人准备_点击经典系列赛"]
    race = json.loads((ROOT / "assets/resource/pipeline/race_screens.json").read_text(encoding="utf-8"))
    intro_guard = copy.deepcopy(race["多人结算_已返回系列赛"])
    pipeline = {
        "多人准备_入口": {
            "recognition": "DirectHit", "action": "DoNothing", "timeout": PAGE_LOAD_TIMEOUT_MS,
            "next": ["多人准备_仅拥有已开启", "多人准备_开启仅拥有", "多人准备_介绍页开始", "多人准备_点击经典系列赛", "多人准备_切换多人标签"],
        },
        "多人准备_切换多人标签": switch,
        "多人准备_点击经典系列赛": {
            "recognition": "And", "all_of": [selected, template("classic_card")],
            "action": "Click", "target": [350, 350], "max_hit": 1,
            "post_delay": 500, "timeout": PAGE_LOAD_TIMEOUT_MS,
            "next": ["多人准备_仅拥有已开启", "多人准备_开启仅拥有", "多人准备_介绍页开始"],
        },
        "多人准备_介绍页开始": {
            "recognition": "And", "all_of": [*copy.deepcopy(intro_guard["all_of"]), template("classic_start")],
            "action": "Click", "target": [1110, 650], "max_hit": 1,
            "post_delay": 500, "timeout": PAGE_LOAD_TIMEOUT_MS,
            "next": ["多人准备_仅拥有已开启", "多人准备_开启仅拥有"],
        },
        "多人准备_开启仅拥有": {
            **selection("owned_off"), "action": "Click", "target": [1130, 107],
            "max_hit": 1, "post_delay": 500, "timeout": 10000,
            "next": ["多人准备_仅拥有已开启"],
        },
        "多人准备_仅拥有已开启": {
            **selection("owned_on"), "action": "DoNothing", "next": [],
        },
    }
    path = ROOT / "assets/resource/pipeline/multiplayer_navigation.json"
    path.write_text(json.dumps(pipeline, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    pipeline = json.loads(path.read_text(encoding="utf-8"))
    cases = {
        "多人游戏_经典系列赛_首页_黄金.png": "多人准备_介绍页开始",
        "多人游戏_经典系列赛_首页_白银.png": "多人准备_介绍页开始",
        "多人游戏_选车_青铜起点_仅拥有关闭.png": "多人准备_开启仅拥有",
        "多人游戏_选车_青铜起点_仅拥有开启.png": "多人准备_仅拥有已开启",
        "每日赛事_进入后_无奖励.png": None,
    }
    for source in (ROOT / "captures").glob("多人游戏_选车_黄金*.png"):
        cases[source.name] = "多人准备_仅拥有已开启"
    for source in (ROOT / "captures").glob("多人游戏_选车_*仅拥有关闭.png"):
        cases[source.name] = "多人准备_开启仅拥有"
    for source in (ROOT / "captures").glob("多人游戏_选车_*仅拥有开启.png"):
        cases[source.name] = "多人准备_仅拥有已开启"
    for source in (ROOT / "captures").glob("*_车辆详情_*.png"):
        cases[source.name] = None
    for source in (ROOT / "captures").glob("*_主页*.png"):
        cases[source.name] = "多人准备_点击经典系列赛" if source.name == "多人游戏_主页选中_无奖励.png" else "多人准备_切换多人标签"
    report = []
    for source, expected in cases.items():
        image = read_image(ROOT / "captures" / source)
        matches = [name for name in pipeline["多人准备_入口"]["next"] if hit(pipeline[name], image)]
        assert matches == ([] if expected is None else [expected]), (source, matches, expected)
        report.append({"screenshot": source, "matches": matches})
        print(f"PASS {source}: {matches}")
    (ROOT / "captures/multiplayer_navigation_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS {len(cases)} screenshot branch checks; device execution not tested")

if __name__ == "__main__":
    main()
