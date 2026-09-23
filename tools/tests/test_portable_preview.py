from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import prepare_portable_preview as preview


class PortablePreviewTest(unittest.TestCase):
    """Drive the real staging logic against a small fixture tree."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        source_ui = self.root / "install"
        source_ui.mkdir(parents=True)
        for name in preview.REQUIRED_FILES:
            (source_ui / name).write_text("ui")
        for name in preview.REQUIRED_DIRECTORIES:
            (source_ui / name).mkdir()
            (source_ui / name / "entry.txt").write_text("lib")
        self.agent = self.root / "dist/ma9-agent"
        (self.agent / "agent").mkdir(parents=True)
        (self.agent / "ma9-agent.exe").write_text("exe")
        generated = self.root / "data/generated"
        generated.mkdir(parents=True)
        (self.root / "data/sources").mkdir()
        for name in preview.REQUIRED_DATA_FILES:
            (self.root / name).write_text("{}")
        interface = self.root / "assets/interface.json"
        interface.parent.mkdir(parents=True)
        rows = ",\n    ".join(
            '{"name": "%s", "entry": "%s"}' % (entry, entry) for entry in sorted(preview.TASKS))
        interface.write_text(
            '{\n  "controller": [{"type": "Adb"}, {"type": "Win32"}],\n'
            '  "resource": [],\n  "task": [\n    %s\n  ]\n}\n' % rows,
            encoding="utf-8")
        (self.root / "assets/resource").mkdir()
        (self.root / "assets/resource/pipeline.json").write_text("{}")
        self.base = self.root / "output"

    def _run(self) -> Path:
        self.base.mkdir(exist_ok=True)
        import argparse
        with patch.multiple(preview, ROOT=self.root, SOURCE_UI=self.root / "install",
                            BASE=self.base, DESTINATION=self.base / "MA9-preview",
                            AGENT=self.agent), \
                patch.object(argparse.ArgumentParser, "parse_args",
                             return_value=argparse.Namespace(zip=False)):
            preview.main()
        return self.base / "MA9-preview"

    def test_marker_is_written_only_into_the_completed_package_root(self) -> None:
        target = self._run()
        self.assertTrue((target / preview.PORTABLE_MARKER).is_file())
        self.assertEqual((target / preview.PORTABLE_MARKER).read_text(encoding="utf-8"), "")
        self.assertFalse((self.root / preview.PORTABLE_MARKER).exists())
        self.assertFalse((self.root / "install" / preview.PORTABLE_MARKER).exists())
        self.assertFalse((self.base / preview.PORTABLE_MARKER).exists())

    def test_marker_is_created_only_after_every_required_entry_exists(self) -> None:
        from collections import deque
        calls: deque[Path] = deque()

        def record(target: Path) -> None:
            calls.append((target / preview.PORTABLE_MARKER).is_file())

        with patch.object(preview, "assert_preview_complete", side_effect=record):
            target = self._run()
        self.assertEqual(list(calls), [False])
        self.assertTrue((target / preview.PORTABLE_MARKER).is_file())

    def test_private_development_directories_are_never_copied(self) -> None:
        (self.root / "config").mkdir()
        (self.root / "config/garage.json").write_text('{"owned": ["secret"]}')
        (self.root / "config/vehicle_search_test.json").write_text("{}")
        (self.root / "debug").mkdir()
        (self.root / "debug/selection_runtime.json").write_text("{}")
        target = self._run()
        self.assertFalse((target / "config").exists())
        self.assertFalse((target / "debug").exists())
        self.assertEqual([path.name for path in target.rglob("garage.json")], [])
        self.assertTrue((target / preview.PORTABLE_MARKER).is_file())

    def test_incomplete_package_raises_and_leaves_no_marker(self) -> None:
        self.agent.joinpath("ma9-agent.exe").unlink()
        with self.assertRaises(FileNotFoundError):
            self._run()
        target = self.base / "MA9-preview"
        self.assertFalse((target / preview.PORTABLE_MARKER).exists())

    def test_missing_data_file_raises_before_the_marker_is_created(self) -> None:
        (self.root / "data/generated/vehicle_catalog.json").unlink()
        with self.assertRaises(FileNotFoundError):
            self._run()
        self.assertFalse((self.base / "MA9-preview" / preview.PORTABLE_MARKER).exists())

    def test_missing_preview_task_raises_before_the_marker_is_created(self) -> None:
        (self.root / "assets/interface.json").write_text(
            '{"controller": [{"type": "Adb"}], "resource": [], "task": []}\n', encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self._run()
        self.assertFalse((self.base / "MA9-preview" / preview.PORTABLE_MARKER).exists())

    def test_unsafe_destination_is_rejected(self) -> None:
        import argparse
        with patch.multiple(preview, ROOT=self.root, SOURCE_UI=self.root / "install",
                            BASE=self.base, DESTINATION=self.root,
                            AGENT=self.agent), \
                patch.object(argparse.ArgumentParser, "parse_args",
                             return_value=argparse.Namespace(zip=False)):
            with self.assertRaises(RuntimeError):
                preview.main()


if __name__ == "__main__":
    unittest.main()
