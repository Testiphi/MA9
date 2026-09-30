# 05AL-B — DeepSeek v4.1flash 人工中转：单会话规划器驱动

你是实现owner，DeepSeek v4.1flash平台默认。唯一总控为用户指定GPT-6.1 Sol medium/Standard，旧Astra要求已覆盖。只通过用户人工中转；不spawn下级、不自动建聊天/调用模型API、不连接或操作设备。

cwd固定 `E:/hzz/work/MA9/MA9-worktrees/duel-scan`，分支lane/duel-scan，HEAD `9b29bd9015bd081a2b66f04bdab3d5b94a6b0583`。先核对实际Git，保留六个未跟踪C/D文件及所有已有工作；若基点变更或目标文件已存在，报告不覆盖。Python `E:/hzz/work/MA9/.venv/Scripts/python.exe`（本机3.14.4）。确认工具能力，无本地访问则仅提供补丁/分析，不伪称测试。

必读：根 `E:/hzz/work/MA9/agent/orchestration/05AL-contract.md`；lane `agent/ma9_agent/global_garage_prepare_plan.py`、`global_garage_prepare_observation.py`、`agent/ma9_agent/global_garage_mfa_probe.py`；C工具只读参考RunClock/capture及等待语义。不用重载总控历史或重派B/C/人工六次采样。

owns=[]，owns_generated=[]，仅owns_new：

- `agent/ma9_agent/global_garage_prepare_loop.py`
- `agent/tests/test_global_garage_prepare_loop.py`

独占证据目录 `E:/hzz/work/MA9/MA9-evidence/20260930-05AL/B/`。A可并行实现自己的文件；本模块不能导入A实现，测试注入独立fake executor。禁止修改A/合同、planner/observation/screen及既有测试、C/D六文件、interface/runtime_action/pipeline、根编排/账本/原包。不要stage/commit/切分支/reset/clean/rebase/push。

实现 `run_prepare(*, session_id, capture, ocr, executor_factory, monotonic, sleep, cancelled, emit)->Mapping`；Sample/Outcome/日志合同完整键名见v1，不改接口。入口启动单一30秒绝对预算，start(session,started_at)，工厂恰好一次executor_factory(session,deadline)，保持64事件原语义。capture/OCR/observe/executor/emit依赖注入（observe复用现有模块），模块本身不得创建controller/tasker/连接或加载设备SDK。

采样成功时给本轮唯一递增frame_id，image副本与OCR同帧绑定，observe原样生产Observation，按自然start/step驱动。Decision.executable=False不修改；能力由后续固定新入口与A核验。只有最新本轮Observation产生的action才能execute，失败/blocked/timeout/取消/结果不明立刻停止，无补点。Outcome绑定本session/pending action/intent；只有按时明确终结job的receipt才step；fake回执在测试中只标fake，不能报告真实设备结果。错ID/session/receipt重复或缺失应停止，不将None包装成ok=False。

receipt成功与画面到达分开：必须等收到回执后才发下一capture，capture_started_at晚于回执完成时刻（同一单调时钟），旧缓存/inflight帧/跨session不得确认。连续两次独立D新采样才能ready；像素相同但确为两次capture允许。初始off精确O,T,A,O,A；初始on精确O,T,A,O,T,A,O,A。后者必须先off提交再on提交，不能用人工off证据替代。verify重开on且不改控件关闭，再双D确认；不见D就跳ready。

unknown按规划器有界wait；other/其他筛选不清/明确矛盾blocked。不自动清理其他筛选/选等级/滑动。每一阶段前后检查30s/取消/非法或倒退时间、第64事件边界；capture/OCR慢调用返回后超时也不能送观察继续发输入。C旧capture等待done优先，B外层须严格检查截止。不得延長预算掩盖冷启动。0.1秒采样节流，禁止忙循环；停止后不再capture/OCR/execute。

report/emit输出单session有序trace、各阶段/decision、实际输入attempt、真实或fake来源、回执/帧关联、elapsed/events、终态、未确定job、starts_race=False；emit异常停止并保留已有记录，不能伪完整成功。不要写账号配置/库存，不假称直接保存了MFA帧证据（包内落盘包装由总控集成）。inflight调用不可硬取消，partial动作如实报告；不close MFA拥有连接。

离线验收至少覆盖：两完整链及精确5/8次轨迹；全程D但未完成链不得ready；未知等待、旧帧/跨session、回执失败/超时/迟到/重复/错ID、页面跳离/其他筛选、控件变化/先验冲突、取消各边界、30s及第64事件、时间异常、capture/OCR/emit失败、相同像素独立采样。不修改planner以让测试方便；fake executor按合同建固定结果并记录真实调用序列。source=fake，不运行live。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& 'E:/hzz/work/MA9/.venv/Scripts/python.exe' -X utf8 -B -m unittest discover -s agent/tests -p test_global_garage_prepare_loop.py -v
```

只跑开发定向测试与必要反例；已有235项与六次采样不重做，不读取六大多人分片、不触碰根外分配器，不宣称verify_default/tools全绿。回传report：模型档位、HEAD/status、精确文件SHA256、接口符合性、off/on trace、全部实际命令/退出码、失败矩阵覆盖、未测试/未实机/无设备声明。困难保留最小反例交总控拆分，一次有界返修，不自行升级模型。实现后由另一个DeepSeek独立上下文只读复核。
