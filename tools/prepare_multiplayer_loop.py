"""生成无需 Agent 的 3/20 局白银试跑，向下兼容青铜；每局独立计数。"""
import copy
import argparse
import json
from pathlib import Path
from PIL import Image
from check_daily_navigation import read_image, hit as template_hit
from prepare_race_screens import hit
from vehicle_search import swipe_timing

ROOT = Path(__file__).resolve().parents[1]
CROPS = {
    "Cadillac Cien Concept": [660, 340, 755, 360],
    "Ferrari Daytona SP3": [788, 339, 897, 360],
    "Mercedes-Benz Mercedes-AMG GT Black Series": [1090, 347, 1210, 360],
    "Maserati MC20 GT2": [327, 577, 433, 597],
    "Renault R.S. 01": [1090, 576, 1195, 598],
    "Bentley Mulliner Bacalar": [635, 576, 724, 598],
    "Saleen S1": [190, 557, 244, 598],
    "Nissan 370Z Nismo Neon Edition": [192, 346, 305, 360],
    "Lamborghini Miura Concept": [326, 339, 435, 360],
    "Lamborghini Huracan Super Trofeo EVO": [628, 581, 741, 598],
    "Lamborghini Huracan STO": [170, 580, 260, 596],
    "TVR Sagaris": [630, 339, 704, 360],
    "Kimera EVO37": [760, 338, 820, 360],
    "Hyundai IONIQ 5 N": [732, 339, 807, 360],
    "Praga R1": [730, 324, 770, 360],
    "Nissan Z GT4": [772, 340, 823, 360],
    "Porsche Panamera Turbo S": [919, 580, 1035, 597],
    "Ferrari 599XX EVO": [788, 580, 880, 598],
    "DS Automobiles DS E-Tense Performance": [605, 582, 710, 596],
    "Ferrari J50": [985, 327, 1040, 359],
}


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse-list-checks", action="store_true", help="复用未变更的列表模板交叉检查，仅校验新状态")
    args = parser.parse_args()
    profile = read("data/multiplayer_profile.json")
    import os
    profile["current_league"] = os.environ.get("MA9_BUILD_LEAGUE", profile["current_league"])
    assert profile["current_league"] in ["白银", "黄金"]
    profile["compatible_leagues"] = (["黄金"] if profile["current_league"] == "黄金" else []) + ["白银", "青铜"]
    rotation = read("data/" + profile["rotation_file"])
    vehicles = [dict(v, league=league) for league in profile["compatible_leagues"]
                for group in rotation["groups"] if group["league"] == league for v in group["vehicles"]]
    pending_review = profile["selection_policy"] == "reverse_fallback_pending_review"
    if pending_review:
        vehicles = []
    image_folder = ROOT / "assets/resource/image/navigation/loop"
    image_folder.mkdir(parents=True, exist_ok=True)
    server_source = ROOT / "captures/多人游戏_服务器错误.png"
    with Image.open(server_source) as image:
        assert image.size == (1280, 720)
        for key, crop in {"server_title": (192, 227, 351, 265), "server_close": (1074, 224, 1113, 265)}.items():
            image.convert("RGB").crop(crop).save(image_folder / f"{key}.png")
    server_guard = {"recognition": "And", "box_index": 0, "all_of": [
        {"recognition": "TemplateMatch", "template": "navigation/loop/server_close.png", "roi": [1060, 210, 65, 70], "threshold": 0.9},
        {"recognition": "TemplateMatch", "template": "navigation/loop/server_title.png", "roi": [180, 215, 185, 65], "threshold": 0.9}]}
    with Image.open(ROOT / "captures/Lamborghini Huracan Sterrato_图纸获取.png") as image:
        image.convert("RGB").crop((66, 354, 365, 459)).save(image_folder / "blueprint_heading.png")
        image.convert("RGB").crop((1159, 66, 1195, 102)).save(image_folder / "blueprint_close.png")
    blueprint_guard = {"recognition": "And", "all_of": [
        {"recognition": "TemplateMatch", "template": "navigation/loop/blueprint_heading.png", "roi": [55, 340, 325, 135], "threshold": 0.9},
        {"recognition": "TemplateMatch", "template": "navigation/loop/blueprint_close.png", "roi": [1145, 50, 65, 65], "threshold": 0.9}]}
    available, missing = [], []
    templates_unchanged = True
    for vehicle in vehicles:
        title, cid = vehicle["title"], vehicle["catalog_id"]
        sources = sorted((ROOT / "captures").glob(f"多人游戏_选车_{vehicle['league']}_{title}完整可见_仅拥有*.png"))
        source = sources[0] if sources else None
        if title not in CROPS or source is None:
            missing.append(title)
            continue
        destination = image_folder / f"{cid}_list.png"
        old_template = destination.read_bytes() if destination.exists() else None
        with Image.open(source) as image:
            assert image.size == (1280, 720)
            image.convert("RGB").crop(CROPS[title]).save(image_folder / f"{cid}_list.png")
        templates_unchanged &= old_template == destination.read_bytes()
        identity = {"recognition": "TemplateMatch", "template": f"navigation/loop/{cid}_list.png",
                    "roi": [0, 190, 1280, 480], "threshold": 0.9}
        assert template_hit(identity, read_image(source)), title
        available.append((vehicle, identity))
    assert available or pending_review
    mp = read("assets/resource/pipeline/multiplayer_navigation.json")
    controls = read("assets/resource/pipeline/vehicle_controls.json")
    fallback = read(os.environ.get("MA9_FALLBACK_FILE", "assets/resource/pipeline/reverse_fallback.json"))
    race = read("assets/resource/pipeline/race_screens.json")
    language = read("assets/resource/pipeline/language_switch.json")
    generic_ready = copy.deepcopy(controls["TouchDrive_已开启"])
    generic_off = copy.deepcopy(controls["TouchDrive_点击开"])
    list_guard = copy.deepcopy(mp["多人准备_仅拥有已开启"])
    reverse_anchors = {}
    for league, anchor_league, target in [("黄金", "白金", [726, 107]), ("白银", "黄金", [671, 107]), ("青铜", "白银", [616, 107])]:
        source = ROOT / "captures" / f"多人游戏_选车_{anchor_league}起点_仅拥有开启.png"
        x = target[0]
        filename = f"reverse_anchor_{anchor_league}.png"
        with Image.open(source) as image:
            image.convert("RGB").crop((x - 27, 91, x + 29, 136)).save(image_folder / filename)
        guard = {"recognition": "And", "all_of": [copy.deepcopy(list_guard),
                 {"recognition": "TemplateMatch", "template": f"navigation/loop/{filename}",
                  "roi": [x - 34, 85, 70, 54], "threshold": 0.9}]}
        assert template_hit(guard, read_image(source)), (league, "reverse anchor")
        reverse_anchors[league] = (target, guard)
    arrows = copy.deepcopy(fallback["倒序兜底_向左切车"])
    for key in ["action", "next", "target", "max_hit", "timeout", "post_delay", "pre_delay", "rate_limit"]:
        arrows.pop(key, None)
    all_nodes = {}
    trial_manifest = []
    for rounds in [3, 20]:
        trial = f"多人循环{rounds}局_" + os.environ.get("MA9_VARIANT_PREFIX", "")
        def prefix(index):
            return trial + f"第{index+1:02}局_"
        trial_nodes = {}
        for index in range(rounds):
            p = prefix(index)
            def n(suffix):
                return p + suffix
            base = {**mp, **fallback, **race}
            renamed = {key: n(key) for key in base}
            nodes = {}
            for key, original in base.items():
                node = copy.deepcopy(original)
                node["next"] = [renamed.get(t, t) for t in node.get("next", [])]
                nodes[renamed[key]] = node
            start = n("确认准备并开始")
            wait = n("等待匹配与局内")
            dispatch = n("页面调度")
            choose = n("推荐选车入口")
            intro = n("系列赛开始选车")
            done = n("本局完成")
            stop = n("停止_未知状态或次数耗尽")
            nodes[stop] = {"recognition": "DirectHit", "action": "StopTask", "next": []}
            # 开始严格受通用可开始、TouchDrive 开状态保护。
            nodes[start] = {**copy.deepcopy(generic_ready), "action": "Click", "target": [1110, 650],
                            "max_hit": 1, "pre_delay": 0, "post_delay": 500,
                            "timeout": 180000, "next": [wait]}
            nodes[n("原地开启TouchDrive")] = {**copy.deepcopy(generic_off), "max_hit": 3, "next": [start]}
            settlement_targets = [n("多人段位_降级确定"), n("多人段位_升级继续"), n("多人结算_点击错失机会"),
                                  n("多人结算_奖励继续"), n("多人结算_成绩继续")]
            nodes[wait] = {"recognition": "DirectHit", "action": "DoNothing", "timeout": 180000,
                           "next": [*settlement_targets, n("多人局内_氮气兜底")]}
            nodes[n("多人局内_氮气兜底")].update(max_hit=28,
                next=[*settlement_targets, n("多人局内_氮气兜底")])
            # 未经历结算不能把刚进入的系列赛误记为完成。
            nodes[n("多人结算_已返回系列赛")]["next"] = [done]
            nodes[n("多人段位_降级确定")]["next"] = [n("降段暂停_请更新段位")]
            nodes[n("降段暂停_请更新段位")] = {"recognition": "DirectHit", "action": "StopTask", "next": []}
            nodes[done] = {"recognition": "DirectHit", "action": "DoNothing", "max_hit": 1,
                           "next": [prefix(index+1) + "页面调度"] if index+1 < rounds else []}
            nodes[intro] = {**copy.deepcopy(race["多人结算_已返回系列赛"]),
                            "action": "Click", "target": [1110, 650], "max_hit": 2,
                            "post_delay": 500, "timeout": 60000,
                            "next": [n("多人准备_仅拥有已开启"), n("多人准备_开启仅拥有")]}
            nodes[n("多人准备_介绍页开始")]["next"] = [n("多人准备_仅拥有已开启"), n("多人准备_开启仅拥有")]
            nodes[n("多人准备_仅拥有已开启")]["next"] = [choose]
            # 倒序兜底找到车后直接开始，终止分支仍停止整个试跑。
            for key, node in list(nodes.items()):
                if key.startswith(n("倒序兜底_")) and not node.get("next"):
                    if key.endswith("_ready") or key == n("倒序兜底_可用车已准备"):
                        node["next"] = [start]
                    elif "停止" in key:
                        node["action"] = "StopTask"
            candidates = []
            skip_conditions = [copy.deepcopy(fallback["倒序兜底_" + suffix]) for suffix in
                               ["缺钥匙", "缺图纸", "黄金段位不可用", "白金段位不可用", "缺油"]]
            for j, (vehicle, identity) in enumerate(available):
                c = n(f"推荐{j+1:02}_{vehicle['catalog_id']}_")
                entry, locate, found, swipe, back = [c+s for s in ["入口", "定位白银", "点击车型", "正向搜索", "不可用返回"]]
                reverse_anchor, reverse_confirmed, reverse_swipe = [c+s for s in ["反向定位起点", "反向起点已确认", "反向搜索"]]
                following = (n(f"推荐{j+2:02}_{available[j+1][0]['catalog_id']}_入口")
                             if j+1 < len(available) else n("倒序兜底_入口"))
                skips = []
                for k, condition in enumerate(skip_conditions):
                    skip = c + f"不可用{k}"
                    condition = copy.deepcopy(condition)
                    condition.update(action="DoNothing", next=[back], pre_delay=0, post_delay=0)
                    nodes[skip] = condition
                    skips.append(skip)
                nodes[back] = {"recognition": "TemplateMatch", "template": "navigation/vehicle/detail_back.png",
                               "roi": [15, 3, 48, 58], "threshold": 0.9, "action": "Click",
                               "target": [40, 30], "max_hit": 1, "post_delay": 450, "next": [following]}
                nodes[entry] = {"recognition": "DirectHit", "action": "DoNothing", "next": [reverse_anchor]}
                anchor_target, anchor_guard = reverse_anchors[vehicle["league"]]
                nodes[reverse_anchor] = {**copy.deepcopy(list_guard), "action": "Click", "target": anchor_target,
                                         "max_hit": 1, "post_delay": 800, "timeout": 60000, "next": [reverse_confirmed]}
                nodes[reverse_confirmed] = {**copy.deepcopy(anchor_guard), "action": "DoNothing", "max_hit": 1,
                                            "timeout": 60000, "next": [found, reverse_swipe, locate]}
                nodes[reverse_swipe] = {**copy.deepcopy(list_guard), "action": "Swipe", "begin": [600, 420], "end": [1000, 420],
                                       **swipe_timing(), "max_hit": 24, "timeout": 15000, "next": [found, reverse_swipe, locate]}
                nodes[locate] = {**copy.deepcopy(list_guard), "action": "Click",
                                 "target": {"黄金": [671, 107], "白银": [616, 107], "青铜": [561, 107]}[vehicle["league"]],
                                 "max_hit": 1, "post_delay": 800, "timeout": 60000, "next": [found, swipe, following]}
                nodes[found] = {"recognition": "And", "all_of": [copy.deepcopy(identity), copy.deepcopy(list_guard)],
                                # 图纸整张都可能跳转。以车名定位，将点击移到左侧车身。
                                "box_index": 0, "action": "Click", "target": True,
                                "target_offset": [-220, -70, 0, 0], "max_hit": 1,
                                "post_delay": 500, "timeout": 15000,
                                "next": [*skips, start, n("原地开启TouchDrive")]}
                nodes[found]["all_of"][0]["roi"] = [300, 190, 980, 480]
                close_blueprint, retry_car = c + "图纸误入关闭", c + "图纸返回后重选"
                nodes[found]["next"].insert(0, close_blueprint)
                nodes[retry_car] = {**copy.deepcopy(nodes[found]), "max_hit": 2}
                nodes[close_blueprint] = {**copy.deepcopy(blueprint_guard), "action": "Click",
                    "target": [1176, 84], "max_hit": 2, "post_delay": 500, "next": [retry_car]}
                nodes[swipe] = {**copy.deepcopy(list_guard), "action": "Swipe", "begin": [1000, 420], "end": [600, 420],
                                **swipe_timing(), "max_hit": 24, "timeout": 15000, "next": [found, swipe, following]}
                candidates.append(entry)
            nodes[choose] = {"recognition": "DirectHit", "action": "DoNothing",
                             "next": [candidates[0] if candidates else n("倒序兜底_入口")]}
            # 从车辆详情启动时返回列表重排，避免跳过推荐顺序。
            nodes[n("详情返回重排")] = {**copy.deepcopy(arrows), "action": "Click", "target": [40, 30],
                                        "max_hit": 2, "post_delay": 450,
                                        "next": [n("多人准备_仅拥有已开启"), n("多人准备_开启仅拥有")]}
            dispatch_targets = [*settlement_targets, n("多人局内_氮气兜底"), intro,
                                n("详情返回重排"), *[n(t) for t in mp["多人准备_入口"]["next"]]]
            # 独立异常分支重新定位页面；不会统一回主页打断局内。
            close, retry, garage = [n(t) for t in ["广告关闭", "连接错误重试", "车库外观领取"]]
            server_close = n("服务器错误关闭")
            # 每次服务器错误恢复用独立选车子图，重新从推荐顺序查找。
            # 不能重用原选车节点：它们的定位、点击、滑动次数可能已经耗尽。
            resume_nodes = []
            selection_keys = {key for key in nodes if key.startswith(n("推荐")) or key.startswith(n("倒序兜底_"))}
            selection_keys.update([start, n("原地开启TouchDrive")])
            # 白银兜底的通用准备已经足够；不用带入旧黄金身份分发。
            nodes[n("倒序兜底_有油且TouchDrive已开")]["next"] = [n("倒序兜底_可用车已准备")]
            selection_keys = {key for key in selection_keys if not key.startswith(n("倒序兜底_car_"))}
            for attempt in range(1, 4):
                rp = n(f"服务器恢复{attempt}_")
                mapping = {key: rp + key[len(p):] for key in selection_keys}
                for key in selection_keys:
                    node = copy.deepcopy(nodes[key])
                    node["next"] = [mapping.get(t, t) for t in node.get("next", [])]
                    nodes[mapping[key]] = node
                resume = rp + "确认选车列表"
                off, on = rp + "开启仅拥有", rp + "仅拥有已开启"
                owned_off = copy.deepcopy(mp["多人准备_开启仅拥有"])
                nodes[off] = {**owned_off, "next": [on], "max_hit": 1}
                nodes[on] = {**copy.deepcopy(list_guard), "action": "DoNothing", "max_hit": 1,
                             "next": [mapping[choose]]}
                nodes[resume] = {"recognition": "Or", "any_of": [copy.deepcopy(list_guard), owned_off],
                                 "action": "DoNothing", "max_hit": 1, "timeout": 15000,
                                 "next": [off, on]}
                resume_nodes.append(resume)
            nodes[server_close] = {**copy.deepcopy(server_guard), "action": "Click", "target": True,
                                   "max_hit": 3, "pre_delay": 0, "post_delay": 2000, "timeout": 15000,
                                   "next": resume_nodes}
            for target, source in [(close, "通用弹窗_关闭广告"), (retry, "通用弹窗_连接错误重试"),
                                   (garage, "通用弹窗_车库外观领取")]:
                nodes[target] = copy.deepcopy(language[source])
                nodes[target].update(next=[dispatch], max_hit=10)
            nodes[dispatch] = {"recognition": "DirectHit", "action": "DoNothing", "max_hit": 15,
                               "timeout": 180000, "next": [server_close, close, retry, garage, *dispatch_targets]}
            for key, node in nodes.items():
                node.setdefault("rate_limit", 100)
                node.setdefault("pre_delay", 0)
                node.setdefault("post_delay", 0)
                node.setdefault("timeout", 15000)
                node.setdefault("on_error", [stop])
                if node.get("next") and key not in [dispatch, close, retry, garage, server_close] and not key.endswith("图纸误入关闭"):
                    node["next"][0:0] = [server_close, close, retry, garage]
                    # 通用广告也找 ×；图纸页面先走保留当前候选的专用恢复。
                    specialized = [t for t in node["next"] if t.endswith("图纸误入关闭")]
                    for t in specialized:
                        node["next"].remove(t)
                    node["next"][0:0] = specialized
            # 独立轮次名称隔离 max_hit，无需 Agent 或清理全局计数。
            trial_nodes.update(nodes)
        entry = trial + "入口"
        trial_nodes[entry] = {"recognition": "DirectHit", "action": "DoNothing", "next": [prefix(0)+"页面调度"]}
        assert all(t in trial_nodes for node in trial_nodes.values() for t in node.get("next", []) + node.get("on_error", [])), rounds
        all_nodes.update(trial_nodes)
        trial_manifest.append({"rounds": rounds, "entry": entry, "nodes": len(trial_nodes)})
    # 选择模板的交叉检查：不同推荐车型不能在同一位置误识别。
    cached_scores = None
    # 黄金分支已完整检查同一批截图及包含的白银/青铜模板；复用该次检查。
    cache_file = ROOT / "debug/loop_黄金_manifest.json"
    if os.environ.get("MA9_VARIANT_PREFIX") and profile["current_league"] == "白银" and templates_unchanged and cache_file.exists():
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
        by_title = {row["title"]: row for row in cache["list_template_checks"]}
        if all(v[0]["title"] in by_title for v in available) and all(
                p.stat().st_mtime <= cache_file.stat().st_mtime for p in (ROOT / "captures").glob("*.png")):
            cached_scores = [by_title[v[0]["title"]] for v in available]
    scores = []
    screenshots = [(source, read_image(source)) for source in sorted((ROOT / "captures").glob("*.png"))]
    for source, image in screenshots:
        assert template_hit(blueprint_guard, image) == source.name.endswith("_图纸获取.png"), (source.name, "blueprint page")
        assert template_hit(server_guard, image) == (source == server_source), (source.name, "server error")
        if source == server_source:
            assert not template_hit(generic_ready, image), "错误遮罩不能触发开始"
    if args.reuse_list_checks:
        previous = read("data/generated/multiplayer_loop_manifest.json")
        previous = previous.get("variants", {}).get(profile["current_league"], previous)
        assert previous["recommended_order"] == [v[0]["title"] for v in available], "名单变更需完整检查"
        scores = previous["list_template_checks"]
    if cached_scores is not None:
        scores = cached_scores
    for vehicle, identity in available:
        if args.reuse_list_checks or cached_scores is not None:
            continue
        positives = []
        for source, image in screenshots:
            if template_hit(identity, image):
                positives.append(source.name)
                assert "_选车_" in source.name, (vehicle["title"], source.name)
        scores.append({"title": vehicle["title"], "positives": positives})
    (ROOT / os.environ.get("MA9_LOOP_OUTPUT", "assets/resource/pipeline/multiplayer_loop.json")).write_text(json.dumps(all_nodes, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    manifest = {"schema_version": 1, "league": profile["current_league"], "trials": trial_manifest,
                "recommended_order": [v[0]["title"] for v in available], "missing": missing,
                "selection_policy": profile["selection_policy"],
                "rotation_file": profile["rotation_file"],
                "compatible_leagues": profile["compatible_leagues"],
                "search_policy": "reverse_24_then_forward_24", "vehicle_click_region": "car_body_left_of_matched_name",
                "list_template_checks": scores, "session_time_limit": None,
                "note": "有界局数试跑；无60分钟计时器。段位变化或异常停止，设备流程待试跑。"}
    (ROOT / os.environ.get("MA9_LOOP_MANIFEST", "data/generated/multiplayer_loop_manifest.json")).write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"PASS {len(available)} compatible candidates in source order; trials={trial_manifest}; clicks not device-tested")


if __name__ == "__main__":
    main()
