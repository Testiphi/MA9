# MA9

基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 的《狂野飙车 9》国服自动化脚本。目前主要在 MuMu 模拟器上开发，重点完善多人游戏循环。

项目处于公开测试阶段。Windows 测试包已经包含图形界面、MaaFramework 和独立运行时，普通使用者不需要安装 VS Code 或 Python。当前重点验证 3 局和 20 局多人循环；长时间运行、不同账号车库和实际升降级后的稳定性仍在测试。

## 下载

前往 [GitHub Releases](https://github.com/Testiphi/MA9/releases) 下载最新的 Windows x64 测试包并完整解压。请不要直接在压缩包内运行，也不要下载仓库的 Source code 代替测试包。

测试包暂时只面向 Windows 和《狂野飙车 9》国服。它会真实操作游戏、消耗车辆油量并开始多人比赛，请先使用方便观察的账号和 3 局任务试跑。

## 使用前准备

1. 安装 MuMu 模拟器，并在模拟器设置中开启 ADB 调试。其他支持 ADB 的安卓模拟器理论上可以连接，但尚未验证。
2. 在模拟器中安装并登录《狂野飙车 9》国服，把游戏语言设为中文。
3. 将游戏切到横屏，建议使用 1280×720 或相同比例；MA9 控制器的短边保持 720。
4. 关闭可能遮挡游戏的悬浮窗，并确保游戏至少已经进入主页。

## 第一次运行

1. 解压测试包，双击 `MFAAvalonia.exe`。
2. 控制器选择“安卓端”，资源选择“官服”。
3. 在设备列表选择正在运行的模拟器。如果没有自动出现，先确认 MuMu 的 ADB 开关和端口，再刷新设备列表。
4. 连接成功后，先运行“多人运行时数据自检（Agent）”。只有自检成功才继续。
5. 从游戏主页运行“多人循环试跑（白金/黄金/白银自动识别，连续3局，自动开赛）”。第一次请观察选车、TouchDrive、开赛、氮气和结算返回是否正常。
6. 3 局完整结束后，再考虑运行连续 20 局版本。

任务显示完成并不一定代表所有比赛都已跑完。如果画面停住、选错车辆或提前结束，请停止任务并保留测试包内的 `debug` 目录。提交问题时说明模拟器版本、游戏分辨率、开始任务时所在页面和最后停留页面，并附上 `debug/maafw.log` 与 `debug/on_error` 中对应截图；日志可能包含本机路径或游戏昵称，公开上传前请自行检查。

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
- 擂台资格赛五车页面可从图形界面生成弱防方案，或按所选等级自动配置五辆当前性能分最低的已拥有车辆；支持 D/C/B/A/S/R，配置完成后停在五车页面，不会点击“开始”。

选车顶部高亮表示列表位置，车辆详情段位图标表示参赛要求，两者都不作为玩家当前段位依据。黄金车辆因段位不可用时会返回系列赛首页重新确认。

## 测试版范围

- 当前自动识别白金、黄金、白银段位；其他段位会停止。
- 测试包不包含开发者的车库、个人选车排序、截图或日志。多人循环先使用内置推荐顺序和游戏内“仅拥有”筛选。
- 未知页面、无法确认段位、恢复次数耗尽或所有车辆不可用时会停止。
- 20 局表示局数上限，不是 60 分钟计时器。
- “账号被其他设备登录：立即顶回并重进擂台”会确认顶号标题和说明，点击右上角 ×，然后从游戏主页重新进入擂台；自定义等待时间后续加入。
- 擂台五车自动配置已加入图形界面，可从多人模式首页、资格赛失败/重开页或资格赛五张地图页面启动；已有五辆防守车时会原样保留并结束，中断后可从当前展开的第一个空位继续。首次请先运行“生成五车弱防方案（预演）”，确认识别结果后再运行实际配置。进攻选车策略仍在开发。

## 开发与本地打包

开发者可在 VS Code 安装 **Maa Pipeline Support**，直接加载 `assets` 资源调试。现有 `install/` 是本机运行目录，可能含日志和本机配置，不能原样发送给别人。已有 Windows x64 的 MFAAvalonia、MaaFramework 与独立 Agent 打包流程；本地构建 Agent 后，可运行 `tools/prepare_portable_preview.py --zip` 在 `build/portable/` 生成经过清理的试用包。

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
- [擂台离线识别清单](docs/zh_cn/develop/duel_offline_recognition.md)
- [框架开发指南](docs/zh_cn/develop/how_to_develop.md)

## 鸣谢与许可

本项目基于 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate)，由 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 驱动，并参考 [MaaAssistantArknights](https://github.com/MaaAssistantArknights/MaaAssistantArknights) 的运行时状态管理、战斗动作调度和基建选择器设计。

MA9 以 [GNU AGPL-3.0-or-later](LICENSE) 发布。源自 MaaPracticeBoilerplate 的部分保留原 MIT 版权和许可声明，详见 [NOTICE](NOTICE) 与 [LICENSES/MIT-MaaPracticeBoilerplate.txt](LICENSES/MIT-MaaPracticeBoilerplate.txt)。
