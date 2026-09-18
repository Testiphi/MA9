"""Recheck unidentified list cards against the latest catalog matcher without touching the game."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from probe_vehicle_fields import match_catalog
from vehicle_scan_merge import merge_vehicle_records


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("survey_dir", type=Path)
    args = parser.parse_args()
    survey_path = args.survey_dir / "survey.json"
    survey = json.loads(survey_path.read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))["vehicles"]
    all_records = []
    repaired = 0
    for league, summary in survey["leagues"].items():
        records = []
        for page in sorted((args.survey_dir / league / "pages").glob("*.json")):
            reports = json.loads(page.read_text(encoding="utf-8"))
            changed = False
            for report in reports:
                if report["values"].get("vehicle") is None:
                    match = match_catalog(report["ocr"]["name"], catalog, league)
                    if match is not None:
                        report["values"]["vehicle"] = match
                        repaired += 1
                        changed = True
            if changed:
                page.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            records.extend(reports)
        summary["cards"] = len(records)
        summary["recognized"] = sum(item["values"]["vehicle"] is not None for item in records)
        summary["unique_vehicle_ids"] = sorted({item["values"]["vehicle"]["id"] for item in records
                                                if item["values"]["vehicle"]})
        all_records.extend(records)
    merged = merge_vehicle_records(all_records)
    (args.survey_dir / "vehicles.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    survey_path.write_text(json.dumps(survey, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"repaired": repaired, "unique": len(merged["vehicles"]),
                      "unidentified": len(merged["unidentified"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
