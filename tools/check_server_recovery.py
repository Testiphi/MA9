"""离线验证服务器错误返回列表及独立恢复计数，不连接设备。"""
import json
from pathlib import Path
from multiplayer_loop_files import load_loop_nodes

from check_daily_navigation import hit, read_image

ROOT = Path(__file__).resolve().parents[1]


def main():
    nodes = load_loop_nodes(ROOT)
    manifest = json.loads((ROOT / "data/generated/multiplayer_loop_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("league_detection") == "series_player_badge":
        from check_dynamic_multiplayer_loop import main as check_dynamic
        return check_dynamic()
    rotation = json.loads((ROOT / "data" / manifest.get("rotation_file", "generated/multiplayer_rotation.json")).read_text(encoding="utf-8"))
    vehicles = [v for league in manifest.get("compatible_leagues", ["白银"])
                for group in rotation["groups"] if group["league"] == league for v in group["vehicles"]]
    assert set(manifest["missing"]).issubset({v["title"] for v in vehicles})
    vehicles = [v for v in vehicles if v["title"] not in manifest["missing"]]
    if manifest.get("selection_policy") == "reverse_fallback_pending_review":
        vehicles = []
    assert manifest["recommended_order"] == [vehicle["title"] for vehicle in vehicles]
    choices = [key for key in nodes if key.endswith("推荐选车入口")]
    assert len(choices) == 23 * 4
    for choice in choices:
        prefix = choice.removesuffix("推荐选车入口")
        entries = [prefix + f"推荐{index:02}_{vehicle['catalog_id']}_入口"
                   for index, vehicle in enumerate(vehicles, 1)]
        assert (entries[0] if entries else prefix + "倒序兜底_入口") in nodes[choice]["next"]
        actual = {key for key in nodes if key.startswith(prefix + "推荐")
                  and key.endswith("_入口")}
        assert actual == set(entries), choice
        for index, entry in enumerate(entries):
            candidate = entry.removesuffix("入口")
            locate = candidate + "定位白银"
            expected = [616, 107] if vehicles[index].get("league", "白银") == "白银" else [561, 107]
            assert nodes[locate]["target"] == expected, locate
            reverse = candidate + "反向定位起点"
            assert reverse in nodes[entry]["next"]
            assert nodes[reverse]["target"] == ([671, 107] if expected == [616, 107] else [616, 107])
            assert nodes[candidate + "反向搜索"]["begin"] == [600, 420]
            assert nodes[candidate + "反向搜索"]["end"] == [1000, 420]
            assert nodes[candidate + "反向搜索"]["max_hit"] == 24
            assert locate in nodes[candidate + "反向搜索"]["next"]
            assert nodes[candidate + "正向搜索"]["max_hit"] == 24
            click = nodes[candidate + "点击车型"]
            assert click["box_index"] == 0 and click["target"] is True
            assert click["all_of"][0]["recognition"] == "TemplateMatch"
            following = entries[index + 1] if index + 1 < len(entries) else prefix + "倒序兜底_入口"
            back = entry.removesuffix("入口") + "不可用返回"
            assert following in nodes[back]["next"], back
    images = [read_image(ROOT / "captures" / name) for name in [
        "多人游戏_选车_黄金起点_仅拥有开启.png",
        "多人游戏_选车_青铜起点_仅拥有关闭.png",
        "多人游戏_车辆详情_Ferrari J50_可开始_TouchDrive开.png",
    ]]
    handlers = [key for key in nodes if key.endswith("服务器错误关闭")]
    list_samples = [read_image(ROOT / "captures" / name) for name in [
        "多人游戏_选车_白银起点_仅拥有开启.png",
        "多人游戏_选车_黄金_滑动后_仅拥有开启.png",
    ]]
    assert len(handlers) == 23
    for handler in handlers:
        resumes = nodes[handler]["next"]
        assert len(resumes) == 3
        starts = []
        for resume in resumes:
            assert resume.endswith("确认选车列表")
            gate = nodes[resume]
            assert gate["max_hit"] == 1
            assert hit(gate, images[0]) and hit(gate, images[1])
            assert not hit(gate, images[2]), resume
            assert all(hit(gate, image) for image in list_samples), resume
            prefix = resume.removesuffix("确认选车列表")
            start = prefix + "确认准备并开始"
            assert nodes[start]["max_hit"] == 1
            assert prefix + "推荐选车入口" in nodes
            starts.append(start)
        assert len(set(starts)) == 3
    assert not any("服务器错误_详情恢复" in key for key in nodes)
    upgrades = [key for key in nodes if key.endswith("多人段位_升级继续")]
    downgrades = [key for key in nodes if key.endswith("多人段位_降级确定")]
    assert len(upgrades) == len(downgrades) == 23
    for key in upgrades:
        prefix = key.removesuffix("多人段位_升级继续")
        assert nodes[key]["target"] == [1132, 653]
        assert prefix + "多人结算_已返回系列赛" in nodes[key]["next"]
        assert key in nodes[prefix + "等待匹配与局内"]["next"]
        assert key in nodes[prefix + "多人结算_点击错失机会"]["next"]
    assert not any(key.endswith("多人结算_降级确定") for key in nodes)
    nitro = [node for key, node in nodes.items() if key.endswith("多人局内_氮气兜底")]
    assert len(nitro) == 23
    assert all(node["repeat"] == 2 and node["repeat_delay"] == 750 and node["post_delay"] == 10000
               and node["max_hit"] == 28 for node in nitro)
    for key, node in nodes.items():
        assert all(target in nodes for target in node.get("next", []) + node.get("on_error", [])), key
    print(f"PASS {len(vehicles)} vehicles in source order across 92 selection branches; "
          "69 list recovery gates; fresh counters; all graph references valid")


if __name__ == "__main__":
    main()
