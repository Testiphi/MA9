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
0. 先检查 git status、实际 HEAD、contract_frozen_at 和 agent/orchestration/state.json。
   若契约 A/B 已提交且祖先关系正确，复用冻结状态，跳过下面的首次冻结步骤；不得重新冻结或覆盖已有工作。
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
   当前不启动 GPT 子智能体；外部席位由编排层生成完整提示词，
   交给用户在指定模型的全新对话运行，收到结果后仍由编排层本地独立验收。

不可违反：
- 只有 Astra 编排层可以创建、调度和结束子智能体；lane 子智能体不得再创建下级智能体，
  不得绕过编排层直接协调其它 lane。跨 lane 发现一律上报编排层。
- 契约与集成由 Astra 编排层亲自负责；日常编排用 medium，冻结、冲突裁决和关键合并用 high。
- 用户已改回外部模型人工中转；具体模型及档位见 lanes.yaml。
- 当前优先擂台管理：duel-scan → duel-defense → duel-attack；multiplayer 暂停，仅占位。
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

### 0.1 当前模型政策（2026-09-23 全新对话交接）

- 总控保持 Astra，负责边界、证据、验收与合并；禁止自动启动 GPT 子智能体。
- 普通业务 owner 默认 ds-v4.1flash high；01 使用 Hy3 文档收尾试点，07 使用 GLM-5.3 high。具体模型见 lanes.yaml。
- 有 reviewer 的 lane 使用另一个独立 GLM-5.3 high 只读上下文；owner 修复，总控独立本地验收。
- 机械资料整理使用GLM-5.3-Flash，截图歧义核对使用Hy4 preview，交接审计使用Kimi-K3；一次一个owner，04暂停。
- 用户重新授权前不调用 Terra、Luna、Sol 席位，不自动购买或重置额度。
- 本节替代旧的 Terra/Luna/Sol 成本试点；历史记录只代表当时配置。

### 0.1.1 自动本地提交（用户于2026-09-23明确要求）

每次较大修改形成完整且通过适用验证的逻辑阶段后，由总控自动创建一次本地Git提交，不再逐次询问。
提交前核对diff、精确边界和验证结果，只暂存本次授权文件；不得纳入用户未授权改动、私有日志/截图或.workbuddy。
较大修改指一个可独立说明的功能、修复、跨lane集成或编排政策阶段，不为每次微小编辑制造提交。
验证失败或工作未完成时如实保留状态，不伪称通过；若必须保存检查点，提交主题和状态须明确未完成。
自动本地提交不等于远端推送；沿用用户既有推送政策，但宿主审批拒绝时不绕过，取得具体目标与内容授权后再操作。
### 0.2 模型启动与人工中转

模型选择与启动渠道是两件事，按 `lanes.yaml.execution_transports` 执行：

- GPT 子智能体当前禁用；总控留在本对话；
- ds-v4.1flash、GLM-5.3、GLM-5.3-Flash、Hy3、Hy4 preview、Kimi-K3由用户在选定平台新建对话并带回结果；
- MiniMax-M3 的启动渠道尚未确定，未补充前只能作为候选，不能实际派活。

WorkBuddy 席位不能依赖 Codex 的自动任务管理。Astra 每次必须生成一份**自包含、可直接复制**的提示词，
其中包括 branch/worktree、文件边界、依赖 commit、任务、验收命令和回传格式。用户带回回复、commit 或 diff 后，
Astra 必须查看本地实际改动并重跑验证；第三方模型声称“测试通过”只算线索，不算验收证据。

### 0.3 成本、调度与持久交接（用户于 2026-09-22 批准）

- 默认同时一个外部 owner，交付后再交给独立 GLM-5.3 reviewer。
  不要求填满槽位；减少并发本身不保证节约总额度，关键是缩小任务、上下文和重复返工。
- GPT 席位共享账号额度。阶段开始/结束读取快照，不把账号差值精确归因到某席。
  建议保留最后 20% 周额度用于验收和故障处理；接近预留线先报告、缩小计划，不启动新的重任务。
  不自动购买额度或重置，不主动启用加价加速。
- 00 为总控，01 导航只收尾，02 构建按需维护，03 仅解决擂台识别阻塞，04 暂停占位，
  05/06/07 按擂台依赖顺序推进。04 不创建 worktree、不派活；既有可选第三方策略契约保持不变。
- 进度写入 agent/orchestration/state.json；登记边界见 lanes.yaml.orchestration_files。
  状态记录保存分支、基点/提交 SHA、阶段、证据、验收、阻塞和下一步。只有总控写状态文件，
  lane 不得因它位于 agent 下就自行编辑。会话恢复先核对实际 Git，再使用状态记录。
- 用户统一在总控对话回传项目名、运行编号、步骤、预期/实际结果和截图/日志。
  私有原始证据存本机共享目录，不提交账号截图。需要长期测试夹具时先登记边界、脱敏再纳入仓库。
- 子智能体提示词只传任务必需上下文。外部辅助给定输入清单、输出格式、结束条件，一包一次交付，
  业务执行可走外部；严格按 lane 边界，契约和越界改动交总控裁决。
- 只读试点审计可以仅运行相关测试，必须标为审计阶段、不能宣称 lane 交付通过。
  写入 owner 开发期间运行针对性检查；正式交付仍跑全套 verify_default/verify_extra。
  同一提交同一验收阶段不无故重复；复用证据必须注明原提交、环境与适用范围，不能伪称重跑。

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

下图表示技术依赖，不代表当前派发计划；成本平衡阶段按 §0.3 调度，尤其 multiplayer 暂停。

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
- 契约 A 为 bd9a535336750d8fae3799f20d321498e21f5b00，元数据 B 为 ab13bf9ec91f916754aa0910bd1138e2f038d0a5。
  2026-09-22 的 01/02 独立验收均为 Agent 82 项通过、tools 12 项通过与 1 项既有跳过、完整 schema 通过。
  这些是指定提交的历史证据，不代表后续改动自动通过；试点审计与正式交付按 §0.3 区分。
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
`E:/hzz/work/MA9/.venv/Scripts/python.exe`。解析后先运行 `{python} -X utf8 --version`，再把同一个绝对路径替换进
所有 lane 的验证命令。解释器可以共享，**cwd 与源码不能共享**：命令必须在对应 worktree 根目录执行，
这样相对路径和导入都来自该 lane。找不到指定解释器时停止并报告，不能静默调用 PATH 中的另一套 Python。

通常不需要设置 `PYTHONPATH`；若某一测试确实需要，只能指向当前 worktree 的 `agent`，不得指向主工作区。
Schema 校验必须显式传 `--schema-dir deps/tools` 及 `lanes.yaml.verify_default` 中的其余参数；
`validate_schema.py` 自带的 `tools/schema` 默认目录在本仓库不存在，省略参数会产生环境型假失败。
所有 Python 验收统一带 `-X utf8`，避免 Windows GBK 控制台无法输出校验器的 Unicode 状态符号。

临时目录必须同时设置 `TMPDIR`、`TMP`、`TEMP` 为当前任务在 MA9 根内的证据临时目录，并记录实际 `tempfile.gettempdir()`。
只改 TMP/TEMP 不足以覆盖宿主 TMPDIR；不得为使测试通过而把夹具移到根外。

### 6.1.1 显式便携包运行根（2026-09-23总控裁决）

两套根查找函数保留独立的数据有效性判据。优先级为：显式 MA9_PROJECT_ROOT/configured（无效即抛错）；
显式便携根标记 `.ma9-portable-root`；无标记时完整保留原有账号根优先及数据根兜底。
标记是包根的普通空文件，其存在表示主动隔离；查找依次从可执行文件目录、cwd以及Agent模块目录向祖先遍历，
首个标记即为边界，若缺少该函数所需数据则抛错，不穿透至另一个账号根。GUI没有模块目录第三起点。
标记仅由02在新建的便携发行包根生成；不得在源码根、开发install、既有已验包或用户账号目录补标记。
不采用所有相邻数据优先或祖先截断。开发install与已验证05旧包的无标记行为保持不变。
runtime_action及其测试由总控亲自维护；GUI、组包脚本及对应测试归02。此次为兼容性增量，不重新冻结A/B，
不修改五个契约模块、schema、interface源或生成数据。新包标记须有工具测试锁定，并保持不携带用户config。

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
5. 有 reviewer 的 lane 完成独立只读复核；needs_device=true 的 lane 有用户实机证据才可闭环。
   离线通过、待实机、待远端 CI、已合入须分开记录；不能用任一单项代替全部完成。

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
执行渠道：<用户选定外部平台的全新对话，手工中转>。
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
- **子任务升档**：同一明确问题至多进行两轮针对性修复；仍失败就保存最小复现返回总控。
  Astra 诊断后给出有界外部任务，不自动启动 GPT 子智能体，不允许无限重试。
- **max**：不是常驻默认值，只有具体算法瓶颈有证据时才考虑。
- **换模政策**：当前外部模型全新对话人工中转，按lanes.yaml分工，验收标准保持不变。

- **窗口吃紧**：`multiplayer` 要同时持有 886 KB 可读 JSON、跑两处 OCR、并接第三方表。
  正确解法是再切一刀（主循环 / 轮换表 / 兜底表），不是换成更弱模型。

## 11. 变更记录

本文件改动需在下面留一行；`lanes.yaml` 的改动不需要（它是数据）。

| 日期 | 改动 | 原因 |
|---|---|---|
| 2026-09-22 | 用户批准成本平衡原生调度：Terra/Luna 主力、Sol 按需；04 暂停、擂台优先；登记持久状态与外部辅助 | 单一 Pro、无额度重置，减少上下文搬运与重复返工，替代旧固定 max 政策 |
| 2026-09-21 | 初版 | 单模型开发转向多模型多 lane 工作流 |
| 2026-09-21 | 新增 §5 赛道识别与策略挂载；§7.1 外来只读输入；完成定义改为 `owns ∪ owns_new`；启动指令同步更新（§0） | 用户确认局内策略改为「只挂载、不自研」：第三方按赛道百分比分点的数据表 + 局前加载界面两级识别（大地图 → 小地图）。原 §5 之后的章节顺延一位 |
| 2026-09-21 | 编排层改为 GPT-6 Astra medium，关键阶段升 high；子任务改为 DeepSeek 优先，`duel-attack` 使用 GLM-5.3 max，并加入 Terra 独立复核、单一编排者、用户实机验证和备用模型规则；完成边界补入 `owns_generated` | 将交接文件改为无历史上下文也能直接执行的模型分工，并消除合法生成物无法通过边界验收的矛盾 |
| 2026-09-21 | 增加 Codex/WorkBuddy 人工中转规则、统一 `{python}` 解析、明确多人 JSON 的生成器归属，并把第三方策略改为可缺省的转写输入 | 适配实际模型启动渠道，消除 worktree 解释器漂移与生成物 owner 空缺，同时允许外部策略长期缺失或以自由文本到达 |
| 2026-09-22 | 冻结流程改为 A/B 两次提交；补齐 contract 测试边界与多人总生成器的全部输出；将 `assets/interface.json` 更正为手写源配置 | 最终交接审计发现提交 SHA 不能自引用，且总生成器实际写入范围大于六个分片；修正后边界可机械验收 |

| 2026-09-22 | 用户因额度成本改回 DeepSeek owner/独立 reviewer 人工中转，停用 GPT 子智能体 | 保留依赖、边界与本地验收 |


## 12. 2026-09-23 目录与全新对话政策

项目唯一根为 E:/hzz/work/MA9。四个 MA9-* 辅助目录已移入此根，Git worktree 登记已修复。
所有子任务由用户在外部平台新建对话，每次提示词独立包含 cwd、HEAD、边界、证据、验收和回传格式。
使用 agent/orchestration/prompts/ 中的新提示词；旧提示词仅为历史记录，不再转发。
入口是 00-orchestrator.md；当前下一席为 05R-review.md，其余未放行席只占位，不能自行开始。
模型分配是有界试点，不声明未经验证的模型性能或价格。MiniMax 只备用，不自动派活。
每次正式派发前总控刷新提示词的实际SHA和窄任务；全新对话不能靠旧聊天或长期记忆推断授权。

| 2026-09-23 | 四目录归入MA9；外部全新对话；登记所有席位提示词及模型 | 用户要求控制目录边界和额度，避免上下文遗漏 |
| 2026-09-23 | 根内验收同时固定TMPDIR/TMP/TEMP；新增显式便携根标记规则，保留无标记账号兼容 | 02C复现祖先账号根抢占新包数据，总控裁决M-α，不重新冻结A/B |
