"""生成 J50 缺油后改选 Panamera 的独立测试，不执行比赛开始。"""
import copy
import json
from pathlib import Path
from PIL import Image
from check_daily_navigation import read_image, hit
from vehicle_search import add_reverse_search, swipe_timing

ROOT = Path(__file__).resolve().parents[1]
LIST = "多人游戏_选车_黄金_Porsche Panamera Turbo S完整可见_仅拥有开启.png"
DETAIL = "多人游戏_车辆详情_Porsche Panamera Turbo S_可开始_TouchDrive开.png"
EMPTY = "多人游戏_车辆详情_Porsche Panamera Turbo S_无燃油_TouchDrive开.png"
PLATINUM = "多人游戏_选车_白金起点_仅拥有开启.png"


def clone(nodes, prefix):
    names = {name: prefix + name for name in nodes}
    result = {}
    for name, node in nodes.items():
        result[names[name]] = copy.deepcopy(node)
        result[names[name]]["next"] = [names[n] for n in node.get("next", [])]
    return result, names


def main():
    for source, filename, box in [
        (LIST, "panamera_list.png", (919, 580, 1035, 597)),
        # 左侧小卡片的车辆图与印刷车型名固定，不使用会滚动的大标题。
        (DETAIL, "panamera_detail_card.png", (79, 98, 153, 189)),
        (PLATINUM, "platinum_selected.png", (699, 92, 754, 135)),
        (PLATINUM, "platinum_start.png", (540, 326, 649, 359)),
        (PLATINUM, "platinum_league_icons.png", (532, 82, 1030, 132)),
    ]:
        with Image.open(ROOT / "captures" / source) as image:
            assert image.size == (1280, 720)
            image.convert("RGB").crop(box).save(ROOT / "assets/resource/image/navigation/vehicle" / filename)

    def read(name):
        return json.loads((ROOT / "assets/resource/pipeline" / name).read_text(encoding="utf-8"))

    # 分别复制，避免两个阶段共用 max_hit 计数，保留原 J50 测试行为。
    pipeline, first = clone(read("j50_search.json"), "两车_")
    controls = read("vehicle_controls.json")
    second_nodes, second = clone({**read("multiplayer_navigation.json"), **controls}, "两车_Panamera_")
    pipeline.update(second_nodes)
    ready, enable = second["TouchDrive_已开启"], second["TouchDrive_点击开"]
    detail_identity = {"recognition": "TemplateMatch", "template": "navigation/vehicle/panamera_detail_card.png",
                       "roi": [70, 88, 95, 112], "threshold": 0.9}
    for name in [ready, enable]:
        pipeline[name]["all_of"].insert(0, copy.deepcopy(detail_identity))
    empty = "两车_Panamera_缺油返回列表"
    exhausted = "两车_Panamera缺油_已返回_测试结束"
    # 复用 J50 的 0/ 前缀、跳过文字和返回箭头，车型身份保持独立。
    pipeline[empty] = copy.deepcopy(pipeline[first["J50测试_缺油返回列表"]])
    pipeline[empty]["all_of"][0] = copy.deepcopy(detail_identity)
    pipeline[empty]["next"] = [exhausted]
    pipeline[exhausted] = copy.deepcopy(pipeline[first["J50测试_缺油已返回"]])
    pipeline[exhausted]["next"] = []
    pipeline[second["多人准备_仅拥有已开启"]]["next"] = [second["黄金定位_点击黄金"]]
    found, swipe = "两车_Panamera_列表点击", "两车_Panamera_滑动搜索"
    pipeline[second["黄金定位_已选中"]]["next"] = [found, swipe]
    pipeline[first["J50测试_缺油已返回"]]["next"] = [second["黄金定位_入口"]]
    list_identity = {"recognition": "TemplateMatch", "template": "navigation/vehicle/panamera_list.png",
                     "roi": [0, 190, 1280, 480], "threshold": 0.9}
    guard = copy.deepcopy(controls["黄金定位_已选中"])
    guard.pop("action")
    guard.pop("next")
    pipeline[found] = {"recognition": "And", "all_of": [list_identity, guard], "box_index": 0,
                       "action": "Click", "target": True, "max_hit": 1, "post_delay": 500,
                       "timeout": 60000, "next": [empty, ready, enable]}
    pipeline[swipe] = {**guard, "action": "Swipe", "begin": [1000, 420], "end": [600, 420],
                       **swipe_timing(), "max_hit": 12, "timeout": 5000,
                       "next": [found, swipe]}
    pipeline["两车_入口"] = {"recognition": "DirectHit", "action": "DoNothing", "timeout": 60000,
                            # 不用 DirectHit 兜底跳入 J50，否则 Panamera 首次漏识别后不再重试。
                            "next": [empty, ready, enable, *pipeline[first["J50测试_入口"]]["next"]]}
    pipeline["两车_Panamera_原地识别入口"] = {
        "recognition": "DirectHit", "action": "DoNothing", "timeout": 10000,
        "next": [found],
    }
    # 反向搜索不依赖黄金标签高亮；只要求列表页和仅拥有开启。
    list_guard = {"recognition": "And", "all_of": copy.deepcopy([
        controls["黄金定位_已选中"]["all_of"][0],
        controls["黄金定位_已选中"]["all_of"][2],
    ])}
    anchor_guard = {"recognition": "And", "all_of": [copy.deepcopy(list_guard),
        {"recognition": "TemplateMatch", "template": "navigation/vehicle/platinum_selected.png",
         "roi": [692, 85, 70, 54], "threshold": 0.9},
        {"recognition": "TemplateMatch", "template": "navigation/vehicle/platinum_start.png",
         "roi": [485, 310, 195, 65], "threshold": 0.9},
    ]}
    reverse_entry, anchor_confirmed, reverse_found, reverse_swipe, reverse_stopped = add_reverse_search(
        pipeline, found, swipe, list_guard, anchor_guard, [726, 107])
    pipeline["两车_Panamera_反向搜索入口"] = pipeline.pop(reverse_entry)
    # 返回列表可能仍高亮白金，完成判断的导航条模板要接受该外观。
    def accept_platinum(node):
        templates = node.get("template")
        if (isinstance(templates, list) and "navigation/multiplayer/league_icons_gold.png" in templates
                and "navigation/vehicle/platinum_league_icons.png" not in templates):
            templates.append("navigation/vehicle/platinum_league_icons.png")
        for child in node.get("all_of", []) + node.get("any_of", []):
            accept_platinum(child)
    for node in pipeline.values():
        accept_platinum(node)
    assert all(n in pipeline for node in pipeline.values() for n in node.get("next", []))
    assert pipeline[first["J50测试_缺油已返回"]]["next"] == [second["黄金定位_入口"]]
    assert not pipeline[ready]["next"]
    assert pipeline[found]["next"][0] == empty
    assert pipeline[empty]["next"] == [exhausted] and not pipeline[exhausted]["next"]
    assert all(pipeline[n]["recognition"] != "DirectHit" for n in pipeline["两车_入口"]["next"])
    report = []
    for source in sorted((ROOT / "captures").glob("*.png")):
        image = read_image(source)
        found_hit = hit(pipeline[found], image)
        ready_hit = hit(pipeline[ready], image)
        enable_hit = hit(pipeline[enable], image)
        empty_hit = hit(pipeline[empty], image)
        exhausted_hit = hit(pipeline[exhausted], image)
        anchor_hit = hit(pipeline[anchor_confirmed], image)
        reverse_found_hit = hit(pipeline[reverse_found], image)
        assert found_hit == (source.name == LIST), (source.name, "list", found_hit)
        assert ready_hit == (source.name == DETAIL), (source.name, "ready", ready_hit)
        assert not enable_hit, (source.name, "unexpected TD off")
        assert empty_hit == (source.name == EMPTY), (source.name, "empty", empty_hit)
        assert exhausted_hit == ("_选车_" in source.name), (source.name, "return", exhausted_hit)
        assert anchor_hit == (source.name == PLATINUM), (source.name, "platinum start", anchor_hit)
        assert reverse_found_hit == (source.name == LIST), (source.name, "reverse list", reverse_found_hit)
        report.append({"screenshot": source.name, "panamera_list": found_hit,
                       "panamera_ready": ready_hit, "panamera_enable": enable_hit,
                       "panamera_empty": empty_hit, "returned_to_list": exhausted_hit,
                       "platinum_start": anchor_hit, "reverse_list": reverse_found_hit})
    # 把滚动标题区域遮掉，验证两种详情分支都完全不依赖标题。
    for source, expected in [(DETAIL, ready), (EMPTY, empty)]:
        image = read_image(ROOT / "captures" / source).copy()
        image[105:163, 165:430] = 0
        assert hit(pipeline[expected], image), (source, "scrolling title dependency")
    # 同一卡片移动到左、中、右区域时都必须识别，不局限于原始截图位置。
    for source, click in [(LIST, found)]:
        original = read_image(ROOT / "captures" / source)
        for dx in [-800, -500, -100, 150]:
            image = original.copy()
            image[190:670] = 0
            if dx < 0:
                image[190:670, :1280 + dx] = original[190:670, -dx:]
            else:
                image[190:670, dx:] = original[190:670, :1280 - dx]
            assert hit(pipeline[click], image), (source, dx, "horizontal search coverage")
            assert hit(pipeline[reverse_found], image)
    # 反查经过黄金车辆时，顶部仍可能高亮白金，车型识别必须继续有效。
    image = read_image(ROOT / "captures" / LIST).copy()
    platinum = read_image(ROOT / "captures" / PLATINUM)
    image[82:134, 528:1035] = platinum[82:134, 528:1035]
    assert hit(pipeline[reverse_found], image)
    assert hit(pipeline[reverse_swipe], image)
    assert not hit(pipeline[anchor_confirmed], image), "highlight alone is not a start marker"
    assert pipeline[swipe]["max_hit"] == 12 and pipeline[reverse_swipe]["max_hit"] == 24
    assert pipeline[swipe]["next"][-1] == pipeline["两车_Panamera_反向搜索入口"]["next"][0]
    assert not pipeline[reverse_stopped]["next"]
    (ROOT / "assets/resource/pipeline/two_car_rotation.json").write_text(
        json.dumps(pipeline, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    (ROOT / "captures/two_car_rotation_check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS {len(report)} screenshot checks and graph references; device execution not tested")


if __name__ == "__main__":
    main()
