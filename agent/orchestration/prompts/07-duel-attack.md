# MA9-07B1-进攻决策矛盾停止窄修复

模型：ds-v4.1flash / high。用户在WorkBuddy或选定平台全新对话粘贴完整提示词。平台无独立档位则如实注明；不自动升max，不创建下级智能体/对话/worktree，不依赖旧聊天。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-attack
branch：lane/duel-attack
完整基点与预期起始HEAD：b063f56cf988bf2544362c3d861cc51ecbe6597d。
此前实现基点72e32dad93165f3c34dc022096c9222c9a1e0977；当前交付已经存在，不从旧基点重做。main尚未合入该模块，工作区须干净。不checkout/reset/merge。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5；验证祖先后复用，禁止重冻。

必读：
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/agent/lanes.yaml
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
E:/hzz/work/MA9/MA9-evidence/20260923-07B-orchestrator/results.json、repro.py、repro.log（总控只读反例，禁止修改）
E:/hzz/work/MA9/MA9-evidence/20260923-07B-attack-session/results.json、tmp/targeted.red.1.log（历史证据保留）
本cwd的agent/ma9_agent/duel_attack_session.py及agent/tests/test_duel_attack_session.py；duel_selection.py只读。

精确本次边界：
owns:
- agent/ma9_agent/duel_attack_session.py
- agent/tests/test_duel_attack_session.py
owns_new: []
owns_generated: []
这两文件已在07原owns_new登记，本轮只修它们。其余生产模块、旧测试、CLI、文档、状态、lanes、契约、schema、interface、资源和生成物全部只读。不得改05/06，不安装依赖，不读取/运行根外MutualExclusionAllocator。

当前问题（总控已运行repro.py，2 failures、exit1）：
F1：[loss,win,win,loss,unplayed] + confirmation='win'：实际next_action='continue_race'，要求'stop'。这是已知完整快照不足三胜与确认判胜矛盾；测试test_confirmed_win_with_insufficient_wins_is_not_released仅断言不confirm_finish，不足以锁定停止。
F2：[win,win,win,unknown,unplayed] + confirmation='loss'、unknown_attempts=0：实际bounded_reread，要求立即stop。总控明确优先级：已经读到明确判负时，不应为了其它未知槽位继续重读；判负分支优先于未知重读。

只做最小修正：
1. 输入校验后，明确loss必须直接stop（包括带unknown）；完整可读快照wins<3且confirmation=win必须stop，不能继续任何比赛建议。
2. 三胜+not_seen仍只能request_finish_confirmation；三胜+win且无未知才confirm_finish并early_finish_allowed=true；未知槽位与非判负确认仍保留既有3次有界重读。不能为修停止分支放宽未知时的提前完成条件。
3. 正常s05两胜两负+未见确认仍continue_race、pending=[5]。三胜请求确认和真实完成是不同阶段；starts_race恒false，requires_live_verification恒true。
4. 两个阻塞用例必须明确assertEqual(next_action,'stop')并核对reason说明对应判负/矛盾，而非仅assertNotEqual(confirm_finish)。覆盖confirmation='win'且0/1/2胜、有未打槽的代表性输入；明确loss带unknown的0/1/2重读计数均不可继续重读。
5. 修正文档/注释与实际一致：模块顶层第6条“wins>=3且仍有未打槽继续”与上面分支矛盾；test_code_decisions_still_reset_the_counter注释及原报告“loss保留预算”与当前实现attempts_next=0不符。当前明确判负直接stop可保持现有0计数；不要为错误报告倒改正确行为。原历史报告不改，本轮另附更正。
6. 候选衔接、plan_attack、状态输入约束、纯函数/不变性/重复帧不累积均保持，不重构整个模块，不加新功能。

计数更正：当前起点b063已有133项=72e32da基点107+本模块26；107中的两项增量来自caf5c04 runtime模块链测试和23ced1f地图顺序测试。f5472bc的05D实际是101，组合后曾为105。按实际起点计数，不把历史混在一起。
原owner已有1轮内部修复，本次作为第2轮有界修复；仍失败或需要扩范围就保留最小复现返回总控，不自动升max或无限重试。通过后仍需要另一个新上下文只读复核，不由本席自评代替。

环境与新证据：
Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；存在才-X utf8 --version，缺失停止不换PATH。所有Python-X utf8、cwd本lane根，不导入main源码。
新证据E:/hzz/work/MA9/MA9-evidence/20260923-07B1-contradiction-fix/；目录存在则停止报告，禁止覆盖。允许report.md、results.json、red.log、green.log、targeted.log、attack-regression.log、agent.log、tools.log、schema-reuse.json和tmp/小夹具。TMPDIR/TMP/TEMP均设为此tmp，记录实际gettempdir。每轮失败日志单独命名保留。
开工/收工核对git status --short、branch、完整HEAD、最近3提交；Git仅-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-attack，不改全局设置。

验证命令（$lanePython为解析路径）：
& $lanePython -X utf8 E:/hzz/work/MA9/MA9-evidence/20260923-07B-orchestrator/repro.py
先运行确认两失败并保存本轮red.log；修复后同一命令应两通过，保存green.log。不能修改总控repro.py。
& $lanePython -X utf8 -m unittest discover -s agent/tests -p test_duel_attack_session.py -v
& $lanePython -X utf8 tools/test_duel_selection.py DuelSelectionTests.test_allocator_uses_distinct_cars_and_best_available_tradeoff DuelSelectionTests.test_unknown_and_empty_tracks_are_reported_without_a_startable_plan DuelSelectionTests.test_same_car_on_every_track_reports_mutual_exclusion_shortage -v
& $lanePython -X utf8 -m unittest discover -s agent/tests -v
& $lanePython -X utf8 -m unittest discover -s tools/tests -v
仅运行指定三个工具假数据测试，不运行real_source或生成器。schema资源/校验器/interface应不变，机械证明与原07B一致并复用07B schema-reuse及05D27项exit0，明确未重跑。任何输入变化不得复用，先上报。长命令续等到最终退出，记录真实数量和跳过原因。

结束条件：总控两条反例红转绿、对应生产测试准确锁定stop、全套适用门禁通过、diff --check干净且只有两文件变化。按用户政策自动本地提交，不合入main、不推送、不构建、不启动GUI/ADB/MuMu/游戏，不开赛或扣票。六个大型分片不读入上下文，data/generated只读。
回传项目、实际模型/平台/档位、cwd/branch、起止完整SHA/commit、diff/stat、两条反例的修复前后退出码、各门禁数量/退出码、复用证明、证据路径与残留风险。修复完成不等于已独立复核或实机通过。
