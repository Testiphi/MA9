# 用户车库识别与账号档案

目标是让分发版用户像使用 MAA 的“干员识别”一样，扫描自己的车库、检查并修正结果，再让选车器只考虑该账号可用的车。MAA 官方[小工具说明](https://docs.maa.plus/zh-cn/manual/introduction/tools.html)列出持有/未持有识别及剪贴板、JSON、Markdown、CSV 导出；[回调协议](https://docs.maa.plus/zh-cn/protocol/callback-schema.html)将全量目录 `all_opers` 与已持有详情 `own_opers` 分开，并用 `done` 标识扫描是否结束。本机 MAA 安装包的 `data/OperBoxData.json` 也把识别结果持久化为 `done`、`own_opers`、`syncTime`。MA9 借鉴这种“公共目录 + 账号档案 + 独立扫描工具”的分层，不直接复用 MAA 的明日方舟识别代码。

## 当前已落地的基础

- `data/generated/vehicle_catalog.json` 是公共车型字典；`config/garage.json` 是本机账号档案，已被 Git 忽略，不写入发布资源。缺少档案时现有逻辑照常工作。
- `tools/sample_vehicle_leagues.py` 在多人选车列表按指定段位采集原图、逐卡 OCR 与页数/停止原因。**建档前须手动开启“仅拥有”**，不从关着的列表推断车辆持有状态。
- `tools/manage_garage.py import-scan <采样目录>` 只把“仅拥有”开启时读到的车型记为持有；未扫到的车保持未知，即使某段位报告到边也不自动标为未持有。用户可用 `set-owned <完整车名或 ID> yes|no|unknown` 手动修正，之后的扫描不会覆盖手动选择。
- Agent 的“识别选车列表可见车辆（只读）”任务和 `VehicleSelector.from_rotation` 已可按账号档案的已持有 ID 缩小候选。油量不从档案读取，仍在每次开赛前看实时画面。

示例：

```powershell
# 游戏停在多人选车列表，并手动开启“仅拥有”后采样。
.venv\Scripts\python.exe tools/sample_vehicle_leagues.py --leagues 青铜 白银 黄金 --max-pages 10
.venv\Scripts\python.exe tools/manage_garage.py import-scan debug/vehicle_scans/league_survey_时间戳
.venv\Scripts\python.exe tools/manage_garage.py set-owned "Ferrari J50" yes
```

档案只记录 `true`（扫描确认持有或手动确认）和手动设定的 `false`。缺项是未知，不等于未持有。每个段位保存 `pages/cards/recognized/status/complete` 和时间；`page_limit`、识别失败或弹窗中断均为部分扫描。用户账号数据留在本机 `config/garage.json`；公共目录与用户档案必须分别更新和备份。

## 分发版还需要完成

1. 增加独立“车库识别”入口：从主页进入车库或多人选车，确认“仅拥有”开启，逐段位扫描；扫描过程中显示进度、已识别数、未知卡片和停止原因。当前采集器仍要求用户先手动停在选车列表，且每段位最多 10 页，不能把 `page_limit` 当作全车库完成。
2. 给分发包配结果界面：按 D/C/B/A/S/R 与段位显示持有、未知、手动排除；点击车型可核对截图和 OCR，手动增删或重命名别名；导出 JSON/CSV/Markdown。MFA 的通用任务列表可先承载扫描入口，但这种可编辑表格需要单独的工具界面或扩展前端。
3. 让正式多人循环在运行时加载 `config/garage.json` 并与用户选车优先级求交集。当前正式循环仍由静态 Pipeline 生成；Agent 只读诊断和选择器已支持过滤，但**尚不能声称正式多人循环已改为按账号档案选车**。运行时仍需核对段位可用、是否解锁、当前油量和 TouchDrive，档案不能替代这些实时检查。
4. 扫描列表只能确认车名、性能、燃油、图纸与卡片升级底色。详情遍历再补当前星级等字段；任何字段识别冲突都保留来源和原图供用户审核。账户切换时应使用不同档案，避免混用车库。
