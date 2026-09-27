"""Bounded, browse-only Duel garage traversal from a user-opened selection list."""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from uuid import uuid4

import cv2
from maa.pipeline import JRecognitionType

from .duel_garage_profile import CLASSES, atomic_json, load_profile, merge_class, timestamp
from .duel_vehicle_runtime import CLASS_X, EDGE_REPOSITION_SWIPE, scan


PAGE_SWIPE = (1090, 480, 400, 480, 300)


def _safe(root: Path, relative: str) -> Path:
    """Reject filesystem redirection, including a junction that stays in root."""
    path = root
    for part in Path(relative).parts:
        if part in ("..", ".") or Path(part).is_absolute():
            raise ValueError("invalid survey path")
        path = path / part
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                raise ValueError(f"redirected survey path: {path}")
    if not path.resolve().is_relative_to(root):
        raise ValueError("survey path escapes runtime root")
    return path


def load_survey(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], Path]:
    """Validate every persistent input before device capture or navigation."""
    root = Path(root).absolute()
    if root.is_symlink() or root.resolve() != root:
        raise ValueError("runtime root must be a real absolute directory")
    marker = _safe(root, ".ma9-portable-root")
    config_path = _safe(root, "config/duel_garage_scan.json")
    catalog_path = _safe(root, "data/generated/vehicle_catalog.json")
    profile_path = _safe(root, "config/duel_garage.json")
    _safe(root, "config/.duel-garage-scan.lock")
    _safe(root, "debug")
    if not marker.is_file():
        raise ValueError("Duel survey requires a portable runtime marker")
    request = json.loads(config_path.read_text(encoding="utf-8-sig"))
    if (not isinstance(request, dict) or type(request.get("schema_version")) is not int
            or request["schema_version"] != 1
            or request.get("runtime_root") != str(root)
            or not isinstance(request.get("account_key"), str)
            or not request["account_key"].strip()
            or request.get("account_confirmed") is not True
            or request.get("navigation_confirmed") is not True
            or request.get("purpose") != "duel_garage_inventory"
            or request.get("classes") != list(CLASSES)):
        raise ValueError("invalid Duel garage survey request")
    max_pages = request.get("max_pages", 30)
    if type(max_pages) is not int or not 1 <= max_pages <= 50:
        raise ValueError("max_pages must be an integer from 1 to 50")
    request["max_pages"] = max_pages
    raw = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    if (not isinstance(raw, dict) or type(raw.get("schema_version")) is not int
            or raw["schema_version"] != 1 or not isinstance(raw.get("vehicles"), list)):
        raise ValueError("invalid portable vehicle catalog")
    catalog = raw["vehicles"]
    ids: set[str] = set()
    for row in catalog:
        if (not isinstance(row, dict) or not isinstance(row.get("id"), str)
                or not row["id"] or row["id"] in ids
                or not isinstance(row.get("title"), str) or not row["title"]
                or row.get("class") not in CLASSES):
            raise ValueError("invalid portable catalog vehicle")
        ids.add(row["id"])
    load_profile(profile_path, root, request["account_key"], {row["id"]: row for row in catalog})
    return request, catalog, profile_path


class _CaptureJob:
    def __init__(self, job: Any, proxy: "_SurveyContext") -> None:
        self.job, self.proxy = job, proxy

    def get(self, *, wait: bool = True) -> Any:
        if wait is not True:
            raise ValueError("survey capture must wait")
        frame = self.job.get(wait=True)
        self.proxy.save_frame(frame)
        return frame


class _Controller:
    def __init__(self, source: Any, proxy: "_SurveyContext") -> None:
        self.source, self.proxy = source, proxy

    def post_screencap(self) -> _CaptureJob:
        self.proxy.budget("capture")
        return _CaptureJob(self.source.post_screencap(), self.proxy)

    def post_click(self, x: int, y: int) -> Any:
        args = (x, y)
        typed = all(type(value) is int for value in args)
        allowed = (typed and self.proxy.active_class is not None
                   and args == (CLASS_X[self.proxy.active_class], 103))
        self.proxy.input_attempt("click", args, allowed)
        if not allowed:
            raise PermissionError("survey forbids this click")
        self.proxy.budget("input")
        return self.source.post_click(x, y)

    def post_swipe(self, *args: int) -> Any:
        typed = all(type(value) is int for value in args)
        allowed = (typed and self.proxy.active_class is not None
                   and args in (PAGE_SWIPE, EDGE_REPOSITION_SWIPE))
        self.proxy.input_attempt("swipe", args, allowed)
        if not allowed:
            raise PermissionError("survey forbids this swipe")
        self.proxy.budget("input")
        return self.source.post_swipe(*args)

    def __getattr__(self, name: str) -> Any:
        raise PermissionError(f"survey forbids controller.{name}")


class _SurveyContext:
    def __init__(self, source: Any, run_dir: Path, max_pages: int) -> None:
        self.source, self.run_dir = source, run_dir
        self.active_class: str | None = None
        self.capture_count = self.input_count = 0
        self.capture_limit = 6 * max_pages * 20 + 120
        self.input_limit = 6 * (max_pages * 4 + 4)
        self.current_frame = 0
        self.tasker = SimpleNamespace(controller=_Controller(source.tasker.controller, self))
        self.inputs: list[dict[str, Any]] = []

    def budget(self, kind: str) -> None:
        if kind == "capture":
            self.capture_count += 1
            if self.capture_count > self.capture_limit:
                raise RuntimeError("survey capture budget exceeded")
        else:
            self.input_count += 1
            if self.input_count > self.input_limit:
                raise RuntimeError("survey input budget exceeded")

    def input_attempt(self, kind: str, args: tuple[int, ...], allowed: bool) -> None:
        item = {"at": timestamp(), "class": self.active_class, "kind": kind,
                "args": list(args), "allowed": allowed, "frame": self.current_frame}
        self.inputs.append(item)
        with (self.run_dir / "input_attempts.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")

    def save_frame(self, frame: Any) -> None:
        next_frame = self.current_frame + 1
        success, png = cv2.imencode(".png", frame)
        if not success:
            raise OSError("survey frame encoding failed")
        data = png.tobytes()
        name = f"{next_frame:06d}.png"
        destination = self.run_dir / "frames" / name
        with destination.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        self.current_frame = next_frame
        item = {"frame": self.current_frame, "file": f"frames/{name}",
                "sha256": hashlib.sha256(data).hexdigest(),
                "width": int(frame.shape[1]), "height": int(frame.shape[0]),
                "at": timestamp(), "class": self.active_class}
        with (self.run_dir / "frames.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")

    def run_recognition_direct(self, recognition_type: Any, params: Any, frame: Any) -> Any:
        if recognition_type != JRecognitionType.OCR:
            raise PermissionError("survey only allows direct OCR")
        result = self.source.run_recognition_direct(recognition_type, params, frame)
        words = []
        for row in result.all_results if result else []:
            words.append({"text": row.text, "confidence": float(row.score),
                          "box": list(row.box)})
        item = {"frame": self.current_frame, "class": self.active_class,
                "roi": list(params.roi), "words": words}
        with (self.run_dir / "ocr.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
        return result

    def __getattr__(self, name: str) -> Any:
        raise PermissionError(f"survey forbids context.{name}")


def _entrance_guard(proxy: _SurveyContext) -> bool:
    from .selection_runtime import _frame, _ocr
    for _ in range(2):
        frame = _frame(proxy)
        words = _ocr(proxy, frame, (20, 55, 740, 95))
        height, width = frame.shape[:2]
        def valid(row: dict[str, Any], top: int, bottom: int) -> bool:
            box = row.get("box")
            confidence = row.get("confidence")
            return (isinstance(box, list) and len(box) == 4
                    and all(type(value) in (int, float) and math.isfinite(value) for value in box)
                    and box[2] > 0 and box[3] > 0
                    and 35 <= box[0] <= 450 and top <= box[1] <= bottom
                    and 20 <= box[0] and 55 <= box[1]
                    and box[0] + box[2] <= min(width, 760)
                    and box[1] + box[3] <= min(height, 150)
                    and type(confidence) in (int, float)
                    and math.isfinite(confidence) and .85 <= confidence <= 1)
        title = any(row.get("text", "").replace(" ", "") == "车辆选择"
                    and valid(row, 60, 100) for row in words)
        subtitle = any("赛道选择车辆" in row.get("text", "").replace(" ", "")
                       and valid(row, 100, 140) for row in words)
        if not title or not subtitle:
            return False
    return True


def _review_text(report: dict[str, Any], profile: dict[str, Any]) -> str:
    lines = ["# 擂台车库扫描复核", "", f"状态：{report['status']}",
             f"账号标签：{report['account_key']}（用户确认，非视觉认证）", "",
             "遍历完成不等于账号车库完整。左侧栏缺口、可选列表与拥有关系、星级均需复核。",
             "本档案不能供完整分配器使用。", "", "## 分类遍历", ""]
    for vehicle_class in CLASSES:
        item = report["classes"].get(vehicle_class)
        if item is None:
            lines.append(f"- {vehicle_class}: 未扫描")
        else:
            lines.append(f"- {vehicle_class}: {item['status']}；页数 {item['pages']}；识别 {item['vehicles']}")
    lines += ["", "## 已记录车辆", ""]
    for vehicle_id, entry in sorted(profile["vehicles"].items(),
                                    key=lambda item: (CLASSES.index(item[1]["class"]), item[1]["title"])):
        readings = entry.get("star_observations", [])
        latest = readings[-1] if readings else None
        raw = (f"{latest.get('stars_lit')}/{latest.get('star_slots')}"
               if latest and latest.get("stars_lit") is not None else "无读数")
        ownership = ("手工记录" if entry.get("ownership_source") == "manual"
                     else "列表可见，拥有待核验")
        lines.append(f"- {entry['class']} {entry['title']} ({vehicle_id})：{ownership}；"
                     f"列表原始星级 {raw}（未确认）；"
                     f"证据 {latest.get('evidence') if latest else '既有档案'}")
    lines += ["", "## 待复核", "", "- 核验 EVO37 左缘/侧栏及每类可见范围。",
              "- 核验擂台可选列表是否严格等于此账号拥有车辆。",
              "- 用重复稳定画面或详情逐车核验星级；空读数不可视为零星。", ""]
    return "\n".join(lines)


def run_garage_survey(context: Any, root: Path, *,
                      scan_fn: Callable[..., dict[str, Any]] = scan) -> tuple[dict[str, Any], Path]:
    """Collect all six classes, retaining partial evidence on a failed class."""
    root = Path(root).absolute()
    request, catalog, profile_path = load_survey(root)
    by_id = {row["id"]: row for row in catalog}
    run_id = uuid4().hex
    run_dir = _safe(root, f"debug/duel-garage-{run_id}")
    lock = _safe(root, "config/.duel-garage-scan.lock")
    token = uuid4().hex
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(token)
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
        (run_dir / "frames").mkdir()
        profile = load_profile(profile_path, root, request["account_key"], by_id)
        proxy = _SurveyContext(context, run_dir, request["max_pages"])
        report: dict[str, Any] = {
            "schema_version": 1, "run_id": run_id, "runtime_root": str(root),
            "account_key": request["account_key"], "status": "partial",
            "classes": {}, "traversal_finished": False, "coverage_complete": False,
            "allocation_ready": False, "browse_only": True,
            "navigation_attempted": False, "selection_attempted": False,
            "starts_race": False, "known_gaps": profile["known_gaps"],
            "started_at": timestamp(), "report_file": str(run_dir / "report.json"),
            "profile_file": str(profile_path), "unique_vehicle_count": len(profile["vehicles"]),
        }
        try:
            if not _entrance_guard(proxy):
                report["status"] = "rejected"
                report["reason"] = "two_frame_duel_selection_guard_failed"
            else:
                for vehicle_class in CLASSES:
                    proxy.active_class = vehicle_class
                    result = scan_fn(proxy, vehicle_class, catalog, target_id=None,
                                     choose=False, max_pages=request["max_pages"])
                    observed_at = timestamp()
                    checkpoint = f"debug/duel-garage-{run_id}/checkpoint-{vehicle_class}.json"
                    atomic_json(run_dir / f"checkpoint-{vehicle_class}.json", result)
                    merge_class(profile, vehicle_class, result, by_id, run_id,
                                observed_at, checkpoint)
                    atomic_json(profile_path, profile)
                    summary = {"status": result.get("status"), "pages": result.get("pages"),
                               "claimed_scan_complete": result.get("scan_complete") is True,
                               "vehicles": len(result.get("vehicles", [])),
                               "checkpoint": checkpoint}
                    report["classes"][vehicle_class] = summary
                    if (result.get("status") not in ("class_boundary", "edge_reached")
                            or result.get("scan_complete") is not True):
                        report["reason"] = f"{vehicle_class}:{result.get('status')}"
                        break
                else:
                    report["status"] = "review_required"
                    report["traversal_finished"] = True
        except Exception as error:
            report["status"] = "partial"
            report["reason"] = f"{type(error).__name__}: {error}"
        finally:
            report["input_attempts"] = proxy.inputs
            report["navigation_attempt_count"] = sum(
                item["allowed"] and item["kind"] in ("click", "swipe")
                for item in proxy.inputs)
            report["navigation_attempted"] = any(
                item["allowed"] and item["kind"] in ("click", "swipe")
                for item in proxy.inputs)
            report["unique_vehicle_count"] = len(profile["vehicles"])
            report["captures"] = proxy.current_frame
            report["capture_attempts"] = proxy.capture_count
            report["finished_at"] = timestamp()
            atomic_json(run_dir / "report.json", report)
            (run_dir / "review.md").write_text(_review_text(report, profile), encoding="utf-8")
        return report, run_dir / "report.json"
    finally:
        if lock.exists() and lock.read_text(encoding="utf-8") == token:
            lock.unlink()
