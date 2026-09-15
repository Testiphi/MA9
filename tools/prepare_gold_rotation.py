"""按数据中的正式黄金顺序生成已有素材的轮换任务及缺图清单。"""
import copy
import json
from pathlib import Path
from PIL import Image
from check_daily_navigation import read_image, hit
from prepare_two_car_rotation import clone
from vehicle_search import add_reverse_search, swipe_timing

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main():
    profile = read("data/multiplayer_profile.json")
    assert profile["current_league"] == "黄金", "该任务目前仅支持手动黄金段位"
    assert profile["stop_before_race"] and profile["require_touchdrive"]
    rotation = read("data/generated/multiplayer_rotation.json")
    vehicles = next(g["vehicles"] for g in rotation["groups"] if g["league"] == "黄金")
    registry = read("data/sources/vehicle_recognition.json")["vehicles"]
    available, missing = [], []
    for vehicle in vehicles:
        spec = registry.get(vehicle["catalog_id"])
        if spec is None:
            missing.append({**vehicle, "reason": "missing_recognition_assets"})
        else:
            assert spec["title"] == vehicle["title"]
            available.append((vehicle, spec))
    assert available, "没有具备识别素材的黄金车型"
    controls = read("assets/resource/pipeline/vehicle_controls.json")
    mp = read("assets/resource/pipeline/multiplayer_navigation.json")
    two = read("assets/resource/pipeline/two_car_rotation.json")
    empty_base = two["两车_Panamera_缺油返回列表"]
    returned_base = two["两车_Panamera缺油_已返回_测试结束"]
    anchor_guard = two["两车_Panamera_滑动搜索_反查起点已确认"]
    list_guard = {"recognition": "And", "all_of": copy.deepcopy([
        controls["黄金定位_已选中"]["all_of"][0], controls["黄金定位_已选中"]["all_of"][2]])}
    pipeline, stages = {}, []
    for vehicle, spec in available:
        cid = vehicle["catalog_id"]
        prefix = "黄金轮换_" + cid + "_"
        nodes, names = clone({**mp, **controls}, prefix)
        pipeline.update(nodes)
        for kind in ["list", "detail"]:
            with Image.open(ROOT / "captures" / spec[kind + "_source"]) as image:
                assert image.size == (1280, 720)
                image.convert("RGB").crop(spec[kind + "_crop"]).save(
                    ROOT / "assets/resource/image/navigation/vehicle" / (cid + "_" + kind + ".png"))
        identity = {"recognition": "TemplateMatch", "template": f"navigation/vehicle/{cid}_detail.png",
                    "roi": [70, 88, 95, 112], "threshold": 0.9}
        ready, enable = names["TouchDrive_已开启"], names["TouchDrive_点击开"]
        for node in [ready, enable]:
            pipeline[node]["all_of"].insert(0, copy.deepcopy(identity))
        empty, returned = prefix + "缺油返回", prefix + "缺油已返回"
        pipeline[empty] = copy.deepcopy(empty_base)
        pipeline[empty]["all_of"][0] = copy.deepcopy(identity)
        pipeline[empty]["next"] = [returned]
        pipeline[returned] = copy.deepcopy(returned_base)
        click, forward = prefix + "点击车型", prefix + "正向搜索"
        list_identity = {"recognition": "TemplateMatch", "template": f"navigation/vehicle/{cid}_list.png",
                         "roi": [0, 190, 1280, 480], "threshold": 0.9}
        variants = [list_identity["template"]]
        for i, variant in enumerate(spec.get("list_variants", [])):
            filename = f"{cid}_list_variant_{i}.png"
            with Image.open(ROOT / "captures" / variant["source"]) as image:
                assert image.size == (1280, 720)
                image.convert("RGB").crop(variant["crop"]).save(ROOT / "assets/resource/image/navigation/vehicle" / filename)
            variants.append("navigation/vehicle/" + filename)
        list_identity["template"] = variants
        pipeline[click] = {"recognition": "And", "all_of": [list_identity, copy.deepcopy(list_guard)],
                           "box_index": 0, "action": "Click", "target": True, "max_hit": 1,
                           "post_delay": 500, "timeout": 60000, "next": [empty, ready, enable]}
        pipeline[forward] = {**copy.deepcopy(list_guard), "action": "Swipe", "begin": [1000, 420],
                             "end": [600, 420], **swipe_timing(),
                             "max_hit": 12, "timeout": 60000, "next": [click, forward]}
        pipeline[names["多人准备_仅拥有已开启"]]["next"] = [names["黄金定位_点击黄金"]]
        pipeline[names["黄金定位_已选中"]]["next"] = [click, forward]
        _, _, _, _, not_found = add_reverse_search(pipeline, click, forward, list_guard, anchor_guard, [726, 107])
        entry = prefix + "入口"
        pipeline[entry] = {"recognition": "DirectHit", "action": "DoNothing", "timeout": 60000,
                           "next": [empty, ready, enable, *pipeline[names["多人准备_入口"]]["next"]]}
        stages.append({"title": vehicle["title"], "catalog_id": cid, "order": vehicle["order"],
                       "entry": entry, "ready": ready, "enable": enable, "empty": empty, "returned": returned,
                       "not_found": not_found, "click": click, "spec": spec})
    exhausted = "黄金轮换_已有素材候选已耗尽"
    pipeline[exhausted] = {**copy.deepcopy(returned_base), "action": "DoNothing", "next": []}
    for i, stage in enumerate(stages):
        following = stages[i + 1]["entry"] if i + 1 < len(stages) else exhausted
        pipeline[stage["returned"]]["next"] = [following]
        # 搜索耗尽只表明未找到，不能冒充未拥有；继续下一候选并保留具体节点记录。
        pipeline[stage["not_found"]]["next"] = [following]
    # 从任一候选详情开始时，先返回列表再从正式顺序的第一辆重新选。
    resets = []
    for stage in stages:
        node = copy.deepcopy(pipeline[stage["empty"]])
        node["all_of"] = [copy.deepcopy(node["all_of"][0]), copy.deepcopy(node["all_of"][-1])]
        name = "黄金轮换_返回列表重排_" + stage["catalog_id"]
        node["next"] = ["黄金轮换_已返回待重排"]
        pipeline[name] = node
        resets.append(name)
    pipeline["黄金轮换_已返回待重排"] = {**copy.deepcopy(returned_base), "next": [stages[0]["entry"]]}
    pipeline["黄金轮换_入口"] = {"recognition": "DirectHit", "action": "DoNothing", "timeout": 60000,
                                  "next": [*resets, *pipeline[stages[0]["entry"]]["next"]]}

    def expand_strip(node):
        templates = node.get("template")
        if (isinstance(templates, list) and "navigation/multiplayer/league_icons_gold.png" in templates
                and "navigation/vehicle/platinum_league_icons.png" not in templates):
            templates.append("navigation/vehicle/platinum_league_icons.png")
        for child in node.get("all_of", []) + node.get("any_of", []):
            expand_strip(child)
    for node in pipeline.values():
        expand_strip(node)
    assert all(n in pipeline for node in pipeline.values() for n in node.get("next", []))
    checks = 0
    for stage in stages:
        spec = stage["spec"]
        for screenshot in (ROOT / "captures").glob("*.png"):
            image = read_image(screenshot)
            positives = spec.get("list_positive_sources", [spec["list_source"]])
            assert hit(pipeline[stage["click"]], image) == (screenshot.name in positives), (stage["title"], screenshot.name, "list")
            assert hit(pipeline[stage["ready"]], image) == (screenshot.name == spec["detail_source"]), (stage["title"], screenshot.name, "ready")
            assert hit(pipeline[stage["empty"]], image) == (screenshot.name == spec.get("empty_source")), (stage["title"], screenshot.name, "empty")
            assert hit(pipeline[stage["enable"]], image) == (screenshot.name == spec["detail_source"].replace("TouchDrive开.png", "TouchDrive关.png")), (stage["title"], screenshot.name, "enable")
            checks += 4
        image = read_image(ROOT / "captures" / spec["detail_source"]).copy()
        image[105:163, 165:430] = 0
        assert hit(pipeline[stage["ready"]], image), "正式任务仍依赖滚动标题"
    assert [s["order"] for s in stages] == sorted(s["order"] for s in stages)
    for i, stage in enumerate(stages):
        following = stages[i + 1]["entry"] if i + 1 < len(stages) else exhausted
        assert pipeline[stage["returned"]]["next"] == [following]
        assert pipeline[stage["not_found"]]["next"] == [following]
        assert not pipeline[stage["ready"]]["next"]
    manifest = {"schema_version": 1, "current_league": profile["current_league"], "scope": "gold_with_assets",
                "complete": not missing, "total_candidates": len(vehicles),
                "active_candidates": [{k: v for k, v in s.items() if k != "spec"} for s in stages],
                "missing_candidates": missing, "exhausted_node": exhausted,
                "note": "缺素材候选未执行；未包含向下兼容的白银和青铜。耗尽不代表正式名单均不可用。"}
    (ROOT / "assets/resource/pipeline/gold_rotation.json").write_text(json.dumps(pipeline, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    (ROOT / "data/generated/gold_rotation_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 黄金轮换识别素材", "", "当前任务仅执行已有素材的候选，保持正式名单相对顺序。", "",
             "已接入：" + " → ".join(s["title"] for s in stages), "", "缺少素材：", ""]
    for v in missing:
        lines += [f"- {v['order']}. {v['title']}（{v['catalog_id']}）"]
    lines += ["", "每辆至少补两张完整 1280×720 框架截图：", "",
              "- 多人游戏_选车_黄金_车型名完整可见_仅拥有开启.png",
              "- 多人游戏_车辆详情_车型名_可开始_TouchDrive开.png", "",
              "未拥有的车不需要强行解锁或进入详情；先说明哪些候选已拥有。缺油样本可复用现有模板，但新车型仍需验证。", "",
              "车型名使用正式 title，保留空格。列表卡片印刷名完整可见即可，不要求每次滑动距离一致。"]
    (ROOT / "data/generated/gold_rotation_capture_plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"PASS {checks} recognition checks; {len(stages)}/{len(vehicles)} gold candidates wired in source order; live execution not tested")


if __name__ == "__main__":
    main()
