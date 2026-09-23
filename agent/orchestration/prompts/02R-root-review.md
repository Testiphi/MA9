# MA9-02R-便携根隔离独立复核

模型：GLM-5.3 / high。用户在外部平台全新对话运行；你是独立只读reviewer，不继承02D owner或总控结论，不创建对话/子智能体/worktree，不自行修复。
cwd：E:/hzz/work/MA9/MA9-worktrees/root-isolation
branch：codex/root-isolation
预期起始与结束HEAD：a7d9910cc945072efbf6ccb9b3d38f4f949a6e87（不得改变）。
总审查基点：d118f5254e4c99df40488779f388fc24a7730e62。
分段：d118f5254e4c99df40488779f388fc24a7730e62..490cbb9ad1f103eb38e4da58e030a4b11ddccf2e为总控runtime/测试/政策增量；490cbb9ad1f103eb38e4da58e030a4b11ddccf2e..a7d9910cc945072efbf6ccb9b3d38f4f949a6e87为02D的5文件改动。
必须同时审总控runtime部分，不能只审owner diff。main当前490cbb9，02原03c6d9751f8b5f31865501d1954b2486568afd76和05原f5472bce3443fde42df17ad8a1819e18b46a2059均未改动；05尚未合入。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00，B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先并复用，不重新冻结。

精确边界：owns=[]，owns_new=[]，owns_generated=[]。所有受控文件只读，不修改源码、测试、文档、配置或编排状态，不提交。唯一允许新建的私有输出为E:/hzz/work/MA9/MA9-evidence/20260923-02R-root-review/下的report.md、results.json、runtime.log、gui.log、preview.log及tmp/小夹具。目录存在则停止上报，不覆盖历史。所有写入、临时输出均限MA9根内；禁止操作根外MutualExclusionAllocator。

必读：
- E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md（6.1.1为当前裁决）
- E:/hzz/work/MA9/agent/lanes.yaml
- E:/hzz/work/MA9/agent/orchestration/state.json
- E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
先看上述两个区间的实际diff，再读owner报告：
- E:/hzz/work/MA9/MA9-evidence/20260923-02C-root-diagnosis/report.md
- E:/hzz/work/MA9/MA9-evidence/20260923-root-contract/{red-result.json,red.log,green-results.json}
- E:/hzz/work/MA9/MA9-evidence/20260923-02D-root-fix/{report.md,results.json,schema-reuse.json}
- E:/hzz/work/MA9/MA9-evidence/20260923-02D-orchestrator/results.json
主仓库编排配置权威，worktree旧提示词仅历史。不能凭另一席口述判定通过。

必须核对的裁决：
1. 显式override优先，无效直接抛错。
2. 标记为包根普通空文件.ma9-portable-root。先穷尽exe目录及其祖先，再穷尽cwd；Agent最后才查模块目录祖先。首个标记即边界；缺本函数必要数据须抛错而非跨标记回退。
3. 无标记时保留原有账号根优先与数据根兜底（注意runtime旧候选cwd在exe前，GUI旧候选exe在cwd前；不是要求把旧顺序统一）。两函数保留各自的数据有效性判据。
4. 标记仅由便携preview组包工具在新包产生；开发install、账号目录、源码根、既有05实机包不补标记。不复制用户config/garage/logs，不扩展为根解析重构。
5. 总控没有声称新标记包实机通过。05原无标记包D级449.013秒实机成功只适用于那个版本与路径，不推广至此功能或其他等级。

重点审查：
- 两套查找在不同深度的exe/cwd标记、缺数据标记、显式override、祖先账号目录和未标记开发install下是否满足裁决，是否可能导致GUI/Agent账号分裂。
- 测试是否真实执行目标函数，ControlledFilesystem是否只限制夹具外文件存在性；有相邻catalog但无garage且祖先有garage的无标记兼容场景是否真正覆盖。不要只看测试名称。
- prepare_portable_preview.py的标记写入时机、文件/目录类型、缺输入、资源缺失及隐私排除是否有可到达的问题；区分helper可单独构造的缺陷与真实main组包路径，不凭假设扩修。
- 测试小夹具是否足以验证新逻辑；不得为review构建真实包或重新执行会删除既有目标的真实组包脚本。
- 文档/报告与代码是否一致。总控已独立证明代码是顺序穷尽，不是owner回传所称交替遍历；detail_select_text.png来自05的0850f33按钮修复，不属于490cbb9。把原报告当待核实材料，不改原证据。
- 请独立核对ControlledFilesystem注释有关Path.is_file/exists参数的说法，以及how_to_develop.md的旧候选顺序和“并行时不交叉/同一层”描述；按实际影响判断是否阻塞，不把措辞问题夸大为代码故障。
- owner基线红日志red.log保留，另两份pre-fix全量日志被后续覆盖；不得把已覆盖结果当作可独立追溯红证据。

验证环境：Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe。存在才运行-X utf8 --version；不存在停止，不换PATH。所有命令cwd为上述worktree，所有Python带-X utf8，不从main导入源码。
同时设置TMPDIR/TMP/TEMP到本review证据目录/tmp，确认实际tempfile.gettempdir()并记录。不得清空或绕过宿主守卫，不把夹具移到MA9外。
Git命令级-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/root-isolation；开工/结束核对status、branch、完整HEAD及祖先。现场不符停止，不reset/checkout/merge，不改全局Git。
最低针对性运行（$lanePython为解析路径）：
& $lanePython -X utf8 -m unittest discover -s agent/tests -p test_runtime_root.py -v
& $lanePython -X utf8 -m unittest discover -s tools/tests -p test_selection_gui_path.py -v
& $lanePython -X utf8 -m unittest discover -s tools/tests -p test_portable_preview.py -v
记录实际最终退出码和数量，长进程续等。可用根内临时小夹具/内联代码复核关键疑点，但不创建受控新测试或修改生产模块。
总控已在a7d9910独立跑Agent86、tools29（28通过/1既有私有截图跳过）均exit0，并重算34项schema输入与05D证据一致。复用需标明来源，不重跑全量schema/npm；六个大型multiplayer_loop分片不读入模型上下文，data/generated只读不生成。

结束条件：完成双阶段代码/边界/证据检查，三组针对性测试取得最终退出码，输出“无阻塞/有阻塞”，或明确“证据不足未完成”。每项发现给文件行号、严重程度、具体复现/影响、最小建议及owner；runtime修复归总控，其余派回02D，不自行改。
统一回传：项目MA9-02R、实际模型/平台/档位、cwd/branch/起止完整SHA、工作区状态、review范围、问题清单、命令/退出码/数量、证据路径、剩余风险。不得打包、发布、推送、启动GUI、操作ADB/MuMu或游戏；04暂停、06/07等待。
