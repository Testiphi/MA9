"""Desktop editor for each multiplayer league's complete owned-car priority list."""

from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))

from ma9_agent.selection_editor import SelectionEditor
from ma9_agent.selection_strategy import LEAGUES


def find_project_root(executable: Path, working_directory: Path,
                      configured: str | None = None) -> Path:
    """Find data beside a release exe or above a development build exe."""
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).resolve())
    for start in (executable.resolve().parent, working_directory.resolve()):
        candidates.extend((start, *start.parents))
    candidates = list(dict.fromkeys(candidates))

    def has_catalog(path: Path) -> bool:
        return (path / "data/generated/vehicle_catalog.json").is_file() and \
            (path / "data/generated/champion_rotation.json").is_file()

    if configured:
        if has_catalog(candidates[0]):
            return candidates[0]
        raise FileNotFoundError(f"MA9_PROJECT_ROOT 中缺少车辆目录：{candidates[0]}")
    return next((path for path in candidates if has_catalog(path) and
                 (path / "config/garage.json").is_file()),
                next((path for path in candidates if has_catalog(path)),
                     None)) or _missing_project_root(executable)


def _missing_project_root(executable: Path) -> Path:
    raise FileNotFoundError(f"在 {executable.parent} 及其上级目录未找到 MA9 的车辆数据")


def project_root() -> Path:
    executable = Path(sys.executable) if getattr(sys, "frozen", False) else Path(__file__)
    return find_project_root(executable, Path.cwd(), os.environ.get("MA9_PROJECT_ROOT"))


class SelectionWindow(tk.Tk):
    def __init__(self, root: Path):
        super().__init__()
        self.title("MA9 多人选车顺序")
        self.geometry("800x660")
        self.minsize(650, 480)
        self.editor = SelectionEditor(root)
        self.rank = tk.StringVar(value=self._current_rank(root))
        self.query = tk.StringVar()
        self.status = tk.StringVar(value="每个段位包含该段位及以下所有已确认拥有的车辆；排在前面的车优先使用。")
        self.visible_ids: list[str] = []
        self.dirty = False

        heading = ttk.Frame(self, padding=12)
        heading.pack(fill="x")
        ttk.Label(heading, text="当前段位").pack(side="left")
        rank_select = ttk.Combobox(heading, textvariable=self.rank, values=LEAGUES,
                                   state="readonly", width=12)
        rank_select.pack(side="left", padx=(8, 25))
        rank_select.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        ttk.Label(heading, text="查找车辆").pack(side="left")
        ttk.Entry(heading, textvariable=self.query).pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.query.trace_add("write", lambda *_: self.refresh())

        body = ttk.Frame(self, padding=(12, 0, 12, 8))
        body.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(body, font=("Microsoft YaHei UI", 11),
                                  activestyle="none", exportselection=False)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="left", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.bind("<Control-Up>", lambda _event: self.move("up"))
        self.listbox.bind("<Control-Down>", lambda _event: self.move("down"))

        buttons = ttk.Frame(body, padding=(12, 0, 0, 0))
        buttons.pack(side="right", fill="y")
        for label, direction in (("置顶", "top"), ("上移", "up"), ("下移", "down"), ("置底", "bottom")):
            ttk.Button(buttons, text=label, command=lambda d=direction: self.move(d)).pack(fill="x", pady=3)
        ttk.Separator(buttons).pack(fill="x", pady=14)
        ttk.Button(buttons, text="恢复本段位默认顺序", command=self.reset).pack(fill="x", pady=3)
        ttk.Button(buttons, text="保存", command=self.save).pack(fill="x", pady=14)
        ttk.Separator(buttons).pack(fill="x", pady=5)
        ttk.Button(buttons, text="从起点定位测试", command=lambda: self.location_test("start")).pack(fill="x", pady=3)
        ttk.Button(buttons, text="从终点定位测试", command=lambda: self.location_test("end")).pack(fill="x", pady=3)

        ttk.Label(self, textvariable=self.status, wraplength=760, padding=(12, 0, 12, 12)).pack(fill="x")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()

    @staticmethod
    def _current_rank(root: Path) -> str:
        try:
            rank = json.loads((root / "data/multiplayer_profile.json").read_text(encoding="utf-8"))["current_league"]
            return rank if rank in LEAGUES else "青铜"
        except (OSError, KeyError, ValueError):
            return "青铜"

    def refresh(self, selected_id: str | None = None) -> None:
        rank = self.rank.get()
        query = self.query.get().casefold().strip()
        self.visible_ids = [vehicle_id for vehicle_id in self.editor.strategy["priorities"][rank]
                            if query in self.editor.vehicles[vehicle_id]["title"].casefold()]
        self.listbox.delete(0, "end")
        for vehicle_id in self.visible_ids:
            vehicle = self.editor.vehicles[vehicle_id]
            actual = self.editor.strategy["priorities"][rank].index(vehicle_id) + 1
            self.listbox.insert("end", f"{actual:3}.  [{vehicle['league']}]  {vehicle['title']}")
        if selected_id in self.visible_ids:
            position = self.visible_ids.index(selected_id)
            self.listbox.selection_set(position)
            self.listbox.see(position)
        suffix = "（查找时请先清空搜索框再排序）" if query else ""
        self.status.set(f"{rank}：{len(self.editor.strategy['priorities'][rank])} 辆可用；当前显示 {len(self.visible_ids)} 辆{suffix}")

    def move(self, direction: str) -> None:
        if self.query.get().strip():
            self.status.set("请先清空搜索框，再调整完整列表顺序。")
            return
        selected = self.listbox.curselection()
        if not selected:
            self.status.set("请先选中一辆车。")
            return
        vehicle_id = self.visible_ids[selected[0]]
        self.editor.move(self.rank.get(), vehicle_id, direction)
        self.dirty = True
        self.refresh(vehicle_id)

    def reset(self) -> None:
        if not messagebox.askyesno("恢复顺序", f"恢复 {self.rank.get()} 的默认顺序？", parent=self):
            return
        self.editor.reset(self.rank.get())
        self.dirty = True
        self.refresh()

    def save(self) -> None:
        try:
            self.editor.save()
        except (OSError, ValueError) as error:
            messagebox.showerror("保存失败", str(error), parent=self)
            return
        self.dirty = False
        self.status.set("已保存。下一局多人选车会读取新顺序。")

    def location_test(self, direction: str) -> None:
        selected = self.listbox.curselection()
        if not selected:
            self.status.set("请先选中要测试的车辆。")
            return
        vehicle_id = self.visible_ids[selected[0]]
        try:
            self.editor.write_location_test(vehicle_id, direction, repeats=3)
        except (OSError, ValueError) as error:
            messagebox.showerror("无法设置定位测试", str(error), parent=self)
            return
        name = self.editor.vehicles[vehicle_id]["title"]
        edge = "起点" if direction == "start" else "终点"
        league = self.editor.vehicles[vehicle_id]["league"]
        note = "传奇列表无终点锚点，将从起点左滑搜索。" if league == "传奇" and direction == "end" else ""
        self.status.set(f"已设置：从 {league}{edge}寻找 {name}，重复 3 次。{note}请在 MA9 主程序运行“指定车辆定位测试”。")

    def close(self) -> None:
        if self.dirty and not messagebox.askyesno("未保存更改", "顺序尚未保存，仍要关闭吗？", parent=self):
            return
        self.destroy()


def main() -> None:
    try:
        window = SelectionWindow(project_root())
    except (OSError, KeyError, ValueError) as error:
        app = tk.Tk()
        app.withdraw()
        messagebox.showerror("无法打开选车顺序", str(error))
        app.destroy()
        raise SystemExit(1) from error
    window.mainloop()


if __name__ == "__main__":
    main()
