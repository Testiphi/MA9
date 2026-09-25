# MA9-05L-赋值后阵容车型确认窄修复

模型ds-v4.1flash，请求high；平台无独立开关按实际默认记录，不自动max。用户外部全新对话，不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整基点/预期起始HEAD ddcb200c066ae7017d48914e46af0ce242415c37。不checkout/reset/merge，不同步main编排。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先复用不重冻。

实际成功与失败分开：用户09:53已实际把Nevera放入第1槽并停阵容，截图支持；程序business却assignment_unverified/assignment_complete=false，after=null，selection_attempted=true，starts_race=false。选车动作成功，自动回页确认未闭合。不得让用户清空阵容/重复选择，也不得直接把False报告改True。
原因已离线证实：_finish_target选择后的确认把(0,170,1280,190)大范围OCR直接match_vehicle，混入4837S等非车型文本，三组独立OCR内容都None；隔离实际RIMAC/NEVERA名称行都命中。诊断隔离按文本选行只是证明原因，生产不得按目标名字过滤自证。
证据E:/hzz/work/MA9/MA9-evidence/20260925-095331-assignment-postcheck/{business.snapshot.json,maafw.snapshot.log,user-success.png,error-screen.png,replay.json,repro.py,results.json}。若error-screen.png不存在，使用user-success.png经已有normalize只作离线输入，不改原图。图片实际尺寸必须核对，不能拉伸非16:9帧。原探针首次遇非OCR日志KeyError已保留，最终exit0；这不是生产缺陷。

精确owns=[agent/ma9_agent/duel_vehicle_runtime.py,agent/tests/test_duel_vehicle_runtime.py]；owns_new=[]；owns_generated=[]。可在现有runtime内加小纯helper，不能改共享vehicle_screen/05F/05G/observer/defense_setup/slot_test/runtime_action/GUI/interface/pipeline/schema/数据/编排。所有写入MA9内，旧包及原证据不改，不运行旧证据main覆盖输出；六个大分片不读，data/generated只读，根外MutualExclusionAllocator不碰，04暂停。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md；本lane两授权文件全文，以及duel_lineup_slot返回几何/标题/证据与duel_slot_selection的后置同槽门禁只读；冻结证据replay.json（真OCR全行）与截图。

窄任务：
1. 只修选择后阵容车型确认的取词范围/分组，不修改已经实机成功的列表定位、详情身份、名称优先分数策略、单次选择点击、占用/按钮守卫或回到同槽的05F校验。不得降低match_vehicle相似门槛或expected_id过滤文字后假确认。
2. 用真实页面布局把展开面板的车型身份区域与性能分/等级/赛道/邻列文字分开；可复用已有只读observer的独立几何来定位展开面板，或通过有证据支持的通用空间范围/两行分组。必须解释选择依据并验证1..5槽版式，不能只对第1槽Nevera硬编码，也不能把数字统统删掉破坏004C/R1/370Z等合法名字；单字车型后缀R不可随意丢弃。
3. 在同一采样帧上分别确认回到阵容与展开面板车型等于目标；不可从点击前详情/请求target_id复制结论。目标不可读、其他车型、多候选/错误页仍assignment_unverified，不开始比赛、不补点选择、不继续下一槽。保留scan原始证据与选择已尝试事实。
4. 必须仍由真实scan返回assigned/assignment_complete=true后，外层05F重新读稳定同槽才能最终assigned；不能为绕过这个早期失败直接跳过scan证明。若需要存小型post-selection evidence可在runtime结果附加，不改既有keys语义。
5. 本次日志显示回页已经稳定到达但名字污染，非等待次数不足。因此本轮不扩大等待预算、不重写全局恢复、不消除既有默认评分排序。若发现独立阻塞先给证据，不借机扩修。

测试与验收：
- 原始三组OCR行与真目录：旧宽区域匹配拒绝，新定位身份区域命中Nevera；保存红绿。原图像+OCR用于离线回放，若用黑/合成帧只证明文字链，要如实说明不可称真实几何通过。
- 同一版式改成其他完整车型、R后缀与数字车型名不能误读/删词；性能分4837S、地图名、邻列字母/数字不应进入展开车型身份；明确错误车型必须拒，不能靠过滤到target词放行。
- 五槽展开几何通过已有测试样本/合成移位代表性覆盖，不能改传expected_slot来影响观察结果。生产位置是从实际frame得来，而非文件名/fixture expected。
- _finish_target或scan→05F组合：确认目标返回后可以assigned，同槽外层保持；原占用/选择按钮/错误车型/choosefalse停详情都不回归。别mock被测函数返回assigned自证。
- 参数/返回签名兼容，原正式防守调用不变，starts_race恒false。无需用户重复旧包或补截图。

新证据E:/hzz/work/MA9/MA9-evidence/20260925-05L-lineup-identity/，已存在停止；可写report.md/results.json/red.log/green.log/targeted.log/agent.log/tools.log/replay-results.json/schema-reuse.json及tmp小夹具/探针，原证据不改。Python MA9_PYTHON优先否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止；全部-X utf8 -B、PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP同设本轮tmp并测gettempdir；cwd lane不从main导入业务源码。
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_runtime.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -v
& $lanePython -X utf8 -B -m unittest discover -s tools/tests -v
基线runtime25、Agent291、tools30（lane既有截图skip按实测）。每项真实最终exit，OK但非0如实报。不改资源schema，机械证明后复用05K两变更项+未变资源历史，非全27重跑；不npm/打包。Git命令级safe.directory，起止status/完整SHA/契约祖先/精确diff记录，不改全局设置。
最多两轮有界修复，成功自动本地提交仅两授权文件；未解决带证据回总控。禁止真实Controller/ADB/MuMu/GUI/游戏、重选/清空/开赛。若需要真实OCR静态验证，只允许复用内存图像输入、所有input方法抛错的原生离线探针模式，绝不连接设备，输出只本轮目录。
回传完整SHA、模型实际平台档位、diff、空间区域/分组依据、红绿与假设范围、最终exit计数、源码与私有证据、未覆盖。用户视觉赋值成功可保留，但此修复不等于自动确认已实机通过；总控验收/独立复核后再决定如何复用既有阵容验证，不能要求用户为假设清阵容重跑。
