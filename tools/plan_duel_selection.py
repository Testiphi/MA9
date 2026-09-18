"""Preview Duel vehicle allocation without touching the game."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from ma9_agent.duel_selection import load_reference, plan_attack, plan_weak_defense  # noqa: E402
from ma9_agent.garage_profile import load_profile, owned_vehicle_ids  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("attack", "weak-defense"))
    parser.add_argument("tracks", nargs="*", help="five 大地图/小地图 pairs for attack")
    parser.add_argument("--zone", choices=("五区", "四区"), default="五区")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))
    garage = load_profile(ROOT / "config/garage.json")
    owned = owned_vehicle_ids(garage)
    if args.mode == "attack":
        if len(args.tracks) != 5 or any("/" not in item for item in args.tracks):
            parser.error("attack requires five 大地图/小地图 arguments")
        pairs = [tuple(item.split("/", 1)) for item in args.tracks]
        reference = load_reference(ROOT / "data/generated/duel_auto_candidates.json")
        plan = plan_attack(pairs, args.zone, owned, reference, catalog, limit=args.limit)
    else:
        if args.tracks:
            parser.error("weak-defense takes no track arguments")
        plan = plan_weak_defense(catalog, owned, ROOT / "data/sources/国服_a9mmgj_top_full.csv")
    print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
