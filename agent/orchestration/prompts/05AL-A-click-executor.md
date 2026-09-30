# 05AL-A — DeepSeek v4.1flash 人工中转：窄点击适配器

你是实现owner，用DeepSeek v4.1flash平台默认档位。总控为用户指定GPT-6.1 Sol medium/Standard，旧固定Astra要求已被覆盖。用户人工中转本任务，禁止原生子席、派下级、自动创建聊天或调用模型API。

工作目录固定 `E:/hzz/work/MA9/MA9-worktrees/duel-scan`；分支lane/duel-scan，基点HEAD `9b29bd9015bd081a2b66f04bdab3d5b94a6b0583`。先只读核对实际HEAD/status；若HEAD变更或自己目标文件已存在，保留现场并报告，不覆盖、不擅自改基点。本机Python `E:/hzz/work/MA9/.venv/Scripts/python.exe`，已核对Python3.14.4/maafw5.13.0。源码与测试全部取lane，不从根导入。

先确认本地读取/写入/命令能力；若无本地工具，明确说未执行，仅返回补丁建议，不伪称测试通过。按需让用户中转下列必需文件，不编造其内容。

必读（不用整篇历史）：

1. `E:/hzz/work/MA9/agent/orchestration/05AL-contract.md`（小接口/失败矩阵/所有权，版本v1）。
2. lane `agent/ma9_agent/global_garage_prepare_plan.py`、`global_garage_prepare_observation.py`；screen只读CHECKBOX_ROI、页面判定/owned读取需要的段落。
3. lane `agent/ma9_agent/global_garage_mfa_probe.py` 与 `tools/diagnose_global_garage.py` 的RunClock/build_capture/_await_job；它们都是只读参考。
4. 本机 `.venv/Lib/site-packages/maa/controller.py` 的post_click/scaled设置与job.py；合同已给官方v5.13.0源码链接。

owns=[]；owns_generated=[]；仅owns_new允许：

- `agent/ma9_agent/global_garage_prepare_executor.py`
- `agent/tests/test_global_garage_prepare_executor.py`

独占证据可写 `E:/hzz/work/MA9/MA9-evidence/20260930-05AL/A/`（report.md、定向日志、来源哈希、临时测试文件）。B可同时写不同文件；禁止改B、合同、根编排/账本、共享契约、interface/runtime_action/pipeline。C/D六文件是未跟踪的有效交付，不能清理/stage/改写；旧只读包不变。不要运行git stage/commit/切分支/reset/clean/rebase/push，统一由总控核对收口。

交付ClickExecutor(controller, *, session_id, deadline, monotonic, sleep, cancelled)及execute(state,decision,sample)->Outcome，完整签名/Mapping键见合同。构造本身不得操作设备。A/B无互相导入要求：只消费既有planner State/Decision与固定Mapping，禁止另建或互改共享接口文件。

执行范围只有open_filter/toggle_owned/apply_filter，从已在全局garage_list开始。每次动作核对本轮pending/session/action、支持布局与新鲜同帧控件，ROI由本包内校准常量确定，不接受JSON/GUI任意坐标或节点。使用根 `captures/global_garage/` 已有PNG与既有面板OCR重放校准筛选/完成按钮；记录来源哈希，门禁必须核验按钮像素与文本/checkbox对应关系。重复/错位置标签、遮挡、unknown、尺寸或页面不符都禁止点击；不改screen/observation。若筛选按钮证据不足，交出最小缺口和零输入blocked，不扩大导航权限或索要重复六次采样。

同session/action_id最多一个post_click：提交前登记attempt，包括异常/失败/timeout不重试。真实post所得job的id/终结状态才可产生ActionResult；ok只表达真实输入结果，不能根据画面猜。无job/结果不明/timeout/取消无伪回执；迟到真实结果只审计不续跑。仅按时succeeded/failed可交给B。全局30s与单job3s截止严格检查（恰好截止也停止），帧最大年龄1s，0.02s轮询；不调用无界job.wait、不宣称能取消在途native。取消或停止锁住实例，不新post、不close MFA-owned controller。

坐标固定Maa处理帧1280×720、短边720/raw_size=False，设备无需改1920×1080。post_click传处理帧ROI中心，不手工乘1.5；离线fake框架测试1920/1280与另一非1倍比例只转换一次，并区分普通控制器与NoScalingTouchPoints路径（后者本阶段不放行）。真实MFA版本匹配与入口集成由总控后续处理，本任务不连设备。

最低离线覆盖：三个意图的控件正反例；错误pending/session/frame与错帧OCR、旧帧/过期帧、任意意图/坐标、去重/重入、post抛错/invalid job/status异常、job失败/超时/迟到/取消、截止前后、时间非法/倒退、框架坐标边界。断言post实际调用列表，不只断言终态。测试fake controller，禁止真实SDK连接、ADB、GUI、设备发现或输入。

定向命令（cwd必须lane）：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& 'E:/hzz/work/MA9/.venv/Scripts/python.exe' -X utf8 -B -m unittest discover -s agent/tests -p test_global_garage_prepare_executor.py -v
```

不跑无变化全套测试、六大多人分片或根外分配器；tools CAR_STAR_RULES/index_anchor_missing基线仍开放，不能声称verify_default全绿。report回传：模型/平台默认档位、实际HEAD、开始/结束status、精确新增文件及SHA256、接口符合性、按钮来源/门禁、fake输入轨迹、每个实际命令/退出码、失败缺口与未执行项。不自行返修扩权；一个明确阻塞交总控拆分。实现后独立DeepSeek新上下文复核，owner不能自审代替。
