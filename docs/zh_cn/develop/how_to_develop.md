# 如何开发

在开始开发前请先阅读 MaaFramework 开发文档的[快速开始](https://maafw.com/docs/1.1-QuickStarted)章节，以便你对MaaFramework 有一个基本的了解。

~~同时，我们还提供了一个[🎞️ 视频教程](https://www.bilibili.com/video/BV1yr421E7MW)以供参考。~~ 视频中使用的版本较老，一切问题须以最新版文档为准。

## 开发前提

使用本教程进行开发则默认你遵守MaaFramework衍生项目的相关开发规范以及共识，所有的讨论也将基于以下前提。

1. 使用基于 git 作为版本控制工具
  如果你还不会用，可以先在[菜鸟教程](https://www.runoob.com/git/git-tutorial.html)进行学习。
2. 使用 GitHub 托管代码并使用相关 [CI/CD 工作流](https://docs.github.com/zh/actions)
  项目中附带了一些基于 [GitHub Actions](https://docs.github.com/zh/actions) 的 CI/CD 工作流配置，你可以通过他们来自动进行测试以及将项目打包和发布。
3. 了解本框架中一些常见的术语
  MaaFramework 手册中的[术语解释](https://maafw.com/docs/1.2-ExplanationOfTerms)章节介绍了一些基本的专有术语。

## 开发步骤

0. 使用右上角 `Use this template` - `Create a new repository` 来基于本模板创建您自己的项目。

1. 克隆你的项目（地址请修改为您基于本模板创建的新项目地址）。

    ```bash
    git clone https://github.com/MaaXYZ/MaaPracticeBoilerplate.git
    ```

2. 下载 OCR（文字识别）资源文件 [ppocr_v5.zip](https://download.maafw.xyz/MaaCommonAssets/OCR/ppocr_v5/ppocr_v5-zh_cn.zip) 解压到 `assets/resource/model/ocr/` 目录下，确保路径如下：

    ```tree
    assets/resource/model/ocr/
    ├── det.onnx
    ├── keys.txt
    └── rec.onnx
    ```

    > [!WARNING]
    > 请注意，您不需要将 OCR 资源文件上传到您的代码仓库中。`.gitignore` 已经忽略了 `assets/resource/model/ocr/` 目录，且 GitHub workflow 在发布版本时会自动配置这些资源文件。

    _如果希望使用其他版本的模型，可以参考[这个说明](https://github.com/MaaXYZ/MaaCommonAssets/tree/main/OCR)。_

3. 进行开发工作。请参考 [MaaFramework 相关文档](https://maafw.com/docs/1.1-QuickStarted)，并按您的业务需求修改 `assets` 目录下的 `resource` 资源文件以及 `interface.json` 文件，然后使用 [开发工具](https://maafw.com/docs/1.1-QuickStarted#%E8%B0%83%E8%AF%95)进行调试。

4. 完成开发后，上传您的代码并发布版本。

    ```bash
    # 配置 git 信息（仅第一次需要，后续不用再配置）
    git config user.name "您的 GitHub 昵称"
    git config user.email "您的 GitHub 邮箱"
    
    # 提交修改
    git add .
    git commit -m "XX 新功能"
    git push origin HEAD -u
    ```

5. 发布您的版本

    本模板附带 GitHub Actions 工作流的[配置文件](/.github/workflows/install.yml)，CI 检测到 tag 会自动进行打包和发布。默认的配置文件会将 [MFAAvalonia](https://github.com/SweetSmellFox/MFAAvalonia) 与你的项目一同打包和发版。

    > [!NOTE]
    > 第一次操作前，需要**先**修改 Github 仓库设置 `Settings` - `Actions` - `General` - `Read and write permissions` - `Save`

    ```bash
    # 给最近的 commit 打上 v1.0.0 标签并推送
    git tag v1.0.0
    git push origin v1.0.0
    ```

    执行上述命令后，CI 会自动进行打包和发布，你可以在项目仓库的 `Actions` 页面中看到工作流的执行情况。如果一切顺利，运行结束后你可以在项目仓库的 `Releases` 页面中看到新发布的版本。更多有关 GitHub Actions 的内容请参考 [GitHub Actions 文档](https://docs.github.com/zh/actions)

## 常见问题

请参考 [FAQ](./faq.md)

## 便携包运行根与开发兼容

项目里有两套各自独立的数据根查找函数，判据不同，不要合并：桌面选车顺序 GUI 用
`tools/selection_gui.py::find_project_root`（要求 `data/generated/vehicle_catalog.json` 与
`data/generated/champion_rotation.json`），Agent 运行时用 `agent/runtime_action.py::find_project_root`
（要求 `data/multiplayer_profile.json`）。两者的查找优先级一致。

**优先级（从高到低）**

1. 显式配置根：环境变量 `MA9_PROJECT_ROOT`（GUI 实际由启动器以 `configured` 传入）。有效即返回；
   路径存在但缺少该函数所需数据时直接抛错，**不回退**到标记或祖先目录。
2. 显式便携根标记：包根下的普通空文件 `.ma9-portable-root`。
3. 无标记时的原有行为：按候选顺序（exe 所在目录、当前工作目录，Agent 还包括模块目录）展开祖先，
   优先返回带 `config/garage.json` 的账号根，否则退回首个带数据的目录。

**标记的语义是「主动隔离」**

查找依次从可执行文件目录、当前工作目录向祖先遍历，**并行时不交叉**：命中第一个标记即停止，
不再向更外层查找。若该标记目录缺少本函数所需数据则抛 `FileNotFoundError`，
**不越过标记**去读另一个账号的数据。同一层起点之间 exe 标记优先于 cwd 标记。
开发模式（源码根、`install/`）不创建标记，因此仍与 Agent 共用同一个祖先账号根。

**标记只由组包工具在新包根产生**

唯一入口是 `tools/prepare_portable_preview.py`，默认输出
`build/portable/MA9-preview/.ma9-portable-root`。它是被忽略的包副本产物，不是仓库根文件。
组包在必需文件与隐私排除检查全部通过后才写入标记，失败不会留下看似完成的标记。
不要在源码根、开发 `install/` 或既有发行包内手动补标记，也不要把用户 `config/`、日志复制进包内。

**临时目录环境**

本机 shell 导出了 `TMPDIR`，而 CPython 的 `tempfile` 候选顺序是 **TMPDIR → TEMP → TMP**。
只设置 `TMP`/`TEMP` 不会移动夹具落点：夹具会落到系统临时目录，凡依赖「夹具位于仓库内」的
用例（例如祖先账号根抢占）会得到相反结论。运行测试前请同时把 **`TMPDIR`、`TMP`、`TEMP`**
三者指向当前任务的证据临时目录，并打印 `tempfile.gettempdir()` 确认实际落点。

## 更多操作

请参考 [个性化配置](./custom_configure.md)（可选）
