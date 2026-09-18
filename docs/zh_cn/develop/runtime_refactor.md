# 多人运行时改造

现有 3 局与 20 局 Pipeline 保留为可运行基线。新实现逐步把需要跨页面保存状态的逻辑迁移到 Python Agent，避免为每一局、每辆车和每次滑动复制节点。

## 模块边界

- `agent/ma9_agent/models.py`：段位、矩形和车辆观察结果等公共模型。
- `agent/ma9_agent/vehicle_selector.py`：过滤、推荐顺序、列表停滞/异常重访判断和安全点击坐标。
- `agent/ma9_agent/race_controller.py`：比赛中断优先级、进度动作和双氮气兜底调度。
- `agent/ma9_agent/runtime_config.py`：读取并验证现有段位、推荐车辆和赛道数据源。
- `agent/runtime_action.py`：MaaFramework 自定义动作注册入口。

识别器负责把画面转换成结构化观察结果；选择器只作决策；控制器负责点击、滑动及点击后的复核。三者不得互相嵌入模板文件名或固定循环次数。

## 当前阶段

第一阶段已完成纯决策核心、数据自检和只读车辆识别动作，尚未替换正式多人循环：

```powershell
python -m unittest discover -s agent/tests -v
```

在 Windows PowerShell 中一键建立开发环境：

```powershell
.\tools\setup_dev.ps1
```

脚本会建立 `.venv`、安装固定版本的 MaaFW/PyInstaller/OpenCV 与校验工具，并在存在 Node.js 时安装 Maa 资源检查器。等价的手动命令为：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r agent/requirements-dev.txt
```

`assets/interface.json` 的开发配置会从 `.venv` 启动 Agent。数据自检任务为“多人运行时数据自检（Agent）”。

账号优先选车顺序现已通过 [选车策略配置](./selection_strategy.md) 接入现有白银、黄金多人循环的生成器；修改配置后需重新生成 Pipeline。倒序兜底沿用原有节点。尚未有列表识别素材的车辆不会进入推荐节点。

“识别选车列表可见车辆（只读）”在多人选车列表截图上复用现有车名模板，只输出可见车名、段位、车名框和安全点击候选点，不点击，也不推断燃油或车辆是否可参赛。结果写入 `debug/vehicle_recognition.json`。当前 49 辆推荐车中有 13 辆具备列表模板；黄金及兼容段位缺少 DB12、P900、Electric R 的列表模板。缺少模板不要求游戏解锁，可在车辆可见时补截图，也可后续加入 OCR 识别。此任务通过 `tools/prepare_vehicle_recognition.py` 生成独立识别节点，正式选车循环目前仍使用原有 Pipeline。

Windows x64 发布包可先构建独立 Agent：

```powershell
.\.venv\Scripts\python.exe tools/build_agent.py --clean
```

生成物位于 `build/agent/win-x64/dist/ma9-agent/`。`tools/install.py` 找到该目录时，会把它复制进发布包并将 `interface.json` 改为启动随包携带的可执行文件；找不到时才退回系统 Python。

完整 Windows x64 包可直接准备固定版本的 MaaFramework 与 MFAAvalonia，再执行打包：

```powershell
.\tools\prepare_release_deps.ps1
.\tools\build_windows_package.ps1 -Version v0.1.0
```

GitHub Actions 的 `install` 工作流会自动下载 MaaFramework v5.13.0 与 MFAAvalonia v2.12.0、构建独立 Agent 并生成 `MA9-win-x86_64`。这与 Python binding 的 MaaFW 版本保持一致。当前实际目标是 MuMu 所在的 Windows x64，因此暂不生成未经验证的 macOS、Linux、ARM 与 Android 包。

## 后续接入顺序

1. 实现车辆卡片自定义识别，输出车名、卡片矩形、拥有/解锁、油量、完整可见状态。
2. 将列表页识别结果交给 `VehicleSelector`，按页面指纹判断继续滑动、停滞或异常重访；列表没有环绕。
3. 点击车辆左侧安全区域，进入详情后复核车辆、有油、可参赛和 TouchDrive。
4. 用运行时会话保存当前段位、已尝试车辆、恢复次数和完成局数。
5. 接入赛道进度 OCR，并由 `RaceController` 执行赛道动作；识别不足时继续使用双氮气兜底。
6. 长时验证通过后，将正式入口从展开式 Pipeline 切换到 Agent 控制器。
