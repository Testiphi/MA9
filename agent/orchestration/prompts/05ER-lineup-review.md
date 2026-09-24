# MA9-05ER-只读槽位观察器独立复核

模型：Qwen3.8-Flash；档位：平台实际默认思考设置，如实记录，不编造high/max或底层身份自证。本轮首次有界Flash代码复核试点，用户当前平台免费/不限量只是用户体验，不作通用能力/成本保证。
用户在外部平台全新对话运行，与ds-v4.1flash owner独立。不得创建子智能体/对话/worktree，不修代码、不继承owner自评结论。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-scan
branch：lane/duel-scan
完整审查基点：02ee41c239bf45734ba3fa5ee44dc9dc7889ec5c
预期起止HEAD：cdeee38cf99ff5efe066f0d189bf6b647eb9ac17
只审该区间两个新增文件：agent/ma9_agent/duel_lineup_slot.py、agent/tests/test_duel_lineup_slot.py。未合入main、未接执行器。
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5；核对祖先后复用，不重新冻结。

精确边界：owns=[]、owns_new=[]、owns_generated=[]；所有受控源码/测试/文档/配置/状态只读。私有输出仅E:/hzz/work/MA9/MA9-evidence/20260924-05ER-lineup-review/下report.md、results.json、targeted.log、replay-results.json及tmp/只读探针/小夹具。目录已存在停止报告，不覆盖旧证据。
不安装依赖、不打包、不提交/推送、不创建Controller/ADB连接，不点击或操作GUI/MuMu/游戏。不读六个大型multiplayer_loop分片，data/generated只读，不触根外MutualExclusionAllocator。

必读：
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/agent/lanes.yaml（主工作区当前规则权威，05 reviewer本轮为Flash）
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
先独立看实际diff、源码与测试，再读：
E:/hzz/work/MA9/MA9-evidence/20260924-05E-lineup-slot/{report.md,results.json,replay.py,replay-results.json,schema-reuse.json}
E:/hzz/work/MA9/MA9-evidence/20260924-05E-orchestrator/results.json
原图清单以replay.py的SAMPLES为准；新图片私有快照在MA9-evidence/20260923-184330-attack-mumu-intake，旧防守样本在MA9/captures。只读原图，不复制到Git。

需求边界：
观察器只读已经打开的五槽阵容页唯一展开槽位1..5；没有预期槽位入参，不靠地图名/车型/账号/票数猜号。未知、非阵容、多个候选须slot=None/slot_verified=false，不能失败默认1。只支持1280x720，不拉伸非16:9图。未来在进入选车前记录槽位、回来复核；本轮不接入口、不选车、不取消正式防守地图顺序保护。

重点复核：
1. 几何实际上由按钮中心、面板亮区右端和“存在时”的折叠标记决定。标记可能完全缺失，不要采信“三路始终独立且强制一致”的说法。缺标记路径是否有足够独立的页面/布局证据，是否有具体可达误报？区分真实样本、合理遮挡/动画与人为完全伪造页面，不凭假设扩修。
2. _panel_run取到的是内容亮区，不一定真实面板边界；114节距、791基准、731展开宽和容差有没有跨槽误判可能？样本外状态只能作为未验证，不能声称一定安全拒绝。
3. OCR参数可省略；省略时geometry-only也返回slot_verified=true。检查该标记的含义是否被文档夸大为完整页面语义验证；提供OCR时标题缺失/冲突是否正确拒绝。低置信度/坏box/多个不同标题的处理与所写输入契约是否一致？给可复现影响，不要求本任务集成OCR引擎。
4. 正例8与负例10的回放是否真实调用观察器，未把文件名或期望slot传入，合成测试是否只复刻实现而遗漏拒绝条件；同图重复/输入不变/尺寸拒绝是否成立。
5. 8个静态正例中只有2张进攻且均slot1，防守1–5旧图只是版式证据。缺进攻2–5和真实过渡动画，不能当成完整实机成功；不能因被测样本全过就允许选择入口接线跳过页面核验。
6. “没有rapidocr/paddleocr/pytesseract/onnxruntime”不等于没有MaaFW原生OCR。当前准确结论是本次没有运行真实OCR，人工冻结标题只验证守卫接线；报告应区分这一点。无需为review安装OCR或接设备。
7. AST导入白名单只能辅助检查无副作用，不能替代功能/误报验证。411行几何代码的复杂度是否必要，可提出非阻塞简化建议，不直接重写。

环境/验证：
Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；检查存在和-X utf8 --version，缺失停止，不换PATH。所有Python-X utf8，cwd为本lane，不从main导入业务源码。TMPDIR/TMP/TEMP同时设本review目录/tmp，记录实际gettempdir。
Git仅-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-scan；开工/结束核对status、branch、完整HEAD与祖先，现场不符停止，不checkout/reset/merge或清理用户文件。
最低命令：
& $lanePython -X utf8 -m unittest discover -s agent/tests -p test_duel_lineup_slot.py -v
独立回放18样本：按owner replay.py清单运行当前观察器，保留geometry-only与人工标题两种来源标记，写入你自己的replay-results.json。禁止直接运行原replay.py的main覆盖其旧输出；可只读runpy加载其清单，或在本review tmp写新探针。不安装依赖或触发设备。
允许少量有界的额外反例检查（原图只读，内存数组不改原图）；结果说明哪些是实际UI、哪些是合成/扰动。不要为了找问题无界随机图搜索。
总控已独立Agent162通过、tools30中29通过+1既有截图skip，退出码0；18静态回放一致、8正例变暗拒绝，schema输入未改复用27exit0。本review不重复全套/schema/npm，明确哪些证据复用。

结束条件：对实际行为/证据/范围完成独立判断，定向测试取得最终退出码，给“无阻塞/有阻塞”或“证据不足复核未完成”。每项发现列文件行号、复现输入/样本、严重程度、实际影响、最小建议，不能只转述owner摘要。
回传项目、实际模型标签/平台/档位、cwd/branch/起止完整SHA、工作区状态、命令/退出码/数量、回放结果与OCR来源、问题清单、证据路径及未覆盖范围。修复归owner/总控重新裁决，reviewer不代修；不宣布合入、实机或安全执行选车。
