# MA9-05E1-槽位观察器标题门禁与证据语义收口

状态：本轮已完成并经05E1R独立复核、总控集成验收。以下为历史提示词，禁止重复派发；下一接线任务须另行登记。

模型：ds-v4.1flash / high。用户在外部平台全新对话粘贴本文件；平台无独立档位如实记录，不自动max，不创建下级智能体/对话/worktree。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-scan
branch：lane/duel-scan
完整基点与预期起始HEAD：cdeee38cf99ff5efe066f0d189bf6b647eb9ac17。
原实现起点02ee41c239bf45734ba3fa5ee44dc9dc7889ec5c。05ER判定当前静态范围无阻塞，本次是接线前的有界收口，不重写已通过的几何算法。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先复用，不重新冻结。

必读：
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/agent/lanes.yaml（05边界）
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
E:/hzz/work/MA9/MA9-evidence/20260924-05ER-lineup-review/report.md、results.json、tmp/counterexamples2.json、tmp/probe3.json
E:/hzz/work/MA9/MA9-evidence/20260924-05E-orchestrator/results.json
本cwd下agent/ma9_agent/duel_lineup_slot.py及agent/tests/test_duel_lineup_slot.py。

精确边界：
owns:
- agent/ma9_agent/duel_lineup_slot.py
- agent/tests/test_duel_lineup_slot.py
owns_new: []
owns_generated: []
原runtime/defense_setup/旧测试/入口pipeline/interface/schema/配置/生成数据/编排文件全部只读。本次不接OCR执行引擎、不安装依赖、不接Controller或选车执行器，不新增模板，不改114节距、面板/按钮几何阈值，不调整既有攻防行为。

已知事实：
18静态回放8正10负均通过，但attack09与defense01_selected真实正例标记数为0仍verified。因此折叠标记是存在时佐证，不可强制四标记，不可声称三路始终独立。
总控在真实attack09图上复现：OCR'好友挑战'且confidence=.99、OCR'挑战'且confidence=.01、同框'挑战'与'资格赛'两高置信标题，当前全部slot=1/verified。这是本次标题门禁改进的精确输入，不修改原始图/报告。

只做以下收口：
1. 修正文档：按钮中心+亮区右端是必要的两项相关几何检查；标记在存在时才佐证。已提交ColorMatch位置在按钮内，不是面板边界。不声称几何一致能证明真实游戏页面、端到端OCR或允许选车。
2. 保持observe_lineup_slot(frame, *, ocr=None)签名和纯函数。保留现有geometry-only观察模式：ocr=None时几何正常可返回槽号，但新增verification_basis='geometry_only'、title_guard_passed=false；已有slot_verified仅表示标定几何一致，不是动作授权。有严格标题且几何通过时basis='geometry_and_title'、title_guard_passed=true；拒绝时basis='rejected'。不要添加can_click/action_ready一类执行许可。
3. 标题区域按已提交同页标题位置收窄为(62,86,110,52)，使用OCR框中心判断是否位于区域；记录与18帧人工冻结标题坐标的回放覆盖。这个区域仍需将来真实OCR接线验证，不声称现已OCR实测通过。
4. 标题文本只允许去除空白后的整串“资格赛”或“挑战”，不得子串/前缀放行“好友挑战”“每日挑战次数:3”“资格赛奖励”等。OCR条目必须有有限数值confidence且>=0.90（bool/缺失/NaN/Inf/越界0..1均无效），低于阈值不能确认标题。只处理规范化条目，不新增真实OCR。
5. 同一区域内两个不同合法标题都是高置信时必须page_title_conflict、slot=None；重复相同标题不算冲突。区域内高置信“车辆选择”仍是否决证据。没有可信合法标题但显式提供OCR时，保持page_title_missing/slot=None，不回退geometry-only。
6. 不可用box（非数值/NaN/Inf/非正宽高等）和无效条目忽略，不能把坏框当命中，也不要让普通OCR坏条目导致观察器崩溃；在测试中锁定。
7. 已检出的标题冲突在几何早退时也要保留：evidence.title_conflicts统一为字符串列表，未冲突为空；早退可继续使用no_expanded_button等几何reason，但调用方仍能看出标题否决。不要改原始证据文件来修报告。
8. AST门禁只辅助，不声称证明所有无副作用。补上review给出的常见文件I/O调用检查（imread/imreadmulti/fromfile/load/loadtxt/save等），或小范围patch常见I/O方法证明正常观察调用不使用它们；不要做通用沙箱框架。

需要新增/加强的测试：
- geometry-only两种真实无标记状态保持可观察，并明确basis/title_guard_passed；有有效标题才geometry_and_title。
- 子串伪标题、低confidence、缺confidence、两个不同标题、相同标题重复、标题区外文本。
- 非法/不可用OCR框的安全忽略；几何早退仍保存标题冲突。
- 部分标记保持既有佐证语义，不能把缺四标记误判为已选阵容失败。
- 正常旧18帧样本仍正确；已标为缺失的进攻2–5/动态过渡不新增虚假通过声明。
不要重构网格计算（F9暂不做）、不要为合成假图验证而改变生产几何阈值；手绘结构图通过几何本身不是本轮要求消除的漏洞，关键是验证依据与动作权限分开。

证据/环境：
新目录E:/hzz/work/MA9/MA9-evidence/20260924-05E1-title-guard/（存在停止，不覆盖）；允许report.md、results.json、red.log、green.log、targeted.log、agent.log、tools.log、replay.py、replay-results.json、schema-reuse.json及tmp/。原05E/05ER证据只读，不运行旧replay.main覆盖它。
Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；验证存在并-X utf8 --version，缺失停止不换PATH。所有Python-X utf8、cwd本lane；TMPDIR/TMP/TEMP同时设为新证据tmp，记录实际gettempdir。只读主仓库原图允许，不从main导入业务源码。
Git只用-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-scan；核对status/branch/完整HEAD/最近3提交，现场不符停止，不reset/checkout/merge，不改全局Git。

命令（$lanePython为解析路径）：
& $lanePython -X utf8 -m unittest discover -s agent/tests -p test_duel_lineup_slot.py -v
& $lanePython -X utf8 -m unittest discover -s agent/tests -v
& $lanePython -X utf8 -m unittest discover -s tools/tests -v
新私有replay.py带-X utf8，仅用旧18帧清单回放当前观察器，使用本轮标题规则准备人工冻结条目，明确OCR来源是人工，记录每张期望/输出/basis/标题guard；不得传文件名或期望槽位到观察器。原geometry结果应保持，标题伪正例红转绿单独留日志。
schema输入不变，机械证明仅两文件改动，复用05E/05ER引用的schema27exit0并写schema-reuse.json，不重跑不相关npm/schema、不生成大分片。所有命令取得最终退出码；失败日志不覆盖，有界修复最多两轮，不自动max。

结束条件：标题反例正确拒绝、无标题不冒充完整页面验证、原几何回放保持、全套适用门禁通过、diff --check干净且只有两文件变化。自动本地提交一次完整交付，不合入main、不推送、不打包、不实机。
回传项目、实际模型/平台/档位、cwd/branch/起止完整SHA/commit、diff/stat、API新增字段/拒绝语义、红绿反例及退出码、回放与人工OCR来源、复用证据与未覆盖范围。总控验收后再安排短复核和单槽接线。
不得Controller/ADB/MuMu/游戏点击，不验证择敌/扣票/胜率。六个大型分片不读入上下文，data/generated只读，根外MutualExclusionAllocator不读写。任何后续执行接线必须另有页面来源核验、稳定帧一致与入页/回页同槽证据；本模块单独通过不代表可安全选车。
