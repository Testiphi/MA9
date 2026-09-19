"""MaaFramework Agent entry actions for the incremental runtime migration."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from ma9_agent.runtime_config import RuntimeConfig
from ma9_agent.garage_profile import load_profile, owned_vehicle_ids
from ma9_agent.vehicle_recognizer import available_candidates, recognize_visible
from ma9_agent.selection_runtime import select_recommended
from ma9_agent.vehicle_location_test import run_location_test
from ma9_agent.duel_map_screen import read_five_tracks
from ma9_agent.duel_vehicle_runtime import scan as scan_duel_vehicles
from ma9_agent.duel_defense_setup import run_defense_setup
from ma9_agent.account_conflict import account_conflict_from_ocr
from ma9_agent.selection_runtime import _frame, _ocr


@AgentServer.custom_action("ma9_account_conflict_diagnose")
class AccountConflictDiagnoseAction(CustomAction):
    """Recognize another-device login and leave recovery to the caller."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        del argv
        root = find_project_root()
        frame = _frame(context)
        report = account_conflict_from_ocr(_ocr(context, frame, (140, 200, 1000, 330)))
        destination = root / "debug/account_conflict_live.json"
        destination.parent.mkdir(exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"event": "ma9_account_conflict", **report}, ensure_ascii=False), flush=True)
        return report["detected"]


def find_project_root() -> Path:
    configured = os.environ.get("MA9_PROJECT_ROOT")
    if configured:
        root = Path(configured).resolve()
        if (root / "data/multiplayer_profile.json").is_file():
            return root
        raise FileNotFoundError(f"MA9_PROJECT_ROOT does not contain runtime data: {root}")
    candidates: list[Path] = []
    for start in (Path.cwd(), Path(sys.executable).resolve().parent,
                  Path(__file__).resolve().parent):
        candidates.extend((start, *start.parents))
    candidates = list(dict.fromkeys(candidates))
    valid = [path for path in candidates if (path / "data/multiplayer_profile.json").is_file()]
    # During local development the distributable lives in MA9/install while the
    # account strategy remains in MA9/config. Prefer the same account root as GUI.
    for candidate in valid:
        if (candidate / "config/garage.json").is_file():
            return candidate
    if valid:
        return valid[0]
    raise FileNotFoundError("cannot locate MA9 runtime data; set MA9_PROJECT_ROOT")


@AgentServer.custom_action("ma9_runtime_validate")
class RuntimeValidateAction(CustomAction):
    """Validate data sources before the runtime controller takes over a task."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        del context
        config = RuntimeConfig.load(find_project_root())
        params = json.loads(argv.custom_action_param or "null")
        print(
            json.dumps(
                {
                    "event": "ma9_runtime_validated",
                    "params": params,
                    **config.summary(),
                },
                ensure_ascii=False,
            )
        )
        return True


@AgentServer.custom_action("ma9_selection_diagnose")
class SelectionDiagnoseAction(CustomAction):
    """Read one game frame and report the selection/detail state without input."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        del argv
        frame = context.tasker.controller.post_screencap().get(wait=True)
        checks = {
            "selection_owned_on": "多人准备_仅拥有已开启",
            "selection_owned_off": "多人准备_开启仅拥有",
            "detail_touchdrive_on_start_visible": "TouchDrive_已开启",
        }
        hits = {}
        for label, node in checks.items():
            result = context.run_recognition(node, frame)
            hits[label] = bool(result and result.hit)
        if hits["selection_owned_on"] and not hits["selection_owned_off"]:
            state = "selection_owned_on"
        elif hits["selection_owned_off"] and not hits["selection_owned_on"]:
            state = "selection_owned_off"
        elif hits["detail_touchdrive_on_start_visible"]:
            state = "detail_ready"
        else:
            state = "unknown"
        report = {
            "event": "ma9_selection_diagnosis",
            "time": datetime.now().isoformat(timespec="seconds"),
            "state": state,
            "checks": hits,
            "image_size": [int(frame.shape[1]), int(frame.shape[0])],
        }
        destination = find_project_root() / "debug" / "selection_diagnostic.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False), flush=True)
        return state != "unknown"


@AgentServer.custom_action("ma9_vehicle_recognize")
class VehicleRecognizeAction(CustomAction):
    """List visible recommended vehicles without clicking or inferring fuel."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        del argv
        config = RuntimeConfig.load(find_project_root())
        frame = context.tasker.controller.post_screencap().get(wait=True)
        states = {
            "owned_on": "多人准备_仅拥有已开启",
            "owned_off": "多人准备_开启仅拥有",
        }
        matched = {key: bool((result := context.run_recognition(node, frame)) and result.hit)
                   for key, node in states.items()}
        state = "owned_on" if matched["owned_on"] else "owned_off" if matched["owned_off"] else "unknown"
        garage_path = config.project_root / "config/garage.json"
        garage = load_profile(garage_path) if garage_path.is_file() else None
        owned_ids = owned_vehicle_ids(garage) if garage is not None else None
        candidates, missing = available_candidates(config.project_root, config.rotation, owned_ids)
        visible = recognize_visible(context, frame, candidates) if state != "unknown" else []
        report = {
            "event": "ma9_visible_vehicles",
            "time": datetime.now().isoformat(timespec="seconds"),
            "state": state,
            "visible": visible,
            "template_count": len(candidates),
            "garage_filter": "owned_profile" if garage is not None else "none",
            "garage_owned_count": len(owned_ids) if owned_ids is not None else None,
            "missing_template_count": len(missing),
            "missing_templates": missing,
            "note": "Only names and positions are recognized; ownership, fuel, and eligibility require separate checks.",
        }
        destination = config.project_root / "debug" / "vehicle_recognition.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False), flush=True)
        return state != "unknown"


@AgentServer.custom_action("ma9_select_recommended")
class SelectRecommendedAction(CustomAction):
    """Apply the account's full priority list with OCR, then resume the loop."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        config = RuntimeConfig.load(find_project_root())
        if config.selection_strategy is None:
            return False
        params = json.loads(argv.custom_action_param or "{}")
        player_league = params["player_league"]
        catalog = json.loads((config.project_root / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))
        result = select_recommended(context, config.project_root, player_league,
                                    catalog, config.rotation, config.selection_strategy)
        prefix = argv.node_name.removesuffix("推荐选车入口")
        round_prefix = prefix.split("服务器恢复", 1)[0]
        server_close = round_prefix + "服务器错误关闭"
        if result["status"] not in {"selected", "fallback"}:
            frame = context.tasker.controller.post_screencap().get(wait=True)
            server = context.run_recognition(server_close, frame)
            if server and server.hit:
                result["status"] = "server_error"
        destination = config.project_root / "debug" / "selection_runtime.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"event": "ma9_selection_runtime", **result}, ensure_ascii=False), flush=True)
        interrupts = [round_prefix + "广告关闭", server_close]
        if result["status"] == "server_error":
            return context.override_next(argv.node_name, [server_close])
        if result["status"] == "selected":
            return context.override_next(argv.node_name,
                                         [*interrupts, prefix + "确认准备并开始",
                                          prefix + "原地开启TouchDrive"])
        if result["status"] == "fallback":
            return context.override_next(argv.node_name, [*interrupts, prefix + "倒序兜底_入口"])
        return False


@AgentServer.custom_action("ma9_vehicle_location_test")
class VehicleLocationTestAction(CustomAction):
    """Locate one chosen car and stop on its details without starting a race."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        del argv
        root = find_project_root()
        request_path = root / "config/vehicle_search_test.json"
        request = json.loads(request_path.read_text(encoding="utf-8"))
        catalog = json.loads((root / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))
        rotation = json.loads((root / "data/generated/champion_rotation.json").read_text(encoding="utf-8"))
        garage = load_profile(root / "config/garage.json")
        report = run_location_test(context, catalog, rotation, garage, request)
        destination = root / "debug/vehicle_location_test.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"event": "ma9_vehicle_location_test", **report}, ensure_ascii=False), flush=True)
        return report["status"] == "found"


@AgentServer.custom_action("ma9_duel_read_tracks")
class DuelReadTracksAction(CustomAction):
    """Read all five ordered map pairs from the current lineup without input."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        del argv
        root = find_project_root()
        reference = json.loads((root / "data/generated/duel_auto_candidates.json").read_text(encoding="utf-8"))
        report = read_five_tracks(_ocr(context, _frame(context), (55, 165, 1190, 160)), reference)
        destination = root / "debug/duel_tracks_live.json"
        destination.parent.mkdir(exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"event": "ma9_duel_tracks", **report}, ensure_ascii=False), flush=True)
        return report["complete"]


@AgentServer.custom_action("ma9_duel_vehicle_scan")
class DuelVehicleScanAction(CustomAction):
    """Scan one Duel class, optionally opening or assigning a named vehicle."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        root = find_project_root()
        params = json.loads(argv.custom_action_param or "{}")
        if params.get("request_file"):
            request_path = (root / "config" / params["request_file"]).resolve()
            if request_path.parent != (root / "config").resolve():
                raise ValueError("Duel request must be a file in config")
            params = json.loads(request_path.read_text(encoding="utf-8"))
        catalog = json.loads((root / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))
        report = scan_duel_vehicles(context, params.get("class", "D"), catalog["vehicles"],
                                    target_id=params.get("vehicle_id"),
                                    choose=params.get("choose", False),
                                    max_pages=params.get("max_pages", 25),
                                    expected_performance=params.get("performance"),
                                    expected_stars=params.get("stars"))
        destination = root / "debug/duel_vehicle_scan_live.json"
        destination.parent.mkdir(exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"event": "ma9_duel_vehicle_scan", **report}, ensure_ascii=False), flush=True)
        return report["status"] in {"edge_reached", "class_boundary", "detail_verified", "assigned"}


@AgentServer.custom_action("ma9_duel_defense_setup")
class DuelDefenseSetupAction(CustomAction):
    """Plan or assign all five qualification-defense cars without starting."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        params = json.loads(argv.custom_action_param or "{}")
        try:
            report = run_defense_setup(context, find_project_root(), params)
        except Exception as exc:
            print(json.dumps({"event": "ma9_duel_defense_setup",
                              "status": "stopped", "error": str(exc),
                              "starts_race": False}, ensure_ascii=False), flush=True)
            return False
        print(json.dumps({"event": "ma9_duel_defense_setup",
                          "status": report["status"],
                          "mode": report["mode"],
                          "vehicle_class": report["vehicle_class"],
                          "assigned": len(report["assigned"]),
                          "starts_race": False}, ensure_ascii=False), flush=True)
        return report["status"] in {"planned", "five_assigned"}
