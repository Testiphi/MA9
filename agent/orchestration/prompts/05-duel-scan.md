# MA9-05F-防守单槽选车薄适配

模型：ds-v4.1flash / high。平台没有独立档位开关如实注明，不自动max；用户外部全新对话运行，不依赖旧聊天，不创建子智能体/对话/worktree。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-scan
branch：lane/duel-scan
完整基点与预期起始HEAD：fd35979cdd4c9f708892f8b076f8a2b0d2bf33fc。
总控已创建并快进干净工作区。本提交已登记两个新增文件；不要回到17371c9，不自行checkout/reset/merge。main后续编排提交不要求你合并。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，核对祖先复用，不重新冻结。

任务：新增防守测试环境的单槽薄适配。开始时用户/调用方已经打开所需槽位的资格赛阵容页；本模块验证稳定槽位，调用外部注入的入页适配，再复用已有scan定位/可选赋值；赋值后验证返回同一槽位。默认只定位到详情，禁止默认选择。不要实现多槽循环、地图识别或从主页导航。
本轮只是代码与离线fake-context验证，绝不能连接真实游戏。独立复核后才由总控绑定测试账号数据根、GUI/Agent入口并产出用户测试包。

必读：
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/agent/lanes.yaml（05 owns_new，contract/06/07只读边界）
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
E:/hzz/work/MA9/MA9-evidence/20260924-native-lineup-title/results.json（真实MaaFW原生OCR静态18/18；不是无OCR环境）
E:/hzz/work/MA9/MA9-evidence/20260924-lineup-observer-integration/results.json
本cwd下agent/ma9_agent/duel_lineup_slot.py、duel_vehicle_runtime.py、selection_runtime.py的公开frame_of/ocr_roi、vehicle_screen.py的匹配返回结构，以及相应现有测试（只读）。

精确边界：
owns: []
owns_new:
- agent/ma9_agent/duel_slot_selection.py
- agent/tests/test_duel_slot_selection.py
owns_generated: []
已有文件一律只读。不得改观察器、旧scan/assign_visible/defense_setup、runtime_action、__init__、旧测试、pipeline、interface、schema、lanes/state、配置或生成物；不新增依赖/模板/GUI任务，不复制账号图进Git。发现必须改旧模块就保存最小阻塞回总控。

设计只保留小型稳定观察helper和一个单槽流程函数，不做通用插件/状态机框架。公开API名称和request类型由你选清晰最小形式，docstring说明。

一、输入与动作边界
- request包含expected_slot(严格int1..5)、target_id、vehicle_class、choose(严格bool，默认False)、account_key(非空追踪标签)；catalog与confirmed_owned_ids显式由调用方传入。可传expected_performance、expected_stars、page_hint、max_pages，沿用旧scan的合法范围。
- 在任何截图/入口/scan调用之前验证请求：车型在catalog且等级匹配、目标在confirmed_owned_ids、参数类型/范围正确。错误ValueError，不能先点击后报错。account_key仅追踪标签，不冒充已验证游戏账号；实际账号/数据根绑定由后续总控测试入口保障。本模块不读任何config/garage文件。
- enter_selection是必需的外部回调，接收context和刚确认的槽位证据，明确返回bool；无回调/返回False或异常则停止，不调用scan。模块不写防守导航节点名，不直接调用run_task或post_click/post_swipe；入页动作只经此回调，选车页动作只经既有scan。回调不是此次要实现的真实入口。
- 此版只允许资格赛防守测试页（page_title='资格赛'），读到'挑战'应明确unsupported_environment并停止，不按已有slot1进攻样本放行。后续推广进攻另行验收；共有选车核心保持不含地图名。

二、稳定前置槽位观察
- 每个采样独立调用公开frame_of(context)，再对同一帧用ocr_roi(...,LINEUP_TITLE_ROI)取得真实接口形态条目，送observe_lineup_slot(frame,ocr=...)。不传预期slot给观察器、不用人工标题常量填充生产路径。
- 必须连续两次有效且相同：page_title、expanded_slot、panel左右边界、按钮box一致；同时slot_verified=true、title_guard_passed=true、verification_basis=geometry_and_title。任何无效或变化重置连续计数，不能从geometry_only放行。
- 最多4次采样，间隔0.2s即可（测试patch sleep）；这是调用次数预算，不保证实机总秒数。耗尽返回lineup_unstable等清晰停止状态，无入口/scan调用，不默认slot1。
- 稳定槽位不等于expected_slot时返回slot_mismatch，不进入别槽；模块不尝试切槽纠正。前置证据每次调用重新获得，不接受持久化旧token作为当前证明。

三、复用选车页能力
- 前置满足后仅调用enter_selection一次；成功后调用duel_vehicle_runtime.scan(context,vehicle_class,catalog,target_id=...,choose=...,max_pages=...,expected_performance=...,expected_stars=...,page_hint=...)。不得自写第二套OCR/滚动定位算法，不包一层无界重试；已有scan内的有界恢复保持。
- choose=False：只接受目标的detail_verified结果，保留原详细证据，assignment_complete=false；停在详情页，不点击选择、不自动返回；不能写assigned。扫描失败/车型不符/占用等原始结果保持可追溯，不能伪装成功。
- choose=True：只有scan报告status='assigned'、assignment_complete=true，且其detail_vehicle/selected_card等车型证据指向请求目标，才进入后置观察。不能仅凭一个字符串assigned报成功。

四、返回同槽核验
- 选择后重新独立采样阵容页，仍用上述两次一致规则和资格赛页守卫，不能复用前置截图/报告。
- 后置slot必须同时等于前置slot和expected_slot；不稳定、错误页、错误槽或异常时返回assignment_unverified，并保留原scan_report，明确selection_attempted=true/可能已发生选车，不能谎称没有副作用，也不能继续下一槽。
- 只有已有目标车型核验与后置同槽证据全满足，才返回status='assigned'、assignment_complete=true。starts_race在任何输出均false，无开始比赛动作。
- report包含account_key、request摘要、before/after证据、scan_report、entry_attempted/selection_attempted与清晰status/reason；无图像数组写盘，无文件/网络读取。选择是否真实完成只以已获得证据为限；不宣称实机通过。

明确不做：从主页进入防守、五槽自动轮换、识别地图名、制定进攻/弱车策略、已有阵容直接成功跳过、账号冲突恢复、清阵容、开赛、入组、票券/奖励、默认使用main车库。不得修改正式防守地图顺序/已有阵容保护。普通燃油规则不在此模块新增；进攻不耗普通燃油的用户规则不能无依据扩写成所有模式。

测试（用fake context/注入回调；严禁真实设备）：
1. 1..5五槽稳定两帧：前置/回调/scan/后置顺序可核对，choose参数透传，starts_race=false。
2. 单帧不放行、交替槽位、低置信/geometry_only/多标题/无法定位等不放行；第4次耗尽无入口/scan，后续一次调用不沿用上次计数。
3. 稳定错误槽和进攻页拒绝；无效请求（含未确认拥有）在任何上下文调用前拒绝。
4. entry False/异常不scan；旧scan失败不写assigned；choose=False停详情且无后置赋值宣称。
5. choose=True回正确槽成功；回错槽/不稳定/不匹配车型报告assignment_unverified且保留已尝试事实，不做额外点击/纠正。
6. 不得mock新模块被测流程返回值；可以stub依赖的截图/OCR/旧scan与入口回调。至少有案例让真实observe_lineup_slot处理合成或允许的静态帧，以免只测试伪造slot报告。原188?基线以186实际日志为准，不猜新总数。
7. 旧选车runtime定向测试保持；不得加skip或放宽已有门禁。

证据与命令：
新目录E:/hzz/work/MA9/MA9-evidence/20260924-05F-slot-selection/，已存在停止不覆盖。允许report.md、results.json、targeted.log、runtime-regression.log、agent.log、tools.log、schema-reuse.json及tmp/小夹具。每轮失败另存，不能覆盖红日志。不要执行旧证据脚本的main覆盖输出。
Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；检查存在并-X utf8 --version，缺失停止不换PATH。所有Python-X utf8 -B、cwd本05根；TMPDIR/TMP/TEMP均指向本证据tmp并记录gettempdir；PYTHONDONTWRITEBYTECODE=1，避免只读导入写旧证据cache。不从main导入业务源码。
Git仅-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-scan，开工/收工检查status/branch/完整HEAD/最近3提交/祖先；不改全局设置，不清理用户文件。
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_slot_selection.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_runtime.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -v
& $lanePython -X utf8 -B -m unittest discover -s tools/tests -v
资源/schema/旧校验器不变，机械证明只有两新增文件，schema复用MA9-evidence/20260924-lineup-observer-integration/results.json引用的27项exit0，保存schema-reuse.json，明确未重跑；输入不同则上报。无需npm/真实构建。长进程续等最终退出，失败最多两轮有界修复后返回总控。

结束条件：两新增文件内完成小型适配，所有适用门禁通过，入口真正注入、地图/正式防守规则未动、默认不赋值、前后同槽与错误副作用报告准确。git diff --check干净，自动本地提交一次完整交付，仅暂存自己的文件；不合入main、不推送/打包/发布、不启动真实Controller/ADB/MuMu/游戏。
回传项目、模型实际标签/平台/档位、cwd/branch、起止完整SHA/commit、diff/stat、API、状态表、命令/最终退出码/数量、复用证据与未覆盖范围。总控独立验收后用新上下文短复核，再由总控编写真实入口/账号隔离/用户测试包。不要把fake context通过说成已接实机。
六个大型分片不读入上下文，data/generated只读不生成；根外MutualExclusionAllocator不接触。04暂停。
