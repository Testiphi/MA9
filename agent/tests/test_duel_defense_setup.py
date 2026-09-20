from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_defense_setup import (
    _read_tracks,
    _retry_target_after_wrong_detail,
    _run_task,
    _scan_class_ladder,
    parse_setup_params,
    run_defense_setup,
)


class _Job:
    succeeded = True

    def wait(self):
        return self


class _TaskDetail:
    def __init__(self, succeeded=True):
        self.status = type("Status", (), {"succeeded": succeeded})()


class _Controller:
    def __init__(self):
        self.clicks = []

    def post_click(self, x, y):
        self.clicks.append((x, y))
        return _Job()


class _Context:
    def __init__(self, ready=False, unselected_slot=None):
        self.entries = []
        self.ready = ready
        self.unselected_slot = unselected_slot
        self.tasker = type("Tasker", (), {"controller": _Controller()})()

    def run_task(self, entry):
        self.entries.append(entry)
        return _TaskDetail()

    def run_recognition(self, entry, _frame):
        hit = ((self.ready and entry == "对决_防守_已选车可开始")
               or (self.unselected_slot is not None
                   and entry == f"对决_防守_第{self.unselected_slot}赛道展开未选车"))
        return type("Recognition", (), {"hit": hit})()


class DuelDefenseSetupParamsTest(unittest.TestCase):
    def test_defaults_are_safe_plan_only(self) -> None:
        self.assertEqual(parse_setup_params({}), {
            "class": "D", "mode": "plan", "strategy": "weakest_current", "max_pages": 25,
        })

    def test_all_vehicle_classes_are_supported(self) -> None:
        for vehicle_class in "RSABCD":
            with self.subTest(vehicle_class=vehicle_class):
                parsed = parse_setup_params({"class": vehicle_class.lower(), "mode": "apply"})
                self.assertEqual(parsed["class"], vehicle_class)
                self.assertEqual(parsed["mode"], "apply")

    def test_invalid_parameters_stop_before_input(self) -> None:
        for params in ({"class": "X"}, {"mode": "start"}, {"max_pages": 0},
                       {"max_pages": True}, {"strategy": "fastest"}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                parse_setup_params(params)

    def test_pipeline_failure_is_not_treated_as_success(self) -> None:
        context = type("Context", (), {
            "run_task": lambda _self, _entry: _TaskDetail(False),
        })()
        with self.assertRaisesRegex(RuntimeError, "failed: broken"):
            _run_task(context, "broken")


class DuelDefenseSetupFlowTest(unittest.TestCase):
    def _root(self, temporary: str) -> Path:
        root = Path(temporary)
        generated = root / "data/generated"
        generated.mkdir(parents=True)
        (generated / "duel_auto_candidates.json").write_text("{}", encoding="utf-8")
        (generated / "vehicle_catalog.json").write_text(
            json.dumps({"vehicles": [{"id": name, "title": name, "class": "D"}
                                      for name in "abcdef"]}), encoding="utf-8")
        return root

    @staticmethod
    def _tracks():
        return {"complete": True, "tracks": [
            {"big": "Map", "small": str(index)} for index in range(1, 6)]}

    @staticmethod
    def _scan(_context, _vehicle_class, _catalog, **kwargs):
        if kwargs.get("target_id"):
            return {"status": "assigned", "performance": kwargs["expected_performance"]}
        return {"status": "edge_reached", "scan_complete": True, "vehicles": [
            {"vehicle": {"id": name, "title": name}, "class": "D",
             "performance": [score, None], "stars_lit": None}
            for name, score in zip("abcdef", [2600, 2400, 2200, 2000, 1800, 1600])
        ]}

    def test_plan_returns_to_lineup_without_assigning_or_starting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            context = _Context()
            with patch("ma9_agent.duel_defense_setup._read_tracks", return_value=self._tracks()), \
                    patch("ma9_agent.duel_defense_setup._frame", return_value=object()), \
                    patch("ma9_agent.duel_defense_setup.scan_duel_vehicles", side_effect=self._scan), \
                    patch("ma9_agent.duel_defense_setup.time.sleep"):
                report = run_defense_setup(context, self._root(temporary), {"mode": "plan"})
        self.assertEqual(report["status"], "planned")
        self.assertEqual(context.entries, ["对决_资格赛入口", "对决_防守_进入第1赛道选车"])
        self.assertEqual(context.tasker.controller.clicks, [(32, 25)])
        self.assertFalse(report["starts_race"])
        self.assertFalse(any("开始" in entry for entry in context.entries))

    def test_apply_assigns_exactly_five_slots_and_never_starts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            context = _Context()
            with patch("ma9_agent.duel_defense_setup._read_tracks", return_value=self._tracks()), \
                    patch("ma9_agent.duel_defense_setup._frame", return_value=object()), \
                    patch("ma9_agent.duel_defense_setup.assign_visible",
                          return_value={"status": "assigned", "performance": 1600}), \
                    patch("ma9_agent.duel_defense_setup.scan_duel_vehicles", side_effect=self._scan), \
                    patch("ma9_agent.duel_defense_setup.time.sleep"):
                report = run_defense_setup(context, self._root(temporary), {"mode": "apply"})
        self.assertEqual(report["status"], "five_assigned")
        self.assertEqual(len(report["assigned"]), 5)
        self.assertEqual(context.entries, [
            "对决_资格赛入口",
            *[f"对决_防守_进入第{index}赛道选车" for index in range(1, 6)]])
        self.assertFalse(any("开始" in entry for entry in context.entries))

    def test_ready_five_car_lineup_is_preserved_without_opening_garage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            context = _Context(ready=True)
            with patch("ma9_agent.duel_defense_setup._frame", return_value=object()), \
                    patch("ma9_agent.duel_defense_setup._read_tracks") as read_tracks, \
                    patch("ma9_agent.duel_defense_setup.scan_duel_vehicles") as scan:
                report = run_defense_setup(context, self._root(temporary), {"mode": "apply"})
        self.assertEqual(report["status"], "already_configured")
        self.assertTrue(report["existing_defense_preserved"])
        self.assertEqual(context.entries, ["对决_资格赛入口"])
        self.assertEqual(context.tasker.controller.clicks, [])
        read_tracks.assert_not_called()
        scan.assert_not_called()

    def test_interrupted_partial_lineup_resumes_from_expanded_empty_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            context = _Context(unselected_slot=3)
            with patch("ma9_agent.duel_defense_setup._read_tracks", return_value=self._tracks()), \
                    patch("ma9_agent.duel_defense_setup._frame", return_value=object()), \
                    patch("ma9_agent.duel_defense_setup.assign_visible",
                          return_value={"status": "assigned", "performance": 2000}), \
                    patch("ma9_agent.duel_defense_setup.scan_duel_vehicles", side_effect=self._scan), \
                    patch("ma9_agent.duel_defense_setup.time.sleep"):
                report = run_defense_setup(context, self._root(temporary), {"mode": "apply"})
        self.assertEqual(report["status"], "five_assigned")
        self.assertEqual(report["resumed_from_slot"], 3)
        self.assertEqual([row["slot"] for row in report["assigned"]], [3, 4, 5])
        self.assertEqual(context.entries, [
            "对决_资格赛入口",
            "对决_防守_进入第3赛道选车",
            "对决_防守_进入第4赛道选车",
            "对决_防守_进入第5赛道选车",
        ])

    def test_track_reader_waits_through_black_transition(self) -> None:
        incomplete = {"complete": False, "tracks": [], "observed_groups": 0}
        complete = self._tracks()
        with patch("ma9_agent.duel_defense_setup._frame", side_effect=[object(), object()]), \
                patch("ma9_agent.duel_defense_setup._ocr", return_value=[]), \
                patch("ma9_agent.duel_defense_setup.read_five_tracks",
                      side_effect=[incomplete, complete]), \
                patch("ma9_agent.duel_defense_setup.time.sleep"):
            report = _read_tracks(object(), {}, timeout=1, interval=.01)
        self.assertEqual(report, complete)

    def test_wrong_neighbor_detail_returns_to_list_and_retries_once(self) -> None:
        context = _Context()
        target = {"vehicle_id": "a", "performance": 1600, "stars_lit": None}
        expected = {"status": "assigned", "performance": 1600}
        with patch("ma9_agent.duel_defense_setup.scan_duel_vehicles",
                   return_value=expected) as scan:
            actual = _retry_target_after_wrong_detail(
                context, {"status": "detail_not_verified"}, "D", target,
                [{"id": "a", "title": "a", "class": "D"}], 25)
        self.assertEqual(actual, expected)
        self.assertEqual(context.tasker.controller.clicks, [(32, 25)])
        scan.assert_called_once()

    def test_target_not_found_restarts_scan_without_leaving_garage(self) -> None:
        context = _Context()
        target = {"vehicle_id": "a", "performance": 1600, "stars_lit": None}
        expected = {"status": "assigned", "performance": 1600,
                    "assignment_complete": True}
        with patch("ma9_agent.duel_defense_setup.scan_duel_vehicles",
                   return_value=expected) as scan:
            actual = _retry_target_after_wrong_detail(
                context, {"status": "target_not_found", "scan_complete": True},
                "D", target, [{"id": "a", "title": "a", "class": "D"}], 25)
        self.assertEqual(actual["status"], "assigned")
        self.assertEqual(context.tasker.controller.clicks, [])
        scan.assert_called_once()

    def test_incomplete_scan_cannot_become_a_completed_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            context = _Context()
            incomplete = {"status": "edge_reached", "scan_complete": False,
                          "vehicles": []}
            with patch("ma9_agent.duel_defense_setup._read_tracks",
                       return_value=self._tracks()), \
                    patch("ma9_agent.duel_defense_setup._frame", return_value=object()), \
                    patch("ma9_agent.duel_defense_setup.scan_duel_vehicles",
                          return_value=incomplete), \
                    patch("ma9_agent.duel_defense_setup.time.sleep"):
                with self.assertRaisesRegex(RuntimeError, "scan stopped"):
                    run_defense_setup(context, self._root(temporary), {"mode": "apply"})

    def test_class_ladder_scans_lower_class_only_when_needed(self) -> None:
        context = _Context()

        def class_scan(_context, vehicle_class, _catalog, **_kwargs):
            count = {"R": 2, "S": 4}[vehicle_class]
            return {
                "status": "class_boundary",
                "scan_complete": True,
                "vehicles": [
                    {"vehicle": {"id": f"{vehicle_class}{index}"},
                     "class": vehicle_class, "performance": [2000 - index, None]}
                    for index in range(count)
                ],
            }

        with patch("ma9_agent.duel_defense_setup.scan_duel_vehicles",
                   side_effect=class_scan) as scan:
            report = _scan_class_ladder(context, "R", [], 25)
        self.assertEqual(report["status"], "class_ladder_complete")
        self.assertEqual(report["scanned_classes"], ["R", "S"])
        self.assertEqual(len(report["vehicles"]), 6)
        self.assertEqual([call.args[1] for call in scan.call_args_list], ["R", "S"])


if __name__ == "__main__":
    unittest.main()
