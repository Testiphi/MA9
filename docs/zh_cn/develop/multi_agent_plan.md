# MA9 多智能体工作计划

本文档是编排层（GPT-6 Astra）与八条 lane 的工作规则，长期有效。
每席的边界、模型、依赖、验收命令在 `agent/lanes.yaml`；本文件负责「为什么」与「不可违反项」。

---

## 0. 启动指令（把这一段原样交给编排层）

```
你在 MA9 仓库里担任编排层。默认使用 GPT-6 Astra medium；冻结契约、
处理跨 lane 冲突和最终关键合并时临时升到 high。先读这两个文件，不要凭记忆：
  docs/zh_cn/develop/multi_agent_plan.md     （规则，长期有效）
  agent/lanes.yaml                            （每席的边界、模型、依赖、验收命令）
需要写契约时再读 docs/zh_cn/develop/contract_freeze_draft.md

执行顺序：
1. 由编排层亲自冻结契约，不得下放给普通子智能体：按 contract_freeze_draft.md 固化 models / vehicle_screen /
   garage_profile / selection_strategy / selection_runtime 的签名，处理其中
   标出的两处待决瑕疵；再冻结第 6 节的「赛道策略表」接缝（schema + 断言）。
   为 runtime_action.py 与 assets/interface.json 指定单 owner。
   契约必须以「签名 + 断言 + schema」表达，不要写成散文。
2. 使用两次提交完成冻结：先把契约实现、断言与 schema 提交到 main，得到提交 A；
   再把 lanes.yaml 的 contract_frozen_at 填为 A，并单独提交元数据提交 B。
   不能在 A 中填写 A 自身的 SHA，因为字段变化会改变提交 SHA。
3. 从 B 或其后提交按 lanes.yaml 建 worktree，一次只放行「依赖已满足且设备空闲」的 lane。
4. 每个 lane 的提示词按本文件第 9 节的模板写，不要自己发挥。
   提示词里必须写明该席的 owns、owns_new 与 owns_generated —— 少了边界，lane 会越界改别人的文件。
   GPT 席位通过 Codex 直接启动；DeepSeek、GLM、Kimi 席位由编排层生成完整提示词，
   交给用户转发到 WorkBuddy，收到结果后仍由编排层在本地独立验收。

不可违反：
- 只有 Astra 编排层可以创建、调度和结束子智能体；lane 子智能体不得再创建下级智能体，
  不得绕过编排层直接协调其它 lane。跨 lane 发现一律上报编排层。
- 契约与集成由 Astra 编排层亲自负责；日常编排用 medium，冻结、冲突裁决和关键合并用 high。
- 子任务优先使用 DeepSeek V4.1 Flash；擂台进攻的回溯、Pareto 前沿、互斥与 DP 使用 GLM-5.3 max。
- `multiplayer`、`duel-scan`、`duel-attack` 属关键路径，禁止降低各自在 `lanes.yaml` 中的档位。
- 局内策略是「只挂载、不自研」：第三方按赛道百分比分点的策略表以只读方式接入，
  读不到赛道名或读不到百分比时一律落回通用兜底。要改这个前提，先回来改本文件。
- 跳幅超限的读数（真实 40 误读成 91）必须丢弃该帧，不得接受；
  阈值迟到越过 not_after 时必须跳过而不是补发。这两条是灾难级失败的唯一防线。
- `assets/interface.json` 是 contract 单一 owner 管理的手写源配置；多人循环 JSON 等受控生成物禁止手改；
  第三方策略表属外来只读输入，禁止手改、禁止提交进本仓库。
- ADB 是单例（127.0.0.1:16384）。needs_device 为 true 的 lane 验证请求必须串行；只有用户明确要求智能体实机操作时才发设备令牌。
- 为节省额度，**实机验证默认由用户执行**。lane 负责产出安装包、最短复现步骤和要回传的日志；
  除非用户在当前会话明确要求智能体操作模拟器，否则不得自行接管游戏。
- 每席的完成定义 = 通过 lanes.yaml 的 verify_default 全部三项，
  且 git diff --name-only 落在 owns ∪ owns_new ∪ owns_generated 内；owns_generated 只能由指定工具生成，仍禁止手改。
- 有冲突时以 CI 为准，不以任何 lane 的自我报告为准。
```

这段刻意写得很短：它的唯一作用是把编排层引到上面那两个文件。以后调整 lane 配置只改 `lanes.yaml`，不需要重新粘贴任何东西。

### 0.1 模型与档位政策

- **编排层**：GPT-6 Astra medium。它负责拆解、依赖调度、设备令牌、验收、合并与最终裁决；
  冻结契约、跨 lane 冲突或关键路径失败时临时切到 high。若环境不能在会话中切档，单独启动一次 Astra high 任务处理该阶段。
- **主要执行模型**：DeepSeek V4.1 Flash。`nav`、`build`、`duel-defense` 用 high；
  视觉、长上下文或关键遍历任务 `vehicle`、`multiplayer`、`duel-scan` 用 max。
- **最难算法席**：`duel-attack` 用 GLM-5.3 max。
- **独立复核**：`lanes.yaml` 存在 `reviewer` 的 lane，在 owner 验收通过后必须由 GPT-5.6 Terra high
  做只读复核；复核者不得修代码，之后仍由 Astra 编排层决定是否合入。
- **备用模型**：MiniMax-M3 仅在 DeepSeek 连续失败后用于长程、多模态任务；Kimi-K3 只做边界明确的只读研究，
  不直接修改仓库；GPT-5.6 Luna 只做可机械验收、范围极窄的批量任务。首轮不为这三者分配固定 lane。
- `effort` 必须写供应商原生枚举。Astra 使用 `medium/high`；DeepSeek 与 GLM 使用 `low/high/max`。
  禁止再用 `20/30/70` 这类跨供应商不可比较的数字。

### 0.2 模型启动与人工中转

模型选择与启动渠道是两件事，按 `lanes.yaml.execution_transports` 执行：

- GPT-6 Astra、GPT-5.6 Terra、GPT-5.6 Luna 由 Codex 直接启动；
- DeepSeek V4.1 Flash、GLM-5.3、Kimi-K3 通过 WorkBuddy，由用户负责复制提示词和带回结果；
- MiniMax-M3 的启动渠道尚未确定，未补充前只能作为候选，不能实际派活。

WorkBuddy 席位不能依赖 Codex 的自动任务管理。Astra 每次必须生成一份**自包含、可直接复制**的提示词，
其中包括 branch/worktree、文件边界、依赖 commit、任务、验收命令和回传格式。用户带回回复、commit 或 diff 后，
Astra 必须查看本地实际改动并重跑验证；第三方模型声称“测试通过”只算线索，不算验收证据。

---

## 1. 为什么要切，以及按什么切

实测：`agent/ma9_agent/` 18 个模块 2524 行。**扇入（fan-in）** 如下 —— 这是切片的唯一依据：

| 模块 | 行数 | 扇入 |
|---|---|---|
| `models` | 76 | **6** |
| `vehicle_screen` | 133 | **4** |
| `garage_profile` | 75 | **4** |
| `selection_strategy` | 103 | **4** |
| `selection_runtime` | 282 | **3** |
| 其余 13 个 | — | ≤ 1 |

**铁律：`fan-in ≥ 3` 即契约层，必须冻结、单一 owner；`fan-in ≤ 1` 即叶子，可独立成 lane。**

这 5 个模块合计 669 行、只占 26%，却是全部耦合所在；剩下 74% 都是叶子。依赖形状是浅锥形（`duel_vehicle_runtime` → `duel_defense_setup`），而 `agent/runtime_action.py` 是唯一装配点。

## 2. 上下文负担在哪里（关键，别搞错）

| 载体 | 体量 | 含义 |
|---|---|---|
| 代码 + 文档 | ≈ 230 KB | 任何档位都装得下，30 篇文档合计只有 128 KB |
| 可读 pipeline JSON | 1.1 MB（20 个文件） | 其中 `多人在线循环` 一席独吞 886 KB |
| 生成 pipeline JSON | **102.6 MB（6 个文件）** | **任何模型都读不进去，占 pipeline 总量 99%** |

结论：**上下文负担既不在代码里，也不在文档里，而在那 6 个谁都读不进的文件里。** 所以：

- 那条 lane 只能操作**生成器** + 靠 CI 校验，不许去读产物。它需要的是「在看不见全局的前提下严守约束」，这个能力用窗口和钱都换不来。
- 生成物必须制度化隔离。32 MB 的 JSON 在 diff 里什么都看不出来，两条 lane 同时改同一个生成器必然冲突。

## 3. 契约冻结的判据

冻结**不是**重新设计，而是把现有签名固化 + 补上断言。冻结清单与签名草稿见 `contract_freeze_draft.md`。

需要冻结四类东西：

1. **5 个契约模块的公开签名与不变式**（草稿已给）
2. **pipeline 节点命名规范**：`<领域>_<动作>` 中文命名，如 `对决_防守自动配置入口`；新增节点不得与既有 22 个历史失败节点重名
3. **`assets/interface.json` 的 49 个任务注册表**：它是手写源配置，由 contract 单一 owner 管理；
   任务名是 GUI 与用户之间的契约，改名等于破坏用户习惯
4. **验收标准**：即 CI 的 `check.yml`（`npm run check` + `unittest discover` + `validate_schema.py`）

## 4. 依赖顺序（不许颠倒）

```
contract ──┬─→ nav          （可即刻并行）
           ├─→ build        （可即刻并行）
           ├─→ vehicle      （可即刻并行）
           ├─→ multiplayer  （可即刻并行）
           └─→ duel-scan ─→ duel-defense ─→ duel-attack   （串行接力）
```

- **契约不提交，任何 worktree 都不许建。** 未提交的文件不会出现在新建 worktree 里。
- **擂台三席是接力，不是并行。** `duel_defense_setup` 唯一的新增 import 是 `.duel_vehicle_runtime`（取 `CLASS_ORDER`），必须等 ① 合入 main 后才能开 ② 的 worktree，否则中间那个 commit 直接 import 失败。
- **名义 8 席，契约后最多有 4 条互不依赖的子 lane 可并行。** 实际并发取决于运行环境提供的
  子智能体槽位；编排层必须以实时可用槽位为准，不能假设一定能同时运行 4 条。需要设备的 lane 仍受 ADB 单例限制而串行。

### 4.1 交接时的已知基线

- 编写本轮交接时 `main` 位于 `c5bd047`；新编排层仍须以实际 `git rev-parse HEAD` 为准，不要硬编码该 SHA。
- D 级防守五车自动配置已经实机成功：能选择五辆互不重复的 D 级车，最终状态为 `five_assigned`，且不会点击开始比赛。
- 首轮实机约耗时 20 分钟；之后已加入稳定页面两次一致即继续、记录车辆页码、快速滑到附近再精确核对、失败后完整重扫的优化。
  优化后的总耗时尚待用户复测，不能把离线测试通过写成实机性能结论。
- R/S/A/B/C 的等级交界与车辆不足时向下兼容已有离线测试，尚未完成各等级实机验证。
- 最近一次 Agent 单元测试为 50 项通过；任何 lane 开工前仍须重新执行 `verify_default`，不能沿用这个结果。
- 用户负责后续实机验证。需要设备的 lane 应交付明确的入口、预期画面、成功判据以及应回传的 `debug/*.json` 或日志路径。

## 5. 赛道识别与策略挂载（2026-09-21 新增）

### 前提：局内策略不自研，只挂载

第三方已有一套**按赛道百分比分点**的策略，载体是**数据表**。我们这边只做三件事：
识别赛道 → 查表 → 按百分比派发。表缺失或赛道名未命中时，一律落回通用兜底 ——
**兜底是默认实现，永远可用**。

### 识别是两级漏斗，不是平铺匹配

局内地图加载界面是**大地图一行 + 小地图一行**。先识别大地图，把候选域收窄到该子树的几条，
再在其中比对小地图；失败则回读重认。

**漏斗必须放进 Agent 的自定义识别，不要摊进 pipeline 节点图。** 理由不是偏好，是能力边界：
MaaPipeline 是声明式的，节点模板列表静态，**做不到「先看大地图、再动态决定只比对哪几张」**。
硬要塞进节点图，只能为每个大地图开一组分支节点，节点数倍增，且全部变成手写 JSON。
pipeline 里只留**一个**节点（`assets/resource/pipeline/track_identity.json`）。

附带好处：父子索引可以从第三方策略表**直接派生**，不需要另维护一份父子映射。

### 重试的截止信号是「加载界面消失」，不是秒数

加载界面停留 **2–10 秒**（取决于加载速度），差 5 倍。任何固定秒数预算都错 ——
按 2 秒设，长加载时白扔 8 秒；按 10 秒设，短加载时来不及。而「重试次数上限 N」也没法拍，
因为单次尝试耗时取决于 OCR 实际速度。所以：

- 加载界面**仍匹配** → 可以继续重试；
- 加载界面**消失** → 立刻停止：命中就派发，没命中就落兜底（比赛已开始，兜底即刻接管）；
- 硬上限 **15 秒**（> 最长加载 10 秒），仅作防死循环的安全网，**不是预算**。

派生要求：**两行必须在同一次识别调用里读**（一次截屏、两次 OCR）。拆成两个节点会让每轮重试
开销翻倍，短加载那种情况就只够试一次。

### 读数是数字，所以三条护栏都不能省

HUD 上是**数字**而不是进度条，必须 OCR。`race_controller.py` 的 `progress_gte` + `once`
**已经**是「阈值触发」语义 —— 任一 ≥ 阈值的读数触发一次，漏读只迟到不丢。
**不要另起一套触发机制。** 但阈值语义带来两个新失败模式，加上一个原有缺口，共三条护栏
（完整定义见 `contract_freeze_draft.md` 第 6 节）：

1. **跳幅超限的读数必须丢帧** —— 真实 40 误读成 91，会让 50/60/70/80/90 **全部**触发。
2. **迟到越过 `not_after` 必须跳过而非补发** —— 否则长漏读之后多个阈值集中触发，时间点全错。
3. **持续读不到时由调用方超时降级**（800–1500 ms）落回兜底。

**`race_controller.py` 保持纯函数式、如实报告、不猜** —— 它没有内部时钟，超时策略属于调用方。
已提交的 `b4a3e59`（缺读数时报 `guard:no_progress`，而不是静默降级成兜底）正是这个语义；
它现在从「潜伏缺陷的卫生清理」升级为**关键路径上的验收工具**。

### 归属

本节的实现全部属于 `multiplayer` 一席（新建 `track_identity.py` / `race_strategy.py`）；
schema 与断言属于 `contract` 一席。**两个 OCR 不要拆成独立 lane** —— 它们与局内循环同屏同帧，
拆开会让两席改同一批节点。

## 6. 单例资源（本项目特有，最容易被忽略）

| 资源 | 冲突后果 | 处置 |
|---|---|---|
| **ADB `127.0.0.1:16384`** | 两条 lane 同时跑真机自动化会互相抢屏 | 默认由用户实机验证；编排层串行安排验证请求。只有用户明确授权时才向 lane 发设备令牌 |
| `debug/maafw.log` | 并发运行互相覆盖 —— 而排查故障正靠它 | 同一时刻只允许一条 lane 上真机 |
| `build/` 产物目录 | 176 MB zip 与 159 MB downloads 互相覆盖 | 各 worktree 独立 build，或只让 CI 构建 |
| `.venv` | 与绝对路径绑定，worktree 里不存在 | 编排层解析共享 `{python}`；所有命令以 lane worktree 根目录为 cwd |
| Node 堆 | `maa-tools` 扫描 102.6 MB 生成物时默认约 4 GB 堆会 OOM | `npm run check` 固定设置 `NODE_OPTIONS=--max-old-space-size=6144`，与 CI 一致 |

### 6.1 跨 worktree 的 Python 规则

`lanes.yaml.python_runtime` 是唯一解析规则。编排层优先读取 `MA9_PYTHON`；本机未设置时使用
`E:/hzz/work/MA9/.venv/Scripts/python.exe`。解析后先运行 `{python} --version`，再把同一个绝对路径替换进
所有 lane 的验证命令。解释器可以共享，**cwd 与源码不能共享**：命令必须在对应 worktree 根目录执行，
这样相对路径和导入都来自该 lane。找不到指定解释器时停止并报告，不能静默调用 PATH 中的另一套 Python。

通常不需要设置 `PYTHONPATH`；若某一测试确实需要，只能指向当前 worktree 的 `agent`，不得指向主工作区。
Schema 校验必须显式传 `--schema-dir deps/tools` 及 `lanes.yaml.verify_default` 中的其余参数；
`validate_schema.py` 自带的 `tools/schema` 默认目录在本仓库不存在，省略参数会产生环境型假失败。
所有 Python 验收统一带 `-X utf8`，避免 Windows GBK 控制台无法输出校验器的 Unicode 状态符号。

### 6.2 当前主机的 Git 传输故障

本机曾间歇出现 `git-remote-https.exe` 空指针读取弹窗。它属于本地 HTTPS 传输进程故障，不能据此判断
GitHub Actions 或项目测试失败。遇到时先保留本地 commit，关闭弹窗并结束残留传输进程，再单独重试 push；
Actions 的失败原因必须从对应 run 日志判断。不要为了绕过该弹窗重写历史、重建仓库或把测试失败标成已通过。

### 6.3 Node 校验内存

`npm run check` 的另一项已知本地失败是 `JavaScript heap out of memory`。这不是 schema 或功能错误；
未设置 Node 堆时本机已在约 4 GB 处复现。按 `lanes.yaml.node_runtime.check_environment` 配置 6 GB 后校验通过。

## 7. 生成物禁令

以下文件**只能由工具产出，禁止手改**（完整清单见 `lanes.yaml` 的 `generated_artifacts`）。
`assets/interface.json` 不在此列：它是手写源配置，只是修改权归 contract：

- `assets/resource/pipeline/multiplayer_loop.json`、`reverse_fallback.json`、`vehicle_recognition.json`
- `assets/resource/pipeline/multiplayer_loop_{3,20}_{黄金,白金,白银}.json`（6 个，合计 102.6 MB）
- `assets/resource/image/navigation/loop/player_{黄金,白金,白银}.png`
- `captures/reverse_fallback_check.json`
- `data/generated/*.json`

六个大型多人 JSON 归 `multiplayer` lane。权威入口只有：

```text
{python} -X utf8 tools/prepare_dynamic_multiplayer_loop.py
```

该入口调用 `prepare_reverse_fallback.py` 与 `prepare_multiplayer_loop.py`，再调用 `prepare_vehicle_recognition.py`，
同时更新主循环、六个分片、兜底表、车型识别表、三个段位徽章、检查报告和 manifest。
这些生成器及 `multiplayer_loop_files.py` 可由该 lane 修改；全部输出只列在 `owns_generated`，模型不得手改，
其中六个大型分片不得打开或读入模型上下文。
生成后必须运行 `lanes.yaml` 的 `verify_generated`，并由 CI 完成最终校验。

`generated_artifacts` 是全局禁改清单，并不表示每个文件当前都允许某条 lane 重新生成。
只有同时出现在某条 lane 的 `owns_generated` 中的精确路径才有生成 owner；其余 `data/generated/*`
默认保持只读。后续任务若确实需要重建其中某项，编排层必须先把生成器和精确输出路径登记到同一 lane，
再派活，不能用通配符临时放宽边界。

## 7.1 外来只读输入

第三方赛道策略是**可选的外来输入**（见 `lanes.yaml` 的 `foreign_readonly_inputs`）。来源可能是结构化表，
也可能是需要转写的自由文本，并且可能一直拿不到。这个不确定性不得阻塞 `multiplayer`：

- 没有来源、没有规范化副本或赛道名未命中 → 落回兜底，**不报错、不阻断**；
- 有来源 → 保留来源标识，先转写/解析成 `config/external/track_strategy.normalized.json`，并把转写报告写到
  `config/external/track_strategy.transcription.json`，
  再通过 `race_strategy_schema` 校验；自由文本绝不能直接驱动比赛；
- 原始资料与规范化副本都只存本地，不提交；仓库现有 `.gitignore` 已整体忽略 `config`；
- 在真实来源出现前，用假表完成加载、派发、过期、误读和兜底测试。不要预先猜测第三方文本格式，
  也不要创建绑定某种未知格式的导入器；来源明确后先在 `lanes.yaml` 登记 importer 文件边界再实现；
- 换表或换模型之后，必须重跑护栏断言（`contract_freeze_draft.md` 第 6 节）；
- 适配层负责补第三方表缺失的字段（目前只有一个：过期上界 `not_after`）。

## 8. 每席的完成定义

一条 lane 算完成，必须同时满足：

1. 自己的模块 + 自己的测试在 `agent/tests` 或 `tools/tests` 里
2. `lanes.yaml` 的 `verify_default` 三项全过
3. 只动了自己名下的文件：`git diff --name-only` 必须落在
   **`owns ∪ owns_new ∪ owns_generated`** 内；`owns_generated` 中的文件必须能追溯到生成命令
4. 涉及 pipeline 的席位，新增节点通过 `validate_schema.py`

关于第 3 条：`owns` 只列**已经存在**的文件，本席要新建的文件列在 `owns_new`。
三者必须分开，否则新建文件或合法生成物会落在集合外，完成定义根本无法满足。
`owns_new` 里的名字是建议名 —— 改了名字就回来改 `lanes.yaml`，不要留着不一致。

**有冲突时以 CI 为准，不以任何 lane 的自我报告为准。**

## 9. 给每条 lane 写提示词时，用这个模板

编排层不要自由发挥 —— 每个 lane 的提示词必须薄，否则会把刚切开的上下文又合回去。

```
你在 MA9 的 <branch> 分支上负责「<title>」这一条 lane。

模型与档位：<model> / <effort>。你是执行 lane，不得创建下级智能体；
跨 lane 依赖、冲突或缺失信息一律报告编排层，不要直接修改别席文件。
<若 needs_device=true：默认只准备安装包、复现步骤、成功判据和日志路径，由用户实机验证；没有明确授权不得操作模拟器。>
执行渠道：<Codex 直接任务，或 WorkBuddy 用户中转>。
Python：将下文的 {python} 替换为编排层已验证的绝对路径；所有命令在本 lane 的 worktree 根目录执行。

先读这三个文件，不要凭记忆：
  docs/zh_cn/develop/multi_agent_plan.md         （总规则）
  agent/lanes.yaml 里 id 为 <id> 的那一节         （你的边界与验收）
  docs/zh_cn/develop/<你名下的那份 doc>

你的边界：
  可以改：<owns 列表>
  可以新建：<owns_new 列表>（为空就写「本席不新建任何文件」）
  可以由工具重新生成：<owns_generated 列表>（为空就写「本席不生成受控产物」）
  可以读、不可以改：契约层那 5 个模块 + race_strategy_schema.py
  绝对不要读：multiplayer_loop_*.json 等生成物（102.6 MB，读不进去也没意义）
  外来只读输入（第三方策略表）只许读，不许改、不许提交

本次任务：<一句话，可验收>

完成标准：
  1. <模块> + <测试文件>
  2. {python} -X utf8 -m unittest discover -s agent/tests -v 全过，并完成 lanes.yaml 的其余 verify_default
  3. git diff --name-only 的输出全部落在 owns ∪ owns_new ∪ owns_generated 内；生成物附生成命令

<若本席有 reviewer：完成后只报告 commit、验证结果和 diff 文件清单；不要自行合并，等待只读复核。>

卡住时先跑测试再问我，不要猜。
```

## 10. 升降档与换模判据（不要凭感觉）

- **编排升档**：冻结契约、跨 lane 冲突、关键合并或同一问题连续两轮失败时，Astra 从 medium 临时升到 high。
- **子任务升档**：同一 lane 连续两轮没通过自己的测试 / 出现「改了 A 坏了 B」/ 需要同时推理三个以上子系统时，
  DeepSeek 从 high 升到 max；已经是 max 则由 Astra 接管诊断，不要无限重试。
- **换模**：DeepSeek max 连续两轮仍失败，先用 Terra high 做只读故障复核；若属于纯算法难题，再转 GLM-5.3 max。
- **降档**：只有连续 3 个任务都是「照着已有模式改」且都有确定性测试兜底，才允许从 max 降到 high；
  `multiplayer`、`duel-scan`、`duel-attack` 不允许降档。
- **窗口吃紧**：`multiplayer` 要同时持有 886 KB 可读 JSON、跑两处 OCR、并接第三方表。
  正确解法是再切一刀（主循环 / 轮换表 / 兜底表），不是换成更弱模型。

## 11. 变更记录

本文件改动需在下面留一行；`lanes.yaml` 的改动不需要（它是数据）。

| 日期 | 改动 | 原因 |
|---|---|---|
| 2026-09-21 | 初版 | 单模型开发转向多模型多 lane 工作流 |
| 2026-09-21 | 新增 §5 赛道识别与策略挂载；§7.1 外来只读输入；完成定义改为 `owns ∪ owns_new`；启动指令同步更新（§0） | 用户确认局内策略改为「只挂载、不自研」：第三方按赛道百分比分点的数据表 + 局前加载界面两级识别（大地图 → 小地图）。原 §5 之后的章节顺延一位 |
| 2026-09-21 | 编排层改为 GPT-6 Astra medium，关键阶段升 high；子任务改为 DeepSeek 优先，`duel-attack` 使用 GLM-5.3 max，并加入 Terra 独立复核、单一编排者、用户实机验证和备用模型规则；完成边界补入 `owns_generated` | 将交接文件改为无历史上下文也能直接执行的模型分工，并消除合法生成物无法通过边界验收的矛盾 |
| 2026-09-21 | 增加 Codex/WorkBuddy 人工中转规则、统一 `{python}` 解析、明确多人 JSON 的生成器归属，并把第三方策略改为可缺省的转写输入 | 适配实际模型启动渠道，消除 worktree 解释器漂移与生成物 owner 空缺，同时允许外部策略长期缺失或以自由文本到达 |
| 2026-09-22 | 冻结流程改为 A/B 两次提交；补齐 contract 测试边界与多人总生成器的全部输出；将 `assets/interface.json` 更正为手写源配置 | 最终交接审计发现提交 SHA 不能自引用，且总生成器实际写入范围大于六个分片；修正后边界可机械验收 |
