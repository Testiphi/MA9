# MA9-05GR-防守单槽入口回调独立复核

模型登记：Qwen3.8-Flash；平台实际默认档位，没有独立开关如实注明，不自证底层身份、不自动max。用户手动在带本地工具的全新独立对话运行，与owner分离。禁止创建子智能体/对话/worktree。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-scan
branch：lane/duel-scan
完整基点：f9182dac671e19e9e9a0d8a3af3c334df46c9a5d
预期起止HEAD：7eedd3f0934ba89d8c1234e6534345e66c85a9df
区间恰一提交两个新增文件。主仓库新编排不用同步，禁止checkout/reset/merge。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5；核查A→B→HEAD祖先，复用不重冻。

精确边界：owns=[]、owns_new=[]、owns_generated=[]，全部受控文件只读，不代修、不提交/合并/推送。
唯一私有输出：E:/hzz/work/MA9/MA9-evidence/20260924-05GR-entry-review/，目录已存在停止，不覆盖。允许report.md、results.json、targeted.log、slot-regression.log、probe-results.json、tmp/小型探针与内存夹具。不得改旧报告、不得运行旧证据脚本main。
不连接真实Controller/ADB/MuMu/游戏，不开GUI、构建、安装依赖，不点击真实设备。六个大型multiplayer_loop分片不读；data/generated只读；根外MutualExclusionAllocator不触及。04暂停。

必读：
E:/hzz/work/MA9/agent/lanes.yaml
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/docs/zh_cn/develop/contract_freeze_draft.md
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
E:/hzz/work/MA9/agent/orchestration/prompts/05G-slot-entry.md（唯一任务规范）
本lane agent/ma9_agent/duel_slot_entry.py、agent/tests/test_duel_slot_entry.py全文与diff；duel_slot_selection.py、duel_lineup_slot.py、selection_runtime.py相关接口只读。
E:/hzz/work/MA9/MA9-evidence/20260924-05G-slot-entry/{report.md,results.json,schema-reuse.json}
E:/hzz/work/MA9/MA9-evidence/20260924-05G-orchestrator/{results.json,process-results.json}
E:/hzz/work/MA9/MA9-evidence/20260924-05FR-slot-review/results.json

目标：独立判断05G入口能否进入后续总控账号根/GUI接线阶段，不能宣布真实入口实机就绪。API真实形态不等于真实设备执行。不要因owner或总控测试全绿而省代码审查。
重点：
1. 输入证据非法先拒绝；不改写其任何嵌套字段；输入仅供比较，真实stable观察与最后一帧必须独立采样，资格赛、槽号、panel、button box都对齐，不能用期望值喂观察器。
2. 最后一帧的标题和按钮OCR必须同帧；整串选择车辆/更换车辆、finite confidence>=.90、框中心在观测按钮ROI内；冲突/低置信/坏框拒绝；绝对/相对坐标依据真实ocr_roi实现核查。
3. 点击中心来自最后实际观察box；全函数最多一次post_click，无其他输入/任务链/选车/开赛；失败/异常不重试。False可能已点击，不能解读无副作用。
4. 点击后最多6次，车辆选择严格标题、置信度和ROI，连续两次；坏帧/异常重置。尺寸检查和通道检查与docstring是否一致，按真实frame_of返回形态评估可达影响，不能把伪造依赖自动当作生产缺陷。
5. 组合05F：入口False不得scan，成功默认choose=False，starts_race=false；不污染before追溯。账户身份与数据根尚未绑定，不在本模块伪装实现。
6. 计数更正：05G回调最大4(稳定采样预算)+1(最后一帧)+6(到达)=11，不是owner写的9；顺利路径2+1+2=5。05F外层前置/后置和scan采样另计，不能把11当成整条选车链上限。用探针覆盖稳定出现在第4次+到达耗尽6次，锁定上限和点击次数。旧报告不改，更正写本轮。
7. _supported_frame的三通道声明、OCR iterable多次遍历、异常捕获范围等可自行检视；分清当前真实依赖可达与防御性改进。判断须有最小复现、行号和影响；不为假设扩修、也不忽略真实误放行。
8. 两帧不保证真实新鲜度，截图与点击非原子，按钮/到达页尚无真实OCR实跑证据；保留到下一阶段真实静态OCR/用户串行设备验收，不以fake通过取代。

最少独立实跑（不重复全套）：
Python优先MA9_PYTHON否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止，-X utf8 -B检查版本；PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP均为本证据tmp并记录gettempdir；cwd本lane，不从main导入业务源码。
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_slot_entry.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_slot_selection.py -v
预期26与30，保存最终exit。另写少量独立边界探针，使用真实观察器/稳定helper处理内存帧，stub OCR/frame/controller允许，不mock被测函数返回值。探针应有断言或显式机器比较，不能仅打印后把exit0称全部断言通过。
Agent242、tools30(29+1skip)已由总控在7eedd3f实跑exit0，查日志后明确复用不重跑；schema27历史exit0，两新Python文件不改输入，明确复用不重跑npm/schema。
开工收工git仅-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-scan，记录status、branch、完整HEAD、祖先、diff边界；不改全局Git配置。

结束：完成独立审读、两项定向与边界探针，工作区和HEAD不变，输出有/无阻塞、逐项问题、最小复现和行号、代码行为与文字更正分开、实跑与复用分开。回传项目/实际模型平台档位/cwd分支/完整起止SHA/命令最终exit计数/证据路径/下一阶段前置。禁止宣布合入、打包或实机放行。
