# MA9-05G-防守当前槽选车入口回调

模型：ds-v4.1flash；请求high，平台无独立开关如实记录，不自动max。用户外部全新对话运行，不创建子智能体/对话/worktree。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-scan
branch：lane/duel-scan
完整基点与预期起始HEAD：f9182dac671e19e9e9a0d8a3af3c334df46c9a5d。
主仓库编排文件为最新授权，lane仍留此基点；不checkout/reset/merge，不同步主仓库。收工HEAD应为基点之上的本轮单次提交。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，仅验证A→B→HEAD并复用，禁止重冻。

唯一目标：实现可注入05F select_vehicle_for_slot的真实API形态入口回调，仅从用户已经打开的资格赛当前展开槽进入选车页。代码用真实frame_of/ocr_roi/controller.post_click接口，验证全部用fake context，禁止接真实设备。默认05F choose=False不变。不是五槽导航，不是GUI/Agent接线，不是实机放行。

精确边界：owns=[]；owns_new=[agent/ma9_agent/duel_slot_entry.py, agent/tests/test_duel_slot_entry.py]；owns_generated=[]。
现有观察器/05F/scan/selection_runtime/defense_setup/runtime_action/__init__/旧测试/资源pipeline/interface/schema/lanes/state/生成物一律只读。不得新增依赖、模板、配置或框架。发现必须改旧文件就记录阻塞回总控，不越权。
所有写入限MA9。六个大型multiplayer_loop分片不读，data/generated只读不生成；根外MutualExclusionAllocator不接触。04暂停；不取消正式防守地图顺序和已配置阵容保护。

必读：
E:/hzz/work/MA9/agent/lanes.yaml
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/docs/zh_cn/develop/contract_freeze_draft.md
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
本lane agent/ma9_agent/duel_slot_selection.py及其测试、duel_lineup_slot.py及其证据结构、selection_runtime.py公开frame_of/ocr_roi与现有点击接口、duel_vehicle_runtime.py入口页判据。
本lane assets/resource/pipeline/duel_slot_navigation.json（仅了解现有入口和选车标题，不改、不调用会自动切槽的进入第N赛道任务）。
E:/hzz/work/MA9/MA9-evidence/20260924-05FR-slot-review/{report.md,results.json,probe-results.json}
E:/hzz/work/MA9/MA9-evidence/20260924-native-lineup-title/results.json（真实OCR静态帧，不是动态实机）。

接口与实现约束：
1. 提供enter_defense_slot_selection(context, slot_evidence)->bool，可直接作为05F回调。失败返回False或抛清晰异常由05F捕获；不要返回truthy dict。不引入状态ful全局缓存。不得改写slot_evidence或任何嵌套对象；测试深比较确保不变。account_key不在此伪造账号认证。
2. 先验证证据结构：严格int槽1..5、资格赛、geometry_and_title、title_guard_passed=true、合法1280x720内button box/panel边界等；缺失/坏类型/越界先拒绝，不点击。具体使用字段基于真实05F输出，别自造其不存在的字段。输入证据只供比对，不能当新鲜页面授权。
3. 调用已有observe_stable_lineup_slot(context)默认参数独立取得新的两帧稳定资格赛证据，比较槽号、标题、panel左右、button box与传入证据一致。漂移/挑战/不稳定拒绝，不自动切槽。不要复制观察器算法，不用持久化旧截图替代采样。
4. 点击前再frame_of获取一帧，对同帧调用ocr_roi(LINEUP_TITLE_ROI)及真实observe_lineup_slot，重新核对同槽/同几何/资格赛。随后对该帧的已检测button box读按钮OCR，整串trim后只接受“选择车辆”或“更换车辆”，confidence有限0..1且>=0.90，至少一条可信匹配且框中心确在button box；冲突或看不清拒绝。OCR条目使用真实ocr_roi返回形态，不猜坐标是相对还是绝对，先查实现。必要时加入小纯函数验证，但不做第二套识别框架。
5. 只有以上满足才点击该观测button box的中心一次（坐标取整、须在图像内）。使用context.tasker.controller.post_click(...).wait().succeeded真实API形态；不能以run_task触发含切槽/开赛的长链。失败/异常不重试点击。只允许这一次输入，无滑动/返回/选择车辆详情按钮/开赛。
6. 点击成功不等于已入页。最多6次独立frame_of采样，间隔0.2s（调用次数预算，不承诺墙钟耗时），用公开ocr_roi在现有选车标题ROI (40,60,220,60)读取。严格“车辆选择”整串trim、有限confidence>=0.90，可信框中心在ROI内；两次连续有效才返回True，失败/异常重置连续计数。期间无任何追加点击，耗尽False。尺寸非1280x720拒绝，不拉伸假装适配。由已有scan继续承担完整车库状态核验；本回调不定位车型。
7. 时间窗无法做到截图与点击原子化，如实记录仍需用户实机新鲜帧验证。异常发生在点击之后可能已入页，返回False不宣称“无副作用”；05F的entry_attempted保留事实。不扩充05F载荷、不写磁盘日志；必要诊断交报告。

验证：只用fake controller、内存帧、OCR依赖stub；必须包含真实observe_lineup_slot处理合成帧，不mock新回调返回值自证。可复用05F测试夹具只读导入（-B），不执行旧证据脚本main。
- 1..5槽正常流程；未选/已选按钮文字；输入证据深结构不变；点击中心与顺序明确。
- 非法证据不点击；旧槽证据与当前槽不同、几何变动、挑战、geometry_only、低置信/多标题/空白均拒绝。
- 最后一帧变槽/按钮改变不点击；按钮文本错误、低置信、越ROI、NaN/Inf/bool置信度不放行。
- 仅一次点击，失败/异常无补点；一帧选车标题不算成功，间隔坏帧重置，6次耗尽停止。
- 与真实05F select_vehicle_for_slot组合：入口False不scan；成功choose=False只定位详情、starts_race=false；按需stub旧scan，不接设备。
- 不要把“真实API形态fake context通过”写成真实点击或实机通过。现有库接口以现场为准，发现矛盾停止报告，不临时改契约。

环境/命令：Python优先MA9_PYTHON否则E:/hzz/work/MA9/.venv/Scripts/python.exe，检查存在与-X utf8 -B --version；缺失停止不换PATH。所有Python -X utf8 -B，PYTHONDONTWRITEBYTECODE=1，cwd本lane；TMPDIR/TMP/TEMP统一本轮证据tmp并实测gettempdir。不得从main导入lane代码。
证据新目录E:/hzz/work/MA9/MA9-evidence/20260924-05G-slot-entry/，已存在停止不上覆。允许report.md、results.json、targeted.log、slot-regression.log、agent.log、tools.log、schema-reuse.json及tmp/小夹具。失败日志另名保留，长进程等待最终退出码。
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_slot_entry.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_slot_selection.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -v
& $lanePython -X utf8 -B -m unittest discover -s tools/tests -v
基线Agent216、tools30(29+1既有skip)。新总数据日志报告，不增加skip。schema机械确认差异只有两新Python文件后复用05F-orchestrator所引27项exit0，明确未重跑；不npm/构建/生成资源。
Git仅命令级-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-scan，开工/收工核对status、branch、完整HEAD、祖先和精确diff边界。修复最多两轮，仍失败带证据回总控。
结束：适用门禁通过、仅两新文件、无设备操作，自动本地提交自己的两文件；不合入main、不推送、不打包、不启动GUI/ADB/MuMu。回传项目、模型实际标签/平台/档位、cwd/branch、完整起止SHA、diff、API、最大采样/点击预算、命令最终退出码与数量、证据、未覆盖范围。下一阶段仍须独立复核及总控账号数据根/GUI接线，不能自行放行用户实机。
