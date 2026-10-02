# 05AO 新MFA自动过滤准备包交付收据

> 本收据为首次离线交付历史。用户首跑failed/witness_event_missing、零输入，原包保留取证，不继续使用。后续repair1收口见总控账本第61节与state.global_garage_mfa_integration_task；修复包要求用户先关闭当前实例实时视图。本收据中的N1插件pin不是repair1新pin。

2026-10-01：主对话GPT-6.1 Sol medium仅编排；原生独立上下文Sol medium实现、low构建、medium只读窄复核。用户确认DS已停止后保留并整合真实WitnessReader假宿主夹具，不保留两套接线接口。冲突版本在本地implementation/conflict。

cwd/worktree：E:/hzz/work/MA9/MA9-worktrees/duel-scan，codex/garage-filter-mfa，HEAD 8127abc5cada1c0185b0232b07815be0fb2920cd。tracked业务文件未改，六新增文件未提交/推送。

| 文件 | SHA256 |
| --- | --- |
| agent/global_garage_prepare_main.py | 7a504303ff5ec7e103ad18df4aa66d1b0961efa29c8c9a4607e06ced0fd41f9a |
| agent/ma9_agent/global_garage_mfa_prepare.py | e9b9686b6d135c4d916acce77df64543765a594a9ae1a1d78f27d07131e1a8ba |
| agent/tests/test_global_garage_mfa_prepare.py | 744b8607471e1faeeb1f57540dc5f86a6725a4723139cf92eeb2a0d4d959175a |
| tools/build_global_garage_prepare_package.py | 8d96fc6ee1dc69b3ba9011551a8350ab01209aaaeeeab8355ee51ac4e4793b9a |
| tools/tests/test_build_global_garage_prepare_package.py | 461abdf11b0db38eb3ef313b6d2936d81e4ee3563f023dc34eaaaa68b3851c9a |
| docs/zh_cn/develop/global_garage_filter_prepare.md | 301377b275067fd1cbce4c0b039224ce5c0481080400f763996fad1889c037de |

新包：E:/hzz/work/MA9/MA9-evidence/20261001-05AO-mfa-filter/package/MA9-preview。
manifest：global_garage_prepare_manifest.json，SHA256 108493e044f9d1b9bfb45a8f7274cf280eb7faf9d9f993547b1b6ec189b4c85d，列388文件。
Agent exe SHA256 52cd2373d608397e16a03150570b2e9dce922ef97b39429d67a3576432ed3d4f。
宿主插件复用N1交付34ebab7bb6698a8d8e04e108df7c55727f232bf3e58351f2b487fe704a746897，未重编译/加载。

真实离线命令结果：根.venv Python -X utf8 -B，新Agent unittest discover 5 tests/10场景exit0；builder suite 4 tests exit0；PyInstaller构建exit0；包schema/pin/隐私/helper/manifest回读exit0；编译Agent无参数启动exit2（必须MFA提供socket），检查命令exit0。TMP三变量设证据临时目录、禁pyc。同版旧全量/红基线/六次人工采样未重跑。

fake off/on调用真实Reader、G、loop、observer、ClickExecutor，自然ready分别5/8点击、7/10捕获；失败/超时/取消停止，缺身份/冻结帧零输入。已修AgentServer正常_framework=None导致身份拒绝、截图有限轮询、具体异常原因丢失；builder显式复制MaaAgentBinary无扩展名触控后端和.so。独立medium只读静态复核无剩余阻断、六SHA一致，未重复suite；复核证据为子代理回传，文件写入权限拒绝未形成独立report文件，不伪称存在。

证据：MA9-evidence/20261001-05AO-mfa-filter/implementation/integration-suite.txt；build/builder_tests.log、pyinstaller_build.log、no_args.log、package_validation.log。总控回读日志及manifest/唯一task/固定插件pin/源码一致exit0。

任务只从全局车库列表执行open_filter/toggle_owned/apply_filter，保持720短边/设备1920×1080；回执后新帧、去重及30s/64事件/3s job/1s帧龄保持。原只读任务/旧包/默认入口不改，无全库翻页或开赛。

离线通过不等于实机成功。下一由用户打开新包MFA、连接原设备、停全局车库列表首跑一个记录初始状态，回传debug/global_garage_prepare/<session>/summary.json与关键帧/界面结果；失败保留现场，成功再覆盖另一初始状态，之后才讨论全库翻页。智能体未连接设备、运行MFA/ADB、加载宿主插件或修改memory。
