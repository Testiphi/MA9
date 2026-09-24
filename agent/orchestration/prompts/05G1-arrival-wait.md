# MA9-05G1-防守入页等待预算窄修复

模型ds-v4.1flash，请求high；平台无独立开关记录实际默认，不自动max。用户外部全新对话，不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整基点/预期起始HEAD cf8815b2268d07142b679b06272101e9f1b2191e；不checkout/reset/merge，不同步main后续编排。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先后复用不重冻。

唯一任务：修复真实入页切换较慢时六次采样过早结束的问题，保持严格连续两帧到达确认和最多一次入口点击。
实机证据：E:/hzz/work/MA9/MA9-evidence/20260924-211053-slot-entry-live/ 下business.snapshot.json、maafw.snapshot.log、error-screen.png、user-screen.png、repro.py、repro.json、repro-red.log、results.json。
实际21:10:59.108单次点击(596,517)；六次到达OCR前五次仍资格赛，21:11:03.768第六次首次车辆选择(score .999930, box52/70/113/33)。business=entry_failed, scan_report=null，车型扫描根本没开始。右侧露出Nevera不是本轮故障原因，不修改车型匹配/滚动/性能分/类导航。
repro额外第七帧是最终真实OCR的合成重复，用来锁定等待行为，不冒充采到第七张实机帧。当前repro断言失败exit1，保留红日志。

精确owns=[agent/ma9_agent/duel_slot_entry.py,agent/tests/test_duel_slot_entry.py]；owns_new=[]；owns_generated=[]。
只允许上述两已有文件。其余包括05F/observer/scan/runtime_action/interface/pipeline/schema/lanes/state/工具全只读。禁止改旧包、配置或原证据，不运行旧repro.py原地覆盖repro.json；复制到本轮并将输出指向本轮，或自行实现等价回归。所有写入MA9内；不读六个大分片，data/generated不生成；根外MutualExclusionAllocator不碰，04暂停。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md；本lane两被改文件完整源码、05F observe_stable_lineup_slot和selection_runtime.frame_of/ocr_roi相关实现；原05G任务及05GR报告只读；上述本次实机证据。

总控窄裁决：
- 只改到达等待，不改前置槽位复核、最后同帧按钮识别、置信度/ROI/整串匹配、单次点击和bool接口。
- 到达等待采用双上限：最多20次采样，并用time.monotonic固定15秒截止（从开始到达等待起算，不因读到第一帧或异常重置截止）。间隔保留0.2秒。每次发起新采样前检查截止，避免超时后开始新采样；单次底层截图/OCR可能阻塞超过截止，必须如实说明非硬墙钟中断，不另加线程或强杀设备调用。
- 仍必须连续两次可信“车辆选择”才True，任何无效/异常重置连续计数，预算耗尽False。不能首帧即成功、不能复用前置/第一帧作第二帧，不能增加点击重试或自动返回。
- 常量/docstring写清新预算；回调总最大采样4+1+20=25（主流程05F前后与scan另计），顺利5。不能声称固定耗时15秒或全部25必执行，时间与次数先到者限制新采样。
- 不增加现场诊断框架或改05F载荷；本轮只修等待+必要回归。

测试必须：
1. 冻结日志五次旧页+一次首次到达，再第七次合成稳定到达 =>旧六预算False、新True，恰一次点击（可测helper与完整入口至少一个组合）。真实OCR条目逐字取证，只stub frame/OCR/时钟/controller，不mock被测函数结果；注明第七帧合成。
2. 第一帧到达后立即预算/时间耗尽=>False；到达/坏帧/到达/到达才True，异常同样重置。
3. 始终非到达页：快时钟场景最多20帧，时间截止场景到期不开始下一帧；边界0/15秒、时间前进与单次读取超时的处理有确定性测试，不真实sleep15秒。
4. 未点击/点击失败不进入等待；至多一次点击，False不谎称无副作用；原5槽/错误槽/按钮门禁/只定位组合不回归。不得为了新预算删除失败场景或加skip。

输出新目录E:/hzz/work/MA9/MA9-evidence/20260924-05G1-arrival-wait/，已存在停止；允许report.md、results.json、red.log、green.log、targeted.log、slot-regression.log、agent.log、tools.log、schema-reuse.json与tmp/小夹具。原证据保持。
Python MA9_PYTHON优先否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止；全部-X utf8 -B，PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP均本轮tmp并测gettempdir，cwd lane，不从main导入源码。
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_slot_entry.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_slot_selection.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -v
& $lanePython -X utf8 -B -m unittest discover -s tools/tests -v
基线Agent252、entry26、slot30、tools30（lane截图差异可有既有skip，如实记录）。每条取最终进程exit，不用OK代替；出现exit21保存日志报告，不吞错误。schema输入无变则机械复用05H两项新增/变更校验及旧资源历史，不重跑完整27/npm/大分片。
Git仅命令级safe.directory，本lane起止branch/HEAD/status与diff --check留档。最多两轮有界修复；成功后自动本地提交仅两授权文件，不合入/推送/构建/发布。不启动GUI/ADB/MuMu/真实Controller/游戏；实机由用户后续串行做。
回传完整起止SHA、模型平台实际档位、精准diff、红绿证据、计数与最终exit、两个预算和守卫保持情况、未覆盖。修复不等于新包已验证或实机成功；总控验收后再安排窄复核/新包，不让用户重复跑旧包。
