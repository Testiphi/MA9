"""Read stored multiplayer list/detail screenshots with Maa OCR.

This is an offline probe: it never sends input to the game. The fixed regions are
only for the detail layout and are deliberately kept separate from list scanning.
"""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import json
import os
import re
import shutil
import unicodedata
from pathlib import Path

import cv2
import numpy as np
from maa.controller import AdbController
from maa.pipeline import JOCR, JRecognitionType
from maa.resource import Resource
from maa.tasker import Tasker

from vehicle_card_locator import detect_list_cards, normalize_list_image


DETAIL_ROIS = {
    "name": (160, 115, 520, 135),
    "performance": (1230, 165, 360, 100),
    "blueprints": (252, 237, 390, 90),
    "fuel": (690, 935, 390, 105),
}

LIST_CARD_ROIS = {
    "name": (305, 122, 135, 52),
    "performance": (5, 25, 250, 58),
    "blueprints": (320, 165, 130, 52),
    "fuel": (8, 177, 90, 48),
}

LEAGUES = ("青铜", "白银", "黄金", "白金", "翡翠", "钻石", "精英", "宗师", "传奇")
LEAGUE_CENTERS = (560, 616, 671, 727, 782, 837, 893, 948, 1003)


def selected_league(image: np.ndarray) -> str | None:
    """Read the pink underline from the normalized multiplayer selection screen."""
    if image.shape[:2] != (720, 1280):
        return None
    matches = []
    for label, x in zip(LEAGUES, LEAGUE_CENTERS):
        blue, green, red = map(int, image[132, x])
        if red >= 190 and green < 80 and blue >= 55:
            matches.append(label)
    return matches[0] if len(matches) == 1 else None


def parse_fraction(text: str) -> tuple[int, int] | None:
    """Accept OCR punctuation noise but reject impossible numerator/denominator."""
    normalized = text.replace("，", ",").replace("．", ".")
    match = re.search(r"([\d,.]+)\s*[/／]\s*([\d,.]+)", normalized)
    if not match:
        return None
    try:
        current, limit = (int(part.replace(",", "").replace(".", "")) for part in match.groups())
    except ValueError:
        return None
    return (current, limit) if limit > 0 and 0 <= current <= limit else None


def match_catalog(ocr: list[dict], catalog: list[dict], league: str | None = None) -> dict | None:
    parts = [item["text"] for item in sorted(ocr, key=lambda item: item["box"][1])
             if item["confidence"] >= 0.7 and re.search(r"[A-Za-z0-9]", item["text"])]
    observed = re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", " ".join(parts)).casefold())
    if not observed:
        return None
    # The stylized Praga wordmark is consistently read as "Proqo" by OCR.
    observed = {"proqor1": "pragar1"}.get(observed, observed)
    scored = sorted(((SequenceMatcher(None, observed, re.sub(r"[^a-z0-9]", "", car["title"].casefold())).ratio(), car)
                     for car in catalog), key=lambda pair: pair[0], reverse=True)
    score, car = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    if score < 0.78 or score - runner_up < 0.05:
        # Some in-game cards show only a short model name. Accept a catalog
        # prefix only when the selected league leaves exactly one candidate.
        if league is None or len(observed) < 6:
            return None
        candidates = [item for item in catalog
                      if item["league"] == league and
                      re.sub(r"[^a-z0-9]", "", item["title"].casefold()).startswith(observed)]
        if len(candidates) != 1:
            return None
        car = candidates[0]
        score = 0.8
    return {"id": car["id"], "name": car["title"], "class": car["class"],
            "catalog_league": car["league"], "confidence": round(score, 3)}


def count_stars(image: np.ndarray) -> tuple[int | None, int | None]:
    """Calibrated detail star row; returns unknown if its pattern is inconsistent."""
    height, width = image.shape[:2]
    lit = slots = 0
    for index in range(6):
        x = round((180 + 24 * index) * width / 1280)
        y = round(95 * height / 720)
        b, g, r = map(int, image[y, x])
        gold = r >= 190 and g >= 150 and b < 150
        gray = 75 <= r <= 180 and max(abs(r - g), abs(g - b)) < 20
        if not (gold or gray):
            break
        slots += 1
        lit += int(gold)
    return (lit, slots) if slots >= 3 else (None, None)


def card_upgrade_state(image: np.ndarray, card: tuple[int, int, int, int]) -> bool | None:
    """Blue and gold list-card backgrounds are distinct; ambiguous pixels stay unknown."""
    x, y, width, height = card
    if width < 350 or height < 190:
        return None
    patch = image[y + round(height * .91):y + round(height * .95),
                  x + round(width * .35):x + round(width * .45)]
    if patch.size == 0:
        return None
    hue = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)[:, :, 0]
    saturation = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)[:, :, 1]
    gold = float(np.mean((hue >= 8) & (hue <= 42) & (saturation >= 75)))
    blue = float(np.mean((hue >= 85) & (hue <= 130) & (saturation >= 60)))
    if gold >= .7:
        return True
    if blue >= .7:
        return False
    return None


def read_list_card(path: Path, tasker: Tasker, catalog: list[dict], card: tuple[int, int, int, int],
                   image: np.ndarray | None = None) -> dict:
    image = normalize_list_image(read_image(path) if image is None else image)
    x, y, width, height = card
    if width < 350 or height < 190:
        raise ValueError("card must be sufficiently visible for calibrated field regions")
    fields = {key: recognize_roi(tasker, image, (x + roi[0], y + roi[1], roi[2], roi[3]))
              for key, roi in LIST_CARD_ROIS.items()}
    values = {key: next((list(pair) for item in fields[key] if (pair := parse_fraction(item["text"]))), None)
              for key in ("performance", "blueprints", "fuel")}
    # A lost leading digit in a high-tier performance score must not become
    # a believable value such as 972/4020.
    league = selected_league(image)
    performance = values["performance"]
    if performance and league in LEAGUES[3:] and performance[0] < 1000 and performance[1] >= 2000:
        values["performance"] = None
    values.update({"vehicle": match_catalog(fields["name"], catalog, league),
                   "blueprint_maxed": (True if any("最高" in item["text"] for item in fields["blueprints"])
                                       else False if values["blueprints"] else None),
                   "fully_upgraded": card_upgrade_state(image, card)})
    return {"source": str(path), "screen": "list", "card": list(card), "values": values, "ocr": fields}


def read_image(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(path.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"could not read {path}")
    return image


def scale_roi(roi: tuple[int, int, int, int], shape: tuple[int, ...]) -> tuple[int, int, int, int]:
    height, width = shape[:2]
    return tuple(round(value * scale) for value, scale in zip(roi, (width / 1920, height / 1080) * 2))


def recognize_roi(tasker: Tasker, image: np.ndarray, roi: tuple[int, int, int, int]) -> list[dict]:
    job = tasker.post_recognition(JRecognitionType.OCR, JOCR(roi=roi), image)
    job.get(wait=True)
    detail = tasker.get_task_detail(job.job_id)
    if not detail:
        return []
    matches: list[dict] = []
    for node in detail.nodes:
        result = node.recognition
        if not result:
            continue
        for item in result.all_results or []:
            matches.append({"text": item.text, "confidence": round(float(item.score), 3), "box": list(item.box)})
    return matches


def read_detail(path: Path, tasker: Tasker, catalog: list[dict]) -> dict:
    image = read_image(path)
    if image.shape[1] / image.shape[0] < 1.7:
        raise ValueError("detail probe expects the 16:9 multiplayer layout")
    fields = {key: recognize_roi(tasker, image, scale_roi(roi, image.shape)) for key, roi in DETAIL_ROIS.items()}
    values = {}
    for key in ("performance", "blueprints", "fuel"):
        values[key] = next((list(pair) for match in fields[key] if (pair := parse_fraction(match["text"]))), None)
    if values["performance"] is None:
        numbers = [int(m.group().replace(",", "")) for item in fields["performance"]
                   if (m := re.search(r"\d[\d,]*", item["text"]))]
        values["performance"] = [numbers[0], None] if numbers else None
    stars_lit, star_slots = count_stars(image)
    values.update({
        "vehicle": match_catalog(fields["name"], catalog),
        "stars_lit": stars_lit,
        "star_slots": star_slots,
        "blueprint_maxed": (True if any("最高" in match["text"] for match in fields["blueprints"])
                              else False if values["blueprints"] else None),
        "fully_upgraded": None,  # Detail has no reliable independent gold-card cue.
    })
    return {"source": str(path), "screen": "detail", "values": values, "ocr": fields}


def make_tasker(resource_path: Path, adb_path: Path, address: str) -> Tasker:
    resource = Resource()
    resource.post_bundle(resource_path).wait()
    if not resource.loaded:
        raise RuntimeError(f"failed to load Maa resource {resource_path}")
    controller = AdbController(adb_path, address)
    connection = controller.post_connection().wait()
    if not connection.succeeded:
        raise RuntimeError(f"could not connect to ADB at {address} with {adb_path}")
    tasker = Tasker()
    if not tasker.bind(resource, controller) or not tasker.inited:
        raise RuntimeError("failed to bind Maa OCR tasker")
    return tasker


def write_annotated_list(image: np.ndarray, reports: list[dict], destination: Path) -> None:
    canvas = normalize_list_image(image).copy()
    for report in reports:
        x, y, width, height = report["card"]
        values = report["values"]
        vehicle = values["vehicle"]
        color = (0, 220, 0) if vehicle else (0, 0, 255)
        label = vehicle["name"] if vehicle else "unknown"
        fuel = "/".join(map(str, values["fuel"])) if values["fuel"] else "?"
        blueprints = "/".join(map(str, values["blueprints"])) if values["blueprints"] else "max" if values["blueprint_maxed"] else "?"
        upgrade = "gold" if values["fully_upgraded"] is True else "blue" if values["fully_upgraded"] is False else "?"
        cv2.rectangle(canvas, (x, y), (x + width, y + height), color, 2)
        overlay = canvas.copy()
        cv2.rectangle(overlay, (x + 2, y + 2), (x + width - 2, y + 42), (5, 12, 25), -1)
        cv2.addWeighted(overlay, .8, canvas, .2, 0, canvas)
        cv2.putText(canvas, label[:48], (x + 7, y + 17), cv2.FONT_HERSHEY_SIMPLEX,
                    0.43, color, 1, cv2.LINE_AA)
        cv2.putText(canvas, f"fuel {fuel} | BP {blueprints} | {upgrade}", (x + 7, y + 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.43, color, 1, cv2.LINE_AA)
    destination.parent.mkdir(parents=True, exist_ok=True)
    extension = destination.suffix or ".png"
    success, encoded = cv2.imencode(extension, canvas)
    if not success:
        raise ValueError(f"could not encode annotation {destination}")
    destination.write_bytes(encoded.tobytes())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, nargs="+")
    parser.add_argument("--screen", choices=("detail", "list"), default="detail")
    parser.add_argument("--card", type=int, nargs=4, metavar=("X", "Y", "W", "H"),
                        help="optional manual card override; list mode auto-detects all complete cards")
    parser.add_argument("--adb", type=Path, help="ADB executable; overrides local config and MA9_ADB_PATH")
    parser.add_argument("--address", help="ADB device address; overrides local config and MA9_ADB_ADDRESS")
    parser.add_argument("--output", type=Path, help="write UTF-8 JSON to this path instead of stdout")
    parser.add_argument("--annotate-dir", type=Path, help="save list screenshots with detected card boxes")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    local_config_path = root / "debug/vehicle_scan_env.json"
    local_config = json.loads(local_config_path.read_text(encoding="utf-8")) if local_config_path.is_file() else {}
    adb_value = args.adb or os.environ.get("MA9_ADB_PATH") or local_config.get("adb_path") or shutil.which("adb")
    if not adb_value or not Path(adb_value).is_file():
        parser.error("ADB not found; set --adb, MA9_ADB_PATH, or debug/vehicle_scan_env.json")
    address = args.address or os.environ.get("MA9_ADB_ADDRESS") or local_config.get("address", "127.0.0.1:16384")
    tasker = make_tasker(root / "assets/resource", Path(adb_value), address)
    catalog = json.loads((root / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))["vehicles"]
    reports = []
    for index, path in enumerate(args.image, start=1):
        if args.screen == "detail":
            reports.append(read_detail(path, tasker, catalog))
            continue
        image = normalize_list_image(read_image(path))
        cards = [tuple(args.card)] if args.card else detect_list_cards(image)
        if not cards:
            raise ValueError(f"no complete car cards found in {path}")
        page_reports = [read_list_card(path, tasker, catalog, card, image) for card in cards]
        reports.extend(page_reports)
        if args.annotate_dir:
            write_annotated_list(image, page_reports, args.annotate_dir / f"{index:03d}_{path.stem}.png")
    output = json.dumps(reports, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"Vehicle scan report: {args.output}")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
