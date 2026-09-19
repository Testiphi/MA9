"""Read five ordered Duel maps from stored 16:9 lineup screenshots."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maa.resource import Resource
from maa.tasker import Tasker

from probe_duel_vehicle_selection import SavedImageController
from probe_vehicle_fields import read_image, recognize_roi


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
from ma9_agent.duel_map_screen import read_five_tracks  # noqa: E402
from ma9_agent.duel_vehicle_screen import normalize  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", type=Path, nargs="+")
    args = parser.parse_args()
    reference = json.loads((ROOT / "data/generated/duel_auto_candidates.json").read_text(encoding="utf-8"))
    resource = Resource()
    if not resource.post_bundle(ROOT / "assets/resource").wait().succeeded:
        raise RuntimeError("Maa resource load failed")
    controller = SavedImageController(normalize(read_image(args.images[0])))
    if not controller.post_connection().wait().succeeded:
        raise RuntimeError("saved image controller failed")
    tasker = Tasker()
    if not tasker.bind(resource, controller):
        raise RuntimeError("Maa tasker bind failed")
    all_complete = True
    for path in args.images:
        image = normalize(read_image(path))
        words = recognize_roi(tasker, image, (55, 165, 1190, 160))
        report = read_five_tracks(words, reference)
        all_complete &= report["complete"]
        print(json.dumps({"source": str(path), **report}, ensure_ascii=False), flush=True)
    return 0 if all_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
