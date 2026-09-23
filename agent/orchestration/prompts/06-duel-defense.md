# MA9-06A-防守配置剩余门禁审计

模型：ds-v4.1flash / high。用户新建外部对话粘贴本文件；你是06的只读审计执行者。不得创建对话、子智能体或worktree，不依赖旧聊天。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-defense
branch：lane/duel-defense
完整基点与预期起止HEAD：550c01dc95af0e5bc2cb16f8ccc70b316b88980d。
总控已创建worktree，不自行checkout/merge/reset。主仓库编排文件是当前权威，main后续可能仅有提示词/状态提交，以现场为准。

依赖已满足：05 f5472bce3443fde42df17ad8a1819e18b46a2059经独立复核与用户D级实机后，在f36f3b23db952aae67e2583f9e74ae965fa6fa65合入；根隔离a7d9910cc945072efbf6ccb9b3d38f4f949a6e87在380b051afceac70af1f31471c0339de071a076ce合入。组合Agent105、tools29均通过exit0，schema输入等价复用27项exit0。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00，B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5；检查祖先并复用，不重新冻结。
总控已在550c01d明确归还duel_defense_setup.py和其测试给06；本次仍只读，不因owner归还就擅自改代码。

本次目标：对现有“防守五车配置、停阵容、不开始比赛”阶段出具剩余门禁清单及最小下一步建议，判断哪些事实已完成、哪些只有离线证据、哪些真有复现缺陷。不要重写已成功D级流程，不把完整五场比赛驾驶偷换为本次配置阶段验收，也不宣称完整日常擂台闭环已完成。

必读（主仓库绝对路径）：
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/agent/lanes.yaml（06/05/07与契约边界）
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
证据：
E:/hzz/work/MA9/MA9-evidence/20260923-091020-D-five-assigned/acceptance.json及四份业务JSON
E:/hzz/work/MA9/MA9-evidence/20260923-combined-integration/results.json
E:/hzz/work/MA9/MA9-evidence/20260923-02R-root-review/report.md（根隔离只读背景，不重审）
本cwd源码：agent/ma9_agent/duel_defense_setup.py、agent/tests/test_duel_defense_setup.py、agent/ma9_agent/duel_map_screen.py、assets/resource/pipeline/duel_defense.json、docs/zh_cn/develop/duel_daily_model.md；按需只读duel_vehicle_runtime.py及duel_selection.py的调用边界。不得从main导入业务源码。

精确本次写入边界：owns=[]、owns_new=[]、owns_generated=[]；不修改任何受控源码、测试、文档、状态。06名下5文件仅供审查，写入任务须等总控下一份独立提示词。
允许新建的私有输出：E:/hzz/work/MA9/MA9-evidence/20260923-06A-defense-audit/下report.md、results.json、defense-tests.log及tmp/小夹具。目录已存在停止报告，不覆盖历史。所有写入只在MA9内，不接触根外MutualExclusionAllocator。runtime_action、五契约模块、schema、assets/interface.json只读。
六个大型multiplayer_loop分片不读入上下文，不运行生成器；data/generated只读。第三方赛道策略可永久缺失，04暂停不启动。

具体检查与输出：
1. 以当前代码和证据建立简短矩阵：D级五车互斥/状态/停阵容；已配置阵容保留；中途断点恢复；地图顺序变更；识别不足/选车失败的有界停止；R/S/A/B/C降级与不足五车；账号冲突最多一次恢复和错误链。
2. 每项写“实机已证/仅离线/尚无证据/有可复现缺陷”，给代码或测试行号、证据路径。D级实机449.013秒有效，不能推广其他等级、账号恢复或新标记包。日志业务JSON在主仓库debug是无标记旧规则导致，已冻结在证据目录，不误读动态debug旧文件。
3. 若发现缺陷，给最小复现和严重程度、所属lane；只建议最小修复，不改代码、不取消互斥/等级/排序/身份/占用校验。07缺读数与排序矛盾共用错误消息仍归07；根隔离低优先级文档/测试建议归02/总控，不纳入06修复。
4. 只建议一个最有价值的下一步：关闭当前06配置阶段并准备07只读规划，或一个有证据的06窄修复/必要用户测试。给理由与可验收结束条件，不为假设要求用户重跑已通过D级或大规模截图。

运行：Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；验证存在与-X utf8 --version，找不到停止，不换PATH。TMPDIR/TMP/TEMP同时指向本证据tmp并记录实际tempfile.gettempdir。所有Python命令-X utf8，cwd必须为06 worktree。
开工和收工核对git status --short、branch、完整HEAD；Git只用-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-defense，不改全局设置，不清理其他改动。
最低针对性验证：
& $lanePython -X utf8 -m unittest discover -s agent/tests -p test_duel_defense_setup.py -v
记录最终退出码/数量，长命令续等。全量Agent/tools/schema已有组合证据，本只读审计不重复跑，不声称独立重跑。需要小夹具复现仅写证据tmp；不得启动GUI、ADB/MuMu、游戏或调用真实设备。

结束条件：针对性测试退出码可核实、矩阵和一个最小下一步建议完整、工作区保持干净。回传项目名、模型实际标签/平台/档位、cwd/branch/起止完整SHA、命令/退出码/数量、结论、发现行号/复现、证据路径、剩余风险。由总控最终决定06是否闭环及07是否放行；本席不自行提交、合并、推送、打包、发布或开赛。
