# MA9-05HR-隔离账号与GUI定位入口独立复核

模型登记Qwen3.8-Flash；平台实际默认，无独立high/max开关如实记录，不自证底层身份，不自动升级。用户全新带本地工具对话，独立于总控实现者。不得创建子智能体/对话/worktree。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-scan
branch：lane/duel-scan
审查基点：1634c1708c9e806f43454369773a586cef26a2dc
预期起止HEAD：cf8815b2268d07142b679b06272101e9f1b2191e
总控已快进该lane到待审提交，不自行checkout/reset/merge。基点..HEAD恰1提交8文件，main后续编排无需同步。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先并复用，禁止重冻。此轮是总控新增测试入口，不是改冻结五模块行为；49个既有GUI任务名称/入口/相对顺序不变，仅新增第50项及对应断言。

边界：owns=[]、owns_new=[]、owns_generated=[]。所有受控文件只读，包含总控独占runtime_action/interface/测试文件，严禁代修、提交、推送。
新私有证据目录E:/hzz/work/MA9/MA9-evidence/20260924-05HR-wiring-review/，已存在停止不覆盖。可写report.md、results.json、targeted.log、probe-results.json、tmp/小夹具与只读探针。旧证据不改、不运行旧脚本main。不连接真实Controller/ADB/MuMu/游戏，不开GUI、不构建/安装依赖/生成资源；六个大型multiplayer_loop分片不读，data/generated只读；根外MutualExclusionAllocator不接触，04暂停。

必读：
E:/hzz/work/MA9/agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md。
本lane基点..HEAD全部8文件diff，完整读agent/ma9_agent/duel_slot_test.py和agent/tests/test_duel_slot_test.py；runtime_action新增DuelSlotTestAction及find_project_root；新增assets/resource/pipeline/duel_slot_test.json、docs/zh_cn/develop/duel_slot_test.md；interface只读此diff不扩大任务。
已复核05F/05G模块可按接口读，不重复几何审查。
E:/hzz/work/MA9/MA9-evidence/20260924-05H-test-wiring/{results.json,targeted.log,agent.log,tools.log,schema-delta.log}
E:/hzz/work/MA9/MA9-evidence/20260924-native-slot-entry/{results.json,process-result.json}（18/18真实静态OCR，输入全部禁止，非实机）。
私有user-request.template.json只在本机用于核对目标，不把账号标签复制到受控文件或外部报告。目标catalog确切为Rimac Nevera，S级，car_d51e24a1fd5f83c0；不是Nevera R。用户确认拥有，目标第1槽，首次仅定位。

独立审查问题：
1. 本测试额外要求便携标记、请求绝对runtime_root等于解析根、environment=defense_test、account_confirmed严格true。无标记祖先根不能偷偷沿用主账号garage；本模块根本不读garage.json。明确这只是文件配置隔离和用户账号确认，不是自动游戏账号认证；find_project_root全局旧规则未改。
2. 路径resolve+is_relative_to是否阻止输入/输出逃出所选根（含符号链接/目录联接形态）；请求缺失/类型错误/目标未拥有/槽号非法/choose非false应在设备调用前失败。恶意本地修改所有可信输入不属于此隔离保证，别宣称防恶意管理员。
3. 车型等级来自包内catalog；目标唯一匹配，confirmed_owned_ids不能用字符串冒充列表；现存05F仍在任何frame前验证最终request。不得拿bool当slot。额外字段是否会改变choose或重定向路径。
4. GUI新增任务经新DirectHit→ma9_duel_slot_test→run_slot_test→已审05F/05G；无后继开赛/导航，custom_action_param不能打开choose。成功必须located，失败返回false不冒充完成。保留原49任务与公共冻结实现，新增断言不是放松旧校验。
5. report每次唯一名且在同根debug，含实际runtime_root/account_key/request/业务证据；账号标签不代表视觉身份认证。入口失败/scan失败与异常处理如何报告、是否会丢失可能已点击事实，应按实际影响定级。报错路径不能被描述为无副作用。私有配置不进Git。
6. 测试fixture不得借main车库、不得在测试里补override掩盖真实根策略问题；当前测试使用显式root是被测函数接口，真实action入口也要核查。可补小型夹具探针覆盖符号链接或根绑定（宿主不允许建链接则如实记录，不越权）。

最低验证：MA9_PYTHON优先否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止；所有Python-X utf8 -B、PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP同设本轮tmp并实测，cwd本lane不从main导入业务模块。
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_slot_test.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_runtime_root.py -v
保存最终退出码与实测数量。另做少量独立带机器断言的边界探针，stub设备接口即可；绝不使用真实控制器。
总控main同提交已Agent252/tools30全通过exit0，明确复用不再全套。schema仅变更interface+新增pipeline两项实跑exit0，未变旧资源复用既有结果；不是完整27重跑，也不是27原封全部复用（interface已变）。可检查差异/输入，勿读大型分片或自行重跑20分钟完整schema。
Git仅命令级safe.directory，开工收工记录branch/完整HEAD/status/祖先/精确8文件边界，不改全局设置。

结束：输出有/无阻塞、真实缺陷与文档/防御性建议分级、行号/前提/最小复现；输出命令最终exit/计数、复用与实跑、证据路径、未覆盖范围。不能代修、不能宣布包已验证/实机就绪；下阶段才由总控准备准确构建源和私有配置绑定，再由用户串行实机。
