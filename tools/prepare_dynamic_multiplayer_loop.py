"""生成每局从系列赛首页徽章确认黄金/白银的多人循环。"""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from PIL import Image
from check_daily_navigation import read_image, hit

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main():
    nodes, manifests = {}, {}
    for league in ["黄金", "白银"]:
        env = dict(os.environ, MA9_BUILD_LEAGUE=league, MA9_VARIANT_PREFIX=league + "_",
                   MA9_FALLBACK_FILE=f"debug/fallback_{league}.json",
                   MA9_LOOP_OUTPUT=f"debug/loop_{league}.json",
                   MA9_LOOP_MANIFEST=f"debug/loop_{league}_manifest.json")
        for tool in ["prepare_reverse_fallback.py", "prepare_multiplayer_loop.py"]:
            subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools" / tool)], env=env, check=True)
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
            for suffix in ["服务器错误关闭", "广告关闭", "连接错误重试", "车库外观领取"]:
                name = p + suffix
                nodes[name] = copy.deepcopy(nodes[seed + suffix])
                nodes[name].update(next=[dispatch], max_hit=10)
                targets.append(name)
            targets += [seed + suffix for suffix in ["多人段位_降级确定", "多人段位_升级继续",
                "多人结算_点击错失机会", "多人结算_奖励继续", "多人结算_成绩继续", "多人局内_氮气兜底"]]
            for league, guard in badges.items():
                name = p + "当前段位_" + league
                nodes[name] = {**copy.deepcopy(guard), "action": "DoNothing", "max_hit": 5,
                    "next": [f"多人循环{rounds}局_{league}_第{index+1:02}局_系列赛开始选车"]}
                targets.append(name)
            unknown = p + "系列赛段位不支持"
            nodes[unknown] = {**copy.deepcopy(race["多人结算_已返回系列赛"]), "action": "StopTask", "next": []}
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
                nodes[vp + "多人段位_降级确定"]["next"] = [vp + "多人结算_已返回系列赛"]
                nodes.pop(vp + "降段暂停_请更新段位", None)
                # 实际掉段时立即返回首页重读，避免遍历整段不可用黄金车。
                if league == "黄金":
                    gold_ids = {v["catalog_id"] for group in read("data/generated/champion_rotation.json")["groups"]
                                if group["league"] == "黄金" for v in group["vehicles"]}
                    for key, node in list(nodes.items()):
                        if key.startswith(vp) and (key.endswith("倒序兜底_黄金段位不可用") or
                            (key.endswith("不可用2") and any(cid in key for cid in gold_ids))):
                            node["next"] = [detail]
            for key in [k for k in nodes if k.startswith(p)]:
                nodes[key].setdefault("timeout", 15000)
                nodes[key].setdefault("rate_limit", 100)
                nodes[key].setdefault("pre_delay", 0)
                nodes[key].setdefault("post_delay", 0)
                nodes[key].setdefault("on_error", [stop])
        nodes[f"多人循环{rounds}局_入口"] = {"recognition": "DirectHit", "action": "DoNothing",
            "next": [f"多人循环{rounds}局_第01局_自动段位调度"]}
    assert all(target in nodes for node in nodes.values() for field in ["next", "on_error"]
               for target in node.get(field, []))
    (ROOT / "assets/resource/pipeline/multiplayer_loop.json").write_text(json.dumps(nodes, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    manifest = {"schema_version": 2, "league_detection": "series_player_badge", "supported_leagues": list(badges),
                "variants": manifests, "league_template_checks": checks, "node_count": len(nodes),
                "note": "每局重新确认；黄金不可用立即重读；服务器恢复保持当前局；设备长时运行待验证。"}
    (ROOT / "data/generated/multiplayer_loop_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    # 独立不开赛测试仍按配置中的初始段位生成；循环自身每局动态确认。
    import shutil
    initial = read("data/multiplayer_profile.json")["current_league"]
    shutil.copyfile(ROOT / f"debug/fallback_{initial}.json", ROOT / "assets/resource/pipeline/reverse_fallback.json")
    print(f"PASS dynamic leagues: {checks}; {len(nodes)} nodes; device loop not tested")


if __name__ == "__main__":
    main()
