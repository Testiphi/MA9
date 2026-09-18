"""Import the reviewed Gauntlet automatic-car order into MA9 stable vehicle IDs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT.parent / "MutualExclusionAllocator" / "repo"
OUTPUT = ROOT / "data" / "generated" / "duel_auto_candidates.json"


def key(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKC", value).casefold()
                   if char.isalnum())


def build(source: Path, catalog: dict) -> tuple[dict, dict]:
    gauntlet_path = source / "gauntlet_data.json"
    car_path = source / "cars.json"
    raw = gauntlet_path.read_bytes()
    gauntlet = json.loads(raw)
    car_data = json.loads(car_path.read_text(encoding="utf-8"))
    by_title = {key(row["title"]): row for row in catalog["vehicles"]}
    if len(by_title) != len(catalog["vehicles"]):
        raise ValueError("MA9 catalog contains ambiguous normalized titles")
    nickname_map = car_data["_nickname_map"]
    mapped: list[dict] = []
    unresolved: set[str] = set()
    seen_tracks: set[tuple[str, str]] = set()
    candidate_count = 0
    for track in gauntlet["tracks"]:
        big, small = track["大地图"], track["小地图"]
        pair = big, small
        if pair in seen_tracks:
            raise ValueError(f"duplicate track: {big}/{small}")
        seen_tracks.add(pair)
        zones = {}
        for zone in ("五区", "四区"):
            candidates = []
            seen_cars: set[str] = set()
            for entry in track.get(zone, {}).get("自动", []):
                cars = entry.get("cars", [])
                if len(cars) != 1:
                    raise ValueError(f"expected a single car in {big}/{small}/{zone}: {cars}")
                alias = cars[0]["name"]
                title = nickname_map.get(alias, alias)
                vehicle = by_title.get(key(title))
                if vehicle is None:
                    unresolved.add(alias)
                    continue
                vehicle_id = vehicle["id"]
                if vehicle_id not in seen_cars:
                    candidates.append(vehicle_id)
                    seen_cars.add(vehicle_id)
            candidate_count += len(candidates)
            zones[zone] = candidates
        mapped.append({"big": big, "small": small, "zones": zones})
    result = {
        "schema_version": 1,
        "source": "MutualExclusionAllocator/repo/gauntlet_data.json",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "candidate_tier": "自动",
        "tracks": mapped,
    }
    report = {
        "tracks": len(mapped),
        "automatic_candidates": candidate_count,
        "empty_tracks_by_zone": {
            zone: [f'{row["big"]}/{row["small"]}' for row in mapped if not row["zones"][zone]]
            for zone in ("五区", "四区")
        },
        "unresolved_aliases": sorted(unresolved),
    }
    return result, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))
    result, report = build(args.source, catalog)
    if report["unresolved_aliases"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print("Unresolved car names; refusing to publish an incomplete reference", file=sys.stderr)
        return 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
