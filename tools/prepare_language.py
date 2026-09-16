"""生成英转简中独立流程，确认重载后等待中文主页。"""
import copy
import json
from pathlib import Path
from PIL import Image
from check_daily_navigation import read_image, hit

ROOT = Path(__file__).resolve().parents[1]
HOME = "主页面_英语.png"
CONNECT = "设置_连接_英语.png"
SETTINGS = "设置_游戏设置_英语.png"
EN = "设置_语言_英语.png"
CN = "设置_语言_中文.png"
RESTART = "语言更改_重启.png"
RESTART_VARIANT = "语言更改_重启_新游戏设置.png"
GARAGE = "车库外观广告.png"
ADS = ["BXR氮气特效广告.png", "每日超能礼包广告.png"]
CONNECTION_ERROR = "连接错误.png"
SPECS = {
    "options": (CONNECT, (71, 82, 337, 115), [55, 70, 300, 60]),
    "care": (CONNECT, (306, 321, 533, 356), [290, 305, 260, 65]),
    "settings_tab": (CONNECT, (583, 154, 695, 206), [565, 140, 150, 80]),
    "language_button": (SETTINGS, (338, 504, 487, 534), [315, 485, 195, 70]),
    "controls_button": (SETTINGS, (338, 417, 488, 447), [315, 400, 195, 70]),
    "language_en": (EN, (59, 164, 417, 199), [45, 150, 390, 65]),
    "current_en": (EN, (60, 208, 233, 234), [45, 195, 205, 55]),
    "chinese_choice": (EN, (580, 345, 697, 382), [560, 330, 155, 70]),
    "language_cn": (CN, (59, 165, 210, 202), [45, 150, 185, 65]),
    "current_cn": (CN, (59, 208, 192, 234), [45, 195, 165, 55]),
    "restart_title": (RESTART, (193, 227, 377, 264), [175, 210, 225, 70]),
    "restart_body": (RESTART, (440, 382, 828, 412), [420, 365, 430, 65]),
    "restart_close": (RESTART, (1074, 225, 1111, 264), [1060, 210, 65, 70]),
    "garage_title": (GARAGE, (359, 114, 922, 172), [340, 95, 600, 95]),
    "garage_claim": (GARAGE, (882, 551, 1048, 595), [860, 535, 210, 75]),
    "back_arrow": (CONNECT, (25, 12, 53, 49), [15, 3, 48, 58]),
    "ad_close_white": (ADS[0], (1067, 92, 1105, 130), [1000, 70, 160, 110]),
    "ad_close_pink": (ADS[1], (1061, 99, 1100, 138), [1000, 70, 160, 110]),
    "connection_title": (CONNECTION_ERROR, (575, 192, 705, 230), [555, 175, 170, 70]),
    "connection_retry": (CONNECTION_ERROR, (610, 482, 671, 516), [590, 465, 100, 65]),
}
for name, box in [
    ("pass", (102, 644, 190, 697)), ("season", (280, 644, 375, 697)),
    ("daily", (504, 644, 614, 697)), ("multiplayer", (715, 644, 806, 697)),
    ("club", (985, 644, 1041, 697)), ("single", (1108, 644, 1237, 697)),
]:
    SPECS["home_en_" + name] = (HOME, box, [0, 610, 1280, 110])


def main():
    output = ROOT / "assets/resource/image/navigation/language"
    output.mkdir(parents=True, exist_ok=True)
    for name, (source, box, roi) in SPECS.items():
        with Image.open(ROOT / "captures" / source) as image:
            assert image.size == (1280, 720), source
            image.convert("RGB").crop(box).save(output / (name + ".png"))
    def template(name):
        return {"recognition": "TemplateMatch", "template": f"navigation/language/{name}.png",
                "roi": SPECS[name][2], "threshold": 0.9}
    def guarded(names, target, following):
        return {"recognition": "And", "all_of": [template(n) for n in names],
                "action": "Click", "target": target, "max_hit": 1, "post_delay": 500,
                "timeout": 60000, "next": following}
    return_nodes = json.loads((ROOT / "assets/resource/pipeline/return_navigation.json").read_text(encoding="utf-8"))
    chinese_home = copy.deepcopy(return_nodes["主页返回_已到达"])
    chinese_home["next"] = []
    gear = copy.deepcopy(chinese_home["all_of"][0])
    restart = "语言切换_确认重启"
    done = "语言切换_已到中文主页"
    pipeline = {
        "语言切换_入口": {"recognition": "DirectHit", "action": "DoNothing", "timeout": 60000,
                            "next": [restart, done, "语言切换_中文语言页返回", "语言切换_选择简体中文",
                                     "语言切换_打开语言", "语言切换_进入游戏设置", "语言切换_英文主页设置"]},
        "语言切换_英文主页设置": {"recognition": "And", "all_of": [gear,
            {"recognition": "Or", "any_of": [template(n) for n in SPECS if n.startswith("home_en_")]}],
            "action": "Click", "target": [1250, 30], "max_hit": 1, "post_delay": 500,
            "timeout": 60000, "next": ["语言切换_打开语言", "语言切换_进入游戏设置"]},
        "语言切换_进入游戏设置": guarded(["options", "care", "settings_tab"], [640, 180], ["语言切换_打开语言"]),
        "语言切换_打开语言": guarded(["options", "language_button", "controls_button"], [412, 518], ["语言切换_选择简体中文"]),
        "语言切换_选择简体中文": guarded(["language_en", "current_en", "chinese_choice"], [640, 365], [restart, "语言切换_中文语言页返回"]),
        "语言切换_中文语言页返回": guarded(["language_cn", "current_cn"], [1250, 30], [restart, done]),
        restart: {"recognition": "And", "all_of": [template("restart_body"), template("restart_close")],
                  "action": "Click", "target": [1092, 244], "max_hit": 1,
                  "post_delay": 1000, "timeout": 180000, "next": [done]},
        done: chinese_home,
    }
    english_home = copy.deepcopy(pipeline["语言切换_英文主页设置"])
    english_home.update(action="DoNothing", next=[])
    for key in ["target", "max_hit", "post_delay", "timeout"]:
        english_home.pop(key, None)
    common_home = {"recognition": "Or", "any_of": [copy.deepcopy(chinese_home), english_home],
                   "action": "DoNothing", "next": []}
    # 单独的弹窗任务只领取并返回主页；语言任务内同样处理后继续检查语言。
    for prefix, after_home in [("通用弹窗_", []), ("语言切换_弹窗_", ["语言切换_入口"])]:
        claim, home, back = prefix + "车库外观领取", prefix + "已到主页", prefix + "逐级返回"
        close, retry = prefix + "关闭广告", prefix + "连接错误重试"
        following = [close, retry, claim, home, back]
        pipeline[claim] = guarded(["garage_title", "garage_claim"], [966, 572], following)
        pipeline[close] = {"recognition": "TemplateMatch",
                           "template": [template("ad_close_white")["template"], template("ad_close_pink")["template"]],
                           "roi": SPECS["ad_close_white"][2], "threshold": 0.9,
                           "action": "Click", "target": True, "max_hit": 10,
                           "post_delay": 500, "timeout": 180000,
                           "next": ["语言切换_入口"] if after_home else following}
        pipeline[retry] = guarded(["connection_title", "connection_retry"], [640, 497],
                                  ["语言切换_入口"] if after_home else following)
        pipeline[retry].update(max_hit=10, post_delay=2000, timeout=180000)
        pipeline[home] = copy.deepcopy(common_home)
        pipeline[home]["next"] = after_home
        pipeline[back] = {**template("back_arrow"), "action": "Click", "target": [40, 30],
                          "max_hit": 20, "post_delay": 500, "timeout": 60000, "next": following}
        pipeline[prefix + "入口"] = {"recognition": "DirectHit", "action": "DoNothing", "timeout": 180000,
                                      "next": [close, retry, claim, home]}
    language_claim = "语言切换_弹窗_车库外观领取"
    pipeline[language_claim]["max_hit"] = 3
    # 重载后可能再次出现推广弹窗，因此重启后的等待也允许处理它。
    for name in list(pipeline):
        if name.startswith("语言切换_") and name != language_claim and not name.startswith("语言切换_弹窗_"):
            if pipeline[name].get("next"):
                pipeline[name]["next"][0:0] = ["语言切换_弹窗_关闭广告", "语言切换_弹窗_连接错误重试", language_claim]
    report = []
    for source in sorted((ROOT / "captures").glob("*.png")):
        image = read_image(source)
        expected = {
            "语言切换_英文主页设置": source.name == HOME,
            "语言切换_进入游戏设置": source.name == CONNECT,
            "语言切换_打开语言": source.name == SETTINGS,
            "语言切换_选择简体中文": source.name == EN,
            "语言切换_中文语言页返回": source.name == CN,
            restart: source.name in [RESTART, RESTART_VARIANT],
            done: "_主页" in source.name,
            "通用弹窗_车库外观领取": source.name == GARAGE,
            "通用弹窗_关闭广告": source.name in ADS,
            "通用弹窗_连接错误重试": source.name == CONNECTION_ERROR,
            "通用弹窗_已到主页": "_主页" in source.name or source.name == HOME,
        }
        # 中文终点可命中主页任意标签，按现有主页任务的条件验证，不能在英文页命中。
        matches = {name: hit(pipeline[name], image) for name in expected}
        assert matches == expected, (source.name, matches, expected)
        if source.name in [HOME, CONNECT, SETTINGS, EN, CN, RESTART]:
            assert not matches[done], (source.name, "false Chinese homepage")
        report.append({"screenshot": source.name, "matches": matches})
    assert all(n in pipeline for node in pipeline.values() for n in node.get("next", []))
    (ROOT / "assets/resource/pipeline/language_switch.json").write_text(json.dumps(pipeline, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    (ROOT / "captures/language_switch_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert pipeline[restart]["max_hit"] == 1 and pipeline[restart]["next"][-1] == done
    assert pipeline["通用弹窗_逐级返回"]["next"].index("通用弹窗_已到主页") < pipeline["通用弹窗_逐级返回"]["next"].index("通用弹窗_逐级返回")
    print(f"PASS {len(report) * 11} recognition checks; live execution not tested")


if __name__ == "__main__":
    main()
