"""Cross-check one-pass runtime list OCR against the saved per-card survey."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from ma9_agent.vehicle_screen import read_page  # noqa: E402
from probe_vehicle_fields import make_tasker, read_image, recognize_roi  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("survey_dir", type=Path)
    parser.add_argument("--max-pages-per-league", type=int, default=0)
    args = parser.parse_args()
    config = json.loads((ROOT / "debug/vehicle_scan_env.json").read_text(encoding="utf-8"))
    tasker = make_tasker(ROOT / "assets/resource", Path(config["adb_path"]), config["address"])
    catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))["vehicles"]
    survey = json.loads((args.survey_dir / "survey.json").read_text(encoding="utf-8"))
    pages = cards = correct = 0
    problems = []
    for league in survey["leagues"]:
        sources = sorted((args.survey_dir / league / "pages").glob("*.json"))
        if args.max_pages_per_league:
            sources = sources[:args.max_pages_per_league]
        for source in sources:
            frame = read_image(source.with_suffix(".png"))
            ocr = recognize_roi(tasker, frame, (0, 190, 1280, 480))
            observed = read_page(frame, ocr, catalog,
                                 retry_ocr=lambda roi: recognize_roi(tasker, frame, roi))
            expected = json.loads(source.read_text(encoding="utf-8"))
            pages += 1
            for card in expected:
                cards += 1
                nearby = next((item for item in observed if item["card"][:2] == card["card"][:2]), None)
                wanted = (card["values"]["vehicle"] or {}).get("id")
                found = (nearby["vehicle"] or {}).get("id") if nearby else None
                if wanted == found:
                    correct += 1
                else:
                    problems.append({"page": str(source), "card": card["card"],
                                     "expected": wanted, "observed": found})
        print(json.dumps({"league": league, "pages": pages, "cards": cards, "correct": correct},
                         ensure_ascii=False), flush=True)
    print(json.dumps({"pages": pages, "cards": cards, "correct": correct,
                      "problems": problems}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
