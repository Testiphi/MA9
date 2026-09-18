"""Import an only-owned vehicle survey or manually correct an account garage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from ma9_agent.garage_profile import (load_profile, merge_owned_survey,  # noqa: E402
                                      owned_vehicle_ids, save_profile, set_owned)


def catalog() -> tuple[dict[str, dict], dict[str, dict]]:
    rows = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))["vehicles"]
    return ({row["id"]: row for row in rows}, {row["title"].casefold(): row for row in rows})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "config/garage.json")
    commands = parser.add_subparsers(dest="command", required=True)
    imported = commands.add_parser("import-scan")
    imported.add_argument("survey_dir", type=Path)
    manual = commands.add_parser("set-owned")
    manual.add_argument("vehicle", help="catalog ID or full catalog title")
    manual.add_argument("state", choices=("yes", "no", "unknown"))
    args = parser.parse_args()

    by_id, by_title = catalog()
    profile = load_profile(args.profile)
    if args.command == "import-scan":
        survey_path = args.survey_dir / "survey.json"
        survey = json.loads(survey_path.read_text(encoding="utf-8"))
        if survey.get("owned_filter") != "on":
            parser.error("this survey did not have the only-owned filter enabled; ownership was not imported")
        records = []
        for league in survey.get("leagues", {}):
            for page in sorted((args.survey_dir / league / "pages").glob("*.json")):
                records.extend(json.loads(page.read_text(encoding="utf-8")))
        merge_owned_survey(profile, survey, records, by_id)
    else:
        vehicle = by_id.get(args.vehicle) or by_title.get(args.vehicle.casefold())
        if vehicle is None:
            parser.error(f"unknown catalog vehicle: {args.vehicle}")
        set_owned(profile, vehicle, {"yes": True, "no": False, "unknown": None}[args.state])
    save_profile(args.profile, profile)
    print(json.dumps({"profile": str(args.profile), "owned": len(owned_vehicle_ids(profile)),
                      "manual_not_owned": sum(item.get("owned") is False for item in profile["vehicles"].values()),
                      "unknown": len(by_id) - len(profile["vehicles"]),
                      "coverage": profile["coverage"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
