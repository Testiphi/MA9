# 05AL 总控一次有界返修（2026-09-30）

状态：修复版定向离线验收通过，待外部独立差异复核；不继承旧版本PASS。旧A/B owner报告、review/report.md、合同v1、C/D及B交付全部原样保留。未修改个人memory；回传末尾关于MEMORY瘦身的声明不作为项目验收证据。

## 实际版本与范围

根HEAD `fd4021c19c8bc37868c5476fdf4c87fdbfcd1988`，lane HEAD `9b29bd9015bd081a2b66f04bdab3d5b94a6b0583`。lane仍为10个未跟踪文件、tracked无修改；没有stage/commit/merge/push。收到的四文件哈希与本机逐项相符；下列为修复前后实际SHA256。

| 文件（相对lane） | 独立review原签字版本 | 总控修复版本 |
| --- | --- | --- |
| agent/ma9_agent/global_garage_prepare_executor.py | f89fee3fae2e06398ce621c4c5fa4c9b07162b645358ccf60cf3a2c51c045735 | 5140bea877f4943bfa7f08df7f9cbb5d3329f7a35aee183f9536e093c8246bf5 |
| agent/tests/test_global_garage_prepare_executor.py | 5af8d30a6e0753dcd6611503712da7a6f513754d16a58fd04325241f10af6b1f | afb9672054ff90cc452e9fc424039466992bc7878d12e639cf43f8eb220ea0e8 |
| agent/ma9_agent/global_garage_prepare_loop.py | 1894eebba13bd8a34ed30d989e847f684248e75cb8ccf3e9769b2ddc7e914d3f | 未变化 |
| agent/tests/test_global_garage_prepare_loop.py | 7345f75f4d46954b15f35c145078d1bf90f226f68cff1c15f798b6c8a5a50734 | 未变化 |

三个只读依赖仍为planner `ed398e1e264a3afef2cf669755db3e3421cc22c82a38f1890882df4628023dff`、observation `83939fbd21c3247c75ca74e02b9dbe4b5e64babe63048926cfefb2986ae900fe`、screen `3207dd951aea4ebae9603a410571a7233af97f8b458258d9493ed21d99c73002`。C/D六项仍逐条匹配合同和账本45.2，未改写。合同仍根路径 `E:/hzz/work/MA9/agent/orchestration/05AL-contract.md`，SHA `bfc83e36d8253f7e9e7ec59346684cdd4cac182408492e78ab1edc45484626d9`；lane未跟踪合同不是缺口。

## 裁决及修复

- P2：保持合同，从capture_started_at起算帧年龄，>=1秒拒绝；不把合同放宽到captured_at。两处边界夹具分别改为capture完成距now0.949/0.95秒（capture耗时0.05秒），使开始年龄0.999/1.0秒。另在控件核验后、post之前再次核验年龄与时钟倒退，慢核验不能延长窗口。新增10秒capture/最近0.1秒完成、核验耗时、核验期间时钟倒退反例，全部零post。
- P3恒定宽高比：删除DONE_MIN_ASPECT及恒定判断，保留aspect仅作校准说明；真正门禁仍是固定ROI中同帧lime像素和唯一绑定标签，不声称已测按钮动态边界。
- P3重复完成标签：高置信有效“完成”标签须恰好一个并绑定固定按钮ROI，重复无论位于框内/框外均blocked、零post；没有放宽合同。
- P3标量OCR：Sample.ocr必须list，不合法时返回blocked/invalid_sample_ocr并锁实例，不再由execute逸出TypeError。
- P3冻结时钟：job轮询最多ceil(3/0.02)+2=152次；时钟不前进时返回indeterminate/job_poll_budget_exhausted、无伪造timeout或receipt、永久锁实例。该计数包含首次查询，不能称为额外两次有效余量；R1实测理想0.02秒浮点累计路径在第152次迭代才观察到超时，有效余量为0。真实3秒截止仍优先，不宣称native硬取消。
- P3/调用边界：panel输入前复用原observation.observe对同frame/items重新核验page与other_filters_clear，不让伪造clear=True绕过真实已勾选stars。没有重写观察器。
- 同一输入回执面补正：native无效job_id=0也拒绝（原实现只拒负数），结果不明且不重试，新增对应反例。

新增8项失效回归（其中重复标签含框内/外两个subcase），断言实际post轨迹。原“错位OCR”测试因更早触发其他筛选unknown阻断，将该明确原因加入期望集合，零post断言不变。

## 实际命令和结果

cwd均为lane；Python根 `.venv/Scripts/python.exe -X utf8 -B`，PYTHONDONTWRITEBYTECODE=1；所有controller/job均fake，无设备SDK连接。

1. 首轮A定向：`-m unittest discover -s agent/tests -p test_global_garage_prepare_executor.py`，66项，exit1。发现新增scalar测试fixture错误、旧错位OCR原因提前阻断、轮询上限浮点误差使正常3秒超时提前成indeterminate；据此修正fixture/原因期望/余量，没有修改合同或放宽门禁。
2. 修正后A同命令：66项、0 skip，OK，exit0，4.179秒。
3. B相关回归：`-m unittest discover -s agent/tests -p test_global_garage_prepare_loop.py`，61项、0 skip，OK，exit0，11.293秒；B源码及测试未改。
4. 根`git diff --check`，exit0。未对无变化版本重复全量测试、235项、tools或六次人工采样。

独立review原58/61通过及off/on精确5/8输入证据保留；这里只声明新版66/61总控验证，不能代替修复版独立签字。原probe脚本引用被删除的DONE_MIN_ASPECT，故未原样重跑或改动旧probe；使用新增回归验证相关失败面。

## 保留的集成阻断

目标MFA原生库缺版本资源，只能说版本资源读取未能确认，不能推定库不匹配，也不能凭Python5.13.0推定DLL同版；NoScalingTouchPoints运行时识别本层不可达。两项未确认前不生成可放行的实机点击包，不连接设备。后续需独立来源/hash/构建manifest等证据核实DLL及控制器能力，不能靠猜测放行。

SOURCE默认mfa_context的调用信任边界、同帧OCR来源信任边界仍须后续固定MFA包装保全；本轮不扩接口。实例停止锁比可重试逻辑更紧，沿用，不在集成中重建实例绕过去重。不可达的events_used前置分支及terminal_unknown只记防御/桩面，不声称真实SDK可达已生效护栏。CAR_STAR_RULES/index_anchor_missing保持开放，不称verify_default全绿。

下一步只需DeepSeek独立上下文差异复核A修复及新反例；B与C/D旧签字/哈希证据复用。提示词 `agent/orchestration/prompts/05AL-R1-repair-review.md`。若仍有阻塞保留最小反例交总控拆分，不无限返修或自行换模型。
