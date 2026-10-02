# 05AP 有界帧龄和按页OCR优化交付收据

2026-10-02用户明确授权实施：实测帧龄2.21–2.31s下，三筛选intent点击前最大帧龄1→3s，仍capture_started计且>=3拒、post前复验。列表像素确认后免OCR，面板只控件ROI(37,52,330,616)；Done门禁改目标按钮ROI内唯一同帧标签+lime填充+全帧panel/otherfilters像素，不要求全屏唯一。同ID去重、失败取消停止、receipt后newframe及30s/64events/3sjob/1s冻结payload获取不变，合同改v2注明旧v1签字范围。

主对话Sol medium仅编排；原生medium实现、low编译、独立medium只读窄复核。lane/codex/garage-filter-mfa、HEAD8127abc5cada1c0185b0232b07815be0fb2920cd，保留原native4修改和既有6新增文件。业务改动限executor/test、wrapper/test、builder/test/docs七文件，无新框架/fallback/暖机阶段；共享parser/planner/loop/Observation/P/G/native及旧只读入口未改。源码未提交推送。

| 文件 | SHA256 |
| --- | --- |
| executor | 4f842bef581aed519e9a1e8f309c976f0115e7fdbb8710d50bd65b674794faad |
| executor test | ddfcb7ea5272f47344517d8489e14ad70f3ff61a49a6a5cec3bca44615b8908c |
| MFA wrapper | 840748cb4205c91650203a725aa5435a6c8e5d75b1fd016beceaef13d8da30c2 |
| wrapper test | e7e53a474d1cdb9ced0f948153509cd2e0b7871a4f4bf2780ddfe870aace96ba |
| builder | 7c3df6e1746873f7f10ce94553c365465de1214aa8a65920302c1d69a5fd05ed |
| builder test | a935a61c586d6a412b27bfe2e4c1f3312811c631e275959eaa0063401a5b0e26 |
| user doc | 76de3f418863f3fb983dc20aec951aeef29de7ba201f8990dda24ced77c927de |

新包E:/hzz/work/MA9/MA9-evidence/20261002-05AP-filter-ocr/package/MA9-preview，唯一任务default_check=true；不写用户实例config。
manifest SHA83a72ef714798064a2c45157712666dcab79a4332378ff79b345110d320c39b8，388文件/12源码SHA一致。
Agent exe SHAeec4821fd145efe998238afecead4b068db4ba0bd7e2f44046b5fb75a0f252c9。
宿主DLL沿用repair1字节SHA12869378e3da70975bf968dc4632c3eadaccf0692193c37476a9f817a16c1e19，未重编/加载。

真实定向测试：executor66、wrapper6、builder4各一次exit0；fake off/on自然ready分别5/8输入7/10capture。新3s边界/目标ROI内duplicate拒与外duplicate允许等替换旧预期，不叠同构suite。PyInstaller build0、Agent无参数退出2预期、包schema/pin/隐私/helper/manifest来源验收0。未重跑native45、P/G/CI1000/六人工采样。证据implementation/executor-suite.txt、integration-suite.txt；build/builder_tests.log、pyinstaller_build.log、no_args.log、package_validation.log、package_receipt.json（收据SHAbad03ba145d77e76e00d0dc70232d6b26e308ed28982d35eafba9fd9c8146eb7）。官方v5.13.0 OCRer.cpp124-125回box已有全帧偏移，存档implementation/ocr-coordinate-source.json；wrapper无二次offset。

独立medium静态无P1/P2，四SHA一致、不重复suite，旧probe入口diff0。FakeContext只核ROI调用/原有inROI标签及globalbox直传，没有模拟真实空间裁剪；实机ROI识别召回/速度/3s余量仍待验证，不能称性能PASS。总控回读日志并核manifest/12sourceSHA/唯一task默认勾选/DLLpin与旧failed summary保留，exit0。原AO/repair1包及日志/manifest未变。

用户下一步：关闭旧MFA，开新包；idle当前实例关闭设置→运行设置→实时视图，原设备1920×1080保持；全局车库列表、确认唯任务已勾选后运行一次，回传debug/global_garage_prepare/<session>/summary.json和关键帧/实际结果。任务只筛选三操作，不开赛/升星解锁/全库翻页。代理未启动MFA/ADB、连接操作设备、加载宿主插件或改memory，未推送。
