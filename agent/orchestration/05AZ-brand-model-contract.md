# 05AZ 品牌低分与完整型号证据窄修

用户“开始修”授权。复用05AY实机7b1fbfd0b179447bb9c39b5e4c23ca2d帧4/5：DO06E品牌.651142在名称区、CHALLENGER SRT8型号.959318、独立D、完整几何；品牌被现name信任门槛丢弃。只改善通用分层名称证据裁定，不添加OCR、不按车型猜品牌、不全局降低阈值。

单Sol low owner /root/brand_model_identity，仅screen/parser test两文件。先设计品牌低分相容核验与高分完整型号/像素覆盖/独立class，避免无brand字段时按catalog第一word错误拆品牌。明确错品牌、同型号多品牌、前缀更长款、等级冲突、裁切保持未决；不补造品牌观测或把catalog唯一性当完整性证据。

collector/main/prepare/observer/native/P/G/catalog只读，原720、预算、回执和采集范围不变。parser定向一次及本次/此前实帧OCR回放，少量承重正反例；真实截图不入Git，不静态重做OCR/设备采样/旧全量/六采样。

证据MA9-evidence/20261002-05AZ-brand-model/implementation。源码冻结后Luna low顺序新隔离包package/MA9-preview，旧05AY保留。无设备/MFA/DLL加载、推送/memory修改，离线效果不提前写成新实机PASS。
