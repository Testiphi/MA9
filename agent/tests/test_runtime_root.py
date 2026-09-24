from __future__ import annotations

import sys
import inspect
from dataclasses import FrozenInstanceError, MISSING, fields
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime_action import find_project_root
from ma9_agent import garage_profile, models, selection_runtime, selection_strategy, vehicle_screen


class FrozenPublicContractTest(unittest.TestCase):
    def test_interface_task_names_and_entries_are_frozen(self) -> None:
        # Parse strings before comments so URLs and quoted // remain untouched.
        import json
        import re
        source = (Path(__file__).resolve().parents[2] / "assets/interface.json").read_text(encoding="utf-8")
        clean = re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/',
                       lambda match: match[0] if match[0].startswith('"') else "", source)
        tasks = json.loads(clean)["task"]
        expected = [
            ('多人运行时数据自检（Agent）', '多人运行时_数据自检'),
            ('识别当前选车或车辆详情状态（只读）', '多人运行时_选车状态诊断'),
            ('账号被其他设备登录：立即顶回并重进擂台', '通用_账号被顶_立即重进'),
            ('识别选车列表可见车辆（只读）', '多人运行时_可见车辆识别'),
            ('指定车辆定位测试（从起点或终点，停在详情，不开赛）', '多人运行时_指定车辆定位测试'),
            ('多人循环试跑（白金/黄金/白银自动识别，连续3局，自动开赛）', '多人循环3局_入口'),
            ('多人循环试跑（白金/黄金/白银自动识别，连续20局，自动开赛）', '多人循环20局_入口'),
            ('对决（擂台）入口（资格赛或防守）', '对决_资格赛入口'),
            ('识别对决资格赛防守位置（只读）', '对决_防守状态识别入口'),
            ('对决资格赛：生成五车弱防方案（预演，不选车）', '对决_防守自动规划入口'),
            ('对决资格赛：自动配置五辆弱防车（不开始比赛）', '对决_防守自动配置入口'),
            ('对决资格赛：查看第1张图', '对决_防守_查看第1赛道'),
            ('对决资格赛：查看第2张图', '对决_防守_查看第2赛道'),
            ('对决资格赛：查看第3张图', '对决_防守_查看第3赛道'),
            ('对决资格赛：查看第4张图', '对决_防守_查看第4赛道'),
            ('对决资格赛：查看第5张图', '对决_防守_查看第5赛道'),
            ('对决资格赛：进入第1张图选车', '对决_防守_进入第1赛道选车'),
            ('对决资格赛：进入第2张图选车', '对决_防守_进入第2赛道选车'),
            ('对决资格赛：进入第3张图选车', '对决_防守_进入第3赛道选车'),
            ('对决资格赛：进入第4张图选车', '对决_防守_进入第4赛道选车'),
            ('对决资格赛：进入第5张图选车', '对决_防守_进入第5赛道选车'),
            ('当前段位倒序兜底测试（黄金，白金起点向左，不开赛）', '倒序兜底_入口'),
            ('倒序兜底详情测试（原地检查并向左，不开赛）', '倒序兜底_详情原地测试入口'),
            ('通用弹窗（广告关闭，连接重试，返回主页）', '通用弹窗_入口'),
            ('确保简体中文（英文自动切换并重载）', '语言切换_入口'),
            ('多人局内兜底（每5秒氮气，结算后返回）', '多人局内_兜底入口'),
            ('多人结算（继续，错失机会，返回系列赛）', '多人结算_入口'),
            ('识别赛道（神山垭口，坠落，加载页）', '赛道识别_神山垭口_坠落'),
            ('识别多人局内HUD（不操作）', '局内识别_多人HUD'),
            ('黄金轮换选车（已有素材，正式顺序，不开赛）', '黄金轮换_入口'),
            ('验证Panamera反向搜索（白金起点，不开赛）', '两车_Panamera_反向搜索入口'),
            ('验证Panamera列表识别（原地选车，不滑动）', '两车_Panamera_原地识别入口'),
            ('两车换车测试（J50缺油换Panamera，不开赛）', '两车_入口'),
            ('搜索Ferrari J50（黄金，开启TouchDrive，不开赛）', 'J50测试_入口'),
            ('确保TouchDrive开启（车辆详情页）', 'TouchDrive_确认入口'),
            ('定位黄金段位（自动开启仅拥有）', '黄金定位_入口'),
            ('返回主页（房子按钮）', '主页返回_入口'),
            ('准备经典系列赛选车（开启仅拥有）', '多人准备_入口'),
            ('选中多人游戏', '主页_多人游戏_定位入口'),
            ('选中传奇通行证', '主页_传奇通行证_定位入口'),
            ('选中赛季赛事', '主页_赛季赛事_定位入口'),
            ('选中我的俱乐部', '主页_我的俱乐部_定位入口'),
            ('选中单人模式', '主页_单人模式_定位入口'),
            ('选中每日赛事（含奖励）', '每日赛事_定位入口'),
            ('进入每日赛事（仅无奖励，样例页验证）', '每日赛事_进入入口'),
            ('对决防守：独立账号单槽定位测试（停详情，不选车）', '对决_隔离单槽定位测试'),
            ('普通任务', 'MyTask1'),
            ('选项任务', 'MyTask2'),
            ('参数任务', 'MyTask3'),
            ('带Custom的任务', 'MyTask4'),
        ]
        self.assertEqual([(task["name"], task["entry"]) for task in tasks], expected)
        self.assertEqual(len(tasks), 50)

    def test_leagues_round_trip_and_order(self) -> None:
        labels = ("青铜", "白银", "黄金", "白金", "翡翠", "钻石", "精英", "宗师", "传奇")
        self.assertEqual([int(rank) for rank in models.League], list(range(9)))
        self.assertEqual(tuple(rank.label for rank in models.League), labels)
        for rank, label in zip(models.League, labels):
            self.assertIs(models.League.from_label(label), rank)
        with self.assertRaises(ValueError):
            models.League.from_label("不存在的段位")

    def test_vehicle_model_defaults_immutability_identity_and_click(self) -> None:
        rect = models.Rect(100, 200, 453, 227)
        self.assertEqual(rect.safe_vehicle_point(), (236, 325))
        car = models.VehicleObservation("id", "Name", models.League.GOLD, rect, True, True, None)
        self.assertEqual((car.fully_visible, car.can_start, car.selected), (True, True, False))
        self.assertEqual(car.page_identity, "id")
        self.assertEqual(models.VehicleObservation("", "Name", models.League.GOLD, rect,
                                                  True, True, None).page_identity, "Name")
        for item in (rect, car):
            self.assertFalse(hasattr(item, "__dict__"))
            with self.assertRaises(FrozenInstanceError):
                setattr(item, fields(item)[0].name, "changed")
        required = ("vehicle_id", "name", "league", "card_rect", "owned", "unlocked", "fuel")
        self.assertEqual(tuple(field.name for field in fields(car)[:7]), required)
        self.assertTrue(all(field.default is not MISSING for field in fields(car)[7:]))

    def test_public_parameter_names_kinds_and_defaults(self) -> None:
        # Lock call compatibility, including keyword names and optional inputs.
        cases = [
            (models.League.from_label, "label", {}),
            (models.Rect.safe_vehicle_point, "self", {}),
            (vehicle_screen.normalize, "image", {}),
            (vehicle_screen.selected_league, "image", {}),
            (vehicle_screen.detect_cards, "image", {}),
            (vehicle_screen.match_vehicle, "ocr catalog league", {"league": None}),
            (vehicle_screen.parse_fuel, "items", {}),
            (vehicle_screen.read_page, "image ocr catalog retry_ocr", {"retry_ocr": None}),
            (garage_profile.empty_profile, "", {}),
            (garage_profile.load_profile, "path", {}),
            (garage_profile.save_profile, "path profile", {}),
            (garage_profile.owned_vehicle_ids, "profile", {}),
            (garage_profile.merge_owned_survey, "profile survey records catalog scanned_at", {"scanned_at": None}),
            (garage_profile.set_owned, "profile vehicle owned", {}),
            (selection_strategy.vehicle_index, "catalog rotation", {}),
            (selection_strategy.default_priorities, "rotation owned_ids", {"owned_ids": None}),
            (selection_strategy.new_strategy, "catalog rotation garage", {}),
            (selection_strategy.load_strategy, "path catalog rotation garage", {}),
            (selection_strategy.planned_vehicles, "current catalog rotation strategy", {"strategy": None}),
            (selection_runtime.select_recommended, "context root player_league catalog rotation strategy", {}),
            (selection_runtime.scan_rank, "context rank catalog max_pages stop_when", {"max_pages": 50, "stop_when": None}),
            (selection_runtime.frame_of, "context", {}),
            (selection_runtime.ocr_roi, "context image roi", {}),
        ]
        for function, names, defaults in cases:
            with self.subTest(function=function.__qualname__):
                params = inspect.signature(function).parameters
                self.assertEqual(list(params), names.split())
                for name, param in params.items():
                    self.assertEqual(param.kind, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                    self.assertEqual(param.default, defaults.get(name, inspect.Parameter.empty))


class RuntimeRootTest(unittest.TestCase):
    def test_module_chain_marker_is_used_when_executable_and_cwd_are_unmarked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            account = Path(directory) / "account"
            module_root = Path(directory) / "frozen-package"
            for path in (account, module_root):
                (path / "data").mkdir(parents=True)
                (path / "data/multiplayer_profile.json").write_text("{}")
            (account / "config").mkdir()
            (account / "config/garage.json").write_text("{}")
            (module_root / ".ma9-portable-root").touch()
            module_directory = module_root / "_internal"
            module_directory.mkdir()
            with patch.dict("os.environ", {"MA9_PROJECT_ROOT": ""}), \
                    patch("runtime_action.Path.cwd", return_value=account), \
                    patch("runtime_action.sys.executable", str(account / "bin/ma9-agent.exe")), \
                    patch("runtime_action.__file__", str(module_directory / "runtime_action.py")):
                self.assertEqual(find_project_root(), module_root)

    def test_marked_package_beats_ancestor_account_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "account"
            package = root / "build/portable"
            for path in (root, package):
                (path / "data").mkdir(parents=True)
                (path / "data/multiplayer_profile.json").write_text("{}")
            (root / "config").mkdir()
            (root / "config/garage.json").write_text("{}")
            (package / ".ma9-portable-root").touch()
            with patch.dict("os.environ", {"MA9_PROJECT_ROOT": ""}), \
                    patch("runtime_action.Path.cwd", return_value=root), \
                    patch("runtime_action.sys.executable", str(package / "agent/ma9-agent/ma9-agent.exe")):
                self.assertEqual(find_project_root(), package)

    def test_executable_package_marker_precedes_working_directory_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable_root = Path(directory) / "package"
            working_root = Path(directory) / "other-package"
            for path in (executable_root, working_root):
                (path / "data").mkdir(parents=True)
                (path / "data/multiplayer_profile.json").write_text("{}")
                (path / ".ma9-portable-root").touch()
            with patch.dict("os.environ", {"MA9_PROJECT_ROOT": ""}), \
                    patch("runtime_action.Path.cwd", return_value=working_root), \
                    patch("runtime_action.sys.executable", str(executable_root / "agent/ma9-agent/ma9-agent.exe")):
                self.assertEqual(find_project_root(), executable_root)

    def test_incomplete_marked_package_never_falls_back_to_account(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "account"
            package = root / "portable"
            (root / "data").mkdir(parents=True)
            (root / "data/multiplayer_profile.json").write_text("{}")
            (root / "config").mkdir()
            (root / "config/garage.json").write_text("{}")
            package.mkdir()
            (package / ".ma9-portable-root").touch()
            with patch.dict("os.environ", {"MA9_PROJECT_ROOT": ""}), \
                    patch("runtime_action.Path.cwd", return_value=root), \
                    patch("runtime_action.sys.executable", str(package / "agent/ma9-agent/ma9-agent.exe")):
                with self.assertRaisesRegex(FileNotFoundError, "portable root"):
                    find_project_root()

    def test_explicit_root_precedes_marker_and_invalid_override_never_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "explicit"
            package = Path(directory) / "portable"
            for path in (root, package):
                (path / "data").mkdir(parents=True)
                (path / "data/multiplayer_profile.json").write_text("{}")
            (package / ".ma9-portable-root").touch()
            with patch("runtime_action.Path.cwd", return_value=package), \
                    patch("runtime_action.sys.executable", str(package / "agent/ma9-agent/ma9-agent.exe")):
                with patch.dict("os.environ", {"MA9_PROJECT_ROOT": str(root)}):
                    self.assertEqual(find_project_root(), root)
                with patch.dict("os.environ", {"MA9_PROJECT_ROOT": str(root / "missing")}):
                    with self.assertRaisesRegex(FileNotFoundError, "MA9_PROJECT_ROOT"):
                        find_project_root()

    def test_development_install_uses_gui_account_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "MA9"
            install = root / "install"
            for path in (root, install):
                (path / "data").mkdir(parents=True)
                (path / "data/multiplayer_profile.json").write_text("{}")
            (root / "config").mkdir()
            (root / "config/garage.json").write_text("{}")
            with patch.dict("os.environ", {"MA9_PROJECT_ROOT": ""}), \
                    patch("runtime_action.Path.cwd", return_value=install), \
                    patch("runtime_action.sys.executable", str(install / "agent/ma9-agent/ma9-agent.exe")):
                self.assertEqual(find_project_root(), root)
                (install / "config").mkdir()
                (install / "config/garage.json").write_text("{}")
                self.assertEqual(find_project_root(), install)


if __name__ == "__main__":
    unittest.main()
