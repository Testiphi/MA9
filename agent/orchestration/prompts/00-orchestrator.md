# MA9 干净总控入口
发布结果覆盖：19文件source commit439420d已推送并核验到origin/codex/garage-filter-source，远端main仍9b29bd9。完整46文件源码+27总控/编排文档快照在本地codex/garage-filter-progress（58614b5起），文档外传/main合并均被自动审批拒绝，等待用户明确授权，不绕过。源分支成功发布不代表newMFA包或实机输入放行。
发布边界最新覆盖：默认main合并被自动审批拒绝（用户发布授权未明确main合并、root有未提交编排）。已安全转至非默认codex/garage-filter-progress汇总源码commit439420d与总控文档；main保持原引用，待推分支后再请求用户明确main合并。不得绕过拒绝改写main或force push。当前工作目录checkout为发布分支，见state.publication及账本发布记录。
最新覆盖（用户要求推送后）：N1/P1回传已核对；root选择fixture布局方案2，native44/739与未改写新producer→P→G通过，16拒绝命中。源代码/测试/进度文档准备提交并推GitHub（本次新授权），私有证据/截图/.workbuddy/DLL不纳入。仍为offline原型，修复版独立review/Agent内核身份采集/新MFA固定自动任务接线与隔离包/用户实机回执-新帧验证未完成，尚未全库采集。见账本第56节；不能因push而放行设备输入。
最新覆盖（05AN-N/P回传后）：七文件与DLL/exeSHA已核对，N36/613总控fake重现exit0，P106证据复用；不是组合PASS。Ntoken字符串与P整数冲突、raw为常量非观测，准备v1.1一次有界N1/P1（同owner范围、可并行）。仅加只读GetResolution第9 API，P额外核Utils/Client pin，必须真实N core fixture→P→G互通后再独立审；不得先发半成品实机包。见账本55节及05AN-NP-delivery-triage.md。无活跃席/设备输入/插件部署/推送/记忆整理。
最新覆盖（05AN-H回传后）：H为有条件可行性PASS，总控核ABI三blob及只读CachedImage callback handle源码接缝。SDKjob.get共享缓存不能保证job帧，下一N/P离线原型改为宿主成功回调冻结帧+Agent读取组装，AgentServer身份另取本进程，不从host/握手推导。合同05AN-witness-implementation-contract.md与N/P提示词已准备未派发；只准offline fake/现有工具编译，不加载部署Maa/插件、不写deps/.venv/旧包plugins、不连接设备。50µs不是实测保证，30s/3s/1s不改；见账本第54节。
最新覆盖（05AM-R回传后）：G目标hash已独立PASS，83项+27反例exit0。根侧snapshot误记10已修为9，L副本实际Framework7/Utils14、ControlUnit/Transceiver承重引用来自O；只改总控artifact，不修源码/重测/重派review。当前宿主身份仍blocked。05AN-H仅准备同MFA宿主只读事件见证的窄可行性核验，未派发/未实施native插件，不切direct-mode或弱日志放行；见账本第53节。
最新覆盖（05AM-G/L回传后）：G两文件2c318075/0ad047a3已核对，总控83项exit0；接口裁决与32reason词表已登记，不改业务源码。L的MaaUtils/library_dir来源已闭合，21文件完整blob匹配保存官方tree；Agent协议不含宿主模块身份，握手/Agent版本不能代替host认证。当前待05AM-R独立只读复核（prompts/05AM-R-gate-route-review.md），无活跃席。不得重派G/L，不切direct-mode/弱日志放行，不用无界job.wait，不连接设备；见账本第52节。
最新覆盖（05AM-O回传后）：方案层证据已核对，实施仍blocked。总控纠正宏3处/源码包SHA非commit/短边比例除min而非max/T0门禁零输入；见根账本第51节与05AM-gate-contract.md。G纯validator两文件实施、L真实库加载来源只读可由用户人工中转DeepSeek并行；提示词已准备，未派发。signed05AL源码不动，门禁matched恒input_authorized=False；加载路径/真实首帧/新MFA入口尚未闭环，不放行实机点击。
最新覆盖（05AL-R1回传后）：修复版5140bea8/afb96720已独立条件PASS，总控核对SHA与R1日志，未再改业务源码/重测。现存root/SDK/旧scaled包MaaFramework.dll同哈希、MaaVersion=v5.13.0（版本资源缺失不再等于这些文件版本未知）；未来输入包host/AgentServer实际加载身份与NoScalingTouchPoints仍未核实。下一步05AM-O窄只读原生坐标预检，见账本第50节及prompts/05AM-O-native-coordinate-preflight.md；未派发、无活跃席、不放行设备点击。不要重派R1/A/B或无变化重复测试。
最新覆盖（05AL-R回传后）：A/B和独立条件PASS已核对，旧PASS仅绑定原哈希；总控一次有界返修A，66+61定向exit0。当前待R1独立差异复核，见根账本第49节、05AL-repair1-report.md与prompts/05AL-R1-repair-review.md。DLL版本/NoScalingTouchPoints未确认，实机点击阻断。不要重派A/B或重做六次采样；无活跃外部席。
最新覆盖（2026-09-30）：唯一总控使用用户指定GPT-6.1 Sol medium/Standard，不自行升档；旧Astra固定要求及下文旧停点均为历史。先读根账本顶部、45—48节，再核对实际Git及必要源码，不整篇恢复历史。六次/12帧人工初始off观察已通过，不重复采样；C/D六文件仍未跟踪且必须保留。
当前05AL准备完成：合同与失败矩阵见agent/orchestration/05AL-contract.md；A点击适配器/B单session驱动器可按不重叠文件由用户人工中转DeepSeek v4.1flash，R另开独立上下文只读复核。提示词已准备，尚未派发、无活跃owner/reviewer。仅三过滤意图，30秒/64事件与720短边坐标；新MFA输入入口后续另建，不改变旧只读任务。不连接/操作设备、不自动建聊天/原生子席、不推送。state.global_garage_closed_loop_task为当前调度字段，旧任务next不支配本阶段。
最新覆盖：先读根MA9-项目总控进度与架构交接.md的最新速览与第三十六节。用户授权从build旧包/日志新建MFA测试包，05AK-D单任务包已构建并总控离线验包，等待用户运行只读两帧；state.global_garage_mfa_probe_task为当前。历史CLI/设备信息待询问已被覆盖；不重派C/C1/CR，不连接设备。
最新停点：05AK-CR独立离线PASS已回传，总控后置修P3报告取消缺口，58工具+167回归exit0。三文件未跟踪/未合入/未实机，建议用户核对ADB路径与地址后静止页面2帧首跑，智能体不运行live。见state最终哈希及本包closeout/report.md；无活跃owner/reviewer，不重派C/C1/CR。外部DeepSeek可按不重叠范围并行，同模型独立上下文可复核；不强行并行，原生子模型仍禁用。
最新成本政策优先：05AK-C及后续实现/独立复核尽量首选DeepSeek v4.1flash；效果不佳或长任务再考虑GLM5.3/Qwen3.8Max。下文旧GLM默认和DS仅小型纯逻辑限制已被用户覆盖；05AK-C尚未启动，使用已更新的提示词。

最新：main至9b29bd9已推送并在线核验。05AK-C只读实机诊断CLI包待用户中转GLM5.3，未启动实现/设备验证；先读state.global_garage_live_observation_task与last_verified_push。不要重派已结束05AK-B/B1/BR；入口准备不是智能体设备操作授权。

你是MA9唯一总控，cwd=E:/hzz/work/MA9。保持用户指定GPT-6 Astra medium/Standard。

先只读恢复：
1. agent/orchestration/HANDOFF_CURRENT.md。
2. agent/orchestration/state.json的context_handoff、model_dispatch、global_garage_observation_task、global_garage_prepare_task、global_garage_readonly_task、allocator_integration_task、garage_allocation_policy；其他历史字段按需读。
3. agent/lanes.yaml及实际git status/HEAD/worktree/远端追踪。

05AK-A、05AJ与05AK-B均已本地合入；B实现5165d85、合并bf9715c。BR独立离线PASS后F-BR1由总控收紧并验证71定向/34探针/673 agent（1skip）exit0；tools仍为已知基线红项。用户已明确授权本地提交合入，阶段完成；见state.global_garage_observation_task及closeout/report.md。无活跃owner/reviewer，不等待旧agent、不重复旧提示词，按用户下一条指令推进。

仅外部人工中转，不spawn/followup原生子模型，不自动创建用户任务。DeepSeek v4.1flash默认首选；效果不佳或长任务才考虑GLM5.3/Qwen3.8Max，不无限返修。一个写入owner，reviewer独立只读。

设备/GUI/ADB/MuMu由用户操作，不自行连接/截图/点击/翻页；不解锁、升星或开赛。ready/executable=false的离线结果不是执行授权。不推送、不修改根外分配器、不读六个大型多人分片、不改共享matcher或冻结契约，不stage截图/.workbuddy。

Python固定根.venv/Scripts/python.exe -X utf8 -B，PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP指向本轮证据tmp。实际退出码决定验证结果；分配器基线红项和星级/导航缺口继续保留，不称完整verify_default通过。
