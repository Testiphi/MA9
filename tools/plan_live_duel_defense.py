"""Build a five-car defense proposal from live OCR reports, without game input."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from ma9_agent.duel_selection import plan_live_weak_defense  # noqa: E402


def main() -> None:
    tracks = json.loads((ROOT / "debug/duel_tracks_live.json").read_text(encoding="utf-8"))
    scan = json.loads((ROOT / "debug/duel_vehicle_scan_live.json").read_text(encoding="utf-8"))
    plan = plan_live_weak_defense(tracks, scan)
    destination = ROOT / "debug/duel_defense_plan_live.json"
    destination.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
