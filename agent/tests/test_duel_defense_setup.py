from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_defense_setup import parse_setup_params, run_defense_setup


class _Job:
    succeeded = True

    def wait(self):
        return self


class _Controller:
    def __init__(self):
        self.clicks = []

    def post_click(self, x, y):
        self.clicks.append((x, y))
        return _Job()


class _Context:
    def __init__(self):
        self.entries = []
        self.tasker = type("Tasker", (), {"controller": _Controller()})()

    def run_task(self, entry):
        self.entries.append(entry)
        return object()


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
        return {"status": "edge_reached", "vehicles": [
            {"vehicle": {"id": name, "title": name}, "class": "D",
             "performance": [score, None], "stars_lit": None}
            for name, score in zip("abcdef", [2600, 2400, 2200, 2000, 1800, 1600])
        ]}

    def test_plan_returns_to_lineup_without_assigning_or_starting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            context = _Context()
            with patch("ma9_agent.duel_defense_setup._read_tracks", return_value=self._tracks()), \
                    patch("ma9_agent.duel_defense_setup.scan_duel_vehicles", side_effect=self._scan), \
                    patch("ma9_agent.duel_defense_setup.time.sleep"):
                report = run_defense_setup(context, self._root(temporary), {"mode": "plan"})
        self.assertEqual(report["status"], "planned")
        self.assertEqual(context.entries, ["对决_防守_进入第1赛道选车"])
        self.assertEqual(context.tasker.controller.clicks, [(32, 25)])
        self.assertFalse(report["starts_race"])
        self.assertFalse(any("开始" in entry for entry in context.entries))

    def test_apply_assigns_exactly_five_slots_and_never_starts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            context = _Context()
            with patch("ma9_agent.duel_defense_setup._read_tracks", return_value=self._tracks()), \
                    patch("ma9_agent.duel_defense_setup.scan_duel_vehicles", side_effect=self._scan), \
                    patch("ma9_agent.duel_defense_setup.time.sleep"):
                report = run_defense_setup(context, self._root(temporary), {"mode": "apply"})
        self.assertEqual(report["status"], "five_assigned")
        self.assertEqual(len(report["assigned"]), 5)
        self.assertEqual(context.entries[1:], [
            f"对决_防守_进入第{index}赛道选车" for index in range(1, 6)])
        self.assertFalse(any("开始" in entry for entry in context.entries))


if __name__ == "__main__":
    unittest.main()
