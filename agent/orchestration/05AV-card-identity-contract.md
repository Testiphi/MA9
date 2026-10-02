# 05AV 完整卡片识别改善（2026-10-02）

用户“开始改善吧”授权。复用05AU repair1实机01bcd653ecec4aeaabc9cf589c0e18da的frame/OCR；目标改善完整卡BMW等级徽标漏读、Nissan名称前缀未决。先复现并解释实际原因，窄修承重判据，不扩全库/导航/重新设备采样。

唯一实现owner /root/complete_card_identity，GPT-6.1 Sol low，无下级。owns修改 global_garage_screen.py 与 test_global_garage_screen.py；必要新可公开测试小fixture需先登记，不把私有账号截图纳入Git。准备/采集/P/G/native/catalog只读。主对话仅编排。

不从D起点/等级区域或catalog唯一性猜badge；不多OCR重试/添加fallback链。复用已有full-name像素完整性证据，完整geometry单独不是名字未截断证明。真实截断/更长同名/同字近似/跨class歧义与裁切必须保持未决；误拒的有效证据条件可针对实际图片修正，同时删被替代冗余代码。

仅parser定向suite一次及本次实帧离线probe，少量新增承重正反例，不重复旧准备/P/G/native/采集/CI全量/六人工。不修改设备分辨率/坐标合同、授权门禁、账号库存。图片结果仅离线识别证据，非全库正确率。

证据 MA9-evidence/20261002-05AV-card-identity/implementation，TMP三变量同tmp，根Python -X utf8 -B。实现冻结后Luna low顺序生成05AV独立相邻两页包，原05AU包/现场保留；构建输出MA9-evidence/20261002-05AV-card-identity/package/MA9-preview。不连接设备、加载native、自动新聊天、推送、个人memory改动。
