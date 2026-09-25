# MA9-05N-裁切卡片覆盖与滚动长名称有界修复

模型ds-v4.1flash，请求high；平台无独立开关按实际默认登记，不自动max。用户外部全新带本地工具对话，不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整基点/预期起始HEAD ff426c671cc23aef207b5f187db2de1105ac9ea7。不checkout/reset/merge，不同步main编排。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先复用不重冻。
精确owns仅4已有文件：
- agent/ma9_agent/duel_vehicle_screen.py
- agent/tests/test_duel_vehicle_screen.py
- agent/ma9_agent/duel_vehicle_runtime.py
- agent/tests/test_duel_vehicle_runtime.py
owns_new=[]；owns_generated=[]。不得改共享vehicle_screen/match_vehicle/_key或其他冻结模块、05F/05G/observer/slot_test/slot_verify、runtime_action、GUI/pipeline/interface/schema、目录/车库/编排/生成器。允许在上述模块内增加小型纯函数，不新增通用框架或依赖。
所有写入MA9内，旧包/旧证据不改、不执行旧脚本main覆盖输出。六个大分片不读，data/generated只读、不生成、不为FE3改目录或加别名；根外MutualExclusionAllocator不碰，04暂停。

任务证据与事实：
1. E:/hzz/work/MA9/MA9-evidence/20260925-115731-slot3-fe3-scan/：business.snapshot.json、diagnosis.json、ocr-frames.json、maafw.snapshot.log、user-stop.png。实际slot3 A级FE3(car_00bbb8ac1279e6f9)，扫描13页到B边界，target_not_found，未点击目标；仅有入页与A级标签2次点击。
2. 11:55:52.818目标右缘片段FORMU / J CHAMPIONSHIP EDIT，估计left1069；11:55:55.256 FORMULAE / P EDITION / GEN 3 EV，left984。两者left+420都>1295，因此完整卡规则跳过。下一次大滑动后只能见左侧IPION尾片段，未留可用完整FE3识别记录。日志证明存在右边缘覆盖缺口，不能仅靠大幅加等待假装修复。
3. E:/hzz/work/MA9/MA9-evidence/20260925-fe3-full-intake/：四张冻结1280x720原图、native-results.json/native.log/process-result.json/native_probe.py。真实MaaFW原生OCR（内存controller，input全拒）实跑exit0：两张完整列表均漏FE3；第一张FORMU + GEN 3 EVO CHAMPION，第二张FORMU + V 3 EV0 CHAMPIONSH。两详情中第一张FORMULA E + N + GEN 3 EV0 CI不匹配；第二张FORMULA E + 3 EVO CHAMPIONSH现有match命中FE3@.786。图中车名确实横向滚动并可能跨首尾显示。
4. 两类缺口都需处理：一是让右侧部分露出的卡片获得安全完整观察机会，二是完整卡/详情的品牌OCR片段与滚动车型名辨认。不要把真实卡片截图稳定与车名文字稳定混为一谈。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md；本lane4授权文件完整源码/测试、共享match_vehicle只读、duel_slot_selection身份/后置同槽守卫只读、上述两套冻结证据。旧单槽Nevera/296GTB已经成功，不能退化它们。

实现边界与结束要求：
A. 原完整名称/正常车型路径优先且行为保持。需要滚动名兜底时，只在擂台模块内建立通用、有证据的品牌+车型片段规则或有界多帧同卡累积，不按FE3/id/截图名硬编码，不改全局相似门限，不凭“请求想要这辆”过滤候选后宣布唯一。
B. 所有候选必须在完整catalog上独立判定，保留Gen2/Gen3等数字、R等单字后缀；只见FORMULA/EDITION/品牌或非常短片段不能成功。同品牌近名/多个候选、低置信、跨卡/跨页混拼、裁切到另一车型完整名等须有拒绝反例。OCR 0/O等混淆若处理，只能在局部规则里有证据约束并检查歧义，不能全局随意替换或丢数字。明确最小片段/置信度/唯一性/几何一致条件及为何足够。
C. 滚动首尾两段的空间顺序不一定是原车名顺序；多帧如要组合，必须先证明同卡/同页几何一致，在滑动/类别变化后清空，不让相邻卡文字拼出目标。也不能只增加次数等待永远不会完整显示的长名称。可以要求更多可读帧后才确认，但预算必须固定且可测试。
D. 扫描覆盖改为有界、可证明的重叠观察/小幅重定位或等效方案，避免忽略右侧裁切候选后一次大滑移到左侧之外。保持安全卡内点击和充分身份核验，不能简单放宽CARD_WIDTH边界后点未安全显露目标；不能无界左右找。记录额外滑动/观察次数或失败原因，页数/重试上限仍有效，达到预算返回page_limit/明确未完成，不能写scan_complete=true或target_not_found冒充遍历完整。
E. 详情同样可能滚动：允许复用本轮局部通用身份逻辑或有界证据累积，不能列表猜中后直接认定详情正确；明确wrong_detail/不明确身份仍拒绝选择。回阵容名字也可能滚动，若复用新helper必须保留05L空间分离和05F独立同槽门禁；没有FE3真实阵容帧要如实记未覆盖，不为完成宣称已验。
F. 名称优先默认与显式expected_performance/stars、占用/按钮、class边界、starts_race=false、只读入口无输入均不破坏。旧正式防守排序仍严格默认，不给弱车算法引入候选乱序。不得修改地图/多槽编排或自动推进4/5槽。

必须验证：
- 四张真实补图的原始native OCR回放：两完整列表需能得到正确FE3，详情可用有界两帧序列确认；第一张详情信息若仍不足允许单帧拒绝，不能要求每一帧强行通过。图片源/哈希、原生OCR与人工/冻结/合成各自区分。
- 真实13页日志中的右裁切→大滑越过场景做独立红用例；新策略通过mock设备边界有界地产生完整观察机会后才定位，不能靠修改文件名/target预期值或mock scan返回值自证。新增完整观察帧可用用户新图，明确是场景拼接而非原运行真实连拍。
- 名称族负例：Formula E Gen2不可当Gen3、Nevera不可丢R、004C/R1/370Z保留、常见短名路径旧结果保持；跨卡/同品牌近名/只有通用尾词/低conf拒绝。
- full details wrongcar/occupied/unselectable不可赋值；只定位不点击选择，赋值后原同槽仍门禁；扫描失败没有新增盲点/第二次选择点击；旧IONIQ左侧统计回归保持。
- 至少重放全部45组实机列表OCR对比旧已正确识别的车辆，变化逐项解释，不仅FE3正例。相关截图星级/像素若用黑图占位必须标为仅文字解析，不冒充视觉验证。
- 严格diff仅4文件，旧策略不变时计数不删/skip不加。不改原证据；真实OCR如需复跑，复制小探针并改输出本轮目录，内存控制器input全抛错、不得连接真实设备。

环境：MA9_PYTHON优先否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止；全部-X utf8 -B、PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP同设本证据tmp并测gettempdir，cwd lane不从main导入业务源码。Git仅命令级safe.directory，起止branch/status/完整HEAD/祖先/差异边界记录。
新证据E:/hzz/work/MA9/MA9-evidence/20260925-05N-rolling-coverage/，已存在停止；允许report.md/results.json/red.log/green.log/targeted-screen.log/targeted-runtime.log/agent.log/tools.log/replay-results.json/schema-reuse.json及tmp小夹具/探针，失败日志另名保留。
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_screen.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_runtime.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -v
& $lanePython -X utf8 -B -m unittest discover -s tools/tests -v
基点Agent308；screen6/runtime33；tools30（lane既有截图skip按实测）。每条保存真实最终exit，不能OK替代进程退出。schema输入不改则机械复用05M两变更项+旧资源历史，不全27重跑，不npm/构建/生成大分片。

最多两轮有界修复；若证据不足或不得不改冻结层，停止并回传最小阻塞，不擅自改边界。完成后自动本地提交仅4授权文件，不合入/推送/打包/发布。不GUI/ADB/MuMu/真实Controller/游戏，不要求用户重选或清空前两槽。回传模型实际平台档位/完整起止SHA/diff/算法条件与预算/红绿/四图与45帧对比/命令最终exit与数量/复用/未覆盖。总控验收后独立复核，再新包第3槽验证；4/5槽继续暂停。
