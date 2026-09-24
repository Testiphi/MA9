# MA9-05J-单槽目标选车名称优先

模型ds-v4.1flash，请求high；平台无独立开关按实际默认记录，不自动max。用户外部全新对话，不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整基点及预期起始HEAD da22bf1bc844d762d75fb70977284dced7b09e11。主仓库后续编排只读，不同步、不checkout/reset/merge。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5；验证祖先复用不重冻。

用户最新裁决：当前优先跑通名称匹配和单槽指定车辆选中，性能分的几十/一百分差异不应阻塞这条功能测试；完整车库扫描并本地保存只记后续，本轮不做。无需再等待Nevera详情截图。本裁决覆盖此前“本测试必须列表详情性能一致”的要求，但不能破坏正式防守排序与其他旧调用者。
实机已确认：02H能识别且点开Nevera；列表4837，详情ROI读37/4,897并解析为4897，既有跨页分数比较触发返回重试，最终selection_lost。证据E:/hzz/work/MA9/MA9-evidence/20260925-001628-nevera-detail-live/{business.snapshot.json,diagnosis.json,repro.log}。不靠猜4837或修改OCR数字通过门禁。

精确owns（仅4已有文件）：
- agent/ma9_agent/duel_vehicle_runtime.py
- agent/tests/test_duel_vehicle_runtime.py
- agent/ma9_agent/duel_slot_selection.py
- agent/tests/test_duel_slot_selection.py
owns_new=[]；owns_generated=[]。其余全部只读：共享vehicle_screen/其他冻结模块、05G入口/observer、defense_setup、runtime_action、duel_slot_test、GUI/interface/pipeline、lanes/state、数据、生成器。发现必须动边界外文件停止回总控。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md；本lane上述4文件、duel_slot_test.py读取请求与调用方式、defense_setup对scan/assign_visible调用点（只读）；本次实机证据；05I共享精确名修复只读，不返工。

窄实现裁决：
1. 给scan增加keyword-only严格bool verify_list_detail_rating=True，沿_try_target/_finish_target透传；内部helper也以True默认保证旧调用和assign_visible行为不变。非法非bool在任何context/采集/动作前拒绝。不得修改旧scan默认，也不得按车型名/账号硬编码例外。
2. 只有verify_list_detail_rating=False时，跳过“列表当前分与详情当前分必须相等”的隐式比较以及仅由此产生的list_detail_rating_mismatch回退；不是把所有失败改成成功。verify=True完全保留旧检查与裁切千位兼容行为。
3. 调用方若明确传了expected_performance仍必须检查，expected_stars也照旧；False仅取消隐式跨页分数比较，不取消明确请求约束。性能OCR可以暂时留作诊断，不扩大到ROI/解析重写，不猜数；返回原始实际读数并注明比较关闭，不能把4897修饰为4837。无expected_performance时分数差异或缺读数不阻塞已确认身份的定位。
4. SlotSelectionRequest新增严格bool verify_list_detail_rating=False（这条单槽薄适配按用户最新裁决默认名称优先）；_validate_request前置校验、scan调用明确透传，在report.request保留该值；可在scan返回报告中显式标注策略。不要让GUI/文件未知字段开启其他动作，实际GUI choose仍false，开启单次选择由总控后续接线。
5. 身份门禁保持：列表定位目标、详情必须读出同一target_id；wrong_detail/detail_not_verified不能变located或assigned。choose=False停目标详情，不因为纯分数差异触发返回；choose=True仍要求未占用/按钮可用/点击后车型与同槽后置确认。stars/占用/按钮/账号标签语义/starts_race=false/有界恢复/类边界不放松。
6. 正式run_defense_setup/assign_visible等旧路径既有默认仍verify=True，不修改排序策略，不修改_car评分、不全局降低相似阈值；04暂停，不动任何局内流程。本轮不增通用框架、车库扫描存储或账号认证模块。

必须测试：
- 列表4837/详情4897、目标身份正确、无显式expected_performance：新单槽默认choose=False应located且停详情，无返回点击；显式verify=True仍mismatch并按原路径处理。保留旧默认测试，不用改掉旧断言掩盖默认变动。
- verify=False但expected_performance=4837实际4897仍performance_mismatch；expected_stars不符仍拒绝；wrong_detail/身份缺失、occupied_elsewhere等保持。
- 同一场景choose=True只跳过隐式分数比较，仍完整执行原目标/占用/按钮/同槽守卫；没有真实设备操作。choose=False绝无选择点击，starts_race恒false。
- 新bool非法类型前置拒绝，旧scan/assign_visible未传参数默认True；05F默认False正确透传并写入报告。现有源码调用按AST/检索核对，不改05H文件即可让其构造request使用新默认。
- 红绿分清旧行为拒绝和新用户要求；真实记录37/4,897来源与当前解析保持，不伪造像素或实机通过。

环境：MA9_PYTHON优先否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止；全部-X utf8 -B，PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP同设本轮tmp并实测；cwd本lane、不从main导入业务代码。Git仅命令级safe.directory，起止HEAD/status/祖先/diff边界留档，不改全局设置。
新证据E:/hzz/work/MA9/MA9-evidence/20260925-05J-name-first/，已存在停止，不覆盖；允许report.md/results.json/red.log/green.log/runtime.log/slot.log/agent.log/tools.log/schema-reuse.json及tmp小夹具。旧包、旧证据不动，禁止执行旧脚本main原地覆盖。所有写入MA9内，不读六大分片、data/generated只读，根外MutualExclusionAllocator不碰。
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_runtime.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_slot_selection.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -v
& $lanePython -X utf8 -B -m unittest discover -s tools/tests -v
基点Agent268，tools30（lane可有既有截图skip，按实测）；每条真实最终exit记录，非0不能因OK吞码。schema/interface/resources未变，证明差异仅4Python后复用05H两项+旧资源，不全27重跑、不npm/构建。
最多两轮有界修复，仍失败带证据回总控。成功后自动本地提交仅4授权文件，不合入/推送/打包/发布/开GUI/Controller/ADB/MuMu/游戏。回传项目/模型实际平台档位/cwd分支/完整起止SHA/diff/API默认与透传/红绿证据/命令最终exit与计数/复用/剩余风险。名称优先不等于实机已定位或已赋值；总控验收后再独立复核与用户包接线。
