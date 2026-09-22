# MA9-05 Terra high 只读试点结果

日期：2026-09-22。基点/实际 HEAD：103977249b2312ae5cb01b2e1221314553f8ff0c。
worktree：E:/hzz/work/MA9/MA9-worktrees/duel-scan；分支 lane/duel-scan。试点无文件改动。
这是初始审计，不是正式 lane 交付；未运行全量 verify_default、未完成 reviewer 或用户实机验收。

## 已执行检查

Terra high 执行以下命令，cwd 均为上述 worktree，Python 均为 E:/hzz/work/MA9/.venv/Scripts/python.exe（3.14.4）：

```text
{python} -X utf8 -m unittest discover -s agent/tests -p test_duel_vehicle_runtime.py -v
{python} -X utf8 -m unittest discover -s agent/tests -p test_duel_vehicle_screen.py -v
```

分别 4/4、1/1 通过，退出码均 0。契约 B 为祖先，工作区干净。

## 总控核对后的发现

1. **优先修复：不稳定页仍能完成扫描。** `_sample_visible`（duel_vehicle_runtime.py:48-88）可返回 stable=False；`scan`（:291-337）仅在低等级边界判断使用该标志，仍可收录车辆、滑动和判断列表末端。现有 runtime 测试未覆盖此分支。
   总控独立内存模拟：复用测试中的 _Context/_card，将每次 `_sample_visible` 返回固定图像、同一张 D 卡与 False，max_pages=3；得到 status=edge_reached、scan_complete=true、收录 1 车、滑动 2 次。全程 mock，无设备操作、无文件改动。这证明消费者忽略不稳定标志，不代表已证明实机发生概率。
   后续最小范围：duel_vehicle_runtime.py 与 test_duel_vehicle_runtime.py。先建立失败回归，再明确有限重试/安全退出语义；不能仅为通过测试改变滚动车名采样策略。需要覆盖连续不稳定与恢复稳定两类情况。
2. **等级边界覆盖不足。** 代码已有 R→S→A→B→C→D 次序和混合页处理；当前 runtime 用例直接覆盖 R/S。建议在原 runtime 测试内参数化其余相邻边界。防守层的逐级补车测试归 MA9-06，不借此让 MA9-05 越界。
3. **快速重扫起点仍待实机。** 防守层已有最多两次 page_hint=None 重试（duel_defense_setup.py:159-185）；scan 通过点击等级标签尝试回到起点（duel_vehicle_runtime.py:273）。重复点同级标签是否真的重置列表需要用户证据；不能把代码意图等同于实机保证。

## 用户验证卡（供后续安排，尚未执行）

GUI 名称：对决资格赛：自动配置五辆弱防车（不开始比赛）。底层入口：对决_防守自动配置入口。
总控更正初稿：D 级是默认值，不是固定不可更改；assets/interface.json 的“对决防守车辆等级”提供 D/C/B/A/S/R 的 pipeline_override。本轮建议先明确选择 D 级。

从资格赛失败页或可进入配置的空防守页运行上述任务，记录开始/结束时间；不要手动开始比赛。预期最终五格车辆互不重复，报告 five_assigned、starts_race=false。若定位失败，记录是否先快速跳页，再回到等级开头完整扫描。R 级边界测试另行串行安排。

回传运行目录下 debug/duel_defense_gui_setup.json、debug/duel_defense_plan_live.json、debug/duel_vehicle_scan_live.json、debug/duel_tracks_live.json 与 debug/maafw.log；缺失文件据实说明，并附终态截图。日志与原图仅本地保存，不提交账号信息。

## 后续状态

MA9-05：只读试点完成，最小修复待执行；正式提交后仍需完整验收、独立 Terra high 复核和用户实机。MA9-06/07 尚未创建 worktree，MA9-04 保持暂停。
