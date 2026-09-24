# MA9-00-新编排入口（2026-09-23集成后）

你是MA9唯一总控，cwd必须E:/hzz/work/MA9。保持当前模型，日常medium，契约/跨lane/重复失败/关键合并high；不能切档明确说明。禁止启动GPT子智能体或自动创建对话。外部子任务仅由用户在指定模型全新对话粘贴完整提示词。

先完整读取主仓库：docs/zh_cn/develop/multi_agent_plan.md、agent/lanes.yaml、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md、agent/orchestration/duel_scan_stability_report.md；然后核对main和所有worktree实际HEAD/status、最近提交、git worktree list --porcelain。不要凭本文件旧SHA覆盖现场。

所有写入、worktree、证据在MA9根内；四个MA9-*已迁入根内，不能重建同级目录。只有总控建worktree；根外MutualExclusionAllocator未经授权不操作。原始日志旧路径按迁移表定位，不改历史证据。不要清理用户.workbuddy/。
Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；缺失停止。所有Python-X utf8、cwd为对应lane根，不从main导入lane源码。TMPDIR/TMP/TEMP三者同时设为根内证据tmp，记录实际tempfile.gettempdir；不绕过宿主删除守卫，不复用外部会话的单次审批。
Git只用命令级safe.directory，不改全局配置。契约A=bd9a535336750d8fae3799f20d321498e21f5b00，B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5；验证祖先后复用，不重新冻结。五契约模块/schema/runtime_action/interface手写源只允许总控。六个大型multiplayer_loop分片不得读入模型上下文；未精确登记的data/generated只读。04暂停，第三方策略缺失不阻塞其既有兜底设计。

当前已完成：
- 05交付f5472bce3443fde42df17ad8a1819e18b46a2059，GLM-5.3 high独立复核通过，用户D级实机449.013秒，five_assigned、五车互斥、starts_race=false、停阵容页。包user-test-ordering-f5472bc不带新便携标记，成功不推广至其他等级/账号恢复/新标记包。
- 实机原业务JSON落MA9/debug，源于既有账号根优先策略；输入与包仅CRLF/LF不同，JSON一致。已冻结MA9-evidence/20260923-091020-D-five-assigned；不要用动态debug当旧运行证据。
- 根隔离总控490cbb9 + 外部02D a7d9910，独立02R无阻塞；标记.ma9-portable-root，override→顺序穷尽exe标记链→cwd标记链→Agent模块标记链→原无标记逻辑。新包无实机结论。低/信息级文档/测试补充见state followups，不改原02D错误报告。
- 根隔离合并380b051afceac70af1f31471c0339de071a076ce；05合并f36f3b23db952aae67e2583f9e74ae965fa6fa65。组合Agent105、tools29全过无skip、exit0；schema34项输入等价复用27项exit0。证据MA9-evidence/20260923-combined-integration。远端状态必须现场检查，不把本地通过当CI通过。
- 总控在550c01dc95af0e5bc2cb16f8ccc70b316b88980d归还duel_defense_setup.py及其测试给06，已从05 owns移除。

当前下一任务：06配置阶段已按有限范围闭环；仅G1有本轮直接实机证据，G2–G8仍为离线/代码证据，resumed_from_slot=1不证明中途恢复。用户用GLM-5.3 high全新对话执行agent/orchestration/prompts/07-duel-attack.md（07A只读规划）。worktree E:/hzz/work/MA9/MA9-worktrees/duel-attack，branch lane/duel-attack，基点与预期HEAD=2876a4a25f5dcc7101963bfccd97ae23f6f41ba6。未放行写代码、进攻实机、扣票、开赛或根外读取；04暂停。用户已在06A回传后明确确认向既定origin推送；远端状态仍按Git现场与state核实。

保留：01=891d68efc9d33d08cb4799855414579900b5648d未闭环；02原CI=03c6d9751f8b5f31865501d1954b2486568afd76未合入，别与已合入的根隔离任务混淆。当前worktree数量和SHA以git现场为准。旧05R/02D/02R任务已完成，提示词仅历史，不能重复派发。
外部安排：01 Hy3；02/03/05/06 ds-v4.1flash；07及独立review GLM-5.3 high；E GLM-5.3-Flash，V Hy4 preview，H Kimi-K3；MiniMax-M3备用未派发，04无模型。不启用全部模型，不自动购买/重置/升max。
每个新任务完整注明项目、模型/档位、cwd/branch/完整基点与HEAD、必读文件、精确owns/owns_new/owns_generated、验证命令、证据、结束条件和回传格式。用户只回传结果，总控查实际证据、维护状态和下一份提示词。实机默认用户串行执行，不操作ADB/MuMu；GUI完成提示不能替代业务JSON。合入通过后按用户授权推送，除非用户明确不推送；失败如实记录，不改写历史或强推。

用户新增持久规则：每次较大修改形成完整且验证通过的阶段后，自动创建一次本地Git提交，不再逐次询问；只提交授权文件，不纳入私有证据或用户.workbuddy。远端推送与本地提交分开处理，自动审批拒绝时不得绕过。

最新调度补充：用户报告GLM-5.3约4小时额度等待，07A固定2876a4a提示词保留、不换模。期间可执行02E（ds-v4.1flash high，prompts/02-build.md），cwd MA9-worktrees/root-isolation、branch codex/root-isolation、基点18964c884cd3b6a4a81bb3c69edeb96b26ed26dc，仅文档/GUI测试两文件。该18964c8远端check与install现已均成功。总控不自动新建对话或唤醒。

02E最新：8759c9f已由总控合入d0418c1，tools30全过；02E任务结束，不重复派发。07用户新策略为D/C合计至少三辆优先；进攻三胜规则由用户确认，但结束余场的操作未实机验证。防守中断需重做，旧中断判负不直接套进攻。以state.user_strategy及07提示词最新补充为准，不自动退出或操作设备。

用户最新图片进展：7张三胜概览/完成确认/每日进度图已存MA9-evidence/20260923-attack-three-win-user-confirmed；确认页明确提前离开挑战视作获胜，用户手动流程已确认，MA9自动化仍未验证。图8缺失，详见07提示词最新证据段。已获批准的343e2f3已推送并核对远端；新图片说明为后续本地编排提交，不冒称已远端。

最新补图：MA9-evidence/20260923-attack-three-win-supplement新增5张，补齐奖励继续页与第三胜返回大厅页，另有失败/胜/胜/失败/未打反例；2胜2负必须打第五局，完成按钮可见不代表可提前结算。累计胜场按不同槽位计数，比赛#3不是三胜。07提示词已更新，不再重复索取已收到图片。

等待GLM期间最新收尾：02R F5-runtime已在caf5c0455f4ecc6595ed79c82eac365a2e57a1d9补测试，Agent106全过。06工作区已快进caf5c04，当前06提示词为06B地图顺序守卫回归（ds-v4.1flash high，仅test_duel_defense_setup.py一文件）；06A审计已完成，不重复。07A仍按原固定2876a4a与最新图证只读规划。

06B最新：23ced1f已交付并由总控Agent107全过验收，本地集成最早plan模式地图顺序守卫回归，生产未改。06B旧提示词已标完成不重复派发；其余三处守卫只是可选后续。等待期既定收尾全部完成，下一仍为GLM恢复后的07A。

最新07A状态：实际report/results及2+3测试日志已齐全，07HEAD2876a4a干净。平台末尾限额不影响只读规划已完成，不换模型重跑旧07A。下一纯离线状态机为建议，尚未登记新增文件或派发；Qwen3.7-Max只讨论候选，未自动替换模型。

最新派发07B：用户要求high/max建议与完整提示词，总控选择ds-v4.1flash high，不开max。07工作区已快进72e32dad93165f3c34dc022096c9222c9a1e0977，新登记duel_attack_session.py及对应测试，仅纯离线决策/候选衔接；详见07-duel-attack.md。07A已完成不重跑，Qwen3.7-Max只为后续独立review候选。

当前唯一下一步（优先于上面历史附记）：07B b063f56cf988bf2544362c3d861cc51ecbe6597d总控验收被两条停止语义反例阻断，未合入；prompt07现为07B1（ds-v4.1flash high新对话），cwd MA9-worktrees/duel-attack、branch lane/duel-attack、起始HEAD=b063f56cf988bf2544362c3d861cc51ecbe6597d。证据20260923-07B-orchestrator/repro.py+log，修复后再独立review。基点107+新增26=133无计数异常。不要重跑已完成07A或误称07B已验收。总控可继续自动压缩，不需要按固定轮数重开；若新开，先读本文件与state并核对现场。

最新07状态：be381dbc1488cce4ff9e9c1111e50b40421a489d已修两停止分支，总控repro2/Agent139/规划3/tools29+1skip与8192有限安全矩阵全过，schema34输入复用27。尚未合入；当前唯一下一提示词为07R-attack-review.md，Qwen3.7-Max新只读对话、平台默认设置。关注stop只是暂停自动推进，不是退出或证明已输/已结算；owner预算已用完，不擅自重派无限修复。

07R当前模型已按用户可用列表更新为Qwen3.8-Max（非历史3.7），默认平台思考设置；目标仍be381dbc1488cce4ff9e9c1111e50b40421a489d，只读复核提示词07R-attack-review.md。3.8-Flash未派发，不自动max。

最新07结论：07R已完成无行为阻塞；总控集成be381db并修正reason/注释过强措辞，Agent139/tools30全过，8192比较非reason差异0。离线阶段结束，仍无识别/执行器/实机进攻结论。当前需目标MuMu1280x720五图进攻页原图作后续只读识别输入；不要重派07B1或07R。用户报告Qwen3.8-Flash当前平台免费不限量，已登记备用未派发；Max不作常驻反复复核。

最新截图输入：captures新增01–09共12张均1280x720，已逐张查看并冻结于MA9-evidence/20260923-184330-attack-mumu-intake。够开始01–05只读对手页面识别，不等后续赛后图。左/中/右D/C计数3/3/0，用户确认合格者优先巴掌奖励更多，当前中档优先；用户确认擂台进攻不消耗普通燃油。左季风秘境/岩石地带自动候选为空；旧地图ROI不能盲用于新详情布局。不要提交原captures账号图，不把09游戏自动选车当策略结果。07C尚未登记或派发，下一步先定义窄只读识别任务。

2026-09-24最新验证路线：用户提出进攻每天清理、不能长期留页，后续共用选车/计划应用优先用不进组测试号防守页由用户验证。scan/assign_visible可复用，但现defense_setup仅weakest_current且完整阵容会already_configured，需专门入口；绑定独立测试账号数据根，不能沿用旧包的main车库。仅选车不开赛；进攻择敌/扣票/三胜/奖励仍进攻侧另验。当前未授权Agent操作设备或放行新代码任务。

当前唯一新派发任务：05E阵容页槽位只读观察，ds-v4.1flash high，完整提示词05-duel-scan.md。05工作区已快进02ee41c239bf45734ba3fa5ee44dc9dc7889ec5c，新增duel_lineup_slot.py及测试。用户要求入口与地图解耦；先可靠观察唯一展开槽，未知不能默认1，不接入口/选车点击/地图名。其后才做带槽位核验的共用选车；当前仍无Agent设备权限。
