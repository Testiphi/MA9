"""将用户通过的车名审核快照转换为正式推荐数据。仅在用户确认后运行。"""
import json
from pathlib import Path
from import_vehicle_data import LEAGUES

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / "data/generated/champion_name_review.json"
    review = json.loads(source.read_text(encoding="utf-8"))
    groups = []
    for league in LEAGUES:
        vehicles = []
        for row in review["entries"]:
            if row["source_league"] != league:
                continue
            assert len(row["candidates"]) == 1, row
            vehicle = row["candidates"][0]
            assert vehicle["league"] == league, row
            vehicles.append({"order": row["order"], "title": vehicle["title"],
                             "catalog_id": vehicle["id"], "class": vehicle["class"],
                             "league": league, "category": row["category"], "source_name": row["source_name"]})
            row["approved"] = True
        assert [v["order"] for v in vehicles] == list(range(1, len(vehicles) + 1))
        groups.append({"league": league, "vehicles": vehicles})
    review["status"] = "approved"
    source.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rotation = {"schema_version": 1, "source": "各级别霸主.docx + champion_overrides.json",
                "status": "approved", "ordering": "per_league_left_to_right", "groups": groups}
    (ROOT / "data/generated/champion_rotation.json").write_text(json.dumps(rotation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = ROOT / "data/generated/champion_name_review.md"
    md.write_text(md.read_text(encoding="utf-8").replace("# 自动驾驶霸主车名匹配待审核", "# 自动驾驶霸主车名匹配已通过")
                  .replace("车名候选待审核，尚未启用为选车序列。", "车名匹配与顺序已获用户通过；正式推荐数据为 champion_rotation.json。"), encoding="utf-8")
    print(f"Approved {sum(len(g['vehicles']) for g in groups)} vehicles")


if __name__ == "__main__":
    main()
