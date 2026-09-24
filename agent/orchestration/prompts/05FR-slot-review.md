# MA9-05FR-防守单槽薄适配独立复核

状态：总控离线验收通过，等待本轮独立只读复核；不代表真实入口或实机放行。
模型登记标签：Qwen3.8-Flash；档位按平台实际默认记录，无独立开关就如实说明，不编造high/max或底层身份自证。用户在带本地文件工具的全新对话粘贴本提示词，与ds-v4.1flash owner分离。禁止创建子智能体、对话或worktree。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-scan
branch：lane/duel-scan
完整审查基点：fd35979cdd4c9f708892f8b076f8a2b0d2bf33fc
预期起止HEAD：f9182dac671e19e9e9a0d8a3af3c334df46c9a5d
差区间仅一提交、两个新增文件，主仓库后续编排提交不要求同步，不checkout/reset/merge。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证A→B→HEAD祖先后复用，禁止重新冻结。

精确边界：owns=[]；owns_new=[]；owns_generated=[]。全部受控文件只读，不代修、不提交、不合入或推送。
唯一可新增私有输出：E:/hzz/work/MA9/MA9-evidence/20260924-05FR-slot-review/ 下 report.md、results.json、targeted.log、runtime.log、probe-results.json、tmp/小型只读探针。该目录若已存在，停止上报，不覆盖。所有写入限MA9内，旧证据不可改；不要执行旧证据脚本main。禁止安装依赖、构建、GUI、真实Controller/ADB/MuMu/游戏及任何设备输入。不读六个大型multiplayer_loop分片；data/generated只读；根外MutualExclusionAllocator不接触。04暂停。

必读（主仓库编排为权威，业务源码必须读本lane）：
- E:/hzz/work/MA9/agent/lanes.yaml
- E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
- E:/hzz/work/MA9/docs/zh_cn/develop/contract_freeze_draft.md
- E:/hzz/work/MA9/agent/orchestration/state.json
- E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
- E:/hzz/work/MA9/agent/orchestration/prompts/05-duel-scan.md（05F原任务规范）
- 本lane agent/ma9_agent/duel_slot_selection.py 与 agent/tests/test_duel_slot_selection.py 全文及对应diff
- 本lane duel_lineup_slot.py、duel_vehicle_runtime.py及selection_runtime.py相关公开接口与返回结构
- E:/hzz/work/MA9/MA9-evidence/20260924-05F-slot-selection/{report.md,results.json,schema-reuse.json}
- E:/hzz/work/MA9/MA9-evidence/20260924-05F-orchestrator/{results.json,process-results.json}
- E:/hzz/work/MA9/MA9-evidence/20260924-native-lineup-title/results.json（历史18帧真实MaaFW静态OCR，不是设备动态验证）

目标：独立判断此模块能否作为防守单槽薄适配进入下一阶段真实入口开发，不是批准实机。用户已打开资格赛目标槽；expected_slot只作独立观察后的比较，不导航、不读地图名、不自动选五槽。默认choose=False只定位详情。account_key只是追踪标签，账号/数据根绑定尚未实现。

重点核查：
1. 请求/车型/等级/确认拥有/参数非法是否在任何frame/entry/scan前拒绝；expected_slot严格int1..5，choose严格bool。区分正常调用支持的输入与恶意依赖伪造，不为假设扩大范围。
2. 每次frame_of后同帧ocr_roi→真实observe_lineup_slot；不能人工填标题、传预期slot或放行geometry_only。连续两帧标题、槽位、panel边界和button box一致；无效样本/变化重置，默认最多4次；挑战页拒绝，错误槽不入页。独立调用不能借前轮计数。
3. 入口只能注入回调，最多调用一次；缺失/非True/异常不得scan。确认入口尝试与选择尝试两字段语义：entry失败时entry_attempted可为true，selection_attempted仍false。owner旧报告若写反，作为文字更正，勿修改旧报告。
4. scan精确透传且不重写滚动/OCR/正式防守保护。choose=False仅接受目标detail_verified，assignment_complete=false且无后置赋值宣称。choose=True只有scan的assigned+complete+车型证据，再观察返回同一资格赛槽，才assigned。错误页/槽/不稳定保留scan与selection_attempted，不纠正/继续下一槽。
5. starts_race恒false在本模块约束内；任意外部回调行为不受本模块形式保证，未来真实回调必须另审。两次调用不等于设备已提供两张新鲜帧；fake-context通过不证明真实时序。
6. 三个需独立定级的观察点：公开observe_stable_lineup_slot可传attempts/interval而未验证，主流程固定默认；_points_to_target只要求detail_vehicle或selected_card至少一条一致，核对真实scan可达形态；传给回调的before证据对象与输出共享，评估正常回调误改的证据影响。写明确复现、调用前提、是否影响当前主流程，勿把伪造scan结果自动当作生产可达漏洞。若发现真实违反任务最大预算等要求，明确列出，不因总控初验通过而忽略。
7. 比较测试与规范，不能只运行测试给结论；至少自建少量可复核反例/边界探针。可stub frame/OCR/scan/entry并让真实观察器处理合成帧；不得mock被测流程结果。不要接真实设备，不需重做05E几何/标题识别审查。

验证环境：MA9_PYTHON优先，否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止。所有Python均-X utf8 -B，PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP同设本轮证据tmp，实际gettempdir记录。cwd必须本lane，不从main导入业务源码。Git仅-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-scan；开工收工记录branch/status/完整HEAD/祖先/两文件diff边界，不改全局设置。
最低独立命令（$lanePython为上述已验证解释器）：
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_slot_selection.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_runtime.py -v
保存最终进程退出码，预期30与14通过；超时必须续等不能拿日志OK替最终退出。
Agent216、tools30(29通过+1既有跳过)均已由总控在f9182da独立跑完exit0，核查日志后明确复用，不重复全套。schema复用历史27exit0，两新增Python文件不改schema输入，不重跑npm/schema、不生成分片。

结束条件：完成独立代码审读、两条定向命令和少量边界探针，HEAD与受控工作区保持原状，输出有/无阻塞与逐项问题、证据来源、未覆盖范围。不宣布合入、真实入口就绪或实机通过，不代修。
回传：项目/登记模型与实际平台档位/cwd/branch/完整起止SHA/契约与边界/命令最终退出码和计数/问题分级与文件行号和最小复现/复用与独立实跑区分/证据路径/剩余接线前置条件。
