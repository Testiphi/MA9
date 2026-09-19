# 擂台五图选车规划

选车规划器已从本地 MutualExclusionAllocator 仓库读取 `gauntlet_data.json` 和 `cars.json`，将“自动档”赛道候选及车型昵称转换为 MA9 的稳定车辆 ID，产物是 [`data/generated/duel_auto_candidates.json`](../../../data/generated/duel_auto_candidates.json)。产物包含源文件 SHA-256，可随 MA9 分发；重新生成时才需要本地 MutualExclusionAllocator 仓库，不会修改该仓库。

当前源数据有 83 条小地图、21 个大地图；五区 78 条、四区 74 条有自动档候选，共 622 个赛道候选关系。所有自动档车名都已对应到 MA9 的 338 辆车辆目录，没有模糊猜测。缺自动档的赛道会返回 `no_auto_candidates`，不会悄悄采用理论档、高手档或普通档。自动档只有推荐顺序，没有比赛时间，因此不能据此预测胜率，也不能将手动特殊跑法当成 TouchDrive 的实测性能。

进攻规划输入为五组“大地图/小地图”、赛区（五区或四区）与确认拥有的车库。算法过滤未拥有车，枚举五图互斥方案，先尽可能填满五个位置，再保留优先级向量的非支配方案，按优先级和排序输出。若候选不足，`complete=false` 并列出缺口。若已知缺油，可通过 API 的 `unavailable_ids` 排除；即使离线方案完整，实际点击前仍需在游戏中确认车辆可用、油量、五个位置确实已选中和开始按钮可用。

下防是独立策略：进组前五场资格赛优先挑车库里最高性能分最低的五辆 D 级车，满足至少三辆弱 D 级车的要求。性能分只用于挑弱车，不用于预测赛道时间；进组后通常不重打防守。

在 MA9 根目录运行离线预览：

```powershell
.\.venv\Scripts\python.exe -X utf8 tools\plan_duel_selection.py weak-defense
.\.venv\Scripts\python.exe -X utf8 tools\plan_duel_selection.py attack '旷野飙车/河岸狂飙' '热带天堂/酒店大道' '花都疾驰/地铁冲刺' '高地穿梭/灯塔' '沙漠迷雾/地下冲刺' --zone 五区
```

源数据更新后可运行 `tools/import_duel_selection_data.py` 重建，并运行 `tools/test_duel_selection.py` 校验。地图 OCR 和逐级滑动查车现已接入运行时；进攻循环尚未接入。选车任务最多只会配置车辆，绝不点击“开始”。

资格赛点击单张图的“选择车辆”后，会进入与经典系列赛不同的选车页：上方按 R、S、A、B、C、D 等级分栏，只列出已拥有车辆；同一等级按性能分降序排列，读取顺序是先同列上方、再同列下方，然后向右到下一列。列表不显示油量。新增的只读 `duel_vehicle_screen.py` 会对完整可见卡片提取车辆名称、当前/最高性能分和已亮/总星数；当前截图中 R 级三张完整卡片的结果分别为 Jesko Absolut `5,368/5,664`、6/6 星，Bolide `4,627/5,011`、5/6 星，Devel Sixteen `4,185/4,185`、1/6 星。Bolide 的整屏 OCR 曾漏掉性能分首位，局部重读后得到正确数字；若重读仍不可靠，该字段保持未知，不能据排序猜值。右侧露出一部分的 S 级卡片不会作为完整卡片点击。

可用保存的截图离线复查，不需要连接模拟器：

```powershell
.\.venv\Scripts\python.exe -X utf8 tools\probe_duel_vehicle_selection.py "captures\多人游戏_对决_资格赛_选择车辆_R级起点.png"
```

2026-09-18 MuMu 实机补验保存在 [`captures/duel_selection_live/`](../../../captures/duel_selection_live/)。在第 5 张资格赛地图打开选车页，点顶部 D 后，列表定位到 D 级的一段位置，左右边缘卡片可能被裁切；向左滑动会露出后续车辆。两张 D 级列表截图的 OCR 各识别出四张可安全点击的卡片，并读出当前性能分；只显示一个性能分数字时，最高分保留未知。带金色底的卡片会干扰列表星级取样，因此星级保留未知，点开详情后再核对。原 R 级截图的三张完整卡片回归结果未变。`duel_d_start_probe.json` 和 `duel_d_swipe1_probe.json` 记录了对应识别结果。

实机点 Hyundai IONIQ 5 N 列表卡进入车辆详情，详情显示 D 级、当前性能分 `2,559` 和星级，右下绿色“选择”才将车配置到当前地图；配置后回到五图防守页，该位置显示车辆和“更换车辆”，未开赛时右下“开始”仍不可用。同一辆车在另一地图的列表中仍可打开，但卡片上出现原赛道提示；点详情页“选择”会弹出确认框，明确告知车辆将从原赛道自动移出。本次取消了转移，最终只在第 5 张地图保留一辆测试用 D 级车。自动化不能仅凭列表卡片可点击就认为车辆空闲，需读取占用提示并避免误转移。

发布包构建会携带 Maa OCR 模型、车辆目录和 `duel_auto_candidates.json`。新增的 `对决_读取五张地图` 从五图编队页识别按顺序排列的五组大/小地图，结果写到 `debug/duel_tracks_live.json`；五个不同展开位置的保存截图及 MuMu 当前编队均识别完整。若某个名字不能与参考地图可靠匹配，`complete=false`，不猜测。离线复核可运行 `tools/probe_duel_tracks.py` 并传入一张或多张五图截图。

`对决_扫描D级车辆` 从选车页点击 D，向左逐页滑动，去重并在页面停止变化时结束；实机 9 页识别到 25 辆不同的 D 级车，结果写到 `debug/duel_vehicle_scan_live.json`。R 级只读扫描也识别出三辆 R 级车，并在下一页看到 S 级车时判断为等级边界，不将其混入 R 级。`对决_按配置查找车辆` 读取不随发布包提交的 `config/duel_vehicle_request.json`，例如 `{ "class": "D", "vehicle_id": "car_b886dfe99925297f", "choose": false, "max_pages": 25 }`；可增加 `"performance": 2307` 与 `"stars": 4` 作为详情页的精确约束。默认 `choose=false`，找到后停在详情；显式改为 `true` 才会点“选择”。若详情车型、性能分或星级不符，该车已占用其他地图、页面状态不明或找不到车辆，任务停止而不提交。实机已从 D 级起点滑到第 2 页找到 Hyundai IONIQ 5 N，并识别出它占用第 5 图；也已找到未占用的 Peugeot SR1、核对详情后配置到第 4 图，并复核返回页显示了该车。测试期间未开赛；随后模拟器重启，重新进入资格赛时五图均恢复未选车，因此后续运行必须重新读取页面，不能沿用上次的临时配车状态。游戏界面当前只验证 16:9，星级在金色列表卡上保持未知，详情星级解析只用 D 级截图验证；后续接入 MutualExclusionAllocator 时，仍需验证进攻页五图地图布局及油量等可用性检查。
