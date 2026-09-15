"""组合已验证的导航节点，生成有滑动上限的 J50 搜索测试。"""
import copy
import json
from pathlib import Path
from PIL import Image
from check_daily_navigation import read_image, hit, score
from vehicle_search import swipe_timing

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "多人游戏_选车_黄金_Ferrari J50完整可见_仅拥有开启.png"
DETAIL = "多人游戏_车辆详情_Ferrari J50_可开始_TouchDrive"
EMPTY = "多人游戏_车辆详情_Ferrari J50_无燃油_TouchDrive开.png"

def main():
    output = ROOT / "assets/resource/image/navigation/vehicle"
    for source, name, box in [
        (SOURCE, "j50_list.png", (985, 327, 1040, 359)),
        (DETAIL + "开.png", "j50_detail.png", (174, 111, 269, 161)),
        (EMPTY, "fuel_zero.png", (516, 651, 550, 679)),
        (EMPTY, "fuel_skip.png", (1077, 632, 1139, 669)),
        (EMPTY, "detail_back.png", (25, 12, 53, 49)),
    ]:
        with Image.open(ROOT / "captures" / source) as image:
            assert image.size == (1280, 720)
            image.convert("RGB").crop(box).save(output / name)
    mp = json.loads((ROOT / "assets/resource/pipeline/multiplayer_navigation.json").read_text(encoding="utf-8"))
    controls = json.loads((ROOT / "assets/resource/pipeline/vehicle_controls.json").read_text(encoding="utf-8"))
    originals = {**mp, **controls}
    rename = {name: "J50测试_" + name for name in originals}
    pipeline = {}
    for name, node in originals.items():
        node = copy.deepcopy(node)
        node["next"] = [rename[n] for n in node.get("next", [])]
        pipeline[rename[name]] = node
    # 每个复制节点只在本测试中更改后继，不影响现有独立任务。
    pipeline[rename["多人准备_仅拥有已开启"]]["next"] = [rename["黄金定位_点击黄金"]]
    pipeline[rename["黄金定位_已选中"]]["next"] = ["J50测试_列表点击", "J50测试_滑动搜索"]
    ready = rename["TouchDrive_已开启"]
    enable = rename["TouchDrive_点击开"]
    identity = {"recognition": "TemplateMatch", "template": "navigation/vehicle/j50_detail.png",
                "roi": [165, 102, 115, 70], "threshold": 0.9}
    for name in [ready, enable]:
        pipeline[name]["all_of"].insert(0, identity)
    empty_branch = "J50测试_缺油返回列表"
    pipeline[empty_branch] = {
        "recognition": "And", "all_of": [
            identity,
            {"recognition": "TemplateMatch", "template": "navigation/vehicle/fuel_zero.png", "roi": [510, 642, 53, 45], "threshold": 0.9},
            {"recognition": "TemplateMatch", "template": "navigation/vehicle/fuel_skip.png", "roi": [1067, 619, 82, 65], "threshold": 0.9},
            {"recognition": "TemplateMatch", "template": "navigation/vehicle/detail_back.png", "roi": [15, 3, 48, 58], "threshold": 0.9},
        ],
        "action": "Click", "target": [40, 30], "max_hit": 1,
        "post_delay": 500, "timeout": 60000, "next": ["J50测试_缺油已返回"],
    }
    pipeline["J50测试_入口"] = {
        "recognition": "DirectHit", "action": "DoNothing", "timeout": 60000,
        "next": [empty_branch, ready, enable, *pipeline[rename["多人准备_入口"]]["next"]],
    }
    gold_guard = copy.deepcopy(controls["黄金定位_已选中"])
    gold_guard.pop("action")
    gold_guard.pop("next")
    pipeline["J50测试_缺油已返回"] = {
        # 返回完成只确认列表页；筛选状态和段位不应阻止任务结束。
        "recognition": "And", "all_of": copy.deepcopy(gold_guard["all_of"][:2]),
        "action": "DoNothing", "next": [],
    }
    list_identity = {"recognition": "TemplateMatch", "template": "navigation/vehicle/j50_list.png",
                     "roi": [210, 200, 1040, 460], "threshold": 0.9}
    pipeline["J50测试_列表点击"] = {
        "recognition": "And", "all_of": [list_identity, gold_guard], "box_index": 0,
        "action": "Click", "target": True, "max_hit": 1,
        "post_delay": 500, "timeout": 60000, "next": [empty_branch, ready, enable],
    }
    pipeline["J50测试_滑动搜索"] = {
        **gold_guard, "action": "Swipe", "begin": [1000, 420], "end": [600, 420],
        **swipe_timing(), "timeout": 5000,
        "max_hit": 12, "next": ["J50测试_列表点击", "J50测试_滑动搜索"],
    }
    path = ROOT / "assets/resource/pipeline/j50_search.json"
    path.write_text(json.dumps(pipeline, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    pipeline = json.loads(path.read_text(encoding="utf-8"))
    report = []
    for source in sorted((ROOT / "captures").glob("*.png")):
        image = read_image(source)
        j50_found = hit(pipeline["J50测试_列表点击"], image)
        assert j50_found == (source.name == SOURCE), (source.name, j50_found)
        td_matches = [n for n in [ready, enable] if hit(pipeline[n], image)]
        expected = [ready] if source.name == DETAIL + "开.png" else [enable] if source.name == DETAIL + "关.png" else []
        assert td_matches == expected, (source.name, td_matches, expected)
        empty_hit = hit(pipeline[empty_branch], image)
        assert empty_hit == (source.name == EMPTY), (source.name, empty_hit)
        returned = hit(pipeline["J50测试_缺油已返回"], image)
        assert returned == ("_选车_" in source.name), (source.name, returned)
        report.append({"screenshot": source.name, "list_found": j50_found,
                       "list_identity_score": round(score(list_identity, image), 4), "detail_matches": td_matches,
                       "empty_fuel": empty_hit, "returned_to_list": returned})
    # 结构检查：搜索检测顺序、滑动上限、匹配框点击、无比赛开始动作。
    assert pipeline["J50测试_滑动搜索"]["next"][0] == "J50测试_列表点击"
    assert pipeline["J50测试_滑动搜索"]["max_hit"] == 12
    assert all(n in pipeline for node in pipeline.values() for n in node.get("next", []))
    (ROOT / "captures/j50_search_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS {len(report)} screenshot identity checks and graph references; device execution not tested")

if __name__ == "__main__":
    main()
