# MA9-05JR-单槽名称优先策略独立复核

模型登记Qwen3.8-Flash；平台实际默认，无独立high/max开关如实注明，不自证底层身份、不自动max。用户全新带本地工具对话，与ds owner及总控验收分离；不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整基点da22bf1bc844d762d75fb70977284dced7b09e11；预期起止HEAD612531f0107e8125e0106fe680059a03f849d8c0。恰1提交4文件，不checkout/reset/merge；main新编排不用同步。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先复用不重冻。
精确owns=[]、owns_new=[]、owns_generated=[]，所有受控文件只读不代修/提交/合入/推送。只允许新目录E:/hzz/work/MA9/MA9-evidence/20260925-05JR-name-first-review/下report.md/results.json/runtime.log/slot.log/probe-results.json及tmp小探针；目录存在停止，旧证据不改、旧main脚本不执行。所有写入MA9内。不设备/GUI/Controller/ADB/MuMu/构建/依赖安装，不读六大分片，data/generated只读，根外MutualExclusionAllocator不碰，04暂停。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md、agent/orchestration/prompts/05J-name-first.md。
本lane四文件全diff：duel_vehicle_runtime.py及其测试、duel_slot_selection.py及其测试；duel_slot_test.py和defense_setup旧调用只读。
证据20260925-001628-nevera-detail-live/{diagnosis.json,business.snapshot.json}；20260925-05J-name-first/{results.json,red.log,green.log}；20260925-05J-orchestrator/results.json；20260925-02I-612531f/results.json（总控依用户要求先构建的本地待复核进度包，不实机放行）。均位于E:/hzz/work/MA9/MA9-evidence/。

用户裁决优先名称匹配跑通单槽选择，不要求详情图或修分数OCR。本轮只取消单槽流程默认的隐式列表/详情分数相等要求；旧正式防守排序路径必须保留。
核查：
1. scan verify_list_detail_rating关键字默认True，非bool在任何上下文/动作前拒绝；helper透传默认True、assign_visible未改、旧调用不传参数仍严格。
2. SlotSelectionRequest默认False，校验与report.request及scan透传准确；05H加载器默认取得False，但GUI choose仍False，未擅自开选择。检查新增dataclass字段在中间对旧位置参数的兼容性：仓库实际调用是否全关键字，不能把无证据外部调用当生产阻塞，也不能隐瞒API风险。
3. False只跳过隐式list/detail比较；明确expected_performance/stars仍拦截，不更改原始4897为4837。详细身份wrong_detail/detail_not_verified、占用/按钮/返回同槽/starts_race=false不能放松；verifyTrue裁切兼容与旧失败场景不变。
4. 用独立桩证明列表4837/详情4897且相同目标：False时chooseFalse停detail_verified不返回；True时保持mismatch；有显式expected=4837仍拒。chooseTrue不允许绕过占用/不可选/身份后置检查。不能mock被测函数结果自证，stubOCR/点击/详情依赖可用。
5. report添加list_detail_rating_compare=disabled应如实；红绿日志是新代码verifyTrue/False的策略对照，若未执行改前源码，不能称旧提交独立红转绿。sharedhelpers声明严格bool与真实验证位置需准确区分。
6. 找到真实风险列行号/可达前提/最小复现；不要为此轮重写性能分ROI/解析、返回页等待或其他通用流程。既有返回末轮仍点back的问题不是本轮目标，记录不得自行扩修。

环境：MA9_PYTHON优先否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止。所有Python-X utf8 -B、PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP同设本证据tmp并测gettempdir，cwd lane不从main导入业务源码。Git仅命令级safe.directory，起止status/branch/完整HEAD/祖先/diff边界记录。
独立最少命令：
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_runtime.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_slot_selection.py -v
预期25及36，保存最终exit，OK文本不能替代退出。自写少量机器断言探针，禁止设备。总控Agent285/tools30(29+1skip)exit0已在同SHA实跑，核对后复用不再全量；schema引用准确为05H两变更项+未变资源历史，不是05H全27重跑，源码四Python不改输入。
结束回传项目/模型平台实际档位/cwd分支/完整起止SHA/有无阻塞/问题严重性与复现/命令最终exit与计数/实跑复用区分/证据路径/未覆盖。不能宣布包实机就绪、不能代修；复核后总控再合入并决定包放行与选择模式接线。
