# MA9-04-多人循环与赛道策略

模型：未启用；档位：平台默认（不编造枚举）。
指定cwd：E:/hzz/work/MA9/MA9-worktrees/multiplayer
分支：lane/multiplayer
预期HEAD：尚未创建；总控放行时必须填写实际完整SHA，当前禁止开工

本次状态与任务：
暂停占位，不创建worktree、不运行生成器、不做赛道策略研究。不因收到提示词就开始任务。只有用户恢复04且总控登记模型/基点后重新生成启动提示词。

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

可修改的现有文件：
- agent/ma9_agent/race_controller.py
- agent/ma9_agent/vehicle_selector.py
- agent/ma9_agent/runtime_config.py
- agent/ma9_agent/selection_editor.py
- assets/resource/pipeline/gold_rotation.json
- assets/resource/pipeline/two_car_rotation.json
- tools/prepare_dynamic_multiplayer_loop.py
- tools/prepare_multiplayer_loop.py
- tools/prepare_reverse_fallback.py
- tools/prepare_vehicle_recognition.py
- tools/multiplayer_loop_files.py
- tools/check_dynamic_multiplayer_loop.py
- agent/tests/test_runtime_core.py
- agent/tests/test_selection_editor.py
- docs/zh_cn/develop/multiplayer_loop_model.md
- docs/zh_cn/develop/multiplayer_loop_test.md
- docs/zh_cn/develop/multiplayer_preparation.md
- docs/zh_cn/develop/current_multiplayer_model.md
- docs/zh_cn/develop/gold_rotation.md
- docs/zh_cn/develop/reverse_fallback.md
- docs/zh_cn/develop/two_car_rotation.md
- docs/zh_cn/develop/dynamic_league.md
- docs/zh_cn/develop/race_screens.md

精确允许新增/维护的文件：
- agent/ma9_agent/track_identity.py
- agent/tests/test_track_identity.py
- agent/ma9_agent/race_strategy.py
- agent/tests/test_race_strategy.py
- assets/resource/pipeline/track_identity.json
- docs/zh_cn/develop/track_identity.md

仅登记生成器可改的产物：
- assets/resource/pipeline/multiplayer_loop.json
- assets/resource/pipeline/multiplayer_loop_3_黄金.json
- assets/resource/pipeline/multiplayer_loop_3_白金.json
- assets/resource/pipeline/multiplayer_loop_3_白银.json
- assets/resource/pipeline/multiplayer_loop_20_黄金.json
- assets/resource/pipeline/multiplayer_loop_20_白金.json
- assets/resource/pipeline/multiplayer_loop_20_白银.json
- assets/resource/pipeline/reverse_fallback.json
- assets/resource/pipeline/vehicle_recognition.json
- assets/resource/image/navigation/loop/player_黄金.png
- assets/resource/image/navigation/loop/player_白金.png
- assets/resource/image/navigation/loop/player_白银.png
- captures/reverse_fallback_check.json
- data/generated/multiplayer_loop_manifest.json

登记生成命令（04暂停，禁止执行）：
{python} -X utf8 tools/prepare_dynamic_multiplayer_loop.py

本提示词相对路径均相对上面指定cwd；所有未列出的文件只读。正式放行前总控刷新HEAD和任务范围。
