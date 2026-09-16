"""校验动态段位、推荐顺序、倒序锚点和服务器恢复计数隔离。"""
import json
from pathlib import Path
from check_daily_navigation import hit, read_image
ROOT = Path(__file__).resolve().parents[1]


def main():
    nodes = json.loads((ROOT / "assets/resource/pipeline/multiplayer_loop.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "data/generated/multiplayer_loop_manifest.json").read_text(encoding="utf-8"))
    rotation = json.loads((ROOT / "data/generated/champion_rotation.json").read_text(encoding="utf-8"))
    dispatch = "多人循环3局_第01局_自动段位调度"
    for filename, suffix in [
        ("多人游戏_经典系列赛_首页_黄金.png", "当前段位_黄金"),
        ("多人游戏_经典系列赛_首页_白银.png", "当前段位_白银"),
        ("多人游戏_选车_黄金起点_仅拥有开启.png", "返回系列赛确认段位"),
        ("多人游戏_车辆详情_Ferrari J50_无燃油_TouchDrive开.png", "返回列表确认段位"),
        ("Lamborghini Huracan Sterrato_图纸获取.png", "图纸页面关闭并重新确认"),
        ("Lexus LFA Nurburgring Package_图纸获取.png", "图纸页面关闭并重新确认"),
        ("Praga Bohema_图纸获取.png", "图纸页面关闭并重新确认"),
    ]:
        image = read_image(ROOT / "captures" / filename)
        first = next(k for k in nodes[dispatch]["next"] if hit(nodes[k], image))
        assert first == "多人循环3局_第01局_" + suffix, (filename, first)
    for league, variant in manifest["variants"].items():
        vehicles = [v for rank in variant["compatible_leagues"] for group in rotation["groups"]
                    if group["league"] == rank for v in group["vehicles"] if v["title"] not in variant["missing"]]
        assert variant["recommended_order"] == [v["title"] for v in vehicles]
        choices = [k for k in nodes if f"局_{league}_第" in k and k.endswith("推荐选车入口")]
        assert len(choices) == 92
        for choice in choices:
            prefix = choice.removesuffix("推荐选车入口")
            first = prefix + f"推荐01_{vehicles[0]['catalog_id']}_入口"
            assert first in nodes[choice]["next"]
            for index, vehicle in enumerate(vehicles, 1):
                c = prefix + f"推荐{index:02}_{vehicle['catalog_id']}_"
                assert nodes[c+"点击车型"]["target"] is True
                assert nodes[c+"点击车型"]["box_index"] == 0
                assert nodes[c+"点击车型"]["target_offset"] == [-220,-70,0,0]
                assert nodes[c+"点击车型"]["all_of"][0]["roi"] == [300,190,980,480]
                close = c + "图纸误入关闭"
                retry = c + "图纸返回后重选"
                assert close in nodes[c+"点击车型"]["next"]
                assert nodes[c+"点击车型"]["next"][0] == close
                assert retry in nodes[close]["next"]
                assert nodes[close]["next"] == [retry]
                assert nodes[close]["max_hit"] == nodes[retry]["max_hit"] == 2
                assert nodes[c+"反向定位起点"]["target"] == {"黄金":[726,107],"白银":[671,107],"青铜":[616,107]}[vehicle["league"]]
                assert nodes[c+"反向搜索"]["max_hit"] == 24
                assert nodes[c+"正向搜索"]["max_hit"] == 24
        for rounds in [3,20]:
            for index in range(rounds):
                p=f"多人循环{rounds}局_{league}_第{index+1:02}局_"
                assert nodes[p+"多人段位_降级确定"]["next"] == [p+"多人结算_已返回系列赛"]
                assert nodes[p+"倒序兜底_定位相邻段位起点"]["target"] == ([726,107] if league=="黄金" else [671,107])
                nxt=nodes[p+"本局完成"]["next"]
                assert nxt == ([f"多人循环{rounds}局_第{index+2:02}局_自动段位调度"] if index+1<rounds else [])
                restores=nodes[p+"服务器错误关闭"]["next"]
                assert len(restores)==3 and len(set(restores))==3
                for restore in restores:
                    assert nodes[restore]["max_hit"]==1
                if league=="黄金":
                    assert nodes[p+"倒序兜底_黄金段位不可用"]["next"]==[f"多人循环{rounds}局_第{index+1:02}局_返回列表确认段位"]
    assert all(t in nodes for v in nodes.values() for field in ["next","on_error"] for t in v.get(field,[]))
    print("PASS 46 round variants, 138 isolated server recoveries, rank switching and reverse anchors")


if __name__ == "__main__":
    main()
