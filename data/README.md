# 车辆数据

`sources/` 存放人工维护的原始文件：

- `国服_a9mmgj_top.csv`：已整理的 338 辆车基础目录，包含后补的 Tushek Aeon E（S 等级来自 Excel）。已确认 One77 白金、Aglaia 宗师、Aeon E 传奇、5N 青铜。
- `国服_a9mmgj_top_full.csv`：从 MutualExclusionAllocator 的 `数据源/国服_a9mmgj_top.csv` 原样复制的完整参考表（SHA-256：`CEC76FB6686BA51CD1C0B8677145CC2784BAE6EA9896F3AE69D92F4940BA1028`）。包含性能参数、最高星级及图纸需求，仅用于交叉验证。修订版有 338 行、338 个不同车名，已补入 Tushek Aeon E 并消除 Lykan 重复；规范化英文段位后，仍有 8 处与已审核目录不同，不直接覆盖目录。
- `多人选车_new.xlsx`：当前选车顺序来源，完整保留，不修改内容。
- `多人选车.xlsx`：旧版选车工作簿，保留备份。
- `vehicle_name_aliases.json`：人工确认的车型别名，如 loniq 5 N → IONIQ 5 N。

`generated/` 存放从数据源生成的文件：

- `vehicle_catalog.json`：车型、稳定 ID、车辆等级、段位。
- `multiplayer_rotation.json`：九段位的候选车辆顺序、昵称、备注，以及来源行号、位置和优先级。
- `vehicle_import_report.json`：数量和车型未匹配、段位/等级差异。
- `vehicle_import_review.md`：便于人工审核的数据差异表。
- `duel_auto_candidates.json`：从本地 MutualExclusionAllocator 的擂台数据生成的五区/四区“自动档”赛道候选，车名已对应本项目稳定 ID；用于擂台五图离线互斥规划，不代表可直接开赛。导入与用法见 `docs/zh_cn/develop/duel_selection.md`。

`multiplayer_profile.json` 是单独维护的运行偏好，不由导入器覆盖。当前段位手动配置为白银，向下兼容白银和青铜，组内沿用轮换队列次序，未拥有/段位不可用/缺油时跳过，全部不可用则停止。当前阶段停在车辆准备界面。当前倒序兜底生成器读取此配置决定相邻段位起点；原黄金推荐任务仍为独立黄金测试。升降段后需要更新 current_league 和 compatible_leagues，再重新生成倒序任务。

用户个人的持有清单保存在被 Git 忽略的 `config/garage.json`，不属于公共车型目录。用“仅拥有”开启状态下的扫描结果建立档案，未扫描到的车保持未知；手动修正高于后续扫描结果。说明见 `docs/zh_cn/develop/garage_recognition_design.md`。

## 更新

在项目根目录运行（Python 需安装 openpyxl）：

```powershell
python -X utf8 tools/import_vehicle_data.py
```

默认读取 `多人选车_new.xlsx` 的“！复制到脚本选车页”B 列，并检查其公式缓存与各段位 M2 序列一致，严格按序列生成 order。编辑后应在 Excel/WPS 中重新计算并保存。B/C 不一致记录到报告，不采用未更新的 C 列。需要明确改用其他工作簿或 C 列时，可传入 `--workbook 文件名 --sequence-column C`。

重建当前白银多人循环：

```powershell
python -X utf8 tools/prepare_multiplayer_loop.py
python -X utf8 tools/check_server_recovery.py
```

导入按名称忽略大小写、空格、标点和重音符号匹配基础目录，并应用人工别名。无法匹配的条目保留原名称并标记 catalog_id 为 null，不丢弃、不模糊猜测。

选车列表 OCR 的完整参考表校验可运行 `python tools/crosscheck_vehicle_scan.py <采样目录> --additional-records <历史截图识别 JSON>`。它比较车名、等级、已规范化的段位、性能分上界及图纸需求，报告异常但不修改目录或轮换。当前已识别车型清单见 `docs/zh_cn/develop/recognized_vehicles.md`。

实际定位段位和 D/C/B/A/S/R 车辆等级以 CSV 为准。段位冲突时迁移到 CSV 对应队列的末尾，本段位原顺序保持。Porsche Panamera Turbo S 已确认在黄金并恢复原黄金队列位置。车辆等级差异已按用户确认采用 CSV，Excel 原等级保留在 source_class，差异报告作为处理记录。

轮换 schema_version 为 2；source_groups 保留 Excel 原始序列，每个条目 source_league、source_order、source_position、source_row 保留原表来源。order 是迁移后目标段位队列中的执行次序。

“位置”是原表位置参考，不是屏幕点击坐标或当前列表索引。仅拥有、自定义组合、版本变化都可能改变显示位置，后续必须识别车型再点击。九段位分组也不代表自动跨所有段位轮换，需要后续根据赛事可用范围选用分组。

辅助符号、逗号拼接公式、性能参数、奖励自选包和升级计划未混入轮换配置，原工作簿仍保留这些内容。

当前多人循环读取 `multiplayer_profile.json` 的 rotation_file：`generated/champion_rotation.json`，由用户通过的“各级别霸主.docx”与人工修正生成。旧 `multiplayer_rotation.json` 仅保留 Excel 历史数据。当前每局读取系列赛首页玩家徽章，支持白金、黄金、白银三个玩家段位及向下兼容；生成独立的 3/20 局及各次服务器恢复分支，缺模板的候选记录到循环 manifest，不阻挡运行时 OCR 选车。

车名修正与插入位置单独维护于 `sources/champion_overrides.json`。重新匹配使用 `tools/match_champion_names.py`；人工通过后再运行 `tools/approve_champion_rotation.py` 保存审核快照，然后运行 `tools/prepare_dynamic_multiplayer_loop.py`。数据位于 resource 外部，运行时使用已生成任务。
