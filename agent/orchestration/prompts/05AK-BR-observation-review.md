# 05AK-BR 独立只读关键视觉复核

用户人工中转给GLM5.3全新对话，平台默认档位；必须与05AK-B/B1实现上下文独立。你只读源码，不能修代码、派下级、连接设备、截图、点击、stage/commit/push/merge/reset或自动创建任务。

cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan，branch lane/duel-scan，HEAD 5e0c53afeca2b8072dc60cd6b36fd26d09d3dad7。两个未跟踪文件是待审交付，不要忽略或覆盖：
- agent/ma9_agent/global_garage_prepare_observation.py，SHA256 10eb6ccf064563104ec13d148c6746b7d1254ee3626c0866ae90e87655db69a5
- agent/tests/test_global_garage_prepare_observation.py，SHA256 a9b5efb980bcc3499bc9bfc494a60405397f4ebab29e16b610f913f9ab3bbb5d
先验完整哈希及tracked clean；不匹配停止报告。根main的编排提交不要求同步lane。

先读根agent/orchestration/HANDOFF_CURRENT.md、state.json.global_garage_observation_task、原05AK-B提示词、05AK-B1返修提示词，以及MA9-evidence/20260929-05AK-B-observation/root-b1/review.md。原root/review.md与repair1/report.md仅为历史线索，不以总控或owner结论代替独立判断。

范围：只读上述两文件、现有global_garage_screen.py/prepare_plan.py及必要测试、13张根captures/global_garage原图、现有OCR回放和本包证据。不读六个大型多人分片、不读写MA9根外。唯一可写目录E:/hzz/work/MA9/MA9-evidence/20260929-05AK-B-observation/review/（报告、独立探针、日志、tmp），不得覆盖owner/root证据。

重点独立检查：
1. OCR范围/溢出/整个ROI约束；错误或矛盾输入能否false-clear。
2. 三控件“内部空白”检查是否真覆盖内区，仅排除实际装饰角；异常记号、部分遮挡、不同颜色不得误判空。对已拥有off的适配器单向收紧，不能把unknown晋升on/off；05AJ共享函数保持未改，不宣称其直接调用者已修复。
3. 内容区D徽标、分隔线、双行首列几何是否足以支撑本校准范围内的True；随机D、真实R起始几何、顶部D按钮、字形缺损/污染、锚点部分缺失均做独立反例。不要以有限D/R样本宣称普适字形识别。
4. 根checkout与嵌套worktree解析同一原图；不让skip掩盖缺证据。输入纯度、格式、未知语义、session/frame及同帧OCR信任边界；离线重复文件不是两次真实采样。
5. 新观察实际驱动规划器时，未知等待、冲突阻断；不伪造真实回执或将ready当设备许可。

Python E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B；PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP均指向上述review/tmp，先创建。定向运行test_global_garage_prepare_observation.py、test_global_garage_prepare_plan.py、test_global_garage_screen.py（unittest discover -s agent/tests -p 文件名 -v）；至少加入独立于现有测试实现的反例探针。保留真实退出码/skip，不用os._exit。现有tools基线红项保留，不在本包修；无须重复全量或跑大型分片schema。

回传review.md及results.json：PASS/FAIL、完整哈希MATCH、模型/实际档位、cwd/HEAD、每个发现的严重度/文件行/实际复现/影响/最小建议、实跑测试数量和退出码、剩余限制。PASS仅限离线适配器，不是实机验收；如无阻断问题，明确保留校准样本限制。完成后停止，由用户回传总控，不自行合入。
