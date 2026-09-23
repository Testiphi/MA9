# MA9-07B-纯离线进攻状态决策与候选衔接

模型：ds-v4.1flash / high。high足够，禁止自动升max；平台若不暴露档位如实注明，不伪称切换。用户新建外部对话粘贴完整提示词，不依赖旧聊天、不创建子智能体/对话/worktree。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-attack
branch：lane/duel-attack
完整基点与预期起始HEAD：72e32dad93165f3c34dc022096c9222c9a1e0977。
总控已创建并快进工作区、登记新增文件；不再使用07A的2876a4a，不自行checkout/reset/merge。主仓库编排文件为权威。

任务：新增一个纯离线模块，根据同一挑战的五槽状态快照提出下一步建议，并薄封装现有plan_attack结果。不实现OCR、按钮点击、真实挑战或整个日常循环。07A规划已完成，不重复审计整仓。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先后复用，不重新冻结；不得改五契约模块/schema/interface/runtime_action。

必读：
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/agent/lanes.yaml（07 owns_new，按本任务更窄范围）
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
E:/hzz/work/MA9/MA9-evidence/20260923-07A-attack-planning/report.md、results.json
E:/hzz/work/MA9/MA9-evidence/20260923-attack-three-win-user-confirmed/manifest.json
E:/hzz/work/MA9/MA9-evidence/20260923-attack-three-win-supplement/manifest.json（s05两胜两负反例）
本cwd下agent/ma9_agent/duel_selection.py、agent/tests/test_duel_selection.py、tools/test_duel_selection.py；均只读。无需读全套私有截图来重复做识别；本任务输入是规范化枚举，不是图片。

精确写入边界：
owns: []
owns_new:
- agent/ma9_agent/duel_attack_session.py
- agent/tests/test_duel_attack_session.py
owns_generated: []
若文件已存在或工作区非干净停止报告，不覆盖现有成果。只可新增这两文件；不修改duel_selection.py、__init__.py、runtime_action.py、旧测试、CLI、文档、lanes/state、pipeline、资源、generated或05/06文件。不得安装新依赖，不复制/调用根外MutualExclusionAllocator。

设计范围（保持小而纯，不建通用状态机框架）：
A. 五槽快照决策函数
- 输入是同一挑战、同一快照的五个带slot编号条目，slot必须恰好1..5各一次，状态仅win/loss/unplayed/unknown。条目次序可不同，输出按slot排序确定；长度/重复slot/非法状态或非法重试计数以明确ValueError拒绝，不隐式猜测。
- 函数只统计本次快照，不叠加历史帧，不使用全局缓存、文件、时间、随机数或设备。重复调用相同快照不增加胜场；新挑战由调用方提供新快照并重置重读计数。本轮不合并旧快照、不从比赛编号猜胜场。
- 另收规范化确认结果not_seen/win/loss/unknown。这不是OCR文字解析；确认框的“将被视作获胜”应由未来识别层映射为win，本轮只处理枚举。
- 输出至少包含wins、losses、unplayed_slots、unknown_slots、next_action、reason、next_unknown_attempts；以及starts_race=false与requires_live_verification=true。action只是纯建议，不是执行器。
- 无未知/矛盾且wins>=3，确认not_seen：只能request_finish_confirmation，不能标记已胜利结算，也不能许可直接点确认完成。
- wins>=3且确认win：可给confirm_finish建议/early_finish_allowed=true；这两项必须只在此组合成立。仍不宣称已点击或已结算。
- 2胜2负+第五槽unplayed：建议continue_race并明确pending为[5]，绝不提前完成，即使未来UI报告完成按钮可见。
- wins<3、有未打槽且无确认矛盾：建议继续尚未打的槽，不主动放弃。五槽均已完成且wins<3：stop并给出未取得三胜的终态原因，不开始第六局；不在本轮自动处理败局退出。
- 确认loss，或确认win但已知完整快照wins<3：stop且不授权完成。不要把确认判负按成功处理。
- 槽位unknown，或需要确认但确认结果unknown：bounded_reread；重读计数显式传入、返回，累计第3次仍不可读则stop。有效且一致快照将重读计数重置为0。不睡眠、不轮询设备；“3次”只是离线调用预算，不声称实机时延已调优。
- 已有unknown/矛盾时不得跳到完成建议；边界优先级写入函数docstring并测试。无确认时的正常待赛不算未知重读。

B. 候选衔接函数
- 直接调用现有plan_attack，明确接收五图、赛区、owned_ids、reference、catalog及unavailable_ids/limit，原样传递过滤与限制。不得重写算法、改变Pareto/排序/互斥规则或修改原函数。
- 保留complete、filled_slots、gaps、plans和requires_live_vehicle_and_fuel_verification。完整候选只表示五槽有互斥方案，不等于允许Start；封装结果额外明确starts_race=false，不能把候选complete与三胜混为一谈。
- 不隐藏complete=false的缺口；零拥有时现有一个全None方案不能误显示为可开赛。调用既有函数的输入错误保持清晰，不吞异常伪造成功。
- 输入数据、集合、列表不得被修改。只依赖标准库与现有duel_selection纯函数，不导入maa/controller/GUI或真实识别层。
- 两个函数在同一新模块，公开名称与类型可由你选最小清晰实现，在docstring写明，不新增共享契约、配置或持久文件。

明确不做：
对手D/C合计>=3是已记录的后续择敌偏好，本轮不做对手评分/刷新/扣票；不接三档i详情；不做奖励领取、巴掌记账、排行榜返回、真实自动驾驶、断线恢复、图像模板；不修缺读数与排序矛盾共用错误消息。对手“完成”按钮可见、比赛#3、票数N/5、亮起下一槽编号、GP数值均不是输入胜场依据。
用户手动截图证明完成确认路径，但不构成MA9自动化通过。非16:9参考图不直接变1280x720模板。当前不需要用户再补图或跑实机。

新增测试必须至少覆盖：
1. 三胜+not_seen仅请求确认；三胜+win才允许确认完成；loss/unknown分别安全停止或有界重读。
2. s05对应[loss,win,win,loss,unplayed]继续slot5；完成按钮信息不能绕过胜场判断。
3. “第三场赢但前两场输”只有1胜不能提前完成；相同快照重复输入不累计；slot输入排列变化输出相同。
4. unknown三次预算到达stop，恢复有效后计数归零；坏slot/重复slot/非法状态/负计数拒绝；跨调用无共享可变状态。
5. 全完成但只有2胜无第六局建议；确认win与不足三胜矛盾不放行。
6. 用小型假reference/catalog验证衔接结果和直接plan_attack一致：互斥、unavailable排除、缺轨/候选不足、零拥有、确定性、limit传递、完整候选仍starts_race=false；输入不变。
新增测试放agent/tests，确保默认discover覆盖新接口。旧plan_attack三个工具测试仍要显式运行（它们在tools/根，默认discover不会发现）。不得mock被测新函数返回值，不加skip，不大规模穷举。

证据与环境：
仅在E:/hzz/work/MA9/MA9-evidence/20260923-07B-attack-session/新建report.md、results.json、targeted.log、attack-regression.log、agent.log、tools.log、schema-reuse.json或schema.log及tmp/小夹具。目录存在停止，不覆盖原证据；不同轮日志另存带序号文件，不覆盖红/失败记录。
Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；先验证存在并-X utf8 --version，缺失停止，不换PATH。每条Python-X utf8，cwd始终07根，禁止main源码PYTHONPATH。TMPDIR/TMP/TEMP三者同时指向上述tmp，打印并记录实际tempfile.gettempdir；所有写入MA9内，不绕过宿主守卫。
Git开工/收工核对status、branch、完整HEAD、最近3提交及B祖先；只用-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-attack，不改全局配置。

验收命令（$lanePython为已解析解释器）：
& $lanePython -X utf8 -m unittest discover -s agent/tests -p test_duel_attack_session.py -v
& $lanePython -X utf8 tools/test_duel_selection.py DuelSelectionTests.test_allocator_uses_distinct_cars_and_best_available_tradeoff DuelSelectionTests.test_unknown_and_empty_tracks_are_reported_without_a_startable_plan DuelSelectionTests.test_same_car_on_every_track_reports_mutual_exclusion_shortage -v
& $lanePython -X utf8 -m unittest discover -s agent/tests -v
& $lanePython -X utf8 -m unittest discover -s tools/tests -v
第二条只跑三个纯假数据测试，不执行real_source，不运行导入生成器。基点Agent107是历史，不冒充当前新模块通过；本轮需完整实际退出码和数量。
schema门禁：本任务不改schema/interface/资源/校验器，先机械核对输入与已验证基点相同，写schema-reuse.json，引用MA9-evidence/20260923-combined-integration/results.json及05D原schema27项exit0；明确复用不重跑。输入任何不同则停止复用并报告；确需运行的正确命令为：
& $lanePython -X utf8 tools/validate_schema.py --schema-dir E:/hzz/work/MA9/deps/tools --resource-dirs assets/resource --exclude-dirs assets/resource/announcement --interface-files assets/interface.json
所有长进程续等到最终退出。失败最多两轮有界修复仍不过则返回总控；不自动升max、不购买额度或重置。不得读取六个大型multiplayer_loop分片，不生成data/generated，不触根外仓库。

结束条件：仅两个登记新文件，全部适用门禁通过，git diff --check干净，行为明确区分请求确认/确认允许/实际完成，未产生任何设备/I-O副作用。按用户政策自动本地提交一次完整交付；只暂存自己的文件，不合入main、不推送、不打包、不发布、不启动GUI/ADB/MuMu/游戏。
回传项目、实际模型/平台/档位、cwd/branch/起止完整SHA、commit、文件清单/stat、公开API简述、命令/最终退出码/数量、复用证明、证据路径、剩余风险。总控独立验收后另派新上下文只读复核（Qwen3.7-Max仅候选，平台档位不编造；复核不得由owner自评代替）。完成本任务不代表进攻全流程或实机通过。
