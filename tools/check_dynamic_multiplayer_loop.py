"""校验动态段位、推荐顺序、倒序锚点和服务器恢复计数隔离。"""
import json
import sys
from pathlib import Path
from check_daily_navigation import hit, read_image
from multiplayer_loop_files import load_loop_nodes
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
from ma9_agent.garage_profile import load_profile  # noqa: E402
from ma9_agent.selection_strategy import load_strategy, planned_vehicles  # noqa: E402


def main():
    nodes = load_loop_nodes(ROOT)
    assert all(len(node.get("next", [])) == len(set(node.get("next", [])))
               for node in nodes.values()), "duplicate next route"
    manifest = json.loads((ROOT / "data/generated/multiplayer_loop_manifest.json").read_text(encoding="utf-8"))
    rotation = json.loads((ROOT / "data/generated/champion_rotation.json").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))
    garage_path = ROOT / "config/garage.json"
    garage = load_profile(garage_path) if garage_path.is_file() else None
    strategy = load_strategy(ROOT / "config/selection_strategy.json", catalog, rotation, garage)
    dispatch = "多人循环3局_第01局_自动段位调度"
    for rounds in (3, 20):
        for index in range(rounds):
            p = f"多人循环{rounds}局_第{index+1:02}局_"
            first = p + "系列赛段位待确认"
            second = p + "系列赛段位等待徽章_2"
            third = p + "系列赛段位等待徽章_3"
            stop = p + "系列赛段位不支持"
            for current, following in [(first, second), (second, third), (third, stop)]:
                assert nodes[current]["post_delay"] == 3000
                assert nodes[current]["next"][-4:] == [p+"当前段位_白金", p+"当前段位_黄金",
                                                     p+"当前段位_白银", following]
            assert nodes[stop]["action"] == "StopTask"
    for filename, suffix in [
        ("多人游戏_经典系列赛_首页_白金.png", "当前段位_白金"),
        ("多人游戏_经典系列赛_首页_黄金.png", "当前段位_黄金"),
        ("多人游戏_经典系列赛_首页_白银.png", "当前段位_白银"),
        ("多人游戏_选车_黄金起点_仅拥有开启.png", "返回系列赛确认段位"),
        ("多人游戏_车辆详情_Ferrari J50_无燃油_TouchDrive开.png", "返回列表确认段位"),
        ("Lamborghini Huracan Sterrato_图纸获取.png", "图纸页面关闭并重新确认"),
        ("Lexus LFA Nurburgring Package_图纸获取.png", "图纸页面关闭并重新确认"),
        ("Praga Bohema_图纸获取.png", "图纸页面关闭并重新确认"),
        ("名人堂奖励.png", "HALL"),
        ("多人游戏_结算_通行证升级.png", "多人结算_通行证升级关闭"),
    ]:
        image = read_image(ROOT / "captures" / filename)
        first = next(k for k in nodes[dispatch]["next"] if hit(nodes[k], image))
        expected = "多人循环3局_黄金_第01局_多人结算_名人堂奖励继续" if suffix == "HALL" else "多人循环3局_第01局_" + suffix
        assert first == expected, (filename, first)
    # 名堂奖励仍可识别时，叠加真实广告 × 区域应优先关闭广告。
    overlay = read_image(ROOT / "captures/名人堂奖励.png").copy()
    advertisement = read_image(ROOT / "captures/BXR氮气特效广告.png")
    overlay[70:180,1000:1160] = advertisement[70:180,1000:1160]
    assert hit(nodes["多人循环3局_黄金_第01局_多人结算_名人堂奖励继续"], overlay)
    first = next(k for k in nodes[dispatch]["next"] if hit(nodes[k], overlay))
    assert first == "多人循环3局_第01局_广告关闭"
    for league, variant in manifest["variants"].items():
        assert variant["selection_engine"] == ("runtime_ocr" if strategy else "static_templates")
        # These static nodes are a build-time safety net. The Agent reads the
        # saved account order at runtime, so GUI edits must not require rebuild.
        vehicles = variant["recommended_vehicles"]
        assert variant["recommended_order"] == [v["title"] for v in vehicles]
        if not strategy:
            expected = [v for v in planned_vehicles(league, catalog, rotation, None)
                        if v["title"] not in variant["missing"]]
            assert vehicles == expected
        choices = [k for k in nodes if f"局_{league}_第" in k and k.endswith("推荐选车入口")]
        assert len(choices) == 92
        for choice in choices:
            prefix = choice.removesuffix("推荐选车入口")
            if strategy:
                assert nodes[choice]["action"] == "Custom"
                assert nodes[choice]["custom_action"] == "ma9_select_recommended"
                assert nodes[choice]["custom_action_param"]["player_league"] == league
                assert nodes[choice]["timeout"] >= 600000
                round_prefix = prefix.split("服务器恢复", 1)[0]
                assert nodes[choice]["on_error"] == [round_prefix + "停止_未知状态或次数耗尽"]
                for suffix in ("确认准备并开始", "原地开启TouchDrive", "倒序兜底_入口"):
                    assert prefix + suffix in nodes
            first = (prefix + f"推荐01_{vehicles[0]['catalog_id']}_入口" if vehicles
                     else prefix + "倒序兜底_入口")
            assert first in nodes[choice]["next"]
            if vehicles:
                last = prefix + f"推荐{len(vehicles):02}_{vehicles[-1]['catalog_id']}_"
                assert prefix + "倒序兜底_入口" in nodes[last + "正向搜索"]["next"]
                assert prefix + "倒序兜底_入口" in nodes[last + "不可用返回"]["next"]
            for index, vehicle in enumerate(vehicles, 1):
                c = prefix + f"推荐{index:02}_{vehicle['catalog_id']}_"
                assert nodes[c+"点击车型"]["target"] is True
                assert nodes[c+"点击车型"]["box_index"] == 0
                assert nodes[c+"点击车型"]["target_offset"] == [-220,-70,0,0]
                assert nodes[c+"点击车型"]["all_of"][0]["roi"] == [300,190,980,480]
                close = c + "图纸误入关闭"
                retry = c + "图纸返回后重选"
                assert close in nodes[c+"点击车型"]["next"]
                assert nodes[c+"点击车型"]["next"][0].endswith("广告关闭")
                assert retry in nodes[close]["next"]
                assert nodes[close]["next"][0].endswith("广告关闭")
                assert nodes[close]["max_hit"] == nodes[retry]["max_hit"] == 2
                assert nodes[c+"反向定位起点"]["target"] == {"白金":[782,107],"黄金":[726,107],
                                                                "白银":[671,107],"青铜":[616,107]}[vehicle["league"]]
                assert nodes[c+"反向搜索"]["max_hit"] == 24
                assert nodes[c+"正向搜索"]["max_hit"] == 24
        for rounds in [3,20]:
            for index in range(rounds):
                p=f"多人循环{rounds}局_{league}_第{index+1:02}局_"
                owned_off, owned_on = p+"多人准备_开启仅拥有", p+"多人准备_仅拥有已开启"
                assert nodes[owned_off]["max_hit"] == 3
                assert nodes[owned_off]["post_delay"] == 1500
                assert nodes[owned_off]["next"][-2:] == [owned_on, owned_off]
                start, wait = p+"确认准备并开始", p+"等待匹配与局内"
                assert nodes[start]["max_hit"] == 3 and nodes[start]["post_delay"] == 1500
                assert start in nodes[wait]["next"]
                assert nodes[wait]["next"].index(start) < nodes[wait]["next"].index(p+"多人局内_氮气兜底")
                nitro = nodes[p+"多人局内_氮气兜底"]
                assert nitro["post_delay"] == 6000 and nitro["repeat_delay"] == 750
                assert nitro["max_hit"] == 42
                reward = nodes[p+"多人结算_奖励继续"]
                assert reward["max_hit"] == 3 and reward["post_delay"] == 1500
                assert p+"多人结算_奖励继续" in reward["next"]
                assert reward["next"][-2:] == [p+"结算等待新页面", p+"停止_未知状态或次数耗尽"]
                upgrade = nodes[p+"多人段位_升级继续"]
                assert upgrade["max_hit"] == 3 and upgrade["post_delay"] == 1500
                assert p+"多人段位_升级继续" in upgrade["next"]
                assert upgrade["next"][-2:] == [p+"结算等待新页面", p+"停止_未知状态或次数耗尽"]
                assert nodes[p+"结算等待新页面"]["next"][-2:] == [p+"结算等待新页面", p+"停止_未知状态或次数耗尽"]
                assert nodes[p+"多人段位_降级确定"]["next"] == [p+"广告关闭",p+"多人结算_名人堂奖励继续",
                    p+"多人结算_已返回系列赛", p+"结算等待新页面", p+"停止_未知状态或次数耗尽"]
                hall = p + "多人结算_名人堂奖励继续"
                assert hall in nodes[p+"等待匹配与局内"]["next"]
                assert hall in nodes[p+"多人结算_点击错失机会"]["next"]
                assert nodes[hall]["target"] == [1154,660]
                assert p+"多人结算_已返回系列赛" in nodes[hall]["next"]
                assert nodes[p+"页面调度"]["next"][:2] == [p+"多人结算_通行证升级关闭", p+"广告关闭"]
                pass_close = p+"多人结算_通行证升级关闭"
                assert nodes[pass_close]["next"] == [p+"结算等待新页面"]
                assert nodes[p+"结算等待新页面"]["next"][0] == pass_close
                assert nodes[p+"多人结算_点击错失机会"]["next"][0] == pass_close
                assert nodes[p+"倒序兜底_定位相邻段位起点"]["target"] == {
                    "白金": [782,107], "黄金": [726,107], "白银": [671,107]}[league]
                nxt=nodes[p+"本局完成"]["next"]
                assert nxt == ([f"多人循环{rounds}局_第{index+2:02}局_自动段位调度"] if index+1<rounds else [])
                restores=nodes[p+"服务器错误关闭"]["next"]
                server = nodes[p+"服务器错误关闭"]
                assert server["target"] == [1092, 244]
                assert server["max_hit"] == 8
                assert p+"服务器错误关闭" in server["next"]
                restores=[r for r in restores if r.endswith("确认选车列表")]
                assert len(restores)==3 and len(set(restores))==3
                for restore in restores:
                    assert nodes[restore]["max_hit"]==1
                    off = restore.removesuffix("确认选车列表") + "开启仅拥有"
                    on = restore.removesuffix("确认选车列表") + "仅拥有已开启"
                    assert nodes[off]["max_hit"] == 3
                    assert nodes[off]["post_delay"] == 1500
                    assert nodes[off]["next"][-2:] == [on, off]
                if league in {"白金", "黄金"}:
                    assert nodes[p+f"倒序兜底_{league}段位不可用"]["next"]==[
                        p+"广告关闭",f"多人循环{rounds}局_第{index+1:02}局_返回列表确认段位"]
    assert all(t in nodes for v in nodes.values() for field in ["next","on_error"] for t in v.get(field,[]))
    print("PASS 69 round variants, 207 isolated server recoveries, rank switching and reverse anchors")


if __name__ == "__main__":
    main()
