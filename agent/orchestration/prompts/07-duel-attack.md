# MA9-07A-进攻只读规划与最小交付定义

模型：GLM-5.3 / high。用户在外部平台新建完整独立对话粘贴本文件。你是07只读规划执行者，不创建对话、子智能体或worktree，不依赖旧聊天，不自行升档。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-attack
branch：lane/duel-attack
完整基点及预期起止HEAD：2876a4a25f5dcc7101963bfccd97ae23f6f41ba6。
总控已创建工作区，主仓库后续可能有提示词/状态提交；主仓库编排配置权威。现场不符停止，不reset/checkout/merge。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，检查祖先后复用，不重新冻结。05修复f5472bce3443fde42df17ad8a1819e18b46a2059经f36f3b23db952aae67e2583f9e74ae965fa6fa65合入；根隔离a7d9910cc945072efbf6ccb9b3d38f4f949a6e87经380b051afceac70af1f31471c0339de071a076ce合入。

前置范围：06当前“D级五车配置、停阵容、不开始比赛”阶段已闭环，不等于五场资格赛已完成或已进入进攻页面。05的449.013秒D级实机有效；其他等级、已配置阵容保留、中途恢复和账号恢复没有本轮直接实机证明。06A回传“5实机+3离线”已被总控更正为G1直接实机、G2–G8离线/代码证据。禁止扩写成功范围。

本次任务：仅用MA9内现有代码、数据与文档，盘点进攻离线规划能力及其到安全只读页面入口的缺口，给出一个最小可交付的下一实施任务。不要直接写进攻闭环，不操作游戏，不消耗票券，不把离线complete当作开始比赛的授权。
用户最新明确补充（2026-09-23，总控已核实其意图；这是需求，不冒充实机证据）：
- 挑选对手优先考虑五辆防守车中D/C合计至少三辆，不要求同一级三辆。作为偏好而非胜率保证；不凭空添加D比C权重、同分排序、找不到合适对手时刷新/付费或强制挑战的策略。
- 用户确认规则为“进攻已赢三场，整组应赢”，但尚未实机确认三胜之后怎样结束剩余比赛。把胜负条件与退出/跳过/提前结算操作分开；不能据规则自动点击退出、放弃或开始下一场，也不能宣称提前结算已验证。
- 用户澄清此前中断失败关注的是防守：要求五图有效完成，中断一图需从头重做。旧文档将中断判负泛用于进攻的表述存在场景归属争议；保留原证据，按新用户说明区分场景，并在规划报告列出待验证接缝。不要自行更改文档或源码。
- 用户愿意按具体操作卡提供截图/验证。最低建议是在自然进攻取得第三胜的结算页保存完整截图，先不为验证提前退出；由总控根据可见按钮决定下一步。不要要求重跑已通过D级配置或大规模收集截图。
- 防守原话为“五张有效票”，按上下文区分五图有效结果；不能据此发明防守/进攻票券消耗规则。

必读：
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/agent/lanes.yaml（07、06与契约边界）
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
E:/hzz/work/MA9/MA9-evidence/20260923-06A-defense-audit/results.json（须结合总控更正，不采信夸大实机项）
E:/hzz/work/MA9/MA9-evidence/20260923-combined-integration/results.json
本cwd下：agent/ma9_agent/duel_selection.py、agent/tests/test_duel_selection.py、tools/plan_duel_selection.py、tools/test_duel_selection.py、tools/import_duel_selection_data.py（只读，不执行导入器）、docs/zh_cn/develop/duel_selection.md、blueprint_safe_selection.md、duel_daily_model.md；按需读取data/generated/duel_auto_candidates.json与vehicle_catalog.json，禁止重建。

精确本次边界：owns=[]、owns_new=[]、owns_generated=[]。所有受控文件只读，不修改07/06/05、契约、interface源、schema或编排配置。07全lane归属不代表本任务写权限。tools/plan_duel_selection.py和tools/test_duel_selection.py目前不在07写入清单，若建议以后改它们须报告总控先登记。
根外E:/hzz/work/MutualExclusionAllocator本次禁止读写或运行；lanes.external仅历史参考，不构成授权。不要执行import_duel_selection_data.py、不要运行tools/test_duel_selection.py的整套real_source测试、不要复制外部仓库。真实来源缺失不阻塞本次假数据纯函数审计。
允许新建私有输出仅E:/hzz/work/MA9/MA9-evidence/20260923-07A-attack-planning/下report.md、results.json、selection-tests.log、attack-tests.log及tmp/小夹具/有界只读探针。目录存在停止报告，不覆盖历史；所有临时写入根内。不读六个大型multiplayer_loop分片，不运行任何资源生成器。

检查清单（每项给代码/测试/证据位置，区分已实现、离线已证、待实机、缺实现）：
1. plan_attack输入/输出：五图、赛区、确认拥有集合、不可用集合、互斥约束、候选档、未知/无候选/互斥不足、确定性、limit与Pareto排序。识别已有测试与默认discover遗漏，别说“没有测试”而漏看tools/test_duel_selection.py。
2. 现有静态候选只是推荐顺序，不含实测赛道时间，不据此预测胜率；complete与requires_live_vehicle_and_fuel_verification的语义是否被调用端保持。
3. 地图/对手详情/票券/五槽状态等只读输入到离线候选的最小接口。区分“i详情只读”与“挑战立即扣票”；购买、领奖、刷新、提升、开始按钮全部不在本次许可内。没有当前MuMu进攻截图时明确缺什么，不猜模板坐标、不让用户批量收集无关截图。
4. _repair_descending_ratings的缺读数/排序矛盾错误消息待办仍属07；只评估它是否为下一最小任务的真实阻塞，不改护栏，不捎带优化05已验证OCR。
5. 若发现算法/数据缺陷，用小规模确定性假数据复现，保存最小输入与实际输出；禁止无界性能测试或大规模穷举。针对数据规模的风险必须给现有候选数与可验证证据，不泛泛宣称复杂度问题。
6. 最后只建议一个下一写入任务：说明目标、精准文件/owner（缺登记明确标出）、所需最少输入、纯离线验收命令、失败停止条件、独立复核范围。无需一轮列出整个日常系统的实现计划。若已无离线阻塞而缺现场输入，给一个最小用户资料请求建议，由总控决定是否派发，不直接接管设备。

环境与验证：
Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；先验证存在及-X utf8 --version，缺失停止，不切PATH。所有Python-X utf8、cwd始终07工作区，不从main导入源码。TMPDIR/TMP/TEMP同时设为本证据tmp，并打印实际tempfile.gettempdir。
开工/结束核对git status --short、branch、完整HEAD、最近3提交及B祖先；Git只用命令级-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-attack，不改全局配置。
最低命令（$lanePython为解析后的路径）：
& $lanePython -X utf8 -m unittest discover -s agent/tests -p test_duel_selection.py -v
& $lanePython -X utf8 tools/test_duel_selection.py DuelSelectionTests.test_allocator_uses_distinct_cars_and_best_available_tradeoff DuelSelectionTests.test_unknown_and_empty_tracks_are_reported_without_a_startable_plan DuelSelectionTests.test_same_car_on_every_track_reports_mutual_exclusion_shortage -v
上述tools命令只选择3项纯假数据进攻测试，不运行外部源测试。记录最终退出码、数量与复用项；长进程续等到退出。全量Agent/tools/schema为已通过组合证据，不重复跑，不声称本轮独立复现。

结束条件：受控文件保持不变，针对性测试有最终退出码，完成证据化能力清单及一个最小下一任务。回传项目名、实际模型/平台/档位、cwd/branch/起止完整SHA、git状态、命令/退出码/数量、缺陷行号/复现、建议任务、证据绝对路径与剩余风险。总控决定是否授权写入和是否需要独立review；本席不提交、不推送、不打包、不启动GUI/ADB/MuMu，不开赛、不扣票、不购买。04继续暂停。
