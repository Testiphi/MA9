# MA9-06B-防守地图顺序守卫回归收尾

模型：ds-v4.1flash / high。用户在WorkBuddy或选定平台新建完整独立对话粘贴本文件。你是06测试owner，不依赖旧聊天，不创建对话/子智能体/worktree。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-defense
branch：lane/duel-defense
完整基点与预期起始HEAD：caf5c0455f4ecc6595ed79c82eac365a2e57a1d9。
总控已将干净06工作区快进到此基点；不要使用原06A的550c01d，不自行checkout/reset/merge。
本次任务仅覆盖06A F1已知测试缺口，不重新打开已完成的D级配置阶段，不改生产逻辑。07A等待GLM额度且只读，与本次独立。

必读：
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/agent/lanes.yaml（06 owns与契约边界）
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
E:/hzz/work/MA9/MA9-evidence/20260923-06A-defense-audit/report.md、tmp/probe_boundaries.py、tmp/probe-results.json（P2b为既有探针，只读，不原样重跑覆盖证据）
本cwd下agent/ma9_agent/duel_defense_setup.py、agent/tests/test_duel_defense_setup.py。
主仓库编排配置权威。06A“5实机+3离线”已被总控纠正：仅G1直接实机，G2–G8离线/代码证据；不要传播旧统计。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先后复用，不重新冻结。

精确本次边界：
owns:
- agent/tests/test_duel_defense_setup.py
owns_new: []
owns_generated: []
任何生产代码、其它测试、文档、状态、契约、schema、interface、pipeline与生成数据均只读。两个defense_setup文件虽然归06，本次只有其测试可写。不要顺手处理07错误消息或根隔离文档。

唯一目标：补一项有意义的地图顺序守卫回归。
- 复用既有小夹具与fake context，不构建新框架。
- 初次_read_tracks返回五图；车库扫描成功后再次返回同一五图但顺序交换（如前两图互换），完整性仍true。必须用独立列表，不能修改初始列表造成两个读数一起变化。
- 调用真实run_defense_setup，断言抛出对应地图顺序错误；持久progress报告为stopped、starts_race=false且未记录赋值；任何assign_visible调用不得发生，不能出现开始比赛动作。
- 可使用plan模式锁定“车库扫描后顺序变化”这一最早守卫；不要为了覆盖四个抛错点大幅重写测试或生产代码。补一项即可。
- 已有守卫行为被06A探针证明正确，新测试应直接通过；不要求伪造修复前失败，不弱化断言、不添加skip、不mock被测函数返回值。
若实际发现生产缺陷，停止扩大范围并提交最小复现给总控，不自行修复。

环境与证据：
Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe。先验证存在和-X utf8 --version；缺失停止，不换PATH。所有Python命令-X utf8，cwd始终06根，禁止从main导入源码。
新证据目录E:/hzz/work/MA9/MA9-evidence/20260923-06B-map-order-regression/，目录存在则停止报告，不覆盖。只允许report.md、results.json、defense.log、agent.log、reuse.json及tmp/小夹具。TMPDIR/TMP/TEMP三者同时设为该tmp，记录实际tempfile.gettempdir。所有写入在MA9内，不操作微信原图、旧包、账号配置或回收站。
开工与交付核对git status --short、branch、完整HEAD、最近3提交；Git仅-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-defense，不改全局设置。现场不符停止，不自行清理。

验证命令（$lanePython为实际解析路径）：
& $lanePython -X utf8 -m unittest discover -s agent/tests -p test_duel_defense_setup.py -v
& $lanePython -X utf8 -m unittest discover -s agent/tests -v
记录最终退出码、测试数量；长进程续等。基点Agent106已由总控验证，新增一项后预计107，实际数量以日志为准。
本次仅该测试文件变化：tools生产与测试、资源/schema/interface/校验器均不变，机械核对diff文件集合，保存reuse.json，引用02E总控tools30 exit0与schema27历史等价复用证据，不声称本轮重跑。证据分别为MA9-evidence/20260923-02E-orchestrator/results.json、20260923-combined-integration/results.json。无需重复tools/schema/npm或构建。

结束条件：新增回归真实命中守卫，针对性与Agent全套exit0，git diff --check通过，仅一个授权文件变化。按用户政策自动创建一次本地提交，仅暂存自己的测试修改；不合入main、不推送、不打包、不发布。
回传项目、实际模型/平台/档位、cwd/branch、起止完整SHA与commit、diff/stat、命令/退出码/数量、复用证明、证据路径与剩余风险。总控独立核对后集成，不为这项纯测试收尾额外占GLM额度。
禁止GUI/ADB/MuMu/游戏操作，不开赛、不制造账号冲突。六个大型multiplayer_loop分片不读入模型上下文，data/generated只读不生成，根外MutualExclusionAllocator不读写。04暂停，07A原任务保持。
