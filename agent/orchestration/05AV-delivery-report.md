# 05AV 完整卡识别改善离线交付

复用05AU实机六帧及原OCR；仅parser/test改动。BMW D OCR .542415与Nissan D .459462低于原.6门槛；独立红方块/白D单组件/高内孔/直左竖像素证据补等级，confidence=null、source=pixel_badge，不覆盖可信OCR或冲突，不猜其他等级。原名称prefix/fuzzy/完整名字证据及裁切/近似同名保护不变。Nissan较长同名另一class由原class过滤排除，不需额外放宽prefix路径。

65项parser定向exit0；六帧逐卡回放合并unique4→6（BMW Z4 LCI E89、Nissan 370Z NISMO改善），最终frame2/6对合并6、共有2、未决观察7→4（裁切）。真实孔破坏与明确C/C+D冲突保持未决。只离线证据，不宣称新包实机/其他等级/全库正确。

Luna low顺序新包MA9-evidence/20261002-05AV-card-identity/package/MA9-preview，旧05AU包/现场保留。builder4/编译/schema静态exit0，裸Agent无参exit2；根复核24source/389package hashes零不符、单入口及marker。Manifest b27a36900fbfb0363515f25d99392854bbae52bc178b14f82e348cbb56b7a527；receipt ae23e5d4814aeb4e5adc999465722c79f94e83a4fd9f411b99ae6449748ebcf2。Agent 4e58689f33454a6bbf06bb2df1598e813726fb323687cdf930d214cdedac2c3d，GUI仍cbc526325341177499d64df5158684b0e1af9af98a2fdc99a9fd6e97e2b35e3e。Native05AR复用未编译/加载，准备/采集限额不变。

实施report/before-after/tests.log及构建fullreceipt在05AV证据目录。无设备/GUI运行、全量测试/六采样、Git推送或memory更新。下一用户新包一次相邻两页验证完整卡识别，不扩全库。
