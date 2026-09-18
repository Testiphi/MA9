"""Capture multiplayer list pages or traverse detail pages without starting races.

Start this tool while already on the corresponding game screen. It only swipes the
selection list or clicks the detail-page left arrow. Every run has bounded input.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from probe_vehicle_fields import (make_tasker, read_detail, read_list_card,
                                  selected_league, write_annotated_list)
from vehicle_card_locator import detect_list_cards, normalize_list_image
from vehicle_scan_merge import merge_vehicle_records


ROOT = Path(__file__).resolve().parents[1]
TITLE_TEMPLATE = ROOT / "assets/resource/image/navigation/multiplayer/selection_title.png"
LEFT_TEMPLATE = ROOT / "assets/resource/image/navigation/fallback/left.png"
RIGHT_TEMPLATE = ROOT / "assets/resource/image/navigation/fallback/right.png"


def read_png(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"could not read template {path}")
    return image


def template_seen(frame: np.ndarray, template: Path, roi: tuple[int, int, int, int], threshold: float = .86) -> bool:
    x, y, width, height = roi
    sample = frame[y:y + height, x:x + width]
    needle = read_png(template)
    if sample.shape[0] < needle.shape[0] or sample.shape[1] < needle.shape[1]:
        return False
    return float(cv2.matchTemplate(sample, needle, cv2.TM_CCOEFF_NORMED).max()) >= threshold


def is_list(frame: np.ndarray) -> bool:
    return template_seen(frame, TITLE_TEMPLATE, (80, 70, 180, 80)) and bool(detect_list_cards(frame))


def is_detail(frame: np.ndarray) -> bool:
    return (template_seen(frame, LEFT_TEMPLATE, (460, 325, 75, 75)) and
            template_seen(frame, RIGHT_TEMPLATE, (1155, 325, 80, 75)))


def capture(controller, destination: Path) -> np.ndarray:
    frame = normalize_list_image(controller.post_screencap().get(wait=True))
    destination.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", frame)
    if not ok:
        raise RuntimeError("failed to encode game screenshot")
    destination.write_bytes(encoded.tobytes())
    return frame


def capture_expected(controller, destination: Path, predicate, timeout: float = 12.0) -> tuple[np.ndarray, bool]:
    deadline = time.monotonic() + timeout
    while True:
        frame = capture(controller, destination)
        if predicate(frame):
            return frame, True
        if time.monotonic() >= deadline:
            return frame, False
        time.sleep(.5)


def list_fingerprint(reports: list[dict]) -> tuple[str, ...]:
    return tuple((item["values"]["vehicle"] or {}).get("id", "?") for item in reports)


def image_distance(before: np.ndarray, after: np.ndarray) -> float:
    first = cv2.resize(cv2.cvtColor(before[190:665], cv2.COLOR_BGR2GRAY), (160, 60))
    second = cv2.resize(cv2.cvtColor(after[190:665], cv2.COLOR_BGR2GRAY), (160, 60))
    return float(np.mean(cv2.absdiff(first, second)))


def scan_list(tasker, run_dir: Path, catalog: list[dict], max_pages: int,
              expected_league: str | None = None) -> dict:
    controller = tasker.controller
    pages = []
    first_fingerprint = None
    seen_new_page = False
    unchanged = 0
    previous_frame = None
    previous_fingerprint = None
    status = "page_limit"
    for page in range(1, max_pages + 1):
        screenshot = run_dir / "pages" / f"{page:04d}.png"
        frame, ready = capture_expected(controller, screenshot, is_list)
        if not ready:
            status = "unexpected_screen"
            break
        # Swiping through the garage automatically advances the selected rank.
        # Do not count cards from the next rank as part of this rank's survey.
        if expected_league is not None and selected_league(frame) != expected_league:
            status = "league_boundary"
            break
        cards = detect_list_cards(frame)
        reports = [read_list_card(screenshot, tasker, catalog, card, frame) for card in cards]
        fingerprint = list_fingerprint(reports)
        (run_dir / "pages" / f"{page:04d}.json").write_text(
            json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_annotated_list(frame, reports, run_dir / "pages" / f"{page:04d}_annotated.png")
        pages.append({"number": page, "image": str(screenshot), "fingerprint": fingerprint,
                      "cards": len(cards), "recognized": sum(item["values"]["vehicle"] is not None for item in reports),
                      "records": reports})
        if first_fingerprint is None:
            first_fingerprint = fingerprint
        elif fingerprint != first_fingerprint:
            seen_new_page = True
        if previous_frame is not None:
            distance = image_distance(previous_frame, frame)
            if fingerprint == previous_fingerprint and distance < 3.0:
                unchanged += 1
            else:
                unchanged = 0
            pages[-1]["distance_from_previous"] = round(distance, 2)
            if unchanged >= 2:
                status = "edge_reached"
                break
            if seen_new_page and fingerprint == first_fingerprint and "?" not in fingerprint:
                # The list is linear; returning to the first page means an
                # unexpected reset, not completed coverage.
                status = "unexpected_reset"
                break
        previous_frame, previous_fingerprint = frame, fingerprint
        if page == max_pages:
            break
        if not controller.post_swipe(1000, 420, 600, 420, 320).wait().succeeded:
            status = "swipe_failed"
            break
        time.sleep(.8)
    return {"mode": "list", "status": status, "pages": pages,
            "unique_vehicle_ids": sorted({item["values"]["vehicle"]["id"]
                                         for page in pages for item in page["records"]
                                         if item["values"]["vehicle"]})}


def scan_detail(tasker, run_dir: Path, catalog: list[dict], max_cars: int) -> dict:
    controller = tasker.controller
    records = []
    first_id = None
    previous_id = None
    status = "car_limit"
    for index in range(1, max_cars + 1):
        screenshot = run_dir / "details" / f"{index:04d}.png"
        frame, ready = capture_expected(controller, screenshot, is_detail)
        if not ready:
            status = "unexpected_screen"
            break
        record = None
        current_id = None
        for attempt in range(3):
            if attempt:
                # The car-name marquee or transition can obscure the first frame.
                time.sleep(.6)
                capture(controller, screenshot)
            record = read_detail(screenshot, tasker, catalog)
            vehicle = record["values"]["vehicle"]
            current_id = vehicle["id"] if vehicle else None
            if current_id is not None and current_id != previous_id:
                break
        assert record is not None
        records.append(record)
        (run_dir / "details" / f"{index:04d}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if current_id is None:
            status = "unknown_vehicle"
            break
        if first_id is None:
            first_id = current_id
        elif current_id == previous_id:
            status = "arrow_stalled"
            break
        elif current_id == first_id:
            status = "wrapped"
            break
        previous_id = current_id
        if index == max_cars:
            break
        if not controller.post_click(495, 360).wait().succeeded:
            status = "click_failed"
            break
        time.sleep(.8)
    return {"mode": "detail", "status": status, "start_vehicle_id": first_id,
            "records": records, "unique_vehicle_ids": sorted({r["values"]["vehicle"]["id"]
                                                                  for r in records if r["values"]["vehicle"]})}


def enter_detail_from_last_page(tasker, listing: dict, run_dir: Path, catalog: list[dict]) -> dict:
    """Click only a recognized, complete card's left-side body."""
    if not listing["pages"] or listing["status"] in {"unexpected_screen", "swipe_failed"}:
        return {"status": "list_not_ready"}
    last_page = listing["pages"][-1]
    candidate = next((item for item in last_page["records"] if item["values"]["vehicle"]), None)
    if candidate is None:
        return {"status": "no_recognized_card"}
    x, y, width, height = candidate["card"]
    target = (x + round(width * .30), y + round(height * .55))
    controller = tasker.controller
    frame = normalize_list_image(controller.post_screencap().get(wait=True))
    if not is_list(frame) or tuple(candidate["card"]) not in detect_list_cards(frame):
        return {"status": "list_changed"}
    if not controller.post_click(*target).wait().succeeded:
        return {"status": "click_failed", "target": target}
    entry_image = run_dir / "entry_detail.png"
    _, ready = capture_expected(controller, entry_image, is_detail, timeout=20)
    expected_id = candidate["values"]["vehicle"]["id"]
    if not ready:
        return {"status": "detail_not_ready", "target": target, "vehicle_id": expected_id}
    recognized = read_detail(entry_image, tasker, catalog)["values"]["vehicle"]
    if not recognized or recognized["id"] != expected_id:
        return {"status": "entry_mismatch", "target": target, "vehicle_id": expected_id,
                "recognized_vehicle_id": recognized["id"] if recognized else None}
    return {"status": "entered", "target": target, "vehicle_id": expected_id}


def collected_records(report: dict) -> list[dict]:
    if report["mode"] == "list":
        return [item for page in report["pages"] for item in page["records"]]
    if report["mode"] == "detail":
        return list(report["records"])
    return collected_records(report["list"]) + collected_records(report["detail"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("list", "detail", "both"))
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--max-cars", type=int, default=3)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if not 1 <= args.max_pages <= 100 or not 1 <= args.max_cars <= 400:
        parser.error("max-pages must be 1..100 and max-cars 1..400")
    env_path = ROOT / "debug/vehicle_scan_env.json"
    if not env_path.is_file():
        parser.error(f"missing local ADB config: {env_path}")
    connection = json.loads(env_path.read_text(encoding="utf-8"))
    tasker = make_tasker(ROOT / "assets/resource", Path(connection["adb_path"]), connection["address"])
    catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))["vehicles"]
    run_dir = args.output_dir or ROOT / "debug/vehicle_scans" / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    if args.mode == "list":
        report = scan_list(tasker, run_dir, catalog, args.max_pages)
    elif args.mode == "detail":
        report = scan_detail(tasker, run_dir, catalog, args.max_cars)
    else:
        listing = scan_list(tasker, run_dir, catalog, args.max_pages)
        entry = enter_detail_from_last_page(tasker, listing, run_dir, catalog)
        detail = (scan_detail(tasker, run_dir, catalog, args.max_cars) if entry["status"] == "entered"
                  else {"mode": "detail", "status": "not_started", "records": [], "unique_vehicle_ids": []})
        completed_range = (listing["status"] == "edge_reached" and detail["status"] == "wrapped")
        status = ("completed_current_range" if completed_range else
                  "partial" if entry["status"] == "entered" else entry["status"])
        report = {"mode": "both", "status": status,
                  "list": listing, "entry": entry, "detail": detail}
    report["created_at"] = datetime.now().isoformat(timespec="seconds")
    merged = merge_vehicle_records(collected_records(report))
    (run_dir / "vehicles.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "mode": args.mode,
                      "list_status": report["list"]["status"] if args.mode == "both" else None,
                      "detail_status": report["detail"]["status"] if args.mode == "both" else None,
                      "observations": len(collected_records(report)),
                      "unique_vehicles": len(merged["vehicles"]), "output_dir": str(run_dir)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
