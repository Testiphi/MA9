# MA9-07R-离线进攻状态决策独立复核

模型：Qwen3.7-Max；档位：平台默认思考设置（实际可用档位如实记录）。Max是模型名称，不自动选择max推理档，不伪称已切high。你是新的独立只读reviewer，与ds-v4.1flash owner分开；本轮为MA9首次有界Qwen复核试点，不保证与GLM等效。
用户新建外部对话粘贴完整提示词；不得依赖旧聊天、创建下级智能体/对话/worktree，不能代owner改代码。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-attack
branch：lane/duel-attack
预期起止HEAD：be381dbc1488cce4ff9e9c1111e50b40421a489d。
总审查范围：72e32dad93165f3c34dc022096c9222c9a1e0977..be381dbc1488cce4ff9e9c1111e50b40421a489d。
原交付b063f56cf988bf2544362c3d861cc51ecbe6597d曾被总控两条反例阻断；当前修复父提交是b063。必须审整个模块与测试，不只审修复diff。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，核对祖先复用，禁止重冻。main尚未合入本模块。

精确边界：owns=[]、owns_new=[]、owns_generated=[]；所有受控代码、测试、文档、状态只读，不提交。私有输出仅E:/hzz/work/MA9/MA9-evidence/20260923-07R-attack-review/下report.md、results.json、targeted.log、repro.log、attack-regression.log及tmp/小夹具和只读探针。目录存在停止报告，不覆盖历史。
不得接触根外MutualExclusionAllocator，不执行导入生成器，不读取六个大型multiplayer_loop分片；data/generated只读。无GUI/ADB/MuMu/游戏操作权限，不打包/发布/推送/开赛/扣票。

必读：
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/agent/lanes.yaml（主仓库权威，本次Qwen reviewer已登记）
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
先审实际两个文件diff：agent/ma9_agent/duel_attack_session.py、agent/tests/test_duel_attack_session.py；再按需只读既有duel_selection.py接口。
随后看证据：
E:/hzz/work/MA9/MA9-evidence/20260923-07B-orchestrator/{repro.py,repro.log,results.json}
E:/hzz/work/MA9/MA9-evidence/20260923-07B1-contradiction-fix/{report.md,results.json,red.log,green.log,schema-reuse.json}
E:/hzz/work/MA9/MA9-evidence/20260923-07B1-orchestrator/results.json
用户图片事实可读MA9-evidence/20260923-attack-three-win-user-confirmed/manifest.json和20260923-attack-three-win-supplement/manifest.json。本轮只审代码，不要求模型视觉能力，不用非16:9图片推断MuMu坐标。
若平台没有本地文件/命令能力，明确报告复核未完成，不伪称执行；不把无工具聊天当完整本地review。

必须核对的行为：
1. 同一挑战五个唯一slot1..5、win/loss/unplayed/unknown，非法输入拒绝；纯函数无IO/设备/时间/随机状态，输入不变，快照次序与重复调用不影响累计胜场。
2. >=3胜且not_seen只能request_finish_confirmation；>=3胜且确认win且无未知才confirm_finish/early_finish_allowed=true。所有路径starts_race=false、requires_live_verification=true，不声称实际执行完成。
3. 正常s05[loss,win,win,loss,unplayed]+not_seen继续第五局；同快照+确认win是矛盾，必须stop；停止只表示暂停自动推进并保留现场、上报矛盾，绝不是退出/放弃/点击完成或已判负结算。
4. 确认loss优先于未知槽位，立即stop不重读；非判负的未知槽/未知确认有界重读，第三次停止；有效恢复按约定清零预算。
5. plan_attack衔接保持互斥、不可用过滤、limit、缺口与输入不变；候选complete不能变成开赛或已经赢三场语义。零拥有仍显示缺口，不因plans非空而可开始。
6. 无OCR/执行器/生产调用方，未来确认文案严格映射、状态读取与设备验证未完成；不能将人工三胜截图写成Agent实机成功。

特别关注（不预设你的最终判断）：
- 总控两条反例修复前2失败，当前复跑2通过。不要只看“不confirm_finish”，必须检查矛盾时精确stop。
- 当前矛盾分支的注释/reason写“target is out of reach”“challenge already known to be lost”“challenge is settled below the target”。2胜2负尚有第五局时，这些陈述不由输入证明；只知道快照与确认矛盾。请独立评估这是需修正的行为语义输出/文档问题还是非阻塞措辞，给明确理由和最小建议，禁止把stop解释成替用户退出挑战。
- 新owner回传“矛盾stop会终止挑战”也是待纠正的解释，不自动采信。模块没有任何真实退出能力，review应区分函数建议与执行。
- docstring优先级清单与实际分支是否一致，是否存在过强已结算断言；测试断言是否与需求一致而非迁就实现。
- 当前计数基点107+原新增26+修复新增6=139，已经核实；不要再用f5472bc的101或组合105混算。
- owner修复预算已用完：如有阻塞只给最小复现与裁决建议，不自动让owner继续无限修复、不重构分配器。

环境与最低针对性测试：
Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；确认存在并-X utf8 --version，缺失停止，不换PATH。所有Python-X utf8、cwd为07根，不从main导入源码。
TMPDIR/TMP/TEMP同时设本review证据tmp，记录实际tempfile.gettempdir。不清理真实配置、旧包或历史证据，不绕过宿主守卫。
Git开工/结束核对status、branch、完整HEAD、最近3提交与A/B祖先，仅-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-attack，不改全局配置，不checkout/reset/merge。
& $lanePython -X utf8 E:/hzz/work/MA9/MA9-evidence/20260923-07B-orchestrator/repro.py
& $lanePython -X utf8 -m unittest discover -s agent/tests -p test_duel_attack_session.py -v
& $lanePython -X utf8 tools/test_duel_selection.py DuelSelectionTests.test_allocator_uses_distinct_cars_and_best_available_tradeoff DuelSelectionTests.test_unknown_and_empty_tracks_are_reported_without_a_startable_plan DuelSelectionTests.test_same_car_on_every_track_reports_mutual_exclusion_shortage -v
第三条只选3项假数据测试，不运行real_source/生成器。长命令续等最终退出，保存唯一日志，不以进程输出断定成功。
总控已在be381db独立跑反例2、Agent139、旧规划3、tools30（29通过+1既有私有截图跳过），均exit0；额外8192小型状态组合的安全断言通过；schema34项hash相同复用27项exit0。可注明复用，不重跑全量/schema/npm或8192矩阵，除非有新证据需要。

结束条件：全模块/测试/边界复核完成，针对性测试有最终退出码，明确“无阻塞/有阻塞”或“证据不足复核未完成”。每项给文件行号、严重程度、复现输入、影响、最小修正建议；不代修。
统一回传：项目MA9-07R、实际模型/平台/档位、cwd/branch/起止完整SHA、workspace状态、问题清单、命令/退出码/数量、复用来源与证据路径、剩余风险。不要使用owner的自评替代独立判断；不自行宣布合入或实机通过。
