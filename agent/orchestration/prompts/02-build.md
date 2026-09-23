# MA9-02B-f5472bc隔离测试包

模型：ds-v4.1flash / high。用户在外部平台新建独立对话粘贴本文件；不依赖旧聊天，不创建子智能体、对话或worktree，不联系其他lane。
本次已完成并经总控验包：以下保留为02B历史派发内容，禁止再次执行或覆盖已完成包。当前等待用户实机，不再派发构建。原任务仅构建与验包，不改业务代码或构建工具。你是02的临时构建执行者，使用05已验收源码；02原CI交付保持原样。

cwd必须为 E:/hzz/work/MA9/MA9-worktrees/duel-scan
分支必须为 lane/duel-scan
构建基点与起止HEAD均必须为 f5472bce3443fde42df17ad8a1819e18b46a2059。
修复审查范围为0850f33d4f3a127ed79ba7c62a0d25a6282a6845..f5472bce3443fde42df17ad8a1819e18b46a2059。
主仓库现场HEAD=55a8c1c0d5590206d16cce539767175436c86d19，仅编排文件有总控未提交改动和用户.workbuddy/，不可清理。
严禁在lane/build-ci（03c6d9751f8b5f31865501d1954b2486568afd76）打包；它没有本次05修复。无需整合02提交，不checkout/merge/cherry-pick/reset，不覆盖旧包或install。

必读：
- E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
- E:/hzz/work/MA9/agent/lanes.yaml（主仓库为当前权威）
- E:/hzz/work/MA9/agent/orchestration/state.json
- E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
- E:/hzz/work/MA9/MA9-evidence/20260923-05R-accepted/05R-review.md
- cwd下tools/build_agent.py、tools/build_windows_package.ps1（只读参考）、docs/zh_cn/develop/duel_offline_recognition.md。
冻结A=bd9a535336750d8fae3799f20d321498e21f5b00，B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5；核对A→B→HEAD祖先，不重新冻结。

精确受控文件边界：owns=[]；owns_new=[]；owns_generated=[]。所有受控源码、测试、配置、schema和生成物只读；包括assets/interface.json及五个契约模块。不能因为属于02就改工具。构建失败若需要受控修改，保存日志返回总控重新登记。
唯一允许本地写入的范围（均在MA9内）：
1. cwd/build/agent/win-x64/：现有构建工具工作产物，可以由构建工具更新。
2. cwd/build/user-test-ordering-f5472bc/：本次新包及TEST-BUILD.json、实机验证说明.txt；存在即停止，不覆盖。
3. E:/hzz/work/MA9/MA9-evidence/20260923-02B-f5472bc/：新证据目录，存在即停止。允许新增assemble_package.py、verify_package.py、build-agent.log、package-resources.json、compiled-modules.json、smoke.log、results.json、report.md；必要脚本缓存仅在此目录。
工具临时文件和缓存必须重定向到cwd/build/agent/win-x64/内；不得写MA9根外。不得修改任何历史脚本、证据、旧测试包或用户config/logs。
六个大型multiplayer_loop分片不可读入模型上下文；工具可按字节复制及计算哈希。data/generated只复制本次包必需既有文件，不生成。

环境与开工检查（每次命令cwd均为上述lane根）：
PowerShell解析 $lanePython = if ($env:MA9_PYTHON) { $env:MA9_PYTHON } else { 'E:/hzz/work/MA9/.venv/Scripts/python.exe' }
验证存在并 & $lanePython -X utf8 --version；找不到停止，不改用PATH。当前总控验证为Python 3.14.4。
所有Python命令带-X utf8；禁止PYTHONPATH指向main。Git用命令级-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-scan，不改全局设置。
git status --short、rev-parse HEAD、branch --show-current、log -3及祖先检查；HEAD/分支不符或受控文件脏则停止上报，不修现场。

构建与核验：
1. 在上述cwd运行 & $lanePython -X utf8 tools/build_agent.py，日志保存证据目录/build-agent.log；捕获实际最终退出码。不要传--clean删除既有根目录；工具自身正常更新构建产物允许。长进程必须等到退出，不以输出结束推定成功。
2. 历史 E:/hzz/work/MA9/MA9-evidence/select-button-fix/assemble_package.py 仅作参考：其ROOT仍是迁移前路径且DEST为旧包，不得原样运行或修改。新assemble_package.py必须断言当前根、完整HEAD和干净状态，并拒绝覆盖目标。
3. 仅UI/原生运行库/OCR模型可复用主仓库缓存build/mfa、deps、assets/resource/model/ocr。业务源码、受控资源、数据、interface必须来自本lane的f5472bc；Agent必须是本次构建。禁止整体复制旧测试包，排除config/debug/logs/backup/temp及缓存中任何旧业务资源和Agent。
4. 包内interface副本只允许设置版本v0.0.0-duel-ordering-f5472bc和agent.child_exec='./agent/ma9-agent/ma9-agent.exe'、child_args=[]；源assets/interface.json不能改。按需复制LICENSES、README/LICENSE/NOTICE及历史组包列出的数据。旧资源不得残留。
5. 每个受控资源/数据逐文件SHA256与lane源一致并记录来源清单；记录本次Agent完整目录清单及哈希，包内可执行文件与本次dist一致。TEST-BUILD.json记录完整SHA、版本、Python、构建命令/cwd/退出码、源码与Agent哈希、资源验证及review、device_test='not_run'。历史校验必须标明复用。
6. 写verify_package.py，用PyInstaller archive读取器提取PYZ，核对duel_vehicle_screen、duel_vehicle_runtime、duel_defense_setup、duel_selection与本lane源码compile所得代码对象，递归比较代码及所有常量（含数值），忽略仅文件路径元数据差异；缺模块或差异必须非零退出。debug/pyz_probe.py只可参考：其比较忽略部分数值常量、出现不一致仍返回0，不能仅看它exit0。
7. 不传socket参数运行新包agent/ma9-agent/ma9-agent.exe一次，预期Usage和exit1；设置短超时，记录实际输出与退出码，不把任意exit1当成功。不得启动MFAAvalonia、ADB/MuMu或连接游戏。
8. 编写实机操作卡：准确MFAAvalonia.exe绝对路径；用户停止旧任务后运行此新包，选择“对决资格赛：自动配置五辆弱防车（不开始比赛）”，明确D级。成功须业务JSON five_assigned、五车互斥、starts_race=false且停阵容页；already_configured仅代表保留已有阵容，不算本轮五车赋值通过。记录耗时和终屏，回传总控核对包内debug/duel_defense_gui_setup.json、duel_vehicle_scan_live.json、duel_tracks_live.json、duel_defense_plan_live.json、maafw.log及on_error截图。禁止用GUI完成提示替代业务JSON。

本次纯构建不修改受控文件，不重复完整schema/npm/业务测试。复用MA9-evidence/20260923-05D-acceptance/results.json中Agent101、tools12+1skip、schema27 exit0和05R 37项证据；不是本次重跑。仅验证新产物与源码绑定、资源一致、离线启动及最终git diff --check/status。
注意：debug/ocr-call-*.json已陈旧，不能用作23:18:23.444证据；原件不改。原始日志在MA9-evidence/20260922-231746-ordering-handoff/maafw.log。

结束条件：构建最终exit0、包完整、四模块一致、资源及数据哈希一致、离线Usage/exit1符合预期、起止HEAD一致且受控工作区仍干净。失败保留现场并给确切阻塞；不自行扩大边界、不反复无界重试。完成仅回传总控，不能自行宣布实机放行或合并。
回传：项目MA9-02B-f5472bc隔离测试包；模型实际标签/平台/档位；cwd/branch/起止完整SHA；所有命令及最终退出码；包目录和运行入口；TEST-BUILD.json路径、exe哈希、模块/资源核验结果；证据/脚本绝对路径；git状态/diff；复用与实跑分开；剩余风险。不得提交、推送、发布或更新安装目录。04暂停，06/07等待，未授权操作根外MutualExclusionAllocator。
