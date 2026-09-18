"""按手动当前段位生成独立倒序兜底测试，不点击开始。"""
import copy
import json
from pathlib import Path
from PIL import Image
from check_daily_navigation import read_image, hit

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "倒序兜底_"
SPECS = {
    "left": ("多人游戏_车辆详情_TVR Sagaris_可开始_未满油_TouchDrive开.png", (479, 341, 513, 380), [465, 330, 60, 60]),
    "right": ("多人游戏_车辆详情_TVR Sagaris_可开始_未满油_TouchDrive开.png", (1181, 341, 1214, 380), [1165, 330, 65, 60]),
    "key": ("多人游戏_车辆详情_Volkswagen Electric R_不可开始_缺钥匙.png", (984, 619, 1218, 668), [970, 600, 265, 85]),
    "blueprint": ("多人游戏_车辆详情_Renault TREZOR_不可开始_缺图纸.png", (986, 619, 1220, 668), [970, 600, 265, 85]),
    "gold_unavailable": ("多人游戏_车辆详情_Lamborghini Asterion_段位不可用_黄金.png", (1060, 617, 1145, 655), [1045, 600, 120, 70]),
    "platinum_unavailable": ("多人游戏_车辆详情_Nissan GT-R Nismo_段位不可用_白金.png", (1059, 617, 1145, 655), [1045, 600, 120, 70]),
    "emerald_unavailable": ("多人游戏_车辆详情_Apollo N_段位不可用_翡翠.png", (1059, 617, 1145, 655), [1045, 600, 120, 70]),
    "bronze_first": ("多人游戏_车辆详情_Mitsubishi Lancer Evolution_青铜起点_TouchDrive开.png", (79, 98, 153, 189), [70, 88, 95, 112]),
    "anchor_card": ("多人游戏_车辆详情_Nissan GT-R Nismo_段位不可用_白金.png", (79, 98, 153, 189), [70, 88, 95, 112]),
    "gold_anchor_card": ("多人游戏_车辆详情_Lamborghini Asterion_段位不可用_黄金.png", (79, 98, 153, 189), [70, 88, 95, 112]),
    "emerald_anchor_card": ("多人游戏_车辆详情_Apollo N_段位不可用_翡翠.png", (79, 98, 153, 189), [70, 88, 95, 112]),
    "gold_anchor_list": ("多人游戏_选车_黄金起点_仅拥有开启.png", (537, 338, 650, 360), [200, 190, 1000, 230]),
    "gold_selected": ("多人游戏_选车_黄金起点_仅拥有开启.png", (644, 91, 700, 136), [637, 85, 70, 54]),
    "emerald_anchor_list": ("多人游戏_选车_翡翠起点_仅拥有开启.png", (537, 338, 650, 360), [200, 190, 1000, 230]),
    "emerald_selected": ("多人游戏_选车_翡翠起点_仅拥有开启.png", (755, 91, 811, 136), [748, 85, 70, 54]),
}


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main():
    import os
    profile = read("data/multiplayer_profile.json")
    league = os.environ.get("MA9_BUILD_LEAGUE", profile["current_league"])
    assert league in ["白金", "黄金", "白银"], "当前测试支持白金、黄金、白银手动段位"
    anchor_league = {"白银": "黄金", "黄金": "白金", "白金": "翡翠"}[league]
    anchor_source = f"多人游戏_选车_{anchor_league}起点_仅拥有开启.png"
    folder = ROOT / "assets/resource/image/navigation/fallback"
    folder.mkdir(parents=True, exist_ok=True)
    for name, (source, crop, _) in SPECS.items():
        with Image.open(ROOT / "captures" / source) as image:
            assert image.size == (1280, 720)
            image.convert("RGB").crop(crop).save(folder / f"{name}.png")
    def template(name):
        return {"recognition": "TemplateMatch", "template": f"navigation/fallback/{name}.png",
                "roi": SPECS[name][2], "threshold": 0.9}
    def guard(*children):
        return {"recognition": "And", "all_of": list(children)}
    def name(suffix):
        return PREFIX + suffix
    controls = read("assets/resource/pipeline/vehicle_controls.json")
    mp = read("assets/resource/pipeline/multiplayer_navigation.json")
    two = read("assets/resource/pipeline/two_car_rotation.json")
    arrows = guard(template("left"), template("right"))
    ready = copy.deepcopy(controls["TouchDrive_已开启"])
    enable = copy.deepcopy(controls["TouchDrive_点击开"])
    ready.update(next=[])
    enable.update(next=[name("可用车已准备")], max_hit=5)
    empty = copy.deepcopy(two["两车_Panamera_缺油返回列表"])
    empty_guard = guard(*copy.deepcopy(empty["all_of"][1:3]), arrows)
    skips = {
        "缺钥匙": guard(template("key"), arrows),
        "缺图纸": guard(template("blueprint"), arrows),
        "黄金段位不可用": guard(template("gold_unavailable"), arrows),
        "白金段位不可用": guard(template("platinum_unavailable"), arrows),
        "翡翠段位不可用": guard(template("emerald_unavailable"), arrows),
        "缺油": empty_guard,
    }
    pipeline = {name("可用车已准备"): ready, name("可用车开启TouchDrive"): enable}
    recommended = []
    manifest = read("data/generated/gold_rotation_manifest.json")
    gold = read("assets/resource/pipeline/gold_rotation.json")
    for stage in manifest["active_candidates"]:
        cid = stage["catalog_id"]
        # 复用正式推荐车的详情识别和准备动作；不回到搜索入口。
        for kind in ["ready", "enable"]:
            node_name = name(cid + "_" + kind)
            node = copy.deepcopy(gold[stage[kind]])
            node["next"] = [] if kind == "ready" else [name(cid + "_ready")]
            pipeline[node_name] = node
            recommended.append(node_name)
    # 先识别通用可用状态，再分发推荐车身份；缺油和不可用不扫描整份名单。
    pipeline[name("有油且TouchDrive已开")] = {**copy.deepcopy(ready), "pre_delay": 0, "post_delay": 0,
                                               "next": [*recommended, name("可用车已准备")]}
    enable["next"] = [name("有油且TouchDrive已开")]
    checks_next = [name("青铜首车不可用_停止"), *[name(s) for s in skips],
                   name("有油且TouchDrive已开"), name("可用车开启TouchDrive")]
    pipeline[name("青铜首车不可用_停止")] = {**guard(template("bronze_first"),
                                             {"recognition": "Or", "any_of": list(skips.values())}),
                                              "action": "DoNothing", "next": []}
    for suffix, condition in skips.items():
        pipeline[name(suffix)] = {**condition, "action": "DoNothing", "pre_delay": 0,
                                  "post_delay": 0, "timeout": 10000,
                                  "next": [name("向左切车"), name("切车次数耗尽_停止")]}
    for suffix in ["向左切车", "切车次数耗尽_停止"]:
        pipeline[name(suffix)] = {**copy.deepcopy(arrows), "action": "DoNothing", "next": []}
    pipeline[name("向左切车")].update(action="Click", target=[495, 360],
                                     max_hit=338, pre_delay=0, post_delay=450,
                                     timeout=15000, next=checks_next)
    list_guard = copy.deepcopy(mp["多人准备_仅拥有已开启"])
    list_guard.update(action="Click", target=[{"白银": 671, "黄金": 726, "白金": 782}[league], 107], max_hit=2,
                      pre_delay=0, post_delay=800, timeout=60000, next=[name("确认相邻段位起点")])
    pipeline[name("定位相邻段位起点")] = list_guard
    anchor = copy.deepcopy(two["两车_Panamera_滑动搜索_反查起点已确认"])
    if league == "白银":
        anchor = guard(*copy.deepcopy(list_guard["all_of"]), template("gold_selected"), template("gold_anchor_list"))
    elif league == "白金":
        anchor = guard(*copy.deepcopy(list_guard["all_of"]), template("emerald_selected"), template("emerald_anchor_list"))
    anchor.update(action="Click", target=[380, 280], max_hit=1, post_delay=800,
                  timeout=60000, next=[name("锚点向左切车")])
    pipeline[name("确认相邻段位起点")] = anchor
    anchor_card = {"白银": "gold_anchor_card", "黄金": "anchor_card", "白金": "emerald_anchor_card"}[league]
    pipeline[name("锚点向左切车")] = {**guard(template(anchor_card), arrows),
                                       "action": "Click", "target": [495, 360], "max_hit": 1,
                                       "pre_delay": 0, "post_delay": 450, "timeout": 15000,
                                       "next": checks_next}
    owned = copy.deepcopy(mp["多人准备_开启仅拥有"])
    owned["next"] = [name("定位相邻段位起点")]
    pipeline[name("开启仅拥有")] = owned
    pipeline[name("入口")] = {"recognition": "DirectHit", "action": "DoNothing", "timeout": 60000,
                              "next": [name("定位相邻段位起点"), name("开启仅拥有") ]}
    # 已经在高段位详情时一次返回重新定位，不逐辆遍历不可用段位。
    pipeline[name("高段位返回列表")] = {"recognition": "TemplateMatch",
        "template": "navigation/vehicle/detail_back.png", "roi": [15, 3, 48, 58], "threshold": 0.9,
        "action": "Click", "target": [40, 30], "max_hit": 1,
        "pre_delay": 0, "post_delay": 450, "timeout": 15000, "next": [name("入口")]}
    higher_unavailable = {"白银": ["黄金段位不可用", "白金段位不可用"],
                          "黄金": ["白金段位不可用"],
                          "白金": ["翡翠段位不可用"]}[league]
    for suffix in higher_unavailable:
        pipeline[name(suffix)]["next"] = [name("高段位返回列表")]
    pipeline[name("详情原地测试入口")] = {"recognition": "DirectHit", "action": "DoNothing",
                                          "timeout": 15000, "next": checks_next}
    report = []
    for source in sorted((ROOT / "captures").glob("*.png")):
        image = read_image(source)
        matches = {suffix: hit(node, image) for suffix, node in skips.items()}
        expected = {suffix: False for suffix in skips}
        for suffix, spec_key in [("缺钥匙", "key"), ("缺图纸", "blueprint"),
                                 ("黄金段位不可用", "gold_unavailable"),
                                 ("白金段位不可用", "platinum_unavailable"),
                                 ("翡翠段位不可用", "emerald_unavailable")]:
            expected[suffix] = source.name == SPECS[spec_key][0]
        expected["缺油"] = "_无燃油_" in source.name
        expected["黄金段位不可用"] = "_段位不可用_黄金.png" in source.name
        expected["白金段位不可用"] = "_段位不可用_白金.png" in source.name
        expected["翡翠段位不可用"] = "_段位不可用_翡翠.png" in source.name
        assert matches == expected, (source.name, matches, expected)
        found_ready = hit(ready, image)
        found_off = hit(enable, image)
        assert found_ready == (source.name.startswith("多人游戏_车辆详情_") and
                               ("_可开始_" in source.name or "起点_TouchDrive" in source.name)
                               and source.name.endswith("TouchDrive开.png")), (source.name, "ready", found_ready)
        assert found_off == source.name.endswith("_可开始_TouchDrive关.png"), (source.name, "off", found_off)
        report.append({"source": source.name, "skip": matches, "ready": found_ready, "touchdrive_off": found_off})
    assert all(n in pipeline for node in pipeline.values() for n in node.get("next", []))
    assert hit(anchor, read_image(ROOT / "captures" / anchor_source)), "相邻段位锚点失败"
    bronze = read_image(ROOT / "captures" / SPECS["bronze_first"][0]).copy()
    assert not hit(pipeline[name("青铜首车不可用_停止")], bronze), "青铜首车有油不能停止"
    empty_image = read_image(ROOT / "captures/多人游戏_车辆详情_Ferrari J50_无燃油_TouchDrive开.png")
    bronze[600:720, 460:1280] = empty_image[600:720, 460:1280]
    assert hit(pipeline[name("青铜首车不可用_停止")], bronze), "青铜首车缺油必须停止"
    assert not hit(ready, bronze), "缺油不能准备完成"
    (ROOT / "captures/reverse_fallback_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 所有分支使用短识别轮询，匹配后不叠加 Maa 默认动作等待。
    for node in pipeline.values():
        node.setdefault("rate_limit", 100)
        node.setdefault("pre_delay", 0)
        node.setdefault("post_delay", 0)
    (ROOT / os.environ.get("MA9_FALLBACK_FILE", "assets/resource/pipeline/reverse_fallback.json")).write_text(json.dumps(pipeline, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"PASS {len(report)*len(skips)} state checks; current={league}, anchor={anchor_league}; device clicks not tested")


if __name__ == "__main__":
    main()
