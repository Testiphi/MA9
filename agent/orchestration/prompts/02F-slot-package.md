# MA9-02F-cf8815b 防守单槽定位隔离测试包

模型：ds-v4.1flash，请求high；平台无独立开关如实记录实际默认，禁止自动max。用户外部全新对话、本地工具执行；不创建子智能体/对话/worktree。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-scan
branch：lane/duel-scan
准确构建源/预期起止HEAD：cf8815b2268d07142b679b06272101e9f1b2191e
本次打包基点与HEAD相同，受控源码零改动。不要在02旧build-ci分支03c6d975打包；该分支不含新入口。不要合并main后续编排提交，不checkout/reset/merge。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，检查A→B→HEAD后复用，禁止重冻。

目标：只为用户已经登录测试账号、已展开防守第1地图的场景，组装GUI只定位Nevera的隔离包。只构建、离线核验，不启动GUI/AgentServer/socket/真实Controller/ADB/MuMu/游戏。不宣布实机放行。首次choose=false，不选择、不比赛。
精确owns=[]、owns_new=[]、owns_generated=[]；所有受控文件只读，包括build/prepare工具。允许新建以下私有输出（目录存在停止，不覆盖）：
- E:/hzz/work/MA9/MA9-evidence/20260924-02F-cf8815b/：report.md、results.json、build/package/verify/smoke日志、hash清单、离线校验JSON、tmp/与本轮私有Python薄包装/核验脚本、build-root/、pyinstaller-cache/。
- E:/hzz/work/MA9/MA9-worktrees/duel-scan/build/user-test-slot-cf8815b/MA9-preview/：新包唯一根。
任何写入均MA9内，不能删除/移动/覆盖旧dist/install/包/日志、不能绕过宿主删除守卫。不要调用会覆盖既有目录的build_windows_package.ps1或原build_agent默认输出。根外MutualExclusionAllocator不触碰，六个大型multiplayer_loop分片不读入模型上下文；允许工具逐文件复制/哈希，不解析或生成内容。data/generated只读复制，不重建。04暂停。

必读：主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md；lane的tools/build_agent.py、tools/prepare_portable_preview.py、agent/ma9_agent/duel_slot_test.py、runtime_action.py新增action、assets/interface.json新GUI任务和pipeline/duel_slot_test.json、docs/zh_cn/develop/duel_slot_test.md。
证据：
E:/hzz/work/MA9/MA9-evidence/20260924-05H-test-wiring/{results.json,user-request.template.json,schema-delta.log}
E:/hzz/work/MA9/MA9-evidence/20260924-05HR-wiring-review/{report.md,results.json}
E:/hzz/work/MA9/MA9-evidence/20260924-05HR-orchestrator/results.json
E:/hzz/work/MA9/MA9-evidence/20260924-native-slot-entry/{results.json,process-result.json}
旧02B的assemble/verify脚本仅阅读或复用无副作用函数，不执行其main，不改原证据：E:/hzz/work/MA9/MA9-evidence/20260923-02B-f5472bc/verify_package.py。

环境：Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止。全部-X utf8 -B、PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP同设本证据tmp，实测gettempdir并记录。PYINSTALLER_CONFIG_DIR设本证据pyinstaller-cache，不借用或清理全局缓存。所有命令cwd本lane，不从main导入业务源码。不改全局Git配置；safe.directory仅命令级。

构建方式（本轮私有薄包装，禁止改受控工具）：
1. importlib加载本lane tools/build_agent.py（不执行main直到覆盖输出设置）。只把模块ROOT改为本证据/build-root，AGENT_DIR显式保持本lane/agent；确认main.py实际源为cf8815b。sys.argv只给工具名、不传--clean，然后调用main。现有工具内部PyInstaller --clean只针对本轮全新cache/work/spec目录；若宿主仍拦截停止上报，不去解除守卫/提升删除权限。所有输出路径实际resolve并检查在两授权目录内。目录存在不重试覆盖，失败保留，报告总控。
2. 使用本lane prepare_portable_preview.py的原main与完备性检查，通过私有包装覆盖：ROOT=本lane；SOURCE_UI=E:/hzz/work/MA9/install（只复用现有MFA UI/host，逐项hash，不复用其Agent/interface/config）；AGENT=本轮build-root/build/agent/win-x64/dist/ma9-agent；BASE=本lane/build/user-test-slot-cf8815b；DESTINATION=BASE/MA9-preview；TASKS仅{多人运行时_数据自检,对决_隔离单槽定位测试}。sys.argv仅工具名，不zip。运行前确认DESTINATION不存在，避免原工具删除分支。
3. 资源、5项runtime数据必须来自cf8815b lane；若OCR二进制模型为未跟踪缓存缺失，明确列出所需文件与主仓库现存受信本地缓存来源/哈希，再复制到本次包资源，不写lane源码、不联网下载，不用旧资源整体覆盖。除明示缓存外，资源逐文件与lane一致。
4. 便携标记只能由原prepare main在assert_preview_complete成功后写出。不得手工补标记，不修改完备性/隐私检查。先保存“无config、无garage、完备性通过”的证据与空标记hash，然后才进行下一步私有测试配置；不要对含私有config的最终包谎称仍通过原发行隐私检查。
5. 发行组包完成后，按用户明确授权仅新建包内config/duel_slot_test.json：读取05H私有user-request.template.json，runtime_root填当前包根resolve绝对路径，其余原样保留；account_confirmed=true、environment=defense_test、choose=false、slot1、Nevera car_d51e24a1fd5f83c0。不得复制任何garage.json/主账号配置；真实用户标签不得提交Git。此包带私有配置，只留本地、不压缩发布上传。报告公开摘要只写标签已绑定。
6. 原prepare生成的README包含多人3/20局开赛说明，不适用于本包：只在本次包里替换该说明为单槽定位流程。用户自行核对测试账号→1280x720中文资格赛已展开第1地图→运行新增“独立账号单槽定位测试”→停Nevera详情；GUI成功不是业务证据，保留debug/duel-slot-test-*.json及框架日志；本席不操作设备。明确本包不可移动目录后直接运行，移动后须重新绑定runtime_root。GUI只保留上述两项，不出现自动开赛任务；保留所有原资源节点只作为库不自动执行。
7. 包根新建TEST-BUILD.json：完整source HEAD、版本v0.0.0-slot-locate-cf8815b、构建脚本/解释器与exe哈希、构建根、源界面与包界面变换清单、marked-root阶段/私有绑定阶段、device_test=not_run、choose=false。绝不称整个包与source逐字节同一，因为interface明确过滤和child_exec变换。

必须实跑的包核验：
- PyInstaller内部递归代码对象比较（含数值常量，不忽略业务常量；仅允许源码目录前缀元数据差异）：至少runtime_action、ma9_agent.duel_slot_test、duel_slot_entry、duel_slot_selection、duel_lineup_slot、duel_vehicle_runtime、duel_vehicle_screen。旧verify仅4模块不够；可复用read_pyz/compare_code函数写本轮核验器，runtime_action用顶层key与agent/runtime_action.py。确保新module真实存在。不得只查字符串。
- 负对照：只读git show基点1634c1708c9e806f43454369773a586cef26a2dc:agent/runtime_action.py到本轮tmp，核验该旧runtime_action与包内新模块必须不一致、非0；证明核验器有效。不要尝试导入不存在的旧新模块来伪造负对照。
- Agent目录、资源/数据逐文件hash及完整集合比较，记录缓存例外；包界面严格只有自检+单槽定位，准确child_exec指向本轮exe，独立root标记为空且由prepare产出。
- 用本lane已审load_slot_test对最终包配置作纯文件校验（不调用run_slot_test，不注入context、不capture），确认slot1/目标Nevera/classS/choosefalse/根绑定。这只证明源码加载器能读配置，不能冒充已运行包内代码。
- 离线exe无socket参数冒烟：预期Usage并exit1、无连接；若出现exit21/zeromq断言，不准当预期1通过，保留日志并停止交付验收待总控。此前review平台exit21、总控同lane当前/旧版导入与两定向均exit0；未证平台退出差异原因，不声称已修复。
- 如宿主允许，在本证据tmp构造目录联接/符号链接指向本证据另一子目录（两者都在MA9内），验证输入/输出逃出测试根会被拒且不触设备。宿主禁止就记录未验证，不绕过权限；不是强行必须建链接。不要递归删除链接或夹具。
- 起止git status为空、HEAD不变、diff --check通过；契约仍祖先。

复用而非重跑：总控Agent252/tools30 exit0、05H新增pipeline+变更interface两项schema exit0，旧资源历史schema复用，native OCR18/18；本轮包界面经过过滤，应对最终interface及新增pipeline实跑schema（可用本轮tmp小资源目录+源validate_schema工具，旧未变资源复用），不能说全27重跑。不要跑npm或重建大分片。
每条命令记录完整命令/真实最终exit；长进程续等，不能用OK文本代替退出码。限有界定位错误，不修改业务或工具源码；遇到必须变更源码/替换旧目录/构建反复失败就完整回总控。

结束：构建/组包/模块比较/负对照/哈希/根绑定校验/精确exit1无socket冒烟均达成，报告本地包路径和入口、版本、exe SHA256、精确源码HEAD、变换与私有配置阶段、实跑退出码与历史复用、未覆盖。owns三空，受控文件不变，不提交/合入/推送/发布/开GUI或设备。本席不宣布实机放行；总控验包后由用户串行测试。
