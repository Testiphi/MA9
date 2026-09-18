"""生成每局从系列赛首页徽章确认白金/黄金/白银的多人循环。"""
import copy
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from PIL import Image
from check_daily_navigation import read_image, hit

ROOT = Path(__file__).resolve().parents[1]


def write_pipeline(path: Path, nodes: dict) -> None:
    """Write large generated pipelines with one compact node per line."""
    items = list(nodes.items())
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("{\n")
        for index, (name, node) in enumerate(items):
            comma = "," if index + 1 < len(items) else ""
            encoded_name = json.dumps(name, ensure_ascii=False)
            encoded_node = json.dumps(node, ensure_ascii=False, separators=(",", ":"))
            stream.write(f"{encoded_name}:{encoded_node}{comma}\n")
        stream.write("}\n")


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse-list-checks", action="store_true", help="仅在车型模板未变更时复用其交叉检查；新结算页仍检查")
    args = parser.parse_args()
    nodes, manifests = {}, {}
    for league in ["白金", "黄金", "白银"]:
        env = dict(os.environ, MA9_BUILD_LEAGUE=league, MA9_VARIANT_PREFIX=league + "_",
                   MA9_FALLBACK_FILE=f"debug/fallback_{league}.json",
                   MA9_LOOP_OUTPUT=f"debug/loop_{league}.json",
                   MA9_LOOP_MANIFEST=f"debug/loop_{league}_manifest.json")
        for tool in ["prepare_reverse_fallback.py", "prepare_multiplayer_loop.py"]:
            command = [sys.executable, "-X", "utf8", str(ROOT / "tools" / tool)]
            if tool == "prepare_multiplayer_loop.py" and args.reuse_list_checks:
                command.append("--reuse-list-checks")
            subprocess.run(command, env=env, check=True)
        nodes.update(read(env["MA9_LOOP_OUTPUT"]))
        manifests[league] = read(env["MA9_LOOP_MANIFEST"])
    mp = read("assets/resource/pipeline/multiplayer_navigation.json")
    race = read("assets/resource/pipeline/race_screens.json")
    badges = {}
    folder = ROOT / "assets/resource/image/navigation/loop"
    for league in manifests:
        source = ROOT / "captures" / f"多人游戏_经典系列赛_首页_{league}.png"
        Image.open(source).convert("RGB").crop((78, 291, 116, 343)).save(folder / f"player_{league}.png")
        badges[league] = {"recognition": "And", "all_of": [copy.deepcopy(race["多人结算_已返回系列赛"]),
            {"recognition": "TemplateMatch", "template": f"navigation/loop/player_{league}.png",
             "roi": [70, 283, 55, 70], "threshold": 0.9}]}
    checks = []
    for source in sorted((ROOT / "captures").glob("*.png")):
        image = read_image(source)
        matched = [league for league, guard in badges.items() if hit(guard, image)]
        assert len(matched) <= 1, source.name
        if "_选车_" in source.name or "_车辆详情_" in source.name or "_段位_" in source.name:
            assert not matched, (source.name, matched)
        for league in badges:
            if source.name == f"多人游戏_经典系列赛_首页_{league}.png":
                assert matched == [league], (source.name, matched)
        if matched:
            checks.append({"source": source.name, "league": matched[0]})
    for rounds in [3, 20]:
        for index in range(rounds):
            p = f"多人循环{rounds}局_第{index+1:02}局_"
            dispatch, detail, back = p + "自动段位调度", p + "返回列表确认段位", p + "返回系列赛确认段位"
            stop = p + "停止_无法确认当前段位"
            seed = f"多人循环{rounds}局_黄金_第{index+1:02}局_"
            nodes[stop] = {"recognition": "DirectHit", "action": "StopTask", "next": []}
            targets = []
            blueprint = p + "图纸页面关闭并重新确认"
            prototype = next(v for k, v in nodes.items() if k.startswith(seed) and k.endswith("图纸误入关闭"))
            nodes[blueprint] = copy.deepcopy(prototype)
            nodes[blueprint].update(next=[dispatch], max_hit=3)
            targets.append(blueprint)
            pass_close = p + "多人结算_通行证升级关闭"
            nodes[pass_close] = copy.deepcopy(nodes[seed + "多人结算_通行证升级关闭"])
            nodes[pass_close].update(next=[dispatch], max_hit=3)
            targets.append(pass_close)
            for suffix in ["服务器错误关闭", "广告关闭", "连接错误重试", "车库外观领取"]:
                name = p + suffix
                nodes[name] = copy.deepcopy(nodes[seed + suffix])
                nodes[name].update(next=[dispatch], max_hit=10)
                targets.append(name)
            targets += [seed + suffix for suffix in ["多人结算_名人堂奖励继续", "多人段位_降级确定", "多人段位_升级继续",
                "多人结算_点击错失机会", "多人结算_奖励继续", "多人结算_成绩继续", "多人局内_氮气兜底"]]
            for league, guard in badges.items():
                name = p + "当前段位_" + league
                nodes[name] = {**copy.deepcopy(guard), "action": "DoNothing", "max_hit": 5,
                    "next": [f"多人循环{rounds}局_{league}_第{index+1:02}局_系列赛开始选车"]}
                targets.append(name)
            unknown = p + "系列赛段位待确认"
            unknown_retries = [p + f"系列赛段位等待徽章_{attempt}" for attempt in (2, 3)]
            unsupported = p + "系列赛段位不支持"
            # 系列赛首页主体比玩家段位徽章先出现。通用首页命中后先等徽章，
            # 连续几次仍无法确定白金/黄金/白银才判为不支持，避免进入页立刻结束。
            for current, following in zip([unknown, *unknown_retries], [*unknown_retries, unsupported]):
                nodes[current] = {**copy.deepcopy(race["多人结算_已返回系列赛"]),
                    "action": "DoNothing", "max_hit": 1, "post_delay": 3000,
                    "next": [p + "当前段位_白金", p + "当前段位_黄金", p + "当前段位_白银", following]}
            nodes[unsupported] = {**copy.deepcopy(race["多人结算_已返回系列赛"]),
                "action": "StopTask", "next": []}
            nodes[detail] = copy.deepcopy(nodes[seed + "详情返回重排"])
            nodes[detail].update(next=[dispatch], max_hit=10)
            nodes[back] = {"recognition": "Or", "any_of": [copy.deepcopy(mp["多人准备_仅拥有已开启"]),
                copy.deepcopy(mp["多人准备_开启仅拥有"])], "action": "Click", "target": [40, 30],
                "max_hit": 10, "post_delay": 600, "next": [dispatch]}
            targets += [unknown, detail, back]
            # 从主界面进入系列赛后先读玩家徽章，不直接开始选车。
            for suffix in mp["多人准备_入口"]["next"]:
                if "仅拥有" in suffix or "介绍页开始" in suffix:
                    continue
                name = p + suffix
                nodes[name] = copy.deepcopy(mp[suffix])
                nodes[name].update(next=[dispatch], max_hit=10)
                targets.append(name)
            nodes[dispatch] = {"recognition": "DirectHit", "action": "DoNothing", "max_hit": 20,
                "timeout": 180000, "next": targets, "on_error": [stop]}
            for league in manifests:
                vp = f"多人循环{rounds}局_{league}_第{index+1:02}局_"
                nodes[vp + "本局完成"]["next"] = ([f"多人循环{rounds}局_第{index+2:02}局_自动段位调度"]
                                                     if index+1 < rounds else [])
                nodes[vp + "多人段位_降级确定"]["next"] = [vp + "多人结算_名人堂奖励继续",
                    vp + "多人结算_已返回系列赛",
                    vp + "结算等待新页面", vp + "停止_未知状态或次数耗尽"]
                nodes.pop(vp + "降段暂停_请更新段位", None)
                # 实际掉段时立即返回首页重读，避免遍历整段不可用的原段位车。
                if league in {"白金", "黄金"}:
                    current_ids = {v["catalog_id"] for v in manifests[league].get("recommended_vehicles", [])
                                   if v["league"] == league}
                    unavailable_index = {"黄金": 2, "白金": 3}[league]
                    for key, node in list(nodes.items()):
                        if key.startswith(vp) and (key.endswith(f"倒序兜底_{league}段位不可用") or
                            (key.endswith(f"不可用{unavailable_index}") and
                             any(cid in key for cid in current_ids))):
                            node["next"] = [detail]
            for key in [k for k in nodes if k.startswith(p)]:
                nodes[key].setdefault("timeout", 15000)
                nodes[key].setdefault("rate_limit", 100)
                nodes[key].setdefault("pre_delay", 0)
                nodes[key].setdefault("post_delay", 0)
                nodes[key].setdefault("on_error", [stop])
        nodes[f"多人循环{rounds}局_入口"] = {"recognition": "DirectHit", "action": "DoNothing",
            "next": [f"多人循环{rounds}局_第01局_自动段位调度"]}
    # 关闭广告具有最高优先级，包括组合生成时改写的升降级和跨段位分支。
    for key, node in nodes.items():
        match = re.match(r"多人循环(?:3|20)局_(?:(?:白金|黄金|白银)_)?第\d{2}局_", key)
        if not match or not node.get("next") or key.endswith(("广告关闭", "通行证升级关闭", "本局完成", "多人结算_已返回系列赛")):
            continue
        ad = match.group() + "广告关闭"
        node["next"] = [ad, *[t for t in node["next"] if t != ad]]
        pass_close = match.group() + "多人结算_通行证升级关闭"
        if pass_close in node["next"]:
            node["next"] = [pass_close, *[t for t in node["next"] if t != pass_close]]
    assert all(target in nodes for node in nodes.values() for field in ["next", "on_error"]
               for target in node.get(field, []))
    pipeline_dir = ROOT / "assets/resource/pipeline"
    shards = {"multiplayer_loop.json": {}}
    for name, node in nodes.items():
        match = re.match(r"多人循环(3|20)局_(白金|黄金|白银)_", name)
        filename = (f"multiplayer_loop_{match.group(1)}_{match.group(2)}.json"
                    if match else "multiplayer_loop.json")
        shards.setdefault(filename, {})[name] = node
    for filename, part in shards.items():
        write_pipeline(pipeline_dir / filename, part)
    for stale in pipeline_dir.glob("multiplayer_loop*.json"):
        if stale.name not in shards:
            stale.unlink()
    manifest = {"schema_version": 2, "league_detection": "series_player_badge", "supported_leagues": list(badges),
                "variants": manifests, "league_template_checks": checks, "node_count": len(nodes),
                "note": "每局重新确认；原段位不可用立即重读；服务器恢复保持当前局；设备长时运行待验证。"}
    (ROOT / "data/generated/multiplayer_loop_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    # 独立不开赛测试仍按配置中的初始段位生成；循环自身每局动态确认。
    import shutil
    initial = read("data/multiplayer_profile.json")["current_league"]
    shutil.copyfile(ROOT / f"debug/fallback_{initial}.json", ROOT / "assets/resource/pipeline/reverse_fallback.json")
    from prepare_vehicle_recognition import main as prepare_vehicle_recognition
    prepare_vehicle_recognition()
    print(f"PASS dynamic leagues: {checks}; {len(nodes)} nodes; device loop not tested")


if __name__ == "__main__":
    main()
