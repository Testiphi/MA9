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

源数据更新后可运行 `tools/import_duel_selection_data.py` 重建，并运行 `tools/test_duel_selection.py` 校验。当前已完成离线规划和单张截图的只读选车识别；赛道名 OCR、擂台选车交互和进攻循环尚未接入，因此不会在游戏中自动选车或开赛。

资格赛点击单张图的“选择车辆”后，会进入与经典系列赛不同的选车页：上方按 R、S、A、B、C、D 等级分栏，只列出已拥有车辆；同一等级按性能分降序排列，读取顺序是先同列上方、再同列下方，然后向右到下一列。列表不显示油量。新增的只读 `duel_vehicle_screen.py` 会对完整可见卡片提取车辆名称、当前/最高性能分和已亮/总星数；当前截图中 R 级三张完整卡片的结果分别为 Jesko Absolut `5,368/5,664`、6/6 星，Bolide `4,627/5,011`、5/6 星，Devel Sixteen `4,185/4,185`、1/6 星。Bolide 的整屏 OCR 曾漏掉性能分首位，局部重读后得到正确数字；若重读仍不可靠，该字段保持未知，不能据排序猜值。右侧露出一部分的 S 级卡片不会作为完整卡片点击。

可用保存的截图离线复查，不需要连接模拟器：

```powershell
.\.venv\Scripts\python.exe -X utf8 tools\probe_duel_vehicle_selection.py "captures\多人游戏_对决_资格赛_选择车辆_R级起点.png"
```

发布包构建会携带 Maa OCR 模型、车辆目录和 `duel_auto_candidates.json`，因此识别所需数据可以本地运行。当前解析器仍只校准了 16:9 的 R 级起点页面，尚未验证切换等级、横向滑动、车辆选中后的详情和油量。后续需要把解析器接到运行时，逐页去重并对目标车辆点击前复核名称、星级和性能分，选中后再确认详情与油量。
