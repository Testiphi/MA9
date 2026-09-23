# MA9-02E-根隔离文档与GUI回归收尾

模型：ds-v4.1flash / high。用户在WorkBuddy或选定平台新建完整独立对话粘贴本文件；不依赖旧聊天，不创建子智能体/对话/worktree，不自行联系其他lane。
本次已放行：仅修正文档/注释并补GUI兼容性测试，不修改生产行为。07等待GLM额度，02E不依赖07，互不修改对方文件。

cwd：E:/hzz/work/MA9/MA9-worktrees/root-isolation
branch：codex/root-isolation
完整基点及预期起始HEAD：18964c884cd3b6a4a81bb3c69edeb96b26ed26dc。
总控已将干净工作区从旧a7d9910快进到该基点；不要使用旧SHA，不自行merge/checkout/reset。
该基点已推送origin/main，GitHub check=35818798712、install=35818798735均completed/success。05和根隔离均已合入，组合Agent105/tools29全过。远端CI只证明这个SHA，不能直接冒充新提交通过。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5；验证祖先后复用，不重新冻结。02原build-ci的03c6d9751f8b5f31865501d1954b2486568afd76保持不动。

必读：
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md（6.1.1与自动提交政策）
E:/hzz/work/MA9/agent/lanes.yaml（build边界；本次下列清单更窄）
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
E:/hzz/work/MA9/MA9-evidence/20260923-02R-root-review/report.md（F4/F5-GUI/F6）与probe-results.json（P1/P4）
本cwd下docs/zh_cn/develop/how_to_develop.md、tools/tests/test_selection_gui_path.py、tools/selection_gui.py（只读）、agent/runtime_action.py（只读）。
主仓库编排规则权威，worktree内旧提示词仅历史。

精确边界：
owns:
- docs/zh_cn/develop/how_to_develop.md（仅根隔离段落）
- tools/tests/test_selection_gui_path.py（仅错误注释更正与GUI兼容性回归）
owns_new: []
owns_generated: []
禁止修改任何生产模块、组包脚本、其他测试、契约/schema/interface或生成数据。尤其agent/tests/test_runtime_root.py属总控，F5-runtime不在本次范围；07错误消息待办不捎带处理。
所有私有输出仅在 E:/hzz/work/MA9/MA9-evidence/20260923-02E-root-closeout/ 下：report.md、results.json、gui.log、tools.log、reuse.json及tmp/小夹具。目录已存在停止报告，不覆盖；不改任何旧报告或日志。

仅完成三件事：
1. F4文档：标记路径明确“先穷尽exe目录及其祖先，再穷尽cwd链；Agent最后模块链”，与层数无关，不写并行/交替/同层优先。无标记的旧候选顺序分别写清：Agent cwd→exe→模块；GUI exe→cwd。共同优先级不等于旧起点顺序相同。
2. F6注释：删除/更正ControlledFilesystem中“Python3.12起不接收self”的错误说法；真实普通方法补丁会接收bound self。只解释夹具内调用原始存在性方法、夹具外返回False，不借机重构测试隔离机制。
3. F5-GUI补一项真实回归：在受控祖先链内，祖先有catalog+rotation+garage，相邻package自身也有catalog+rotation但无garage且无标记，断言返回祖先；可在同一测试增加写入标记后返回package的对照。必须实际创建数据文件并调用真实find_project_root，不mock返回值、不预设override、不加skip。
这是锁定已证正确的行为，不要求伪造红转绿，也不改断言掩盖原错误。避免重复堆砌多项同义测试；无需改原历史报告F1/F2，总控已有更正记录。

环境与验证：
Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；先确认存在并-X utf8 --version，不存在停止，不切PATH。所有Python-X utf8，cwd必须本worktree，不从main导入源码。
TMPDIR/TMP/TEMP三者同时设为本证据目录/tmp，记录实际tempfile.gettempdir。所有写入/临时目录必须在MA9内，不删除真实账号config、旧包、历史证据或回收站，不绕过宿主守卫。
开工核对cwd、branch、HEAD、git status --short、最近3提交、B祖先。Git只用命令级-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/root-isolation，不改全局配置。现场不符停止，不自行修现场。
命令（$lanePython为已解析路径）：
& $lanePython -X utf8 -m unittest discover -s tools/tests -p test_selection_gui_path.py -v
& $lanePython -X utf8 -m unittest discover -s tools/tests -v
记录最终进程退出码、测试数量与既有私有截图跳过原因；长进程续等，不把工具结束当进程通过。
本次只有文档/工具测试改动，Agent生产/测试、资源/schema/interface/校验器、package/lock/workflow均不变：机械核对相对基点的文件集合，保存reuse.json，沿用基点对应Agent105、schema27和远端check/install成功记录。明确复用而非重跑；不重复全量Agent/schema/npm，不打包。tools全量需本轮实际通过，防止夹具补丁影响其他测试。

结束条件：仅两个授权文件变化，文档与实际代码一致，新回归覆盖指定相邻数据几何，GUI针对性与tools全量最终exit0，git diff --check干净。按用户政策自动创建一次本地提交，仅暂存本次两文件，不反复询问。不得合入main、推送、发布、打包、启动GUI/ADB/MuMu或游戏。
回传：项目名、实际模型/平台/档位、cwd/branch、起始与结束完整SHA、commit、精确diff/stat、命令/退出码/数量、复用证明、证据路径与剩余风险。总控独立核对后决定集成；本次不要求为文档/测试收尾另占GLM额度。若发现生产缺陷，停止扩大范围并报告总控。
六个大型multiplayer_loop分片不读入上下文，data/generated只读不重建。根外MutualExclusionAllocator不得读写。04暂停；07A仍为独立固定基点只读规划，不修改07提示词或状态。
