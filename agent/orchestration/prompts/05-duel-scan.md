# MA9-05E-阵容页槽位只读观察（选车入口解耦第一步）

模型：ds-v4.1flash / high。用户在外部平台全新对话粘贴完整提示词；平台无独立档位开关如实记录，不自动max，不创建子智能体/对话/worktree。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-scan
branch：lane/duel-scan
完整基点与预期起始HEAD：02ee41c239bf45734ba3fa5ee44dc9dc7889ec5c。
总控已从干净f5472bc快进到此基点；保留历史测试包和证据，不能用旧f5472bc起步或重建旧包。不checkout/reset/merge，现场不符报告。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先复用，不重新冻结。

用户目标：推广选车页功能与鲁棒性，不长期占用有时效的进攻页面；未来先用不进组测试号防守页验证共用选车，隔离防守进入选车的入口，只保留第几图/槽位判断，进攻地图名称后接。
本次只做第一块：从已打开的五槽阵容截图，可靠读出唯一展开槽位1..5。不点击、不进入选车、不分配车辆、不接地图名称或策略，也不改旧运行路径。

为什么先做：现有duel_vehicle_runtime.scan/assign_visible已基本独立于入口；_finish_target选择后只看车型和“更换车辆”而不看槽位。选车页本身无可靠1..5编号，需要外层在入页前保存槽位上下文、回阵容后复核。defense_setup._current_unselected_slot失败默认1的旧行为不能复用为新观察器的证据。

必读：
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/agent/lanes.yaml（05新增文件与总控/06/07边界）
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
E:/hzz/work/MA9/MA9-evidence/20260923-184330-attack-mumu-intake/manifest.json
本cwd的agent/ma9_agent/duel_vehicle_runtime.py（选车与选择后核验）、duel_defense_setup.py（只读_current_unselected_slot）、assets/resource/pipeline/duel_slot_navigation.json（仅只读几何/识别条件，不执行节点）、agent/tests/test_duel_vehicle_runtime.py。

精确边界：
owns: []
owns_new:
- agent/ma9_agent/duel_lineup_slot.py
- agent/tests/test_duel_lineup_slot.py
owns_generated: []
只有这两文件可新增；已存在则停止报告。原runtime、screen、defense_setup、旧测试、pipeline、interface、契约、schema、编排文档全部只读。不得新增模板资产/修改生成物/注册Agent入口/改GUI任务。不复制账号图片进受控测试夹具，不安装依赖。

功能要求：
- 新模块为纯只读观察器，可接收1280x720图像及规范化OCR条目（如需要；OCR执行留外层）。不得收“预期槽位”后直接回显，必须从页面布局/观察证据判定。
- 输出至少含page识别状态、expanded_slot(int1..5或None)、可解释reason与slot_verified。可以给出展开区几何供未来核验使用，但不要设计整个导航框架。
- 确认是五槽阵容页且唯一展开位置时才返回槽位；看不清、遮挡、多个候选、非阵容页均slot=None/slot_verified=false。绝不能失败默认1、按地图名猜槽、把选车页标题当槽号。
- 地图名、对手昵称、GP、票数、巴掌、车型不参与“第几槽”的身份定义。不得要求读取赛道参考表、不得调用plan_attack/弱车策略。
- 可用页面标题（资格赛/挑战）和可见五槽结构等作为页面守卫，但不能仅靠某个绿色按钮推断槽位；大厅、车辆详情、选车列表、对手信息弹窗均必须拒绝。
- 以几何/展开位置表达槽位；参考现有静态识别条件时剥离入口动作及“防守专属标题”依赖，不直接运行带Click的pipeline。
- 当前无设备动作：不创建真实Controller、不连接ADB、不调用scan/assign_visible、不点击Start/选择/完成；本模块不读取文件/账号root，不写日志，调用方负责。
- 明确支持尺寸与失败语义；不得将非16:9截图静默拉伸。输入不变、重复调用确定、无隐式全局会话状态。不要同时重写旧05/06/07。

固定样本与期望（原文件只读）：
新MuMu快照目录E:/hzz/work/MA9/MA9-evidence/20260923-184330-attack-mumu-intake/
正例：06进入挑战后的五槽界面尚未选车.png、09五辆车全部配置完成自动选车无策略.png，均展开第1槽。
反例：该目录01大厅、02三档对手、03/04/05对手信息弹窗、07两张选车列表、08三张车辆详情；均不得返回任何阵容展开槽。
旧防守正例位于E:/hzz/work/MA9/captures/：
多人游戏_对决_资格赛_防守_第1赛道展开_已选车_可开始.png
多人游戏_对决_资格赛_防守_第2赛道展开_未选车.png
多人游戏_对决_资格赛_防守_第3赛道展开_未选车.png
多人游戏_对决_资格赛_防守_第4赛道展开_未选车.png
多人游戏_对决_资格赛_防守_第5赛道展开_未选车.png
分别预期1/2/3/4/5，先核对图片实际内容/尺寸。不要按文件名写if返回答案，文件名不传给观察器。
实际图片回放须记录所用OCR的来源：真实离线OCR或人工冻结条目。若只能用人工OCR条目，明确只证明布局解析，不宣称完整OCR通过。可参考tools/check_daily_navigation.py或既有私有离线探针，但不得原样执行会覆盖旧证据或调用设备的脚本。
当前缺进攻2–5展开样本，不能把防守正例当进攻全槽实机通过；输出报告准确限定覆盖。测试需含不确定/遮挡/非阵容等拒绝案例，不能靠无条件返回1让当前两正例过。

测试与证据：
生产新模块+测试放上述两个文件。受控测试用小型合成输入/脱敏数值断言验证逻辑，不提交账号原图。真实截图回放在新私有证据目录E:/hzz/work/MA9/MA9-evidence/20260924-05E-lineup-slot/，允许report.md、results.json、replay.py、replay-results.json、targeted.log、agent.log、tools.log、schema-reuse.json及tmp/；目录存在停止报告，不覆盖旧记录。
Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；先检查存在并-X utf8 --version，缺失停止不换PATH。所有Python-X utf8、cwd为本05根，不从main导入业务源码（只读主仓库图片不等于源码导入）。TMPDIR/TMP/TEMP三者设为本证据tmp，记录实际tempfile.gettempdir。
Git仅-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-scan；开工/结束核对status、branch、完整HEAD、最近3提交，不改全局设置、不清理用户captures/.workbuddy/旧包。

验收命令（$lanePython为解析路径）：
& $lanePython -X utf8 -m unittest discover -s agent/tests -p test_duel_lineup_slot.py -v
& $lanePython -X utf8 -m unittest discover -s agent/tests -v
& $lanePython -X utf8 -m unittest discover -s tools/tests -v
真实回放replay.py也带-X utf8，cwd本lane，记录观察器输出、实际期望和最终退出码。把原图与人工真值输入是否参与OCR明确区分。
schema输入应不变，机械核对相对基点仅新增两文件，保存schema-reuse.json，复用MA9-evidence/20260923-07-integration/results.json引用的27项exit0。不重跑无变化schema/npm、不重建大分片。输入变化则不得复用，应先上报。
全套测试最终退出码必须获得，长命令续等；失败最多两轮有界修复，不自动升max。若发现单靠现有截图无法可靠判断，给最小反例与缺哪种画面，不硬凑通过。

结束条件：所有适用测试通过，真实样本回放与拒绝场景有证据、覆盖如实限定、只有两个新增文件、git diff --check干净。按用户政策自动本地提交，不合入main、不推送、不打包、不实机。
回传项目、实际模型/平台/档位、cwd/branch、起止完整SHA/commit、diff/stat、API与拒绝语义、验证命令/退出码/数量、每张私有样本的输出、OCR来源、复用证据和剩余风险。总控验收后再决定单槽执行入口接线；不得自行取消正式防守的地图顺序/已有阵容保护。
六个大型multiplayer_loop分片不读入上下文，data/generated只读，根外MutualExclusionAllocator不读写。04暂停。此任务不验证择敌、扣票、三胜结算或胜率。
