# MA9-05MR-既有阵容只读核验入口独立复核

模型登记Qwen3.8-Flash，平台实际默认；无独立high/max开关如实记录，不自证底层身份，不自动max。用户全新带本地工具对话，与总控实现者分离，不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整基点d9314f0714f3a64e55dcc8aa3aac5bbe299660b8；预期起止HEAD ff426c671cc23aef207b5f187db2de1105ac9ea7。总控已快进，基点..HEAD恰1提交8文件。只审本delta，不checkout/reset/merge，不同步main新编排。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先复用不重冻。
精确owns=[]、owns_new=[]、owns_generated=[]；所有受控文件只读（含总控独占runtime_action/interface），不代修/提交/合入/推送/构建。
唯一私有新目录E:/hzz/work/MA9/MA9-evidence/20260925-05MR-readonly-lineup-review/，已存在停止不覆盖；允许report.md/results.json/targeted.log/root.log/probe-results.json及tmp小探针。禁止覆盖旧证据或运行旧脚本main。全部写入MA9内，不设备/GUI/Controller/ADB/MuMu，不读六大分片，data/generated只读，根外MutualExclusionAllocator不碰，04暂停。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md。
本lane八文件delta：duel_slot_verify.py、新测试test_duel_slot_verify.py、runtime_action.py新增DuelSlotVerifyAction、test_runtime_root.py、assets/interface.json、pipeline/duel_slot_test.json、docs/zh_cn/develop/duel_slot_test.md、agent/lanes.yaml。完整读新模块/新测试，关联只读load_slot_test/_inside、05L _lineup_identity及observer契约；不重复先前算法全面复核。
证据E:/hzz/work/MA9/MA9-evidence/20260925-05M-readonly-lineup/{results.json,targeted.log,agent.log,tools.log,schema.log}、20260925-05LR-lineup-identity-review/results.json、20260925-095331-assignment-postcheck/results.json。

背景：用户已将Nevera实际放入第1槽，不应为程序后置确认缺口清空重选。新入口只读取当前阵容，用两个独立稳定样本确认期望槽号/车型。不得把本次只读观察冒充旧运行assigned或修订历史失败JSON。

重点：
1. GUI只新增第52项，旧51任务顺序/名称/入口不变；DirectHit Custom ma9_duel_slot_verify、next=[]。action del argv，参数不能切到选择/改请求路径。
2. verify_current_slot只调用配置读取、frame_of、ocr_roi、observer、已审_lineup_identity及本地报告写盘；不调用scan/select_vehicle_for_slot/enter_selection/run_task/post_click/swipe/返回/开始。共享导入模块含动作函数不等于调用，需按真实调用链核查。不要求“没有任何Controller引用”这种会禁止截图的伪安全测试。
3. 复用隔离根duel_slot_assign_test.json仅作期望来源（load choose=True读取既有配置），不执行request.choose。标记/绝对根/用户确认/目标拥有/输出resolve防逃逸保持，错误配置在任何capture前失败。账号标签仍用户确认而非视觉身份认证。
4. 每帧同frame OCR资格赛标题+真实observer，必须slot_verified/title_guard_passed/geometry_and_title/资格赛；再在同帧读独立车型并比较panel。expected_slot/target只在观察完成后比较，不输入observer或过滤OCR。两次连续标题/槽/车/panel左右/buttonbox完全相同才通过；坏帧、异常、变化必须清零。
5. 上限120次、monotonic固定30秒、间隔.3；时间到不发起新采样，不宣称底层截图硬中断；异常记录观察条目不重复点击或继续动作。读取新鲜性只能依赖frame_of每次请求，fake/static不等于设备动态通过。
6. status=lineup_verified和configuration_verified=true只证明当前观察匹配；read_only=true、selection_attempted=false、assignment_complete=false、starts_race=false必须保持，另写duel-slot-verification-uuid.json，不覆盖旧duel-slot-test JSON或倒改历史。action必须依真实业务字段成功而非仅字符串/任务结束。
7. 名字与版式的05L限制继续保留，真实有名slot2..5未验证；本轮不增加或删除名称/评分/占用/选择门禁。只读状态确认不是全套赋值流程实机通过。

独立测试：Python优先MA9_PYTHON否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止；所有-X utf8 -B、PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP同设本证据tmp并实测，cwd lane不从main导入业务源码。
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_slot_verify.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_runtime_root.py -v
预期9和10，保存真实最终exit。独立少量机器断言探针至少覆盖错误槽/车/标题拒绝、单帧拒绝、异常打断连续计数、两个真实不同frame对象同帧OCR链、输入方法全部拒绝仍可正常核验、输出历史不被覆盖。不得mock被测函数返回值自证，可stub设备边界/时钟/OCR并使用真实observer/helper。
总控Agent308/tools30及两变化schema已exit0，查日志明确复用不重跑。schema未变资源历史复用，非完整27重跑。Git仅命令级safe.directory，起止status/branch/完整HEAD/祖先/8文件边界留档。

结束回传项目/模型实际平台档位/cwd/完整起止SHA/有无阻塞/严重性行号可达前提与复现/独立最终exit计数与复用/证据路径/未覆盖。无阻塞只允许总控准备准确只读包；不要让用户再次选择或清空阵容、不宣布实机通过、不代修。
