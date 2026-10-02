# 05AU 相邻两页采集小合同（2026-10-02）

用户“开始推进”授权实现独立相邻两页入口。主对话仅编排；一名 Sol medium owner 实现三个新文件，随后 Luna low 顺序构建。设备操作仍由用户完成，不提交推送。

复用冻结的 run_prepare_owned(context, root)。准备未 ready 不进入采集。整个新任务从准备前计时最多30秒；采集最多16次真实截图、最多一次固定前滑 (1000,360)→(580,360)，350ms。保持短边720、raw=False及设备1920×1080，原准备代码、P/G、native、观察器和解析器只读。

新阶段使用新 request ID，真实成功 job 冻结帧经 WitnessReader/G 核对后才观察。首次实际任务 job 验证后写 scoped source binding；清理先本请求 active 后本请求 binding，不删除外部替换请求。回执与随后新帧分别记录；3秒输入帧龄、3秒 job、0.02秒轮询、152次上限不放宽，不读共享 cached_image，不调用无界 wait/get。

第一页需新阶段两独立帧确认 garage、真实 D 起点及稳定完整唯一车型身份/卡片位置；稳定以身份及位置容差6px判断，不以整图摘要。第二页需成功滑动回执后的新帧，两帧稳定，至少一个新完整唯一 ID 和一个与第一页相同的完整唯一 ID。裁切、歧义和未知保留未决，不用坐标或模糊名称强行归并。无变化/无重叠停止，不重试、不称全库结束，end_status恒 not_proven。

复用 read_page 对整个新帧 OCR 的结果。owned_filter 为调用方声明并关联准备 ON 核验证据，不将声明写成新像素认证。索引只用 data/generated/vehicle_catalog.json（338条、45128B，SHA256 502d755bfe89258feae1738be06d1836e1ccb7e5539a60f2dfacf58355d1b906），不写账号库存。

实现 own_new：agent/global_garage_two_page_main.py、agent/ma9_agent/global_garage_mfa_two_page.py、agent/tests/test_global_garage_mfa_two_page.py。构建 own_new：tools/build_global_garage_two_page_package.py、tools/tests/test_build_global_garage_two_page_package.py、docs/zh_cn/develop/global_garage_two_page_collect.md。禁止并行同文件写入。

独立 action ma9_global_garage_two_page_collect；入口全局车库_相邻两页采集；仅新 marker .ma9-global-garage-two-page-root；manifest global_garage_two_page_manifest.json。输出 MA9-evidence/20261002-05AU-two-page/package/MA9-preview。复制已验05AR原生 DLL，不重编译、不加载。

定向测试仅覆盖准备失败、两页稳定/重叠去重、加载等待、歧义/裁切、无进展/无重叠、回执/来源/取消/期限失败零追加输入。旧定向与全量、六次采样不重复。离线通过仅可交用户首次两页实机，不代表实机识别或全库完成。
