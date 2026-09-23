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


class _HitLimitedRecoveryContext(_Context):
    """Model the context-wide max_hit state which survives a recursive task."""

    recovery_nodes = (
        "对决_切换多人标签",
        "对决_点击首页卡片",
        "对决_重开零进度资格赛",
        "对决_确认重开资格赛",
        "对决_点击资格赛",
    )

    def __init__(self, *, clear_failure: str | None = None):
        super().__init__()
        self.hit_counts: dict[str, int] = {}
        self.clear_calls: list[str] = []
        self.clear_failure = clear_failure

    def run_task(self, entry):
        self.entries.append(entry)
        if entry == "对决_资格赛入口":
            if any(self.hit_counts.get(node, 0) for node in self.recovery_nodes):
                return _TaskDetail(False)
            # The first navigation consumes the same guarded nodes that a
            # recursive recovery must use from the multiplayer home page.
            self.hit_counts = {node: 1 for node in self.recovery_nodes}
        return _TaskDetail()

    def clear_hit_count(self, node):
        self.clear_calls.append(node)
        if node == self.clear_failure:
            return False
        self.hit_counts[node] = 0
        return True


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
    def _tracks(big="Map"):
        return {"complete": True, "tracks": [
            {"big": big, "small": str(index)} for index in range(1, 6)]}

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

    def test_plan_aborts_without_assigning_when_map_order_changes_after_scan(self) -> None:
        """The earliest guard: a re-read that swaps two maps must stop the plan.

        The two reads must be independent lists. Building the second read as a
        shallow copy of the first would let both reads observe one mutation, so
        the guard would never see a difference and the test would pass vacuously.
        """
        with tempfile.TemporaryDirectory() as temporary:
            context = _Context()
            # The shared fixture names every map "Map", so the ordering signal
            # lives in the small-map column. Give the two reads distinct names
            # and swap the first two entries of the second read only.
            first_read = self._tracks("Map")
            swapped = self._tracks("Map")
            swapped["tracks"][0]["small"], swapped["tracks"][1]["small"] = (
                swapped["tracks"][1]["small"], swapped["tracks"][0]["small"])
            self.assertNotEqual(
                [(row["big"], row["small"]) for row in swapped["tracks"]],
                [(row["big"], row["small"]) for row in first_read["tracks"]])
            root = self._root(temporary)
            with patch("ma9_agent.duel_defense_setup._read_tracks",
                       side_effect=[first_read, swapped]) as read_tracks, \
                    patch("ma9_agent.duel_defense_setup._frame", return_value=object()), \
                    patch("ma9_agent.duel_defense_setup.scan_duel_vehicles",
                          side_effect=self._scan), \
                    patch("ma9_agent.duel_defense_setup.assign_visible") as assign, \
                    patch("ma9_agent.duel_defense_setup.time.sleep"):
                with self.assertRaisesRegex(
                        RuntimeError, "defense map order changed after the garage scan"):
                    run_defense_setup(context, root, {"mode": "plan"})
            progress = json.loads(
                (root / "debug/duel_defense_gui_setup.json").read_text(encoding="utf-8"))
        self.assertEqual(read_tracks.call_count, 2)
        self.assertEqual(progress["status"], "stopped")
        self.assertEqual(progress["error"],
                         "defense map order changed after the garage scan")
        self.assertFalse(progress["starts_race"])
        self.assertEqual(progress["assigned"], [])
        assign.assert_not_called()
        self.assertFalse(any("开始" in entry for entry in context.entries))
        self.assertEqual(context.tasker.controller.clicks, [(32, 25)])

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

    def test_account_conflict_recovery_resets_navigation_hits_and_keeps_initial_fault(self) -> None:
        """A same-context retry used to be blocked by the first run's max_hit."""
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            context = _HitLimitedRecoveryContext()
            with patch("ma9_agent.duel_defense_setup._read_tracks",
                       side_effect=[RuntimeError("initial selection_lost"),
                                    self._tracks(), self._tracks()]), \
                    patch("ma9_agent.duel_defense_setup._frame", return_value=object()), \
                    patch("ma9_agent.duel_defense_setup.scan_duel_vehicles", side_effect=self._scan), \
                    patch("ma9_agent.duel_defense_setup._recover_account_conflict", return_value=True), \
                    patch("ma9_agent.duel_defense_setup.time.sleep"):
                report = run_defense_setup(context, root, {"mode": "plan"})
        self.assertEqual(report["status"], "planned")
        self.assertEqual(report["initial_error"], "initial selection_lost")
        self.assertEqual(report["account_conflict_retries"], 1)
        self.assertEqual(context.entries.count("对决_资格赛入口"), 2)
        self.assertEqual(context.clear_calls, list(context.recovery_nodes))
        self.assertFalse(any("账号被顶" in node for node in context.clear_calls))

    def test_second_conflict_stops_without_a_second_recovery_and_keeps_both_faults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            context = _HitLimitedRecoveryContext()
            with patch("ma9_agent.duel_defense_setup._read_tracks",
                       side_effect=[RuntimeError("initial selection_lost"),
                                    RuntimeError("recovered attempt interrupted")]), \
                    patch("ma9_agent.duel_defense_setup._frame", return_value=object()), \
                    patch("ma9_agent.duel_defense_setup._recover_account_conflict", return_value=True) as recover:
                with self.assertRaisesRegex(RuntimeError, "recovered attempt interrupted"):
                    run_defense_setup(context, root, {"mode": "plan"})
            progress = json.loads((root / "debug/duel_defense_gui_setup.json").read_text(encoding="utf-8"))
        self.assertEqual(recover.call_count, 1)
        self.assertEqual(progress["initial_error"], "initial selection_lost")
        self.assertEqual(progress["error"], "recovered attempt interrupted")
        self.assertEqual(progress["account_conflict_retries"], 1)

    def test_non_conflict_failure_does_not_clear_navigation_hits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            context = _HitLimitedRecoveryContext()
            with patch("ma9_agent.duel_defense_setup._read_tracks",
                       side_effect=RuntimeError("initial selection_lost")), \
                    patch("ma9_agent.duel_defense_setup._frame", return_value=object()), \
                    patch("ma9_agent.duel_defense_setup._recover_account_conflict", return_value=False):
                with self.assertRaisesRegex(RuntimeError, "initial selection_lost"):
                    run_defense_setup(context, root, {"mode": "plan"})
        self.assertEqual(context.clear_calls, [])

    def test_failed_navigation_hit_reset_stops_and_preserves_initial_fault(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            context = _HitLimitedRecoveryContext(clear_failure="对决_点击首页卡片")
            with patch("ma9_agent.duel_defense_setup._read_tracks",
                       side_effect=RuntimeError("initial selection_lost")), \
                    patch("ma9_agent.duel_defense_setup._frame", return_value=object()), \
                    patch("ma9_agent.duel_defense_setup._recover_account_conflict", return_value=True):
                with self.assertRaisesRegex(RuntimeError, "initial selection_lost.*could not reset"):
                    run_defense_setup(context, root, {"mode": "plan"})
            progress = json.loads((root / "debug/duel_defense_gui_setup.json").read_text(encoding="utf-8"))
        self.assertEqual(context.entries.count("对决_资格赛入口"), 1)
        self.assertEqual(progress["status"], "stopped")
        self.assertEqual(progress["initial_error"], "initial selection_lost")
        self.assertIn("对决_点击首页卡片", progress["error"])

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
