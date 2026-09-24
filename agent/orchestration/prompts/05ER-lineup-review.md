# MA9-05E1R-标题门禁收口短复核

模型：Qwen3.8-Flash；档位：平台实际默认，如实记录，不编造high/max或底层身份自证。用户新建独立只读对话运行，与ds owner分离，不创建下级智能体/对话/worktree。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-scan
branch：lane/duel-scan
审查基点：cdeee38cf99ff5efe066f0d189bf6b647eb9ac17
预期起止HEAD：17371c9d96eb2caaaf3083c26ca87b16a40bf2ee
契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，检查祖先复用，不重新冻结。只审上述差异；前一05ER几何审查不重复。

精确边界：owns=[]、owns_new=[]、owns_generated=[]；所有受控文件只读，不代修、不提交/合并/推送。唯一私有输出E:/hzz/work/MA9/MA9-evidence/20260924-05E1R-title-review/下report.md、results.json、targeted.log、probe-results.json及tmp/小夹具/只读探针；目录存在停止上报，不覆盖旧证据。
不安装依赖，不接OCR执行引擎/Controller/ADB/MuMu，不点击或运行游戏，不打包。六个大型multiplayer_loop分片不读入上下文；data/generated只读；根外MutualExclusionAllocator不接触。

必读：
E:/hzz/work/MA9/agent/lanes.yaml（05 reviewer，主仓库规则权威）
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
先读实际delta：agent/ma9_agent/duel_lineup_slot.py、agent/tests/test_duel_lineup_slot.py，再读以下证据：
E:/hzz/work/MA9/MA9-evidence/20260924-05ER-lineup-review/report.md（历史F1/F3/F4/F5/F7）
E:/hzz/work/MA9/MA9-evidence/20260924-05E1-title-guard/{results.json,tmp/title-counterexamples.json,replay-results.json}
E:/hzz/work/MA9/MA9-evidence/20260924-05E1-orchestrator/results.json
不要运行旧replay.py的main，它会覆盖旧报告。可读取清单或写本轮小探针。

本轮唯一审查目标：确认门禁和证据语义的收口正确、没有破坏此前几何结果。不得为review自行增加新的视觉识别需求或重写几何。
重点：
1. signature(frame,ocr)不变；geometry-only仍可返回槽号，但basis='geometry_only'/title_guard_passed=false；有可信标题且几何通过才geometry_and_title/true；拒绝都rejected。slot_verified不是动作授权，没有can_click/action_ready。
2. 标题ROI(62,86,110,52)、整串白名单、confidence有限0..1且>=.90；低/缺/NaN/Inf/bool置信度拒绝；不同合法标题冲突，相同重复不冲突，车辆选择否决。输入坏box安全忽略，不用标题猜slot、不回退slot1。
3. 几何早退仍保留evidence.title_conflicts等已解析证据；所有新字段在成功/拒绝/不支持尺寸等路径语义一致。若文本空白处理只trim两端而不消除内部空白，说明真实行为与文档是否一致，按影响区分非阻塞假阴性与误放行，不扩大为新OCR模块。
4. 原几何常量/规则应无行为改变，折叠标记仍可缺失；“两项相关几何+可选佐证”表述准确，不宣称三路独立强制。无标题成功只是几何一致，不证明真实来源/动态稳定/可安全点击。
5. AST与常见IO拦截只辅助，不作通用无副作用形式证明；检查真实代码仍无IO/设备调用。
6. 新接口ImportError不是行为红转绿；真正红证据是同帧同标题输入对旧cdeee38接受、当前17371c9拒绝的6类反例。报告不能拿ImportError冒充已锁定旧行为。

最低验证：
Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；存在才-X utf8 --version，缺失停止不切PATH。全部Python-X utf8、cwd本lane，不从main导入源码。TMPDIR/TMP/TEMP均设本证据tmp，记录实际gettempdir。
Git仅-c safe.directory=E:/hzz/work/MA9/MA9-worktrees/duel-scan；开工/收工核对status/branch/完整HEAD与祖先，不checkout/reset/merge，不改全局Git。
& $lanePython -X utf8 -m unittest discover -s agent/tests -p test_duel_lineup_slot.py -v
记录最终退出码与数量。再在一张真实正例上抽查：geometry-only、有效标题、好友挑战、confidence=.01、两个不同标题及几何早退保留冲突。用现有私有图片只读输入，输出到你自己的probe-results.json，不传文件名或expected_slot给观察器。
总控已独立Agent186、tools30(29通过+1既有截图skip)exit0，18几何等价、6伪正例拒绝通过，schema输入不变复用27exit0。本短复核不重复全量/schema/npm或整套几何扰动扫描；复用明确来源。未运行真实OCR，不声称任何MaaFW OCR不可用。

结论必须明确“无阻塞/有阻塞”或证据不足；问题给文件行号、最小复现、影响与最小建议，不代修。尤其分清本观察模块可合入与可接选车执行：后一阶段还须真实页面来源、真实OCR、稳定帧一致、入页/回页同槽，当前都未实现。进攻2–5和动态帧仍无证据，但可限定后续先做防守测试路径，不要求阻塞所有离线开发。
回传项目、实际模型/平台/档位、cwd/branch/起止完整SHA、工作区状态、命令/退出码/数量、问题清单、复用证据与未覆盖范围。不宣布实机通过或可安全选车。
