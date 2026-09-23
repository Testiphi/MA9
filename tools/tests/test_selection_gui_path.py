from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import selection_gui
from selection_gui import find_project_root


class ControlledFilesystem:
    """Confine root lookup to a fixture so the host's real account is invisible.

    The gate patches ``Path.is_file``/``Path.exists`` with plain functions. A
    plain function replacing an ordinary method still receives the bound ``self``
    path as its single argument (``Path.is_file`` is an ordinary method, not a
    slot wrapper), so the gate can decide per path whether to consult the
    original method.

    Only existence checks *inside* the fixture are delegated to the original
    method and therefore report host truth; every path outside the fixture
    returns ``False``. This is accounting-style scoping, not a blanket pass:
    files used by a test must still be created for real inside the fixture.
    """

    def __init__(self, root: Path):
        self.root = root
        self.path_class = type(Path())
        self.scratch = self.path_class()
        self.original_is_file = self.path_class.is_file
        self.original_exists = self.path_class.exists

    def __enter__(self) -> list[Path]:
        allowed: list[Path] = []
        for directory in (self.root, *self.root.rglob("*")):
            if directory.is_dir():
                allowed.append(directory.resolve())
        self.allowed = allowed
        patcher = patch.multiple(
            self.path_class,
            is_file=self._gate(self.original_is_file),
            exists=self._gate(self.original_exists))
        patcher.start()
        self.patcher = patcher
        return allowed

    def _gate(self, original):
        def check(path: Path) -> bool:
            resolved = self.scratch.__class__(str(path))
            try:
                resolved = resolved.resolve()
            except OSError:
                return False
            inside = any(resolved == kept or kept in resolved.parents for kept in self.allowed)
            return original(path) if inside else False
        return check

    def __exit__(self, *_exception) -> None:
        self.patcher.stop()


class SelectionGuiPathTest(unittest.TestCase):
    def test_build_exe_finds_account_data_in_project_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "MA9"
            generated = root / "data/generated"
            generated.mkdir(parents=True)
            (generated / "vehicle_catalog.json").write_text("{}")
            (generated / "champion_rotation.json").write_text("{}")
            (root / "config").mkdir()
            (root / "config/garage.json").write_text("{}")
            executable = root / "build/selection_gui/dist/ma9-selection.exe"
            with ControlledFilesystem(root):
                self.assertEqual(find_project_root(executable, executable.parent), root)

    def test_release_exe_uses_adjacent_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "install"
            generated = root / "data/generated"
            generated.mkdir(parents=True)
            (generated / "vehicle_catalog.json").write_text("{}")
            (generated / "champion_rotation.json").write_text("{}")
            with ControlledFilesystem(root):
                self.assertEqual(find_project_root(root / "ma9-selection.exe", root), root)

    def test_development_build_above_adjacent_data_still_uses_account_ancestor(self) -> None:
        """No marker keeps the old build/selection_gui/dist account-ancestor shape."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "MA9"
            generated = root / "data/generated"
            generated.mkdir(parents=True)
            (generated / "vehicle_catalog.json").write_text("{}")
            (generated / "champion_rotation.json").write_text("{}")
            (root / "config").mkdir()
            (root / "config/garage.json").write_text("{}")
            executable = root / "build/selection_gui/dist/ma9-selection.exe"
            with ControlledFilesystem(root):
                self.assertFalse((root / "build/selection_gui/dist").joinpath(
                    selection_gui.PORTABLE_ROOT_MARKER).exists())
                self.assertEqual(find_project_root(executable, root), root)

    def test_development_install_keeps_account_ancestor_without_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "MA9"
            generated = root / "data/generated"
            generated.mkdir(parents=True)
            (generated / "vehicle_catalog.json").write_text("{}")
            (generated / "champion_rotation.json").write_text("{}")
            (root / "config").mkdir()
            (root / "config/garage.json").write_text("{}")
            install = root / "install"
            install.mkdir()
            with ControlledFilesystem(root):
                self.assertEqual(find_project_root(install / "ma9-selection.exe", install), root)


class PortableMarkerTest(unittest.TestCase):
    @staticmethod
    def _package(root: Path, marker: bool) -> Path:
        generated = root / "data/generated"
        generated.mkdir(parents=True)
        (generated / "vehicle_catalog.json").write_text("{}")
        (generated / "champion_rotation.json").write_text("{}")
        if marker:
            (root / selection_gui.PORTABLE_ROOT_MARKER).write_text("")
        return root

    @staticmethod
    def _account(root: Path) -> Path:
        root.mkdir(parents=True)
        (root / "config").mkdir()
        (root / "config/garage.json").write_text("{}")
        return root

    @staticmethod
    def _catalog(root: Path) -> Path:
        generated = root / "data/generated"
        generated.mkdir(parents=True, exist_ok=True)
        (generated / "vehicle_catalog.json").write_text("{}")
        (generated / "champion_rotation.json").write_text("{}")
        return root

    def test_marked_package_beats_ancestor_account_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            account = Path(directory) / "account"
            self._account(account)
            self._catalog(account)
            package = self._package(account / "build/portable", marker=True)
            with ControlledFilesystem(account):
                self.assertEqual(
                    find_project_root(package / "MFAAvalonia.exe", package), package)

    def test_unmarked_package_keeps_account_ancestor(self) -> None:
        """An unmarked package without its own catalog still reads outward."""
        with tempfile.TemporaryDirectory() as directory:
            account = Path(directory) / "account"
            self._account(account)
            self._catalog(account)
            package = account / "build/portable"
            package.mkdir(parents=True)
            with ControlledFilesystem(account):
                self.assertEqual(
                    find_project_root(package / "MFAAvalonia.exe", package), account)

    def test_adjacent_package_wins_when_it_is_itself_the_account_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            account = self._account(Path(directory) / "account")
            package = self._package(account / "build/portable", marker=False)
            (package / "config").mkdir()
            (package / "config/garage.json").write_text("{}")
            with ControlledFilesystem(account):
                self.assertEqual(
                    find_project_root(package / "MFAAvalonia.exe", package), package)

    def test_unmarked_adjacent_catalog_without_garage_still_defers_to_ancestor(self) -> None:
        """Adjacent catalog alone must not outrank an unmarked garage ancestor.

        The package carries its own catalog and rotation but no garage, so the
        old account-root-first search still resolves to the garage-bearing
        ancestor. Writing the marker turns the same layout into an explicit
        boundary, which is the contrast half of this geometry.
        """
        with tempfile.TemporaryDirectory() as directory:
            account = self._account(Path(directory) / "account")
            self._catalog(account)
            package = self._package(account / "build/portable", marker=False)
            self.assertFalse((package / "config/garage.json").exists())
            with ControlledFilesystem(account):
                self.assertEqual(
                    find_project_root(package / "MFAAvalonia.exe", package), account)
            (package / selection_gui.PORTABLE_ROOT_MARKER).write_text("")
            with ControlledFilesystem(account):
                self.assertEqual(
                    find_project_root(package / "MFAAvalonia.exe", package), package)

    def test_marked_exe_root_precedes_a_different_marked_cwd_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = self._package(Path(directory) / "package", marker=True)
            other = self._package(Path(directory) / "other-package", marker=True)
            with ControlledFilesystem(Path(directory)):
                self.assertEqual(
                    find_project_root(package / "MFAAvalonia.exe", other), package)

    def test_marked_package_missing_catalog_stops_instead_of_crossing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            account = self._account(Path(directory) / "account")
            self._package(account, marker=False)
            (account / "data/generated/vehicle_catalog.json").write_text("{}")
            (account / "data/generated/champion_rotation.json").write_text("{}")
            package = account / "build/portable"
            package.mkdir(parents=True)
            (package / selection_gui.PORTABLE_ROOT_MARKER).write_text("")
            with ControlledFilesystem(account):
                with self.assertRaises(FileNotFoundError):
                    find_project_root(package / "MFAAvalonia.exe", package)


class ConfiguredRootTest(unittest.TestCase):
    def test_configured_root_precedes_marker_and_invalid_configured_never_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            explicit = Path(directory) / "explicit"
            explicit.mkdir()
            (explicit / "data/generated").mkdir(parents=True)
            (explicit / "data/generated/vehicle_catalog.json").write_text("{}")
            (explicit / "data/generated/champion_rotation.json").write_text("{}")
            package = Path(directory) / "portable"
            package.mkdir()
            (package / selection_gui.PORTABLE_ROOT_MARKER).write_text("")
            with ControlledFilesystem(Path(directory)):
                self.assertEqual(
                    find_project_root(package / "MFAAvalonia.exe", package,
                                      configured=str(explicit)), explicit)
                with self.assertRaises(FileNotFoundError):
                    find_project_root(package / "MFAAvalonia.exe", package,
                                      configured=str(package))


class ProjectRootEntryTest(unittest.TestCase):
    def test_entry_reports_sys_executable_and_cwd_with_environment_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            exported = Path(directory) / "exported"
            exported.mkdir()
            (exported / "data/generated").mkdir(parents=True)
            (exported / "data/generated/vehicle_catalog.json").write_text("{}")
            (exported / "data/generated/champion_rotation.json").write_text("{}")
            other = Path(directory) / "other"
            other.mkdir()
            with ControlledFilesystem(Path(directory)), \
                    patch.object(selection_gui.sys, "frozen", True, create=True), \
                    patch.object(selection_gui.sys, "executable", str(other / "ma9-selection.exe")), \
                    patch.object(selection_gui.Path, "cwd", return_value=other), \
                    patch.dict("os.environ", {"MA9_PROJECT_ROOT": str(exported)}):
                self.assertEqual(selection_gui.project_root(), exported)


if __name__ == "__main__":
    unittest.main()
