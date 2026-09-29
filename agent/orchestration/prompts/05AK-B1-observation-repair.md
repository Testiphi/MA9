# 05AK-B1：唯一一轮有界返修

用户人工中转给05AK-B实现owner GLM5.3，平台默认档位。保持原任务全部边界，不创建下级/任务，不操作设备，不stage/commit/push/merge/reset。不要重复原任务、另起架构或修tools基线。

cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan，branch lane/duel-scan，HEAD必须仍为5e0c53afeca2b8072dc60cd6b36fd26d09d3dad7。唯一可改源码为原两交付文件：agent/ma9_agent/global_garage_prepare_observation.py及agent/tests/test_global_garage_prepare_observation.py（它们仍是未跟踪文件，禁止覆盖其他工作）。开始核验哈希分别为3b8be4a3957d14459581ad50b40bdc322fc15d744d174c542dfbcad9d4cd4dfa和d4f21ccf37546a034f3c3b9dd26d433d77d5ffd464686de17589d0c748f04b65，不符先报告。

先读根MA9-evidence/20260929-05AK-B-observation/root/review.md、probe.py、probe-results.json，逐项修复F1–F4：
1. confidence严格有限[0,1]，box严格有限、正宽高、帧内；排序标签须真实位于ROI而非仅中心命中；极大整数不得引发未捕获OverflowError。非法证据计数拒收，不能产生clear=True。
2. 空控件必须有内部确实为空的证据；白勾/异色记号/部分污染应unknown，不能以“非绿色+边框均值”宣称空。保留真实off/on、原反例，不硬编码上述探针像素；记录真实控件左下/右下装饰与可检测内区的几何关系。
3. 修测试ROOT定位，明确支持根checkout和MA9-worktrees/duel-scan两种布局，允许明确环境路径；用路径解析回归验证，不复制源码到根、不修改根测试或原图。无私有样本仍可明确skip，当前lane必须无skip。总控会在合入前核验根布局。
4. 图像入口验证HxWx3和支持dtype。灰度/四通道/错误dtype等返回统一明确ValueError或文档化unknown；合法非原生大小仍unknown。

先补能在旧实现失败的回归，再最小修改。保留既有正例与全部定向回归。不要扩展D字形识别、主页分类、星级、采样认证或执行器；遇到必须扩界的发现返回总控。

Python固定E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B；PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP指向E:/hzz/work/MA9/MA9-evidence/20260929-05AK-B-observation/repair1/tmp，先创建。仅可在repair1目录写报告/日志/脚本，保留原交付与root证据不覆盖。
在lane运行unittest discover -s agent/tests -p test_global_garage_prepare_observation.py -v，及test_global_garage_prepare_plan.py、test_global_garage_screen.py两项回归；另运行root/probe.py，保存真实输出，明确剩余异常。全部用固定Python，实际exit决定结果；不全扫大型多人分片，不掩盖Maa退出。
repair1/report.md和results.json回传逐F修复、失败前/通过后证据、测试数/skip/exit、两文件完整SHA256、Git边界与剩余缺口。一次返修后停止，交总控重新核验，不自行找reviewer或声称已合入。
