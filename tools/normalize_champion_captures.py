"""规范新增带状态后缀的车辆截图名称；保留像素并记录哈希。"""
import hashlib
import json
import re
from pathlib import Path
from PIL import Image
from import_vehicle_data import key
from check_daily_navigation import hit, read_image

ROOT = Path(__file__).resolve().parents[1]


def main():
    catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))["vehicles"]
    pipeline = json.loads((ROOT / "assets/resource/pipeline/multiplayer_navigation.json").read_text(encoding="utf-8"))
    plan = []
    for source in sorted((ROOT / "captures").glob("*.png")):
        if source.name.startswith("多人游戏_"):
            continue
        match = re.fullmatch(r"(.+?)(完整可见|详细信息|车辆详情_段位不可用)", source.stem)
        if not match:
            continue
        short, state = match.groups()
        candidates = [v for v in catalog if key(short) in key(v["title"])]
        assert len(candidates) == 1, (source.name, candidates)
        vehicle = candidates[0]
        with Image.open(source) as image:
            assert image.size == (1280, 720), source.name
        if state == "完整可见":
            image = read_image(source)
            on = hit(pipeline["多人准备_仅拥有已开启"], image)
            off = hit(pipeline["多人准备_开启仅拥有"], image)
            assert on != off, (source.name, "无法确定仅拥有状态")
            target_name = f"多人游戏_选车_{vehicle['league']}_{vehicle['title']}完整可见_仅拥有{'开启' if on else '关闭'}.png"
        elif state == "车辆详情_段位不可用":
            target_name = f"多人游戏_车辆详情_{vehicle['title']}_段位不可用_{vehicle['league']}.png"
        else:
            target_name = f"多人游戏_车辆详情_{vehicle['title']}_可开始_TouchDrive开.png"
        target = source.with_name(target_name)
        assert not target.exists(), target_name
        plan.append({"source": source.name, "target": target_name,
                     "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    assert len({r["target"] for r in plan}) == len(plan)
    for row in plan:
        source, target = ROOT / "captures" / row["source"], ROOT / "captures" / row["target"]
        source.rename(target)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == row["sha256"]
        print(row["source"], "->", row["target"])
    (ROOT / "data/generated/champion_capture_rename_report.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Renamed {len(plan)} captures; pixels unchanged")


if __name__ == "__main__":
    main()
