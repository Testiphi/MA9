# MA9-02C-运行根隔离诊断（只读，不构建）

模型：ds-v4.1flash / high；用户在WorkBuddy或选定平台全新对话粘贴本文件。独立上下文，不创建对话/子智能体/worktree，不联系其他lane。
本次只读诊断：05已实机成功，但总控集成tools路径测试失败。查清根目录选择规则和最小改进提案，不改代码、不打包、不要求用户重复实机。

cwd：E:/hzz/work/MA9/MA9-worktrees/duel-scan
分支：lane/duel-scan
诊断基点、起始与结束HEAD：f5472bce3443fde42df17ad8a1819e18b46a2059。
主仓库main当前HEAD：d118f5254e4c99df40488779f388fc24a7730e62，只有总控编排更新和用户.workbuddy；不要清理。
05修复基点0850f33d4f3a127ed79ba7c62a0d25a6282a6845，契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，均复用，不能重新冻结。02原分支lane/build-ci的03c6d9751f8b5f31865501d1954b2486568afd76保留，不在那条旧分支诊断/打包05。

必读文件：
- E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
- E:/hzz/work/MA9/agent/lanes.yaml
- E:/hzz/work/MA9/agent/orchestration/state.json
- E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
- E:/hzz/work/MA9/MA9-evidence/20260923-05-main-integration/results.json、tools.log
- E:/hzz/work/MA9/MA9-evidence/20260923-091020-D-five-assigned/acceptance.json
- cwd下agent/runtime_action.py（只需根目录选择与防守入口）、agent/tests/test_runtime_root.py、tools/selection_gui.py（根目录选择）、tools/tests/test_selection_gui_path.py。
主仓库编排配置为权威；lane中的旧模型与路径不适用。

现场已知：
1. 新包f5472bc用户实机耗时449.013秒，业务five_assigned、五个唯一D级车、starts_race=false、终屏阵容页，总控确认运行PID9184对应新包Agent。
2. find_project_root偏好候选祖先中含config/garage.json的账号根，故业务JSON落主仓库debug，框架日志在包debug。运行的两份业务数据与包内JSON结构相同，仅CRLF/LF不同；实机成功有效，但不能宣称隔离包的数据完全隔离。
3. 总控合并候选Agent101通过；tools13项中12通过、test_release_exe_uses_adjacent_data失败：临时install在MA9内时返回MA9账号根。TMP/TEMP放MA9内是当前用户写入边界，不能挪根外逃避问题。相关三个文件在main与05中完全一致，非05新增回归；合并已安全撤回。
4. 开发构建寻找祖先账号配置是既有设计，不能简单删除该兼容行为。发行包相邻数据、显式MA9_PROJECT_ROOT与开发构建优先级需要明确区分。

精确写入边界：owns=[]、owns_new=[]、owns_generated=[]。所有受控文件只读，尤其runtime_action.py属于总控契约；tools/selection_gui.py及其测试尚未登记普通lane owner。五契约模块和schema、assets/interface.json也只读。
允许新建私有输出仅 E:/hzz/work/MA9/MA9-evidence/20260923-02C-root-diagnosis/ 下的report.md、results.json、path-tests.log、reproduce.py及tmp/测试夹具。目录已存在则停止报告，不覆盖证据。所有临时文件必须在该tmp/内；禁止删除或更改现有账号config、历史包、日志及回收站。
不得读取六个大型multiplayer_loop分片；data/generated只读，仅按需结构或哈希比较，不能重新生成。不得读写根外MutualExclusionAllocator。禁止ADB/MuMu、GUI、游戏操作、提交/合并/推送。

任务：
A. 从实际源码解释两套find_project_root的候选顺序、账号根优先及显式override；关联本次日志落点和测试失败，不把两套函数误当同一函数。
B. 构造位于MA9内的最小只读复现：发行包有完整相邻数据但祖先有账号配置；开发build无相邻数据应回退祖先；有效/无效显式override。仅在临时夹具创建数据，不操作真实账号目录，不改生产模块。
C. 给出最小策略提案与测试矩阵：如何识别发行根/开发根，如何避免误读另一个账号，如何维持原开发兼容和明确override优先。区分真正产品行为修正、测试环境隔离和仅操作卡修正；不能只改断言或屏蔽失败。
D. 列出建议修改文件及owner：涉及runtime_action只能总控亲自改；GUI及测试须总控先登记。以文件/行号、行为前后和兼容风险回传，禁止直接实施补丁或扩写跨lane功能。

开工核对cwd、git status --short、branch --show-current、rev-parse HEAD、最近3提交；不符停止，不checkout/reset/merge。Git dubious ownership只用命令级-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-scan，不改全局配置。
Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；存在才运行-X utf8 --version，不存在停止，不替换PATH。所有Python命令-X utf8，cwd始终lane根，禁止从main导入lane源码。TMP/TEMP设为上述新证据目录的tmp；不移除或绕过宿主守卫。
最低复现命令（用解析出的$lanePython）：
& $lanePython -X utf8 -m unittest discover -s tools/tests -p test_selection_gui_path.py -v
这在根内tmp预计1通过1失败，保留实际最终退出码，不当新失败盲目重复。私有reproduce.py仅如有必要才写；执行也带-X utf8。不重跑全量schema/npm/Agent或构建。总控集成证据可引用但标明复用。
结束条件：解释失败机制、有界复现、提出明确最小方案与owner边界；受控文件不变。如果信息不足明确缺项，不猜测已修复。
回传：项目名、实际模型/平台/档位、cwd/branch/起止完整SHA、git状态、复现命令/退出码/断言、文件行号、最小方案、兼容性风险、证据绝对路径和需要总控裁决的选择。该诊断不代表05失败或06放行；04暂停，06/07等待。
