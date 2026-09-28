# MA9 总控当前交接
更新：2026-09-28，05AG经GLM终审通过并本地合入。本文件不是设备操作授权。优先读本文件、state.json当前字段、lanes.yaml，再核对实际Git；不要从旧聊天或旧提示词重复派活。

## 最新05AG状态（覆盖下方旧阶段描述）
- DeepSeek已交付初稿及唯一一次返修；总控确认重复前缀仍会被登记后，按用户“继续下一阶段”接手运行时门禁。不要再次派DeepSeek返修。
- lane实现提交97ae30029f158b59feca204d68d5e7ee012233e3，main合并提交bb1a25315b528948d3480fe1753f70219a5497d2；随后总控提交本交接元数据，实际HEAD以Git为准。五个实现文件已合入：duel_vehicle_screen.py、duel_vehicle_runtime.py、duel_garage_survey.py（两行诊断透传）及screen/runtime两个测试。
- 歧义候选不进入confirmed/点击；未知完整可见名称块通过identity_observations/unresolved_identities留存。重复共同前缀无法证明普通版；有未决位置时采样不稳定，自动遍历停止。普通版共同前缀仍是功能限制，未宣称实机可用。
- 最终agent506项/1skip、tools42项/2skip，退出码均0；schema排除六个禁读分片后通过，不能宣称完整verify_default通过。正式profile、catalog、共享matcher/全局阈值未改；未设备操作或推送。合并后五个文件与lane提交逐项无差异，复用既有测试证据。
- GLM5.3独立只读终审PASS；总控核实待审五文件哈希全部MATCH。R1/R2文档残留已修，不改逻辑；R3位置未决语义、R4保守兜底记录保留。目录338个标题中20个是长名严格前缀，普通版保守停止仍为限制。
- 报告、日志、待审/最终哈希及review/review.md在MA9-evidence/20260928-05AG-runtime-gate/。当前无活跃owner/reviewer，不再重派05AG或等待旧席位。用户端接线、普通版区分证据及实机可用性是后续独立范围，本次不自动启动。

## 最新协作方式
- 用户已撤回原生子模型调度方式。后续仅外部模型：总控给完整提示词，用户粘贴到指定模型的新对话并回传结果。禁止spawn/followup原生子模型，除非用户重新明确恢复。
- 总控保持用户指定GPT-6 Astra medium、Standard。用户提供的成本条件：DeepSeek v4.1flash额度消耗较小、Qwen3.8flash免费、GLM5.3额度较大且大量使用会限流；不是已验证的能力排名。
- 默认DeepSeek做实现/窄修；Qwen做机械整理、文档与低风险初审；GLM只用于关键识别/输入安全/同步边界终审，集中一次用。不猜外部high/max档位，按平台实际默认记录。
- 一个写入owner；独立reviewer只读。外部席不得派下级。一次有界返修仍失败即交总控诊断，避免免费模型反复试错耗掉总控额度。
- 每份提示词由总控填好模型、cwd/branch/实际HEAD、精确文件范围、输入、约束、验证和回传格式；用户不补技术参数。有本地工具先验证路径可读，无工具不能声称已读文件或跑过测试。
- 所有旧原生agent已完成。05AG外部实现、唯一返修及GLM终审已结束，当前无活跃owner/reviewer。不要等待旧对话agent。不要主动创建新的用户任务。

## 根与硬边界
根E:/hzz/work/MA9；实现lane E:/hzz/work/MA9/MA9-worktrees/duel-scan，分支lane/duel-scan。所有产物在MA9，不读六个大型multiplayer分片，04继续暂停。
根外E:/hzz/work/MutualExclusionAllocator/repo仅按05AE用户授权只读检查/同步；不得修改该项目。设备/GUI/ADB/MuMu均由用户操作，总控和外部席不得代操作。
Python固定E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B；PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP三者指向当前证据tmp。Node schema检查须NODE_OPTIONS=--max-old-space-size=6144。MaaDeps退出断言/skip须按实际进程退出记录，不用os._exit掩盖。
冻结A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5已验祖先，只复用不重冻。合格阶段由总控自动本地提交；精确stage本次文件，不带截图/.workbuddy。推送按当次授权，不强推。

## Git与发布状态
业务/README最新已推送并ls-remote核实：origin=https://github.com/Testiphi/MA9.git，main=eb5fbd196da4cb4e9b39d3054b3ac149499158cf。包含普通档偏好、英文默认README.md与README.zh-CN.md互链。当前本轮协作方式/精简交接还会产生一个本地编排提交，未获新的推送请求；恢复时以实际Git为准。
lane上次核实HEAD=1486050420ae64d893b12abb93fb70daa36052a6、tracked clean；它是分配器代码交付，main已经包含它。派下一席前核对或必要时同步lane，然后填写真实基点，不机械沿用此SHA。
main已有用户未跟踪captures和.workbuddy，不能清理或stage。旧交接完整历史保存在Git eb5fbd1版本以及MA9-evidence/20260927-external-relay-handoff/HANDOFF-before-external-relay.md；不要默认全量阅读。

## 当前结果
1. 防守五图+真槽号、首页赛区V/IV及只读候选流程已实现。用户V区/展开槽3两步只读验证通过，旧session已消费，只可历史回放，不可当执行授权。已有五辆车无需清空。
2. 五槽Nevera/296GTB/FE3/GT65/G60此前分别实机assigned+同槽返回、未开赛；不是本次策略自动五槽执行验收。当前私有采集包：MA9-worktrees/duel-scan/build/user-test-garage-bcd-4ef2923/MA9-preview，不让用户重跑旧任务。
3. B/C/D补采完成，原profile252条未覆盖；车型漏档12条已离线审核。星级结果为250算法双帧一致+12模型视觉复核双帧一致，另2条由用户策略排除。不是完整拥有集合或正式confirmed星级，另4个历史新ID仍隔离待核。
4. 用户明确：见“升星就绪”直接配车不可用，不解锁/不升星。Tartarus、DBS GT Zagato已排除，不再索要详情截图；未知星级/普通非满星本身不触发这条排除。规则agent/orchestration/garage_allocation_policy.json。正式profile SHA仍b5cdd0de1fae09758ab7d3dc231766efdb88374b038d5e2b711569f08f3eae1d。
5. Lykan普通版/Neon、Huracan STO/Super Trofeo EVO的5条离线误关联已据原图更正，原星数不变；实时判定代码尚未修，重新扫描可能复发。共享matcher/全局阈值不能擅改。
6. 分配器同步与离线桥已接通：tools/duel_allocator_sync.py、duel_allocator_bridge.js；数据更新校验后原子启用，未知逻辑暂存待审，支持diff/list/crosswalk/兼容快照回退。上游只读，账号数据不被覆盖。无后台同步、无新用户GUI、输出executable=false。
7. 上游当前已审cd425744b111604d6e0505341cba29989a16ef7a；store=MA9-evidence/allocator-store，active=f0e73206dc4645cba21d8a0afacbbe6c5d196e478f1a17968a8eaf1e111878b4。83图/69引用昵称；复用原核心，空槽兼容补丁ma9-empty-every-slot-v1。同步/回退/坏数据保旧、5个独立穷举oracle已过；定向4测试3pass+1实体symlink权限skip，模拟reparse拒绝通过。
8. 用户最新选择普通档，不再以自动档第3槽缺Nevera R为当前阻塞。普通档独立枚举25,387可行分配、14个完整五槽非支配方案，与桥逐项一致；另12候选资料未知。普通档当前参考无time，按名单顺序，不宣称按实际星级计时最优或实机自动驾驶通过。高手档仍因13候选缺星显式阻断。

## 重点文件与证据（按需要读）
- 当前普通档报告/请求/验证：MA9-evidence/20260927-05AF-normal-readme/{report.md,normal-request.json,results.json}。
- 最新车库资格覆盖层：MA9-evidence/20260927-05AD-upgrade-policy/garage-review-overlay.json；正式profile未改。
- 星级与可见身份证据：05AA-stars、05AB-association、05AC-star-gaps各证据目录；05AB/corrections-draft.json及review.md定位5个误关联原帧。
- 运行时缺陷入口：agent/ma9_agent/duel_vehicle_screen.py的_duel_identity；必要时结合duel_vehicle_runtime.py的跨帧采样，不预设只改一处就够。
- 同步/报告验证：MA9-evidence/20260927-05AE-allocator/results.json、review/review.md；使用说明docs/zh_cn/develop/duel_allocator_sync.md。
- 历史未审4个ID：MA9-evidence/20260927-05AA-stars/root/unreviewed-historical-identities.json。

## 干净总控恢复后的下一步
先核对本文件与state当前policy/model_dispatch/allocator_integration_task/normal_tier_readme_task/garage_allocation_policy等字段、lanes的当前模型政策及相关文件边界；然后git status/HEAD/worktree/远端追踪状态。不把state历史模型字段当作新派工指令。
建议下一项仍是运行时车型误关联的有界诊断/窄修，先由总控核定准确源码范围与已有反例，给DeepSeek完整外部任务提示词；关键修复交GLM独立终审。用户还未收到该新任务提示词，本轮不要自动启动。
普通档14方案已可作为后续用户端“车库识别→同步参考数据→预览阵容”的离线基线。未知候选/完整库存、用户端接线与执行门禁仍须分别处理，不捏造拥有或自动开赛。
