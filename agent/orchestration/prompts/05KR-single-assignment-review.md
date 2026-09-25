# MA9-05KR-隔离单槽选择接线独立复核

模型登记Qwen3.8-Flash，平台实际默认；无独立high/max开关如实说明，不自证底层身份，不自动max。用户全新带本地工具对话，与总控实现者分离；不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
审查基点50c3cb58940df144bdf463da0984b37787176bff；预期起止HEAD ddcb200c066ae7017d48914e46af0ce242415c37。总控已快进lane，基点..HEAD恰1提交7文件；只审此delta，不把历史快进纳入scope。不checkout/reset/merge。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5，祖先验证复用不重冻。
精确owns=[]、owns_new=[]、owns_generated=[]；所有受控文件只读，包含总控独占runtime_action/interface。不得代修/提交/合入/推送/构建/打包。
唯一输出新目录E:/hzz/work/MA9/MA9-evidence/20260925-05KR-single-assignment-review/，已存在停止不覆盖；允许report.md/results.json/targeted.log/root.log/probe-results.json及tmp小探针。旧证据不改、不运行旧main脚本。所有写入MA9内；禁止GUI/真实Controller/ADB/MuMu/游戏；不读六大分片，data/generated只读，根外MutualExclusionAllocator不碰，04暂停。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md。
本lane七文件diff：agent/ma9_agent/duel_slot_test.py、agent/runtime_action.py、agent/tests/test_duel_slot_test.py、agent/tests/test_runtime_root.py、assets/interface.json、assets/resource/pipeline/duel_slot_test.json、docs/zh_cn/develop/duel_slot_test.md。完整读测试加载器/两个action与新测试；05F/05G调用和后置同槽逻辑只读关联核查，不重复前轮几何与名字算法审查。
证据：E:/hzz/work/MA9/MA9-evidence/20260925-092207-nevera-located/acceptance.json及business.snapshot.json（私有账号标签不可复制进受控文件）；20260925-05K-single-assignment/results.json及日志；20260925-05JR-name-first-review/results.json。

背景：用户612531f包第1槽Nevera定位已实机located/detail_verified、selection_attempted=false/starts_race=false；仅证明定位，未赋值。现推进同账号同槽同车一次选择，不开始比赛、不五槽轮换。用户先前已要求跑通选中任意车；本轮代码可测试通用输入，实机仍限该单槽目标。
核查：
1. 原定位action固定choose=False不变；新增assignment action固定choose=True，两者del argv，GUI参数不能切模式/改请求路径。旧50任务名称/入口/相对顺序不变，只加第51任务；节点next=[]不挂开赛。
2. load_slot_test/run_slot_test choose关键字默认False、严格bool；False只读config/duel_slot_test.json，True只读config/duel_slot_assign_test.json，不存在回退。配置choose须严格等于入口mode，True额外assignment_confirmed is True；缺失/非bool/模式冲突在任何设备调用前拒。旧定位文件不能当赋值授权。
3. 标记/绝对runtime_root/account_confirmed/environment/slot/catalog/owned及resolve防逃逸规则保留。账号标签仍是用户确认，不冒充视觉身份识别；本轮不读garage、不采集整库。
4. 传入SlotSelectionRequest choose按mode正确设置，verify_list_detail_rating仍取05J默认False；明确名字优先不取消详情目标身份/占用/可选按钮/返回同槽。既有select_vehicle_for_slot应真正通过返回同槽才assigned，别仅看stub返回字典判断链路已安全。
5. assignment action只有status=assigned AND assignment_complete is True AND starts_race is False才True；located/assignment_unverified/缺标志/错误标志一律False。业务JSON仍保存before/after/target/request/尝试事实；失败不补点、不下一槽，不把GUI完成当业务验收。
6. 这次只做入口接线，旧scan/返回页等待未改变。真实慢加载返回是否足够仍待实机，不因本轮通过宣称全面鲁棒性。可记录真实可达缺陷，但不得代修或扩大五槽/地图/04范围。

独立执行：Python优先MA9_PYTHON否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止；全部-X utf8 -B、PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP同设本证据tmp并实测；cwd lane不从main导入业务。
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_slot_test.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_runtime_root.py -v
预期16和10，最终exit真实记录。独立少量带机器断言探针至少覆盖模式隔离/缺确认前置拒绝/成功判据，以及真实05F chooseTrue后置错误槽无法assigned（stub设备边界允许，不mock被测入口返回值自证）。不接设备、不真实截图。
总控同代码Agent291/tools30 exit0与两项变化schema校验已完成，查日志后明确复用不再全套。schema旧未变资源历史复用，不能说全27重跑。Git命令级safe.directory，记录起止status/branch/完整HEAD/祖先/7文件边界。
结束回传项目/模型平台实际档位/cwd分支/完整起止SHA/有无阻塞与严重性行号/最小复现/命令最终exit计数/独立与复用/证据路径/未覆盖。没有阻塞也不宣布实机或包就绪，后续总控才准确打包和绑定独立赋值配置，由用户串行测试。
