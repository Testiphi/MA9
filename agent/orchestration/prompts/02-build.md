# MA9-02D-GUI与便携包根隔离修复

模型：ds-v4.1flash / high，用户在WorkBuddy或选定平台全新对话粘贴本文件。你是build的有界外部owner，不创建下级智能体、对话或worktree，不依赖旧聊天。
本次已放行：实现GUI的显式便携根选择、修正环境相关测试夹具、让便携预览组包生成标记；不构建真实包，不操作设备，不重做02原CI成果。

cwd必须为 E:/hzz/work/MA9/MA9-worktrees/root-isolation
branch必须为 codex/root-isolation
完整基点和预期起始HEAD：490cbb9ad1f103eb38e4da58e030a4b11ddccf2e。
总控已创建该工作区；该提交含总控runtime根增量与边界登记。main同基点，后续仅编排元数据可能前进；以主仓库规则为权威。
02原lane/build-ci HEAD=03c6d9751f8b5f31865501d1954b2486568afd76不得改动。
05 lane/duel-scan HEAD=f5472bce3443fde42df17ad8a1819e18b46a2059，不在本分支；05实机成功仍有效，不能合入或重打包05。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，核对祖先后复用，不重新冻结。

必读（绝对路径）：
- E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md（特别6.1.1）
- E:/hzz/work/MA9/agent/lanes.yaml（build与contract归属）
- E:/hzz/work/MA9/agent/orchestration/state.json
- E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
- E:/hzz/work/MA9/MA9-evidence/20260923-02C-root-diagnosis/report.md、results.json
- E:/hzz/work/MA9/MA9-evidence/20260923-root-contract/green-results.json
- 本cwd下tools/selection_gui.py、tools/tests/test_selection_gui_path.py、tools/prepare_portable_preview.py、agent/runtime_action.py与agent/tests/test_runtime_root.py（后两项只读，只看根目录与对应测试）、docs/zh_cn/develop/how_to_develop.md。

精确本次边界（比build全lane更窄）：
owns:
- tools/selection_gui.py（只改根目录查找相关逻辑）
- tools/tests/test_selection_gui_path.py
- tools/prepare_portable_preview.py（只增加便携标记产出及必要验证）
- docs/zh_cn/develop/how_to_develop.md（仅说明便携根优先级、开发兼容及临时目录环境）
owns_new:
- tools/tests/test_portable_preview.py
owns_generated: []（不生成受控资源/数据；仅测试夹具内的包副本与标记可由工具生成）
不修改tools/install.py、build_windows_package.ps1、build_selection_gui.py、configure.py；这些虽登记build owner，本次明确不授权。五契约模块、schema、runtime_action.py、test_runtime_root.py、assets/interface.json、其他测试和编排文件只读。runtime问题报告总控，不能代改。
六个大型multiplayer_loop分片不得读入模型上下文，不执行生成器。data/generated未精确登记的一律只读。

总控已裁决的行为（不再重新设计）：
1. 显式configured（GUI实际由MA9_PROJECT_ROOT传入）最高优先，有效则返回，无效抛错，不回退。
2. 普通空文件 .ma9-portable-root 表示主动隔离；依次从executable.resolve().parent及working_directory.resolve()，各自从近到远遍历祖先。遇第一个标记就停止查找：缺GUI所需catalog+rotation时抛FileNotFoundError，不越过标记去另一个账号；数据完整则返回该标记所在目录。exe标记优先于不同cwd标记。
3. 没有任何标记时保留原候选顺序、账号根优先与数据根兜底。开发install没有标记，仍与Agent使用同一个祖先车库；不要简单改相邻目录优先，不采用M-β祖先截断。
4. Runtime侧总控已在490cbb9实现相同优先级，但其有效性判据仅multiplayer_profile；两套函数不合并，不要求GUI调用Agent。
5. 标记只在新便携发行包根产生。prepare_portable_preview.py是本次唯一生成入口，默认输出为build/portable/MA9-preview/.ma9-portable-root；它是忽略的包副本产物，不是仓库根文件。不在源码根、开发install或既有05包补标记。不复制用户config/日志。
6. 组包满足必需文件和隐私排除检查后才创建空标记；失败不得留下看似完成的标记。不要扩大改动为重写组包流程或删除策略。

测试要求：
- marked包+祖先账号根→包；无marker包+祖先账号根→原账号根；相邻本身有账号→相邻；开发build无相邻数据→祖先；有效override胜marker；无效override拒绝；marker缺数据拒绝回退；exe marker胜不同cwd marker。
- 原test_release_exe_uses_adjacent_data的独立发行夹具须明确其隔离信号，保留“相邻返回”断言；另加无标记开发兼容对照，不能只改预期让失败消失。
- 如测试无账号祖先回退，必须建立受控文件系统视图，不让主机真实MA9账号意外参与；只屏蔽夹具外的文件存在性，不能mock被测函数的返回值。禁止加skip或预设override绕过本该测的分支。
- 便携脚本测试可通过patch模块ROOT/BASE/SOURCE_UI/AGENT至新建小夹具调用真实组包逻辑；不用真实依赖、真实install、真实构建目录。验证标记仅成功包根存在、私有config未复制、无效输入不产出标记，不读取大型分片。
- 保留修复前红、修复后绿的日志与实际退出码；如从旧源码加载，仅在证据临时目录进行，不覆盖工作区，不从main导入源码。

环境与证据：
优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；验证存在及-X utf8 --version，不存在停止，不换PATH。所有Python命令-X utf8，cwd始终指定worktree，不设置main源码PYTHONPATH。
证据目录：E:/hzz/work/MA9/MA9-evidence/20260923-02D-root-fix（已存在则停止，不覆盖）。仅允许在此目录生成report.md、results.json、red.log、targeted.log、agent.log、tools.log、schema-reuse.json或schema.log，以及tmp/夹具；不写MA9外。
运行前同时将TMPDIR、TMP、TEMP设为该证据目录/tmp，创建目录并记录实际tempfile.gettempdir()，不是只设置两项。保留宿主守卫，不删除真实账号配置、历史包或回收站。临时清理由标准小夹具上下文执行，不用批量删除绕过限制。
开工核对cwd、status、branch、HEAD、log -3和B祖先；不符停止，不reset/checkout/merge。Git只用命令级-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/root-isolation，不改全局设置。

验证命令（$lanePython为已解析解释器）：
& $lanePython -X utf8 -m unittest discover -s tools/tests -p test_selection_gui_path.py -v
& $lanePython -X utf8 -m unittest discover -s tools/tests -p test_portable_preview.py -v
& $lanePython -X utf8 -m unittest discover -s agent/tests -v
& $lanePython -X utf8 -m unittest discover -s tools/tests -v
完整schema第三门禁：先机械核对与f5472bc的资源JSON/JSONC、interface、schema及tools/validate_schema.py的Git对象相同，保存schema-reuse.json，引用MA9-evidence/20260923-05D-acceptance/results.json中的27项exit0，明确复用不重跑；有任何输入差异则不得复用。需要运行时命令为：
& $lanePython -X utf8 tools/validate_schema.py --schema-dir E:/hzz/work/MA9/deps/tools --resource-dirs assets/resource --exclude-dirs assets/resource/announcement --interface-files assets/interface.json
新worktree没有deps副本，以上绝对schema目录为只读工具依赖，不是从main导入业务源码。禁止重建102MB生成物或复制无关资源。
本次不是02原CI任务：package/lock/workflow/JS均不变，不重复npm ci/check；明确仅豁免本次不相关的build verify_extra。正式交付仍须Agent/tools及schema门禁（可按上述等价证明复用）。
所有长进程续等至实际退出，记录退出码与测试数量/跳过原因。失败最多两轮有界修复，仍失败保留证据返回总控，不自动升档。

完成后git diff --check，核对基点到交付的文件集合只在精确owns并owns_new中。仅提交本次修改，不合入main、不推送、不构建/发布/启动GUI或ADB/MuMu。回传完整commit、文件清单/stat、起止HEAD、验证命令/实际退出码/数量、复用证明、证据路径和剩余风险。
结束条件：GUI与runtime优先级兼容、标记产出由工具测试验证、旧开发行为测试保持、边界干净、门禁通过。总控将另发GLM-5.3 high独立复核（包含总控runtime增量），本席不可自我宣布整体集成通过。04暂停、06/07等待，05的449.013秒D级实机成功保留但不推广至新标记包或其他等级。未授权读写根外MutualExclusionAllocator。
