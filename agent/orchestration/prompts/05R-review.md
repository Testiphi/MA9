# MA9-05R-车库排序修复独立复核

模型：GLM-5.3 high；用户新建对话，本次可派发。
角色：独立只读reviewer，不是05D owner。只审代码和证据，不继承owner结论。
cwd：E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch：lane/duel-scan。
审查范围：0850f33d4f3a127ed79ba7c62a0d25a6282a6845..f5472bce3443fde42df17ad8a1819e18b46a2059；预期HEAD=f5472bce3443fde42df17ad8a1819e18b46a2059。

依次检查实际diff后再读owner报告：
1. 仅duel_vehicle_screen.py、其测试、duel_offline_recognition.md三文件，是否都在05边界。
2. 用冻结23:18:23.444 OCR证据核对left锚点、性能ROI、点击坐标，确认7154->2559来自正确徽标而非猜数。
3. 数字型号004C/R1、长滚动车名、被裁切列、无字母组的旧fallback是否引入回归；不要凭假设扩修。
4. 新测试是否真锁住失败路径、修复前能红、修复后能绿；五车plan只是离线计划，不等于实机赋值。
5. 排序断言、按钮图像识别、身份/性能/占用校验、有界重试、不开始比赛是否保持。
6. 对残留_current_rating拼数字和07缺读数共用错误消息分别判定：本次阻塞、后续改进或无证据；不得直接修改07。

证据（全部已迁入MA9）：
E:/hzz/work/MA9/MA9-evidence/20260922-231746-ordering-handoff/maafw.log
同目录三份业务JSON及user-final-screen.png；原始日志旧路径保留为事实，不改。
E:/hzz/work/MA9/MA9-worktrees/duel-scan/debug/duel_ordering_diagnosis.md
同debug目录replay_ordering.py、ocr-call-*.json、identify_package.py、ab-old-vs-new.txt。
E:/hzz/work/MA9/MA9-evidence/20260923-05D-acceptance/ 为总控本地证据，仍须自主判断。

最低针对性重跑：
& E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -m unittest discover -s agent/tests -p test_duel_vehicle_screen.py -v
& E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -m unittest discover -s agent/tests -p test_duel_vehicle_runtime.py -v
& E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -m unittest discover -s agent/tests -p test_duel_defense_setup.py -v
不得修改源码/测试/文档，不提交；辅助报告可写被忽略debug/05R-review.md。
最终明确“无阻塞/有阻塞”，每个问题给文件行号、复现和理由。不要打包或实机。

你运行在用户新建的独立对话，不能依赖任何旧聊天、长期记忆或另一席位的口头授权。
只有 MA9 总控可以调度、修改边界、创建 worktree 和合并；不得创建子智能体、联系其他席位、自动切模型。
项目唯一根：E:/hzz/work/MA9。禁止在 E:/hzz/work 下新建同级 MA9-*，也不要使用旧路径。
若平台没有本地文件/命令能力，明确报告，只分析用户提供的材料，不假称已读取或验证。

必读（绝对路径，主工作区只读）：
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/agent/lanes.yaml
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
按需读 E:/hzz/work/MA9/docs/zh_cn/develop/contract_freeze_draft.md；冻结已经完成，不要重新冻结。
主工作区的编排配置是权威，worktree里的旧模型、旧路径和旧提示词仅历史资料。
契约 A=bd9a535336750d8fae3799f20d321498e21f5b00；基点 B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5。核对 B 是指定 HEAD 祖先。

开工前：核对 cwd、git status --short、git rev-parse HEAD、最近3次提交；不符则报告，不reset、不覆盖改动、不自行checkout/merge其他分支。
不修改全局Git配置；dubious ownership只用命令级 -c safe.directory=<当前worktree绝对路径>。
Python 优先 MA9_PYTHON；为空则 E:/hzz/work/MA9/.venv/Scripts/python.exe。先验证存在并运行 -X utf8 --version；不存在停止，不能替换成PATH解释器。
每条Python命令都加-X utf8，cwd必须为指定lane根；不从主工作区导入源码、不设置指向main的PYTHONPATH。

禁止操作 ADB/MuMu 或启动游戏；实机由用户串行验证。禁止推送、发布、自动更新安装目录或开始比赛。
六个大型 multiplayer_loop 分片不得读入模型上下文或手改；只有登记生成器可以处理对应产物。
未精确登记的data/generated只读。assets/interface.json是契约手写源，不是生成物。
models/vehicle_screen/garage_profile/selection_strategy/selection_runtime、race_strategy_schema、runtime_action及其他契约文件只读；越界问题交总控。
第三方策略原文与规范化副本均本机只读、不提交；缺失走通用兜底，不阻塞多人模块。
私有截图/日志不提交。临时输出写指定worktree被忽略的debug目录；不得创建别席受控文件。

正式代码交付的最低验证（把命令中的解释器替换为已解析的MA9_PYTHON，如未设置则用下面默认值）：
& E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -m unittest discover -s agent/tests -v
& E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -m unittest discover -s tools/tests -v
& E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 tools/validate_schema.py --schema-dir deps/tools --resource-dirs assets/resource --exclude-dirs assets/resource/announcement --interface-files assets/interface.json
需要npm时，PowerShell先设置 $env:NODE_OPTIONS='--max-old-space-size=6144'。
记录实际进程退出码，长命令持续等待到退出；没有输出或工具返回不等于成功。未执行的测试不得引用历史结果冒充。
只读诊断/复核可针对性验证，必须明确不是完整lane交付。

统一回传：项目名、模型实际标签/平台/档位、cwd、branch、起止完整SHA、工作区状态、问题与证据位置、diff文件清单与stat、验证命令/退出码/数量/跳过原因、私有脚本绝对路径、剩余风险与所需下一步。
代码交付先git diff --check并按owns∪owns_new∪owns_generated查边界；只提交自己的修改，不合入main。
复核者只给文件/行号/复现/严重程度，不替owner改代码。用户把结果回传总控，总控独立验收。
实机成功必须five_assigned、五车互斥、starts_race=false并停阵容页；GUI“任务全部完成”不等于业务成功。
