"""Choose an owned car for the no-race multiplayer location test."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from ma9_agent.selection_editor import SelectionEditor


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vehicle", help="exact vehicle name or catalog ID")
    parser.add_argument("--from", dest="direction", choices=("start", "end"), required=True)
    parser.add_argument("--repeats", type=int, default=3, choices=range(1, 6))
    args = parser.parse_args()
    editor = SelectionEditor(ROOT)
    candidates = [vehicle_id for vehicle_id, item in editor.vehicles.items()
                  if vehicle_id == args.vehicle or item["title"].casefold() == args.vehicle.casefold()]
    if len(candidates) != 1:
        parser.error(f"vehicle name must match exactly one catalog entry; matches={candidates}")
    vehicle_id = candidates[0]
    destination = editor.write_location_test(vehicle_id, args.direction, args.repeats)
    print(json.dumps({"file": str(destination), "vehicle": editor.vehicles[vehicle_id],
                      "from": args.direction, "repeats": args.repeats}, ensure_ascii=False))


if __name__ == "__main__":
    main()
