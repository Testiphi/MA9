"""Cross-check saved list OCR against the full vehicle CSV without changing the catalog."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGLISH_LEAGUES = {
    "Bronze": "青铜", "Silver": "白银", "Gold": "黄金",
    "Platinum": "白金", "Emerald": "翡翠", "Diamond": "钻石",
    "Elite": "精英", "Master": "宗师", "Legend": "传奇",
}
LEAGUES = ("青铜", "白银", "黄金", "白金", "翡翠", "钻石", "精英", "宗师", "传奇")


def name_key(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", unicodedata.normalize("NFKC", value).casefold())


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def check_record(record: dict, reference: dict[str, list[dict]]) -> list[dict]:
    vehicle = record["values"].get("vehicle")
    if vehicle is None:
        return [{"kind": "unidentified", "source": record["source"], "card": record.get("card"),
                 "name_ocr": [item["text"] for item in record["ocr"]["name"]]}]
    rows = reference.get(name_key(vehicle["name"]), [])
    result = []
    base = {"vehicle": vehicle["name"], "source": record["source"], "card": record.get("card")}
    if not rows:
        return [{**base, "kind": "absent_from_reference"}]
    if len(rows) != 1:
        return [{**base, "kind": "duplicate_reference", "scores": [row["score"] for row in rows]}]
    row = rows[0]
    if row["class"] != vehicle["class"]:
        result.append({**base, "kind": "class_mismatch", "catalog": vehicle["class"], "reference": row["class"]})
    reference_league = ENGLISH_LEAGUES.get(row["league"], row["league"])
    if reference_league != vehicle["catalog_league"]:
        result.append({**base, "kind": "catalog_league_mismatch", "catalog": vehicle["catalog_league"],
                       "reference": reference_league})
    score = int(row["score"]) if row["score"].isdigit() else None
    performance = record["values"].get("performance")
    if score and performance and performance[1] > score:
        result.append({**base, "kind": "performance_above_reference", "observed": performance,
                       "reference_max": score})
    blueprints = record["values"].get("blueprints")
    requirements = [int(value) for value in row["bp_values"].split(",") if value.strip().isdigit()]
    if blueprints and requirements and blueprints[1] not in requirements:
        result.append({**base, "kind": "blueprint_requirement_mismatch", "observed": blueprints,
                       "reference_requirements": requirements})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("survey_dir", type=Path, help="directory made by sample_vehicle_leagues.py")
    parser.add_argument("--reference", type=Path, default=ROOT / "data/sources/国服_a9mmgj_top_full.csv")
    parser.add_argument("--catalog", type=Path, default=ROOT / "data/generated/vehicle_catalog.json")
    parser.add_argument("--additional-records", type=Path, nargs="*", default=[],
                        help="offline probe_vehicle_fields.py JSON reports to include")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    reference_rows = read_csv(args.reference)
    reference = defaultdict(list)
    for row in reference_rows:
        reference[name_key(row["title"])].append(row)
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))["vehicles"]
    catalog_by_name = {name_key(row["title"]): row for row in catalog}
    records = []
    for league in LEAGUES:
        for page in sorted((args.survey_dir / league / "pages").glob("*.json")):
            for record in json.loads(page.read_text(encoding="utf-8")):
                records.append((league, record))
    for path in args.additional_records:
        for record in json.loads(path.read_text(encoding="utf-8")):
            source = Path(record["source"]).name
            screen_league = next((league for league in LEAGUES if f"选车_{league}_" in source), None)
            vehicle = record["values"].get("vehicle")
            records.append((screen_league or (vehicle["catalog_league"] if vehicle else "未知"), record))
    if not records:
        parser.error("no survey page JSON found")

    issues = []
    recognized = {}
    for screen_league, record in records:
        issues.extend(check_record(record, reference))
        vehicle = record["values"].get("vehicle")
        if vehicle:
            entry = recognized.setdefault(vehicle["id"], {
                "name": vehicle["name"], "class": vehicle["class"],
                "catalog_league": vehicle["catalog_league"], "screen_leagues": set(), "observations": 0,
            })
            entry["screen_leagues"].add(screen_league)
            entry["observations"] += 1
    for item in recognized.values():
        item["screen_leagues"] = sorted(item["screen_leagues"], key=LEAGUES.index)

    missing_from_reference = [row["title"] for row in catalog if name_key(row["title"]) not in reference]
    missing_from_catalog = [row["title"] for row in reference_rows if name_key(row["title"]) not in catalog_by_name]
    duplicate_reference = {rows[0]["title"]: [row["score"] for row in rows]
                           for rows in reference.values() if len(rows) > 1}
    catalog_differences = []
    for car in catalog:
        rows = reference.get(name_key(car["title"]), [])
        if len(rows) != 1:
            continue
        row = rows[0]
        ref_league = ENGLISH_LEAGUES.get(row["league"], row["league"])
        if car["class"] != row["class"] or car["league"] != ref_league:
            catalog_differences.append({"name": car["title"], "catalog_class": car["class"],
                                        "catalog_league": car["league"], "reference_class": row["class"],
                                        "reference_league": ref_league})
    order = {row["id"]: index for index, row in enumerate(catalog)}
    grouped = {league: sorted((car for car_id, car in recognized.items() if car["catalog_league"] == league),
                              key=lambda car: order[catalog_by_name[name_key(car["name"])]["id"]])
               for league in LEAGUES}
    report = {
        "reference": str(args.reference), "reference_rows": len(reference_rows),
        "reference_distinct_names": len(reference), "catalog_missing_from_reference": missing_from_reference,
        "reference_missing_from_catalog": sorted(set(missing_from_catalog)),
        "duplicate_reference": duplicate_reference, "catalog_differences": catalog_differences,
        "observations": len(records),
        "recognized_observations": sum(record["values"].get("vehicle") is not None for _, record in records),
        "recognized_unique": len(recognized), "recognized_by_catalog_league": grouped, "issues": issues,
    }
    output_dir = args.output_dir or args.survey_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "reference_crosscheck.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        reference_label = str(args.reference.resolve().relative_to(ROOT))
    except ValueError:
        reference_label = str(args.reference)
    lines = ["# 已识别车辆与完整 CSV 交叉验证", "",
             f"来源：`{args.survey_dir}` 及历史选车截图；参考：`{reference_label}`。", "",
             f"完整车卡观测 {len(records)} 次；匹配目录 {report['recognized_observations']} 次；"
             f"不重复车型 {len(recognized)} 辆。以下按**当前 MA9 目录段位**列出，不把卡片出现位置当作车型段位。", ""]
    for league, cars in grouped.items():
        if cars:
            lines += [f"## {league}（{len(cars)}）", "", "、".join(car["name"] for car in cars) + "。", ""]
    counts = defaultdict(int)
    for issue in issues:
        counts[issue["kind"]] += 1
    lines += ["## 需要复核", "", f"参考 CSV 缺失：{', '.join(missing_from_reference) or '无'}。", "",
              f"参考 CSV 同名重复：{', '.join(duplicate_reference) or '无'}。", "",
              f"目录与参考 CSV 的等级/段位差异：{len(catalog_differences)} 处（见 JSON；已审核修正不自动覆盖）。", "",
              "逐次观测异常计数：" + "、".join(f"{name} {count}" for name, count in sorted(counts.items())) + "。", "",
              "具体来源、截图卡片位置和数值见 `reference_crosscheck.json`。", ""]
    (output_dir / "recognized_vehicles.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"observations": len(records), "recognized": report["recognized_observations"],
                      "unique": len(recognized), "issues": dict(counts), "output_dir": str(output_dir)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
