# MA9

基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 的《狂野飙车 9》国服自动化脚本。目前主要在 MuMu 模拟器上开发，重点完善多人游戏循环。

项目处于开发试跑阶段。已生成可运行的 3 局和 20 局多人循环；长时运行和实际升降级后的稳定性仍在验证。

## 当前功能

- 主页导航、进入多人游戏及经典系列赛。
- 每局从系列赛首页“我的评级分”左侧徽章确认玩家段位，目前支持白金、黄金、白银。白金可按账号策略使用白金及以下车辆，黄金和白银同样向下兼容。
- 推荐车按审核后的顺序查找，先从相邻高段位起点反向搜索，再从本段位起点正向搜索；开启“仅拥有”，跳过缺油、未拥有和无法参赛的车辆。
- 推荐车全部不可用时倒序遍历车辆详情，找到有油且能参赛的车；到青铜首车仍不可用时停止，避免环绕死循环。
- 以车名定位、点击左侧车身，避开未满星车辆的整张图纸区域。误入图纸获取页时关闭 ×，返回后重新选择同一候选，恢复次数有上限。
- 开赛前确认 TouchDrive 开启。局内采用通用双击氮气兜底：两次间隔 0.75 秒，组合间等待 6 秒。
- 成绩→奖励→跳过广告机会→名人堂奖励（若出现，点击继续）→返回系列赛；处理升级“继续”、降级“确定”，下一局重新确认段位。
- 广告关闭具有最高识别优先级。处理多人服务器错误、连接错误重试和通用广告关闭；服务器错误返回选车列表后用独立计数重新查找推荐车。
- 英文界面切换为中文并应用重启设置，以及车库外观弹窗处理。

选车顶部高亮表示列表位置，车辆详情段位图标表示参赛要求，两者都不作为玩家当前段位依据。黄金车辆因段位不可用时会返回系列赛首页重新确认。

## 开始试跑

1. 在 MuMu 中运行游戏，使用 ADB 连接模拟器，确认截图正常。当前资源以横屏 1280×720 为参考，ADB 控制器短边设为 720。
2. 在 VS Code 安装并打开 **Maa Pipeline Support**，加载本项目资源并选择安卓 ADB 控制器。
3. 刷新任务列表，运行 **多人循环试跑（白金/黄金/白银自动识别，连续3局，自动开赛）**。
4. 3 局稳定后再试 20 局版本。可以从主页多人标签、系列赛首页、选车列表、车辆详情或局内/结算阶段接续；从列表或详情启动时会先返回系列赛首页确认段位。

这些循环会实际选车并开赛。未知页面、无法确认段位、恢复次数耗尽或所有车辆不可用时停止。当前没有独立的 60 分钟计时器。

## 数据与开发

| 目录 | 内容 |
|---|---|
| `assets/resource/pipeline/` | 已生成的导航、选车、异常恢复及多人循环任务 |
| `assets/resource/image/navigation/` | 识别用裁剪模板 |
| `captures/` | 原始截图与离线识别检查结果 |
| `data/sources/` | 车辆 CSV、推荐源文档及人工修正数据 |
| `data/generated/` | 车辆目录、已审核推荐快照和生成清单 |
| `tools/` | 数据导入、素材整理、任务生成和检查脚本 |

账号策略初始把 `data/sources/各级别霸主.docx` 中人工审核的“自动霸主”和“自动挡/脚本”车辆排在前面，其余已确认拥有的兼容车辆追加在后；用户可在 GUI 中重排。审核快照为 `data/generated/champion_rotation.json`，车型别名及段位修正保存在源数据和覆盖表中，旧 Excel 序列不再用于当前循环。

修改素材或已审核推荐数据后，在项目根目录生成动态循环并检查分支：

```powershell
python -X utf8 tools/prepare_dynamic_multiplayer_loop.py
python -X utf8 tools/check_dynamic_multiplayer_loop.py
```

Windows 开发环境可运行 `.\tools\setup_dev.ps1` 一键建立；固定依赖见 `agent/requirements*.txt`。不要用旧的静态 `prepare_multiplayer_loop.py` 直接覆盖动态循环结果。推荐源重新匹配后须先人工审核，再使用 `approve_champion_rotation.py` 保存审核快照。

多人循环使用 Pipeline 与 Python Agent 混合结构。账号选车策略从完整的已拥有车辆列表生成，可用 `tools/selection_gui.py` 打开独立排序窗口；发行包提供 `ma9-selection.exe`。保存后的顺序会在下一次多人选车时读取，所有优先车不可用则进入倒序兜底。九个段位的账号扫描确认拥有 292 辆，存档中的 425 张卡片 OCR 交叉检查全部通过；新运行时选车动作仍需在模拟器上完成多人试跑。开发说明见 [选车策略](docs/zh_cn/develop/selection_strategy.md) 和 [多人运行时改造](docs/zh_cn/develop/runtime_refactor.md)。

发布目标为 Windows x64 免 Python 环境包：MFAAvalonia 界面、MaaFramework 原生运行库、独立 MA9 Agent 和选车排序程序会被放进同一目录。运行 `.\tools\prepare_release_deps.ps1` 后即可用 `.\tools\build_windows_package.ps1` 组装本地包，详细说明见上述开发文档。

## 目前限制

- 自动段位切换覆盖白金、黄金、白银；其他玩家段位需补充首页识别及流程。
- 当前账号的推荐选车使用列表 OCR，不要求每辆车单独制作列表模板；实机滑动、滚动车名和详情状态仍需验证。
- 赛道加载识别仅有初步素材，尚未实现逐赛道百分比操作。局内氮气操作是通用兜底。
- 离线模板、分支和格式检查已经用于验证当前资源，不能替代模拟器实际点击与长时运行测试。

## 相关说明

- [多人循环试跑](docs/zh_cn/develop/multiplayer_loop_test.md)
- [当前多人逻辑模型](docs/zh_cn/develop/current_multiplayer_model.md)
- [指定车辆定位测试](docs/zh_cn/develop/vehicle_location_test.md)
- [动态段位判断](docs/zh_cn/develop/dynamic_league.md)
- [未满星车辆安全选车](docs/zh_cn/develop/blueprint_safe_selection.md)
- [倒序选车兜底](docs/zh_cn/develop/reverse_fallback.md)
- [数据目录说明](data/README.md)
- [框架开发指南](docs/zh_cn/develop/how_to_develop.md)

## 鸣谢与许可

本项目基于 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate)，由 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 驱动，并参考 [MaaAssistantArknights](https://github.com/MaaAssistantArknights/MaaAssistantArknights) 的运行时状态管理、战斗动作调度和基建选择器设计。

MA9 以 [GNU AGPL-3.0-or-later](LICENSE) 发布。源自 MaaPracticeBoilerplate 的部分保留原 MIT 版权和许可声明，详见 [NOTICE](NOTICE) 与 [LICENSES/MIT-MaaPracticeBoilerplate.txt](LICENSES/MIT-MaaPracticeBoilerplate.txt)。
