# 车辆数据

`sources/` 存放人工维护的原始文件：

- `国服_a9mmgj_top.csv`：已整理的 338 辆车基础目录，包含后补的 Tushek Aeon E（S 等级来自 Excel）。已确认 One77 白金、Aglaia 宗师、Aeon E 传奇、5N 青铜。
- `多人选车.xlsx`：原始选车工作簿，完整保留，不修改内容。
- `vehicle_name_aliases.json`：人工确认的车型别名，如 loniq 5 N → IONIQ 5 N。

`generated/` 存放从数据源生成的文件：

- `vehicle_catalog.json`：车型、稳定 ID、车辆等级、段位。
- `multiplayer_rotation.json`：九段位的候选车辆顺序、昵称、备注，以及来源行号、位置和优先级。
- `vehicle_import_report.json`：数量和车型未匹配、段位/等级差异。
- `vehicle_import_review.md`：便于人工审核的数据差异表。

`multiplayer_profile.json` 是单独维护的运行偏好，不由导入器覆盖。当前段位手动配置为黄金，向下兼容，默认按黄金、白银、青铜顺序查找，组内沿用轮换队列次序，未拥有/段位不可用/缺油时跳过，全部不可用则停止。当前阶段停在车辆准备界面。此配置尚未接入自动选车，升降段后需要更新 current_league 和 compatible_leagues。

## 更新

在项目根目录运行（Python 需安装 openpyxl）：

```powershell
python -X utf8 tools/import_vehicle_data.py
```

编辑顺序后应在 Excel/WPS 中重新计算并更新“！复制到脚本选车页”的 C 列仅文本序列，再保存。导入器检查 B 列公式缓存和 C 列一致，并严格按序列生成 order；不按可能并列的“优先级”重新排序。

导入按名称忽略大小写、空格、标点和重音符号匹配基础目录，并应用人工别名。无法匹配的条目保留原名称并标记 catalog_id 为 null，不丢弃、不模糊猜测。

实际定位段位和 D/C/B/A/S/R 车辆等级以 CSV 为准。段位冲突时迁移到 CSV 对应队列的末尾，本段位原顺序保持。Porsche Panamera Turbo S 已确认在黄金并恢复原黄金队列位置。车辆等级差异已按用户确认采用 CSV，Excel 原等级保留在 source_class，差异报告作为处理记录。

轮换 schema_version 为 2；source_groups 保留 Excel 原始序列，每个条目 source_league、source_order、source_position、source_row 保留原表来源。order 是迁移后目标段位队列中的执行次序。

“位置”是原表位置参考，不是屏幕点击坐标或当前列表索引。仅拥有、自定义组合、版本变化都可能改变显示位置，后续必须识别车型再点击。九段位分组也不代表自动跨所有段位轮换，需要后续根据赛事可用范围选用分组。

辅助符号、逗号拼接公式、性能参数、奖励自选包和升级计划未混入轮换配置，原工作簿仍保留这些内容。

当前 JSON 尚未接入游戏选车动作。数据位于 resource 外部，不会被 Maa 当成 Pipeline，也尚未自动打包到发行目录；接入运行时后再增加配置加载与打包路径。
