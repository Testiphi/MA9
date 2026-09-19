"""Check saved 16:9 screenshots for the concurrent-account-login dialog."""

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
from ma9_agent.account_conflict import account_conflict_from_ocr  # noqa: E402
from ma9_agent.duel_vehicle_screen import normalize  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", type=Path, nargs="+")
    args = parser.parse_args()
    resource = Resource()
    if not resource.post_bundle(ROOT / "assets/resource").wait().succeeded:
        raise RuntimeError("resource load failed")
    first = normalize(read_image(args.images[0]))
    controller = SavedImageController(first)
    if not controller.post_connection().wait().succeeded:
        raise RuntimeError("saved-image controller failed")
    tasker = Tasker()
    if not tasker.bind(resource, controller):
        raise RuntimeError("tasker bind failed")
    for path in args.images:
        frame = normalize(read_image(path))
        words = recognize_roi(tasker, frame, (140, 200, 1000, 330))
        result = account_conflict_from_ocr(words)
        print(json.dumps({"source": str(path), **result}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
