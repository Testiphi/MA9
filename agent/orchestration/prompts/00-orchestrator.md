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
