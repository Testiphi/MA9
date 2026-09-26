# MA9-05O-五槽地图只读观察与稳定确认

ds-v4.1flash，请求high；平台无独立档位开关按实际默认登记，不自动max。用户外部全新带本地工具对话，不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整基点/预期起始HEAD 0b8f1de467c0d89645d2c25efa44c0dcad32850e。不checkout/reset/merge，不同步main后续编排。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5：验祖先复用不重冻。

目标：先在防守测试阵容页可靠读出五张地图及其槽号，以后接参考表选车。五个槽位/五等级已逐一实机选车成功，现有五车保留。本轮不选车、不排策略、不开始比赛，不宣称自动五槽循环。
精确owns=[]，owns_new仅agent/ma9_agent/duel_lineup_maps.py、agent/tests/test_duel_lineup_maps.py；owns_generated=[]。
其他全部只读：尤其duel_map_screen.py/duel_defense_setup.py归06不得改；observer、selection_runtime、选车模块、runtime_action/__init__、GUI/pipeline/interface/schema/catalog/参考表/编排均不改。禁止生产monkeypatch旧模块。
全部写入MA9内；data/generated只读；不读六大multiplayer分片；根外MutualExclusionAllocator不碰，04暂停。不GUI/设备/ADB/MuMu/真实Controller/游戏/构建/打包/推送。离线原生OCR只允许内存CustomController，全部输入方法抛错。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md。
lane只读：
- duel_map_screen.read_five_tracks：现有两行参考匹配/去重/x排序，但部分结果会重新编号；漏图不能使用此编号当真实槽号。
- duel_lineup_slot.observe_lineup_slot、LINEUP_TITLE_ROI、evidence.cells/panel。
- duel_defense_setup._read_tracks：一次完整就返回，不是连续双帧证据。
- selection_runtime.frame_of/ocr_roi坐标语义；duel_slot_verify稳定读取参考，但不要引入其磁盘配置/车型。
- data/generated/duel_auto_candidates.json程序读取/局部检索，不全贴。
- tools/probe_duel_tracks.py仅参考，禁止normalize拉伸非原生图片；旧探针不得原地执行覆盖。

建议API（小调整须解释）：
observe_lineup_maps(frame, *, ocr, reference) -> dict
read_stable_lineup_maps(context, reference, *, attempts=120, timeout=30.0, interval=0.3) -> dict
前者纯函数不改入参、无IO/状态；后者仅采集/OCR/时钟，无磁盘/账号/车库/输入操作。

单帧要求：
1. 只接受1280x720，不拉伸。真实observer同帧geometry_and_title严格标题通过且资格赛才支持；挑战明确unsupported_environment。缺标题/冲突/几何不清拒绝，无预期槽参数/默认slot1。
2. 每图必须同帧直接读到大地图和小赛道，两行共同对应参考表同一对；不能靠文件名、预期列表、上帧或已知样本补全，不读车型分数决定地图。
3. 复用read_five_tracks基础解析，但新层必须校验五对结果与observer的五个几何槽区间一一对应。缺一图不能将后续槽前移；缺行/未知/多候选/重复组/参考匹配歧义均不verified。五图全齐才输出可用确认；partial只能诊断且真实槽位有证据。
4. 审视旧函数只取前两行/最高匹配且无歧义间隔的路径，增加保守核对，不改旧函数/全局阈值。同分或无法唯一决定则拒绝，不能依赖目录顺序。不开发泛化OCR纠错/别名，不硬编码本次地图。
5. 至少返回status/maps_verified/expanded_slot/page_title/tracks(slot,big,small,observed,confidence与框/几何证据)/reason/evidence；恒read_only=True、selection_attempted=False、starts_race=False。不添加can_click授权。失败不残留verified=True。
6. 缺失/空/坏reference明确失败，不泄漏IndexError；不引入通用状态机框架。

稳定读取：
- 参数在任何context前严格验证：attempts非bool整数2..120；timeout有限正数<=30；interval有限非负<=1；数值bool拒绝。
- monotonic截止一次创建，每次新capture前检查，失败/首帧不重置；可sleep，不硬杀在途OCR，不声称硬墙钟30秒。
- 独立frame_of每次采样，同帧标题ROI和地图ROI（旧(55,165,1190,160)供参考），合并避免重复行。真实observer/本模块判定，不mock成功。
- 连续两次完整且五对slot/map和expanded_slot一致才确认；异常/缺失/换槽/换序打断。微小框抖动不必阻塞同语义，不能跨帧拼五图。返回最新证据。
- 达预算明确unverified及有界诊断/实际samples。禁止scan/assign/entry/plan_attack/run_task/post_click/post_swipe；只读采集。

新证据E:/hzz/work/MA9/MA9-evidence/20260927-05O-readonly-maps/，已存在停止。允许report.md/results.json/targeted.log/agent.log/tools.log/replay-results.json/schema-reuse.json/tmp与原生OCR资源。旧证据不动，不运行旧main，不写旧__pycache__。
原生1280x720样本来源：
- 20260924-05E-lineup-slot/replay.py的SAMPLES，防守展开1..5及已选车，进攻/车库反例；只读提取清单，不执行旧main。
- 20260924-native-lineup-title/results.json中路径/hash。
- 20260924-native-lineup-title/probe.py、20260924-native-slot-entry/probe.py为真实MaaFW内存Controller/OCR参考；无pip OCR不等于无OCR。
- 最新20260927-slot3-fe3-assigned、20260927-slot4-success-slot5-config、20260927-slot5-success-left-edge的用户截图作人工参考，非1280x720不得拉伸冒充原生输入。
现景五对仅作人工核对线索（不进代码，须原图/参考表实读核对字形）：旷野飙车/世外葡园、花都疾驰/地铁冲刺、高地穿梭/魔法岛屿、狮城/海岸飞驰、凌空之巅/疾速冲锋。
至少原生静态OCR回放旧防守展开1..5；人工冻结/合成/原生分别标注。若真实OCR无法读齐，保留失败和最小缺口，不降低守卫凑绿。不要求用户清空或重复选车。静态通过不代表设备动态通过。

测试：
- 五展开几何对应五槽；真实OCR/冻结与合成分别标注。
- 缺大/小行、四组、错位置/跨槽拼接、无关中文/车型污染、候选同分/歧义、重复、非法尺寸、坏reference、错标题/挑战；锁定缺图不重排放行。
- 连续2帧/单帧不足、中间异常/缺失/换槽/换序清零；截止/采样上限/提前成功、最新证据、同帧OCR；参数前置拒绝。
- 仅IO边界可桩，真实被测逻辑不得mock成功；输入操作若调用即抛错。旧防守/地图生产文件不变。

Python优先MA9_PYTHON否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止。全部-X utf8 -B、PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP同设新tmp并实测gettempdir；cwd lane，不导入main业务。
运行unittest discover -s agent/tests -p test_duel_lineup_maps.py -v、agent全套、tools全套。基点Agent345/tools30(1既有skip)。记录真实进程exit；原生依赖退出期exit21需保留且区分测试OK，不能吞码或写成0。
schema输入未变机械复用，不全27重跑、不npm。最多两轮有界修正，仍阻塞回传不扩范围。
完成按用户政策只两新文件本地提交，未合入/推送/打包/实机。回传模型实际档位、完整SHA/clean/两文件diff/祖先、API拒绝语义、真实OCR路径hash/人工真值、测试与进程exit/复用/未覆盖。总控验收及独立复核后才接GUI只读入口/用户包，再做地图策略候选。