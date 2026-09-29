# 05AK-C：用户启动的只读实机诊断入口（本轮只开发，不连接设备）

模型GLM5.3，平台实际默认档位，用户人工中转；唯一写入owner，无下级。此包涉及真实采样/OCR绑定与输入边界，完成后总控核验，再由独立全新上下文关键复核。禁止在开发/测试时连接设备、启动模拟器、截图、点击、翻页；用户后续亲自执行live命令。

cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan
branch lane/duel-scan
预期HEAD 9b29bd9015bd081a2b66f04bdab3d5b94a6b0583
先核对Git、文件访问能力和新增文件不存在；不符停止写入，不自行reset/sync。根main后续编排提交不要求lane同步。
根已于本轮推送并在线验证origin/main=9b29bd9015bd081a2b66f04bdab3d5b94a6b0583；本包开发不推送。

只读根agent/orchestration/HANDOFF_CURRENT.md、state.json.global_garage_live_observation_task、lanes.yaml当前规则及duel-scan边界。只读现有05AK-A/B模块、对应测试和closeout/report.md；不重复旧任务。

## 精确写入边界

owns：空。owns_new（相对cwd）：
- tools/diagnose_global_garage.py
- tools/tests/test_diagnose_global_garage.py
- docs/zh_cn/develop/global_garage_live_observation.md
owns_generated：空。
报告/独立离线脚本/日志/tmp仅写E:/hzz/work/MA9/MA9-evidence/20260929-05AK-C-live-observation/。
不改既有源码、runtime_action.py、assets/interface.json、pipeline、契约、matcher、原图、profile和编排。工具为独立CLI，不在产品任务菜单新增入口。

## 必须实现的最小行为

1. 导入、--help、参数错误及所有单元测试绝不连设备。只有用户显式调用live子命令后才惰性导入/初始化Maa与ADB控制器；ADB可执行文件路径、address、OCR模型目录均显式参数，禁止自动扫描/自动选择设备、读取旧账号配置或执行shell命令。校验参数及输出目录后才连接。
2. CLI示例接口可为live --adb-path PATH --address ADDRESS --ocr-model PATH --output-root ROOT --frames 40 --interval-ms 1000。默认40帧；frames严格1..120，interval-ms严格500..2000，总采样规划时长不超过120秒；非法值在连接前拒绝。系统单调时钟总预算120秒，失败/取消立即停止，不重连/无限重试。Maa等待采用本地SDK实际支持的有界方式；若底层不能硬取消，报告真实限制，不能声称强制120秒终止阻塞调用，也不能伪造超时API。不得os._exit掩盖退出错误。
3. 连接后仅使用采帧方法；业务采样器只接受capture()与ocr(image)窄接口，没有click/swipe/key/touch/shell/task执行入口。禁止加载pipeline bundle或post_task；只加载指定OCR模型。已有无设备OCR参考根MA9-evidence/20260928-05AJ-root-takeover/replay_ocr.py，可只读复用思路；本机SDK源码可只读检查，禁止联网安装/升级。旧collect_vehicle_scan会点击和滑动，不得调用或套用其入口。
4. 每次成功采样取得一份独立copy的原始BGR像素，严格原生1280x720，不缩放/拉伸/调用frame_of的normalize。就这一份像素保存PNG、运行OCR、调用global_garage_prepare_observation.observe。不得OCR时再截一帧。绑定session_id、递增frame_id、采样前后单调时间、PNG哈希与OCR结果。失败帧不伪装成功观察，不用上一帧补齐。
5. 每次运行创建新session，唯一目录用排他创建保证不覆盖。输出只允许当前MA9根内用户指定的证据目录（默认本包下live），禁止根外路径/..逃逸/已存在session覆盖；创建前resolve校验，注意Windows链接路径。保存manifest、逐帧PNG/同帧OCR/Observation与诊断、最终summary（成功/部分/失败/取消及原因）。日志/截图留本机，不提交。保存失败停止，不产生看似完整报告。异常要保留已保存证据和非零退出码；资源正常收尾。
6. observation保持原适配器executable=false/offline_only语义；外层记录source=live_capture表示实际采样来源，两者不混为设备授权。结果不写ready、不伪造ActionResult、不把回车/用户点击当系统动作成功回执，不自动驱动规划器，更不修改账号。此阶段验收观察与人工时序证据，自动规划事务及执行器仍是下一阶段。
7. 默认仅输出紧凑逐帧page/owned/clear/d_start与证据路径；任何缺证据保持unknown。两帧像素相同是允许的，两次成功采样才有两个frame_id。没有replay文件冒充live的选项；测试假源明确标注，不提供正式live证明。

## 有意义的离线验收（测试先行）

- 假controller只提供capture，所有输入/任务/设备枚举方法若被访问即抛错；正常和异常全链均断言零输入调用。测试不创建真实Maa/ADB连接。
- 导入/--help/错误参数不初始化SDK；frame计数、interval边界、时间耗尽、取消、capture/OCR/保存失败均有界结束，返回码与summary对应。
- capture每次返回不同帧或重复同像素帧；OCR收到的对象/内容与保存PNG及observe输入严格一致；OCR期间源buffer突变不得污染已绑定副本；单次采样恰好一次capture。
- session唯一/不覆盖、frame单调、不从失败补旧帧、同像素连续采样仍合法；图像尺寸不符保持失败或明确unsupported，不悄悄归一化。
- 路径逃逸、已有会话、写失败、OCR失败后部分证据保留；mock时钟/等待避免测试真实长sleep。输出模式与实际来源诚实，不把假测试当实机。
- 根checkout和根内lane路径都能运行；测试可只读现有样本，但不要把截图拷入Git。适配器三组回归继续通过。

开发仅跑定向tools/tests/test_diagnose_global_garage.py和agent的test_global_garage_prepare_observation.py、test_global_garage_prepare_plan.py、test_global_garage_screen.py。工具测试用路径限定，不跑全套tools旧基线或大分片schema；总控后置适用验收。Python固定E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B；PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP指向本包tmp。每条命令记录真实退出码和skip。

## 用户手动验证文档（只写步骤，本轮不执行）

给出真实可复制的PowerShell命令，路径由用户填入；ADB地址可注明历史127.0.0.1:16384仅供核对，不自动连接。先配置原生1280×720，用户手动进全局车库，运行只读命令后做一次短操作序列：任意列表→打开面板→改变已拥有并完成→观察D最左端→重开核对→不改设置完成。若初始on，可人工off提交再on提交，但不是程序动作回执。另短序列手动离开D起点，结果不应保持True。无需重做已完成五车分配或清空车辆。
说明本阶段核验page/控件/起点实际观察与每帧日志；不以人造ActionResult达成READY。列出成功/未知/失败时回传的summary/manifest/必要帧编号，明确Ctrl+C停止及真实底层等待限制；运行前无需解锁、升星或开赛。没有支持的真实状态时记录缺口，不指导用户大量试错或改变账号资格。

交付report.md、results.json：模型/档位、HEAD、三文件SHA256、实测命令/数量/exit、接口与Maa方法来源、输入零调用证明、超时/路径/失败边界、用户命令、未运行live声明。一次有界交付后停止，不stage/commit/push、不派reviewer、不自行实机验收。若需要超出三文件边界，先报告最小需求。
