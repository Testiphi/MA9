# 账号选车顺序与多人循环

`config/garage.json` 记录已确认拥有的车辆；`config/selection_strategy.json` 保存玩家处于九个段位时的选车优先级。账号文件不提交到仓库。初始列表包含当前段位及以下**所有已确认拥有**的车，原先人工审核的霸主推荐排在最前，其余车辆按车辆段位和目录顺序追加。未知拥有状态不会被误判为没有车，也不会加入自动选车。

先运行完整的「仅拥有开启」车辆扫描，并用 `tools/manage_garage.py` 导入结果；然后创建或刷新账号策略：

```powershell
.\.venv\Scripts\python.exe tools/init_selection_strategy.py --refresh
```

打开排序窗口：

```powershell
.\.venv\Scripts\python.exe tools/selection_gui.py
```

发行包中的对应程序是根目录的 `ma9-selection.exe`。窗口按玩家当前段位分组，可查找车辆、置顶、上移、下移、置底、恢复默认及保存。查找只用于定位；排序前清空查找框。保存后，下一次运行时选车动作会直接读取新文件，无需重新生成 Pipeline。再次扫描车库后，重新打开窗口会保留已存顺序，并把新确认拥有的车追加到各兼容段位的末尾。

窗口选中车辆后，还可设置从段位起点或终点寻找该车的独立测试；测试会停在详情页，不开赛。操作见 [指定车辆定位测试](vehicle_location_test.md)。

策略含 `schema_version: 1`、`fallback: "reverse"`、`priorities`。九个 `priorities` 列表可使用当前及以下段位的已拥有车辆，数组从前到后即尝试顺序。运行时在选车列表使用 OCR 识别车名、油量，并点击卡片左侧车身以避开未满星车辆的图纸区；进入详情后再次检查油量和 TouchDrive。若所有优先车辆缺油、不可开始或不在列表，走既有的倒序兜底。正式多人入口目前支持从系列赛首页判断白金、黄金或白银玩家段位，其他六段位的配置已具备，入口识别仍待扩展。

开发时如更改了生成器或新增识别节点，才需重新生成资源：

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/prepare_dynamic_multiplayer_loop.py --reuse-list-checks
.\.venv\Scripts\python.exe -X utf8 tools/check_dynamic_multiplayer_loop.py
```

2026-09-17 的当前账号扫描覆盖九个车辆段位，共 122 页、425 次卡片观察，确认拥有 292 辆。存档截图的运行时 OCR 交叉检查为 425/425；实际多人自动选车仍需在设备上试跑，尤其要观察新车辆的详情可开始判断和跨段位倒序兜底。
