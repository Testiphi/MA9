# MA9

[English](README.md) · 简体中文

MA9 是基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 的《狂野飙车 9》国服自动化脚本，主要在 MuMu 模拟器上开发。项目仍处于公开测试阶段。现有多人循环任务仍可使用，但多人功能的进一步开发目前暂停；擂台车库与配车工作正在做离线复核。

## 下载

从 [GitHub Releases](https://github.com/Testiphi/MA9/releases) 下载 Windows x64 测试包并完整解压。不要直接在压缩包内运行，也不要用仓库的 Source code 压缩包代替测试包。测试包包含图形界面、MaaFramework 和独立运行时，普通使用者无需安装 VS Code 或 Python。

测试包目前只面向 Windows 和《狂野飙车 9》国服。它会操作游戏、消耗车辆油量并开始多人比赛。首次建议使用方便观察的账号，先试跑 3 局任务。

## 使用前准备

1. 安装 MuMu 模拟器，并在设置中开启 ADB 调试。其他支持 ADB 的安卓模拟器尚未验证。
2. 安装并登录《狂野飙车 9》国服，将游戏语言设为中文。
3. 将游戏切到横屏，建议使用 1280×720 或相同比例；MA9 控制器的短边保持 720。
4. 关闭遮挡游戏的悬浮窗，确保游戏至少已进入主页。

## 第一次运行

1. 解压测试包，双击 `MFAAvalonia.exe`。
2. 控制器选择“安卓端”，资源选择“官服”。
3. 在设备列表中选择正在运行的模拟器。如果没有自动出现，检查 MuMu 的 ADB 开关和端口，再刷新设备列表。
4. 连接后先运行“多人运行时数据自检（Agent）”；自检成功后再继续。
5. 从游戏主页运行“多人循环试跑（白金/黄金/白银自动识别，连续3局，自动开赛）”，观察选车、TouchDrive、开赛、氮气和结算返回。
6. 3 局完整结束后，再考虑连续 20 局版本。

任务显示完成不一定代表比赛都已跑完。如果画面停住、选错车或提前结束，请停止任务并保留测试包内的 `debug` 目录。反馈时提供模拟器版本、游戏分辨率、任务开始和最后停留的页面，以及 `debug/maafw.log` 和 `debug/on_error` 中对应截图。日志可能包含本机路径或游戏昵称，公开上传前请检查。

## 当前功能

多人循环从主页进入经典系列赛，每局读取系列赛首页“我的评级分”左侧徽章，识别白金、黄金或白银段位；可用车辆按段位向下兼容。它按已审核推荐顺序查找车辆，并结合游戏内“仅拥有”筛选，跳过缺油、未拥有或不能参赛的车。推荐车都不可用时，会倒序查看车辆详情，直到找到可参赛车辆或到达青铜首车。选车按名称定位并点击左侧车身，以避开未满星车辆的图纸区域；误入图纸页后会有限次恢复。

开赛前会确认 TouchDrive，局内使用通用双击氮气兜底（两次间隔 0.75 秒，组合间等待 6 秒）。赛后处理成绩、奖励、广告机会、名人堂奖励及返回系列赛；升级或降级后，下一局重新确认段位。广告关闭优先处理，服务器或连接错误会有限次重试。另有英文界面切换中文、应用重启设置和车库外观弹窗处理。

擂台资格赛五车页面已有防守配置任务：可从图形界面生成弱防预演方案，或按所选等级配置五辆当前性能分最低的已拥有车辆，支持 D/C/B/A/S/R，不足五辆时依次用更低等级补足且不重复。已有五辆防守车会保留；中断后可从展开的第一个空位继续。车辆扫描使用多帧 OCR，定位失败会回退完整扫描并有限次重试。配置完成后停在五车页面，不点击“开始”。首次请先运行“生成五车弱防方案（预演）”，核对识别结果再运行实际配置。

列表顶部高亮表示位置，车辆详情中的段位图标表示参赛要求，两者都不是玩家当前段位的证据。黄金车因段位限制不可用时，任务会返回系列赛首页重新确认。

## 擂台离线复核与配车

开发用工具可对保存的擂台车库画面复核车型与星条，将 MutualExclusionAllocator 的数据和已审核逻辑同步为有版本的本地快照，支持快照回退与帕累托配车预览。当前离线配车预览采用普通档（Normal）。这个选择不会扩大游戏自动操作能力；离线配车尚未接入执行，也没有完整的用户端车库图形界面。这些开发用工具不代表公开测试包已包含该功能。用法和边界见[分配器同步与离线配车](docs/zh_cn/develop/duel_allocator_sync.md)。

## 测试版范围与限制

- 自动段位切换目前覆盖白金、黄金、白银；遇到其他段位、未知页面、无法确认的状态、恢复次数耗尽或无可用车辆时会停止。
- 测试包不含开发者的个人车库、排序、截图或日志。多人循环先使用内置推荐顺序和游戏内“仅拥有”筛选。20 局是局数上限，不是 60 分钟计时器。
- “账号被其他设备登录：立即顶回并重进擂台”会核对顶号提示，点击右上角 ×，再从主页进入擂台；自定义等待时间尚未加入。
- 赛道加载识别只有初步素材，未实现逐赛道百分比操作；局内氮气仍是通用兜底。擂台进攻选车策略仍在开发。
- 列表 OCR 减少逐车模板需求，但模拟器滑动、滚动车名和详情状态仍需验证。离线识别、分支与格式检查不能代替实际点击和长时间运行测试。

## 开发与本地打包

开发者可在 VS Code 安装 **Maa Pipeline Support** 并加载 `assets` 调试。`install/` 是本机运行目录，可能含日志和配置，不能原样发送给他人。Windows 开发环境可运行 `.\tools\setup_dev.ps1` 建立；依赖见 `agent/requirements*.txt`。

修改素材或已审核推荐数据后，在项目根目录重新生成并检查动态多人循环：

```powershell
./.venv/Scripts/python.exe -X utf8 -B tools/prepare_dynamic_multiplayer_loop.py
./.venv/Scripts/python.exe -X utf8 -B tools/check_dynamic_multiplayer_loop.py
```

不要用旧的静态 `prepare_multiplayer_loop.py` 覆盖动态循环。推荐源重新匹配后先人工审核，再使用 `approve_champion_rotation.py` 保存审核快照。多人循环结合 Pipeline 与 Python Agent；账号策略按已拥有车辆和审核顺序生成。可用 `tools/selection_gui.py` 打开独立排序窗口，发行包中对应 `ma9-selection.exe`。保存后的顺序在下一次多人选车时读取，优先车不可用则进入倒序兜底。开发细节见[选车策略](docs/zh_cn/develop/selection_strategy.md)和[多人运行时改造](docs/zh_cn/develop/runtime_refactor.md)。

本地 Windows x64 打包流程会把 MFAAvalonia、MaaFramework、独立 Agent 和选车排序程序放进同一目录。运行 `.\tools\prepare_release_deps.ps1` 后，可用 `.\tools\build_windows_package.ps1` 组装；也可在本地构建 Agent 后运行 `tools/prepare_portable_preview.py --zip`，在 `build/portable/` 生成清理过的试用包。这些命令说明本地构建方法，不表示新的离线配车工具已进入公开发布包。

| 目录 | 内容 |
| --- | --- |
| `assets/resource/pipeline/` | 导航、选车、异常恢复和多人循环任务 |
| `assets/resource/image/navigation/` | 识别用裁剪模板 |
| `captures/` | 原始截图与离线识别检查结果 |
| `data/sources/` | 车辆 CSV、推荐源文档及人工修正 |
| `data/generated/` | 车辆目录、已审核推荐快照和生成清单 |
| `tools/` | 数据导入、素材整理、任务生成和检查脚本 |

账号策略初始优先使用 `data/sources/各级别霸主.docx` 中人工审核的“自动霸主”和“自动挡/脚本”车辆，再追加已确认拥有的兼容车辆；用户可在 GUI 中重排。当前多人循环使用 `data/generated/champion_rotation.json` 审核快照，不再使用旧 Excel 序列。

## 相关说明

- [多人循环试跑](docs/zh_cn/develop/multiplayer_loop_test.md)
- [当前多人逻辑模型](docs/zh_cn/develop/current_multiplayer_model.md)
- [指定车辆定位测试](docs/zh_cn/develop/vehicle_location_test.md)
- [动态段位判断](docs/zh_cn/develop/dynamic_league.md)
- [未满星车辆安全选车](docs/zh_cn/develop/blueprint_safe_selection.md)
- [倒序选车兜底](docs/zh_cn/develop/reverse_fallback.md)
- [擂台离线识别清单](docs/zh_cn/develop/duel_offline_recognition.md)
- [分配器同步与离线配车](docs/zh_cn/develop/duel_allocator_sync.md)
- [数据目录说明](data/README.md)
- [框架开发指南](docs/zh_cn/develop/how_to_develop.md)

## 鸣谢与许可

MA9 基于 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate)，由 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 驱动，并参考 [MaaAssistantArknights](https://github.com/MaaAssistantArknights/MaaAssistantArknights) 的运行时状态管理、战斗动作调度和基建选择器设计。

项目按 [GNU AGPL-3.0-or-later](LICENSE) 发布。源自 MaaPracticeBoilerplate 的部分保留原 MIT 版权与许可声明，见 [NOTICE](NOTICE) 和 [LICENSES/MIT-MaaPracticeBoilerplate.txt](LICENSES/MIT-MaaPracticeBoilerplate.txt)。
