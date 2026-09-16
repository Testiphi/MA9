# MA9

基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 的《狂野飙车 9》国服自动化脚本。目前主要在 MuMu 模拟器上开发，重点完善多人游戏循环。

项目处于开发试跑阶段。已生成可运行的 3 局和 20 局多人循环；长时运行和实际升降级后的稳定性仍在验证。

## 当前功能

- 主页导航、进入多人游戏及经典系列赛。
- 每局从系列赛首页“我的评级分”左侧徽章确认玩家段位，目前支持黄金、白银。黄金使用黄金→白银→青铜推荐，白银使用白银→青铜推荐。
- 推荐车按审核后的顺序查找，先从相邻高段位起点反向搜索，再从本段位起点正向搜索；开启“仅拥有”，跳过缺油、未拥有和无法参赛的车辆。
- 推荐车全部不可用时倒序遍历车辆详情，找到有油且能参赛的车；到青铜首车仍不可用时停止，避免环绕死循环。
- 以车名定位、点击左侧车身，避开未满星车辆的整张图纸区域。误入图纸获取页时关闭 ×，返回后重新选择同一候选，恢复次数有上限。
- 开赛前确认 TouchDrive 开启。局内采用通用双击氮气兜底：两次间隔 0.75 秒，组合间等待 10 秒。
- 成绩→奖励→跳过广告机会→返回系列赛；处理升级“继续”、降级“确定”，下一局重新确认段位。
- 处理多人服务器错误、连接错误重试和通用广告关闭；服务器错误返回选车列表后用独立计数重新查找推荐车。
- 英文界面切换为中文并应用重启设置，以及车库外观弹窗处理。

选车顶部高亮表示列表位置，车辆详情段位图标表示参赛要求，两者都不作为玩家当前段位依据。黄金车辆因段位不可用时会返回系列赛首页重新确认。

## 开始试跑

1. 在 MuMu 中运行游戏，使用 ADB 连接模拟器，确认截图正常。当前资源以横屏 1280×720 为参考，ADB 控制器短边设为 720。
2. 在 VS Code 安装并打开 **Maa Pipeline Support**，加载本项目资源并选择安卓 ADB 控制器。
3. 刷新任务列表，运行 **多人循环试跑（黄金/白银自动识别，连续3局，自动开赛）**。
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

当前多人推荐来源为 `data/sources/各级别霸主.docx` 中的“自动霸主”和“自动挡/脚本”，使用人工审核后的 `data/generated/champion_rotation.json`。车型别名、段位与顺序修正保存在源数据及 `champion_overrides.json`，旧 Excel 序列不再用于当前循环。

修改素材或已审核推荐数据后，在项目根目录生成动态循环并检查分支：

```powershell
python -X utf8 tools/prepare_dynamic_multiplayer_loop.py
python -X utf8 tools/check_dynamic_multiplayer_loop.py
```

需要 Python、Pillow、NumPy 和 OpenCV。不要用旧的静态 `prepare_multiplayer_loop.py` 直接覆盖动态循环结果。推荐源重新匹配后须先人工审核，再使用 `approve_champion_rotation.py` 保存审核快照。

## 目前限制

- 自动段位切换只覆盖黄金、白银；其他玩家段位需补充首页识别及流程。
- DB12、P900 和 Electric R 当前缺少列表模板，推荐定位暂时跳过；倒序详情遍历仍可遇到这些车辆。
- 赛道加载识别仅有初步素材，尚未实现逐赛道百分比操作。局内氮气操作是通用兜底。
- 离线模板、分支和格式检查已经用于验证当前资源，不能替代模拟器实际点击与长时运行测试。

## 相关说明

- [多人循环试跑](docs/zh_cn/develop/multiplayer_loop_test.md)
- [动态段位判断](docs/zh_cn/develop/dynamic_league.md)
- [未满星车辆安全选车](docs/zh_cn/develop/blueprint_safe_selection.md)
- [倒序选车兜底](docs/zh_cn/develop/reverse_fallback.md)
- [数据目录说明](data/README.md)
- [框架开发指南](docs/zh_cn/develop/how_to_develop.md)

## 鸣谢与许可

本项目基于 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate)，由 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 驱动。代码许可见 [LICENSE](LICENSE)。
