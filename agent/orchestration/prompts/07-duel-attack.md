# MA9-07A-进攻只读规划与最小交付定义

状态：07A已完成。总控已检查report/results、2项与3项测试日志和干净HEAD2876a4a。以下是历史完整派发内容，禁止因平台限额缺最终回复而重跑；下一写入任务须另行登记与派发。

模型：GLM-5.3 / high。用户在外部平台新建完整独立对话粘贴本文件。你是07只读规划执行者，不创建对话、子智能体或worktree，不依赖旧聊天，不自行升档。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-attack
branch：lane/duel-attack
完整基点及预期起止HEAD：2876a4a25f5dcc7101963bfccd97ae23f6f41ba6。
总控已创建工作区，主仓库后续可能有提示词/状态提交；主仓库编排配置权威。现场不符停止，不reset/checkout/merge。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，检查祖先后复用，不重新冻结。05修复f5472bce3443fde42df17ad8a1819e18b46a2059经f36f3b23db952aae67e2583f9e74ae965fa6fa65合入；根隔离a7d9910cc945072efbf6ccb9b3d38f4f949a6e87经380b051afceac70af1f31471c0339de071a076ce合入。

前置范围：06当前“D级五车配置、停阵容、不开始比赛”阶段已闭环，不等于五场资格赛已完成或已进入进攻页面。05的449.013秒D级实机有效；其他等级、已配置阵容保留、中途恢复和账号恢复没有本轮直接实机证明。06A回传“5实机+3离线”已被总控更正为G1直接实机、G2–G8离线/代码证据。禁止扩写成功范围。

本次任务：仅用MA9内现有代码、数据与文档，盘点进攻离线规划能力及其到安全只读页面入口的缺口，给出一个最小可交付的下一实施任务。不要直接写进攻闭环，不操作游戏，不消耗票券，不把离线complete当作开始比赛的授权。
用户最新策略与截图证据（2026-09-23，此段替代旧的“提前结算操作尚无截图”记录）：
- 对手偏好仍为五辆防守车中D/C合计至少三辆；不是同级三辆，也不保证胜率，不发明同分权重/找不到对手时付费刷新策略。
- 总控已收到并查看7张图，原图与hash/尺寸/映射存于E:/hzz/work/MA9/MA9-evidence/20260923-attack-three-win-user-confirmed/manifest.json。按需读该目录p01..p06.png、p07.jpg；只读，不复制到受控素材、不修改原图。
- p01–p03为三场不同挑战的三胜概览，p04–p06为对应完成确认（1↔4、2↔5、3↔6）。确认页有三行有效获胜成绩、两行“未完成”，并明确“如果您现在离开挑战，将被视作获胜”。这是直接界面证据，不再仅是推测规则。
- 用户实际操作说明：第三胜单场成绩页点“返回大厅”→挑战概览右上“完成”→确认页右下“完成”→每日挑战巴掌进度页→点空白继续→可能出现额外奖励页→继续→擂台排名页。第一批为7张；后续已补第三胜成绩页与额外奖励页，详见下段。最终排名页不在两批附件中。
- p07可见“每日挑战奖励”、25/22和“点击继续”。25/22是累计每日进度，不是该挑战新增25；确认页+18 GP不是巴掌奖励；概览右上0/5、1/5、2/5是票数，不能作小图进度。
- 规划提前结算应以≥3个不同槽位明确获胜，并在确认弹窗再次读到“将被视作获胜”为双重判据；未知/矛盾/判负文案不得按成功处理。不能把任意“退出”操作等同于这个专门“完成”流程。
- 已有用户手动实测说明和静态截图，MA9自动识别/点击链路尚未实现或实机验证；不得把人工证据写成Agent通过。p01–p06为2420x1668，p07为1567x1080，不是1280x720 MuMu模板，禁止直接拉伸套坐标。
- 奖励页作为结算后可选分支：有则识别后继续，无则直接验证回排名；不能硬编码必出现，不能把领取/继续当成新挑战或重复记巴掌。动态图动画应等稳定后读累计数，再返回页核对，未知页面有界停止。
- 防守中断需五图重做是另一场景；不把旧防守中断失败泛用于进攻。用户原话“五张有效票”不能据此推断票券消费。
- 当前仍只读规划，不启动设备、不点击完成/退出/开赛。已补齐之前请求的奖励页与第三胜成绩页，不再重复索取或要求整套全流程；真正进入MuMu识别实现时再按具体缺口提出最少资料。
后续补图与必守反例（用户本轮另给5张）：
证据目录E:/hzz/work/MA9/MA9-evidence/20260923-attack-three-win-supplement/，先读manifest.json；s01.jpg为可选奖励页，s02/s03/s04.png为三组第三胜单场成绩页，s05.jpg为两胜两负未锁胜反例。
- s01明确“恭喜！你获得了这些奖励”、擂台币900与“继续”；900只是样例数值，不固定金额/奖励种类，也不将此可选页当作巴掌累计页。
- s02–s04标题“比赛#3 获胜”，底部前三槽均为绿色上箭头，左下“返回大厅”，右下“下一场比赛”。它们分别对应第一批1/4、2/5、3/6样例，支持用户手动链路；不是同一组比赛的连续三个胜场截图。
- s05五槽状态依次“失败、获胜、获胜、失败、未完成”，只有2胜2负，第五局未打。即使右上“完成”按钮可见，必须继续第五局，不能走提前完成分支。它是未锁胜状态，不是三胜。
- 决策依据必须为同一挑战内不同槽位的累计获胜数，不是比赛#序号、完成场数、当前展开槽位或亮起的下一槽编号。重复帧不得累加胜场；未读出/矛盾时有界重读或停止，不猜已锁胜。
- 达到3胜后，才能规划返回大厅→完成，并再次核对确认弹窗“将被视作获胜”；未达3胜且有未完成比赛则继续尚未完成的比赛（本反例特指第五局）。本次并未授权自动开赛或操作设备，这只是状态机需求。
- 第二批尺寸s02–s04=2420x1668，s01/s05=1567x1080。原始图片只读，账号图不提交，不直接拉伸作MuMu模板。当前无需再请求完整流程图。
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
