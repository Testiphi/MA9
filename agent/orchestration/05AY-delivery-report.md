# 05AY 小字号品牌名称OCR离线交付

collector每帧保留full-frame OCR供badge/fields，统一检测name ROI放大3x拼白隔离atlas一次OCR，替换原区域词，padding/crosscell拒，外向取整box逆映回1280x720。无车名猜/失败重试/第三调用，parser/class/prefix/裁切、准备/导航/sourcebinding/3s输入30s整体16frame1forward不变。

真实05AX六帧纯静态Resource/Tasker OCR（未Controller/设备）：DODGE frame5/6恢复，合并6unique/4裁切未决，原uniqueIDs保持。初始2x因DODGE漏读未采用；CHEVROLE“身份退化”说法经ID比较撤回，不是有效回归证据。候选basis/confidence变化不等于身份丢失。

15collector定向exit0。两OCR首帧1.224s、后续.334–.844s；两个确认帧含等待约1.658s，实际capture/gate/IO/parse/submit占剩余3s预算尚未实机验证，门槛未放宽。

Luna顺序新包MA9-evidence/20261002-05AY-name-OCR/package/MA9-preview；旧05AX保留。builder4/编译/schema静态exit0、裸Agent exit2；根核24source/389package hashes零不符。Manifest ae34ce1a79fa31dda78c4db45e60c9cd86ed526c7c487befe5d2f95c207a7d78；receipt37a37e8c5d9addb2ed510c0f6687a1e4a3506848af82c1c3874e5aa6d0d58f46。Agent ef70c88d6687c43702650f69343d390ec90d519a617d90df987784fd71340ef0，GUI cbc526325341177499d64df5158684b0e1af9af98a2fdc99a9fd6e97e2b35e3e；native05AR复用未重编/加载。

证据implementation/report.md/real-ocr.json/tests.log及build/fullreceipt.json。不设备/MFA/全量或六采样重跑/push/memory。下一用户新包一次两页验名称及帧龄；离线6不预记实机6，不扩全库。
