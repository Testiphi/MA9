# MA9-05-擂台车库遍历：Terra high 只读试点

执行渠道：Codex 原生子智能体。模型 gpt-5.6-terra / high。唯一编排层是 Astra；不得创建下级智能体，不得直接联系别席，不得合并或推送。

worktree：E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch：lane/duel-scan。
基点由总控在创建 worktree 后写入 state.json 并在派发消息中给出；必须为契约元数据 B（ab13bf9ec91f916754aa0910bd1138e2f038d0a5）后代。
Python：E:/hzz/work/MA9/.venv/Scripts/python.exe（总控已验证 3.14.4，MA9_PYTHON 未设置）。所有命令 cwd 必须是本 worktree 根，Python 一律 -X utf8，不设置指向主工作区的 PYTHONPATH。找不到解释器停止报告。

先完整读 docs/zh_cn/develop/multi_agent_plan.md、agent/lanes.yaml 中全局规则和 duel-scan 节、docs/zh_cn/develop/duel_offline_recognition.md。

本轮是只读试点：核查等级边界、低等级兼容、快速定位失败后完整重扫和页面稳定读取的现有代码/固定样例/测试，给出下一步最小任务与用户实机验证卡。不要为了展示产出而改写已成功 D 级流程。

lane 未来写入范围（本轮不写）：
- agent/ma9_agent/duel_vehicle_runtime.py
- agent/ma9_agent/duel_vehicle_screen.py
- assets/resource/pipeline/duel_slot_navigation.json
- assets/resource/pipeline/duel_runtime.json
- assets/resource/pipeline/duel_navigation.json
- agent/tests/test_duel_vehicle_runtime.py
- agent/tests/test_duel_vehicle_screen.py
- docs/zh_cn/develop/duel_offline_recognition.md

owns_new、owns_generated 均为空：本轮不新建文件、不生成受控产物。五个契约模块和 race_strategy_schema.py 可读不可改。不要读取六个 multiplayer_loop 大分片；第三方策略不在本次任务范围。不得操作 MuMu/ADB，不得构建与本轮审计无关的产物，不改全局 Git 配置。

执行：
1. git status、HEAD、B 祖先关系；确认冻结指针。
2. 只读核查上述四项行为；关键发现附文件行号及测试/截图证据，未知就写未知。
3. 运行相关 unittest（discover -s agent/tests -p test_duel_vehicle_runtime.py -v；另运行 test_duel_vehicle_screen.py）。结果记录命令、cwd、退出码、数量及跳过原因。
4. 区分真实缺陷、缺少测试、仅缺用户实机证据。至多推荐三个按优先级排序的有边界任务；不得把优化后耗时写为已经实测。
5. 提供最短实机验证卡：实际入口、用户操作、预期终态、需回传的日志/截图位置。默认用户执行。

正式写入交付将另行执行 verify_default：
```text
{python} -X utf8 -m unittest discover -s agent/tests -v
{python} -X utf8 -m unittest discover -s tools/tests -v
{python} -X utf8 tools/validate_schema.py --schema-dir deps/tools --resource-dirs assets/resource --exclude-dirs assets/resource/announcement --interface-files assets/interface.json
```
本轮仅相关测试，不声称完整验收或 lane 闭环。未来提交必须经独立 Terra high 只读复核，再由 Astra 裁决。

回传：实际 HEAD/status、检查发现与定位、测试证据、剩余任务、用户实机验证卡。无代码改动则明确写无改动；只向总控回传，由总控登记状态。发现越界问题报告，不自行修改。
