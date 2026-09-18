"""Create a per-account priority file from confirmed-owned approved recommendations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from ma9_agent.garage_profile import load_profile  # noqa: E402
from ma9_agent.selection_strategy import load_strategy, new_strategy  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "config/selection_strategy.json")
    parser.add_argument("--refresh", action="store_true",
                        help="keep existing order, append newly confirmed-owned vehicles")
    args = parser.parse_args()
    if args.output.exists() and not args.refresh:
        parser.error(f"strategy already exists; refusing to overwrite: {args.output}")
    garage_path = ROOT / "config/garage.json"
    if not garage_path.is_file():
        parser.error("scan or configure an account garage before creating priorities")
    rotation = json.loads((ROOT / "data/generated/champion_rotation.json").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))
    garage = load_profile(garage_path)
    strategy = new_strategy(catalog, rotation, garage)
    if args.output.is_file():
        # Refresh may follow a catalog league correction or ownership change.
        # Keep the still-valid relative order and drop entries no longer valid.
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        if previous.get("schema_version") != 1 or not isinstance(previous.get("priorities"), dict):
            parser.error("cannot refresh an unsupported strategy file")
        for league, all_ids in strategy["priorities"].items():
            old_ids = [vehicle_id for vehicle_id in previous["priorities"].get(league, [])
                       if vehicle_id in all_ids]
            old_set = set(old_ids)
            strategy["priorities"][league] = old_ids + [vehicle_id for vehicle_id in all_ids
                                                          if vehicle_id not in old_set]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(strategy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    load_strategy(temporary, catalog, rotation, garage)
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output), "counts":
                      {league: len(ids) for league, ids in strategy["priorities"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
