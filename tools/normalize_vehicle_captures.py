"""按车辆目录补全英文简名截图；默认预览，--apply 执行重命名。

输入约定：人工确认过的车辆详情、可开始、TouchDrive 开截图。
本工具检查文件格式与车型匹配，不判断画面状态。
"""
import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def normalized(value):
    value = unicodedata.normalize("NFKD", value).casefold()
    return "".join(c for c in value if c.isalnum())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--kind", choices=["detail", "list"], default="detail")
    parser.add_argument("--league", help="列表截图所在段位，也用于限制简称匹配范围")
    parser.add_argument("--owned", choices=["开启", "关闭"], default="开启")
    args = parser.parse_args()
    if args.kind == "list" and not args.league:
        parser.error("列表截图需指定 --league")
    catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))["vehicles"]
    plan, skipped = [], []
    for source in sorted((ROOT / "captures").glob("*.png")):
        if re.search(r"[\u4e00-\u9fff]", source.stem):
            continue
        key = normalized(source.stem)
        candidates = [v for v in catalog if key and key in normalized(v["title"])
                      and (not args.league or v["league"] == args.league)]
        if len(candidates) != 1:
            skipped.append({"source": source.name, "candidates": [v["title"] for v in candidates]})
            continue
        vehicle = candidates[0]
        filename = (f"多人游戏_选车_{args.league}_{vehicle['title']}完整可见_仅拥有{args.owned}.png"
                    if args.kind == "list" else f"多人游戏_车辆详情_{vehicle['title']}_可开始_TouchDrive开.png")
        target = source.with_name(filename)
        if target.exists():
            raise FileExistsError(target)
        with Image.open(source) as image:
            assert image.size == (1280, 720), (source.name, image.size)
        plan.append({"source": source.name, "target": target.name,
                     "catalog_id": vehicle["id"], "title": vehicle["title"],
                     "league": vehicle["league"],
                     "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    assert len({p["target"] for p in plan}) == len(plan), "多个文件匹配同一车型"
    for item in plan:
        print(f"{item['source']} -> {item['target']}")
    if args.apply:
        for item in plan:
            source, target = ROOT / "captures" / item["source"], ROOT / "captures" / item["target"]
            source.rename(target)
            assert hashlib.sha256(target.read_bytes()).hexdigest() == item["sha256"]
        report = {"renamed": plan, "skipped": skipped,
                  "state_basis": "user_confirmed_list_owned_" + args.owned if args.kind == "list" else "user_confirmed_detail_ready_touchdrive_on"}
        report_name = "vehicle_list_capture_rename_report.json" if args.kind == "list" else "vehicle_capture_rename_report.json"
        (ROOT / "data/generated" / report_name).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{'Renamed' if args.apply else 'Planned'} {len(plan)} files; skipped {len(skipped)} unmatched/ambiguous files")


if __name__ == "__main__":
    main()
