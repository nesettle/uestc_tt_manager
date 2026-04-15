# 成电杯报名数据管理系统

`UESTC TT Manager` 是一个面向本地单用户的比赛报名数据管理工具，用来把金数据表单导出、资格名单维护、单打报名比对、NapCat QQ 通知、优赛上传表生成串成一套可重复执行的流程。

项目当前包含两部分：

- Web / 源码模式：适合开发、调试和手动运行
- 桌面版源码：用于构建可直接分发的 Windows 安装包

## 主要功能

- 绑定金数据中的 4 张表
  - 资格赛报名表
  - 正赛单打报名表
  - 正赛双打报名表
  - 正赛团体报名表
- 通过 Playwright 登录并导出金数据表单快照
- 根据资格赛报名表维护本地正赛资格名单
- 支持新增资格人员匹配、导出资格名单、勾选删除资格名单成员
- 支持两类单打比对
  - 报了正赛单打，但不在资格赛报名表中
  - 有正赛资格，但没有报正赛单打
- 对“有资格但没报单打”的对象做 NapCat 预检，并勾选发送 QQ 通知
- 导入最终的单打 / 双打 / 团体报名文件，查重后生成“优赛上传表.xlsx”

## 技术结构

- 后端：FastAPI
- 前端：Jinja2 模板 + 原生 JavaScript
- 金数据访问：Playwright 持久化登录
- QQ 通知：NapCat OneBot 11 WebSocket
- 表格处理：openpyxl + pandas
- 桌面封装：pywebview + Qt 后端（qtpy + PySide6）
- 安装包构建：PyInstaller + Inno Setup

## 重要目录

- `app/`
  - Web 应用源码、服务逻辑、静态文件、模板和测试
- `desktop/`
  - 桌面版源码、打包脚本、PyInstaller spec、Inno Setup 脚本
- `vendor/UESTC_TT_registration_converter/`
  - vendored 上游转换器代码
- `data/`
  - 本地配置、资格名单主表、导出归档目录
- `runs/`
  - 每次任务的输出目录
- `browser_state/`
  - 金数据浏览器登录态

说明：

- 桌面版运行时会把数据写到 `%LOCALAPPDATA%\UESTC TT Manager\`
- 源码模式默认把数据写到项目根目录下的 `data/`、`runs/`、`browser_state/`

## 环境要求

### 源码模式

- Windows
- Python 3.10 及以上
- 已安装 Playwright Chromium
- 可访问金数据

### QQ 通知功能额外要求

- 已安装并登录 QQ 桌面版
- 已安装并启动 NapCat
- 已在 NapCat 中启用 OneBot 11 的 `WS 服务端`

### 桌面版安装包使用者

- 不需要单独安装 Python
- 不需要手动执行 `playwright install`
- 仍然需要自己安装和配置 QQ 与 NapCat

## 源码安装

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

## 启动方式

### 方式 1：源码 / Web 模式

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8050 --reload
```

浏览器访问：

[http://127.0.0.1:8050](http://127.0.0.1:8050)

### 方式 2：桌面版源码入口

```powershell
python .\desktop\app_host.py
```

桌面版 smoke test：

```powershell
python .\desktop\app_host.py --smoke-test
```

说明：

- 当前桌面版固定使用 Qt 后端
- `--smoke-test` 会真实初始化一次 Qt 窗口并自动退出

## 普通使用者安装方式

普通使用者建议直接安装 GitHub Release 中的安装包：

- `UESTC_TT_Manager_Setup.exe`

安装步骤：

1. 如果电脑上装过旧版，先卸载旧版
2. 双击 `UESTC_TT_Manager_Setup.exe`
3. 按提示安装
4. 安装完成后从桌面快捷方式或开始菜单启动

用户数据目录固定为：

```text
%LOCALAPPDATA%\UESTC TT Manager\
```

## 首次启动配置

首次启动后，先进入“系统配置”页，依次完成以下配置。

### 1. 配置 NapCat

NapCat 项目地址：

- [NapCatQQ-Desktop](https://github.com/NapNeko/NapCatQQ-Desktop)

建议流程：

1. 安装并登录 QQ 桌面版
2. 安装并启动 NapCat
3. 打开 NapCat WebUI
4. 启用 OneBot 11 的 `WS 服务端`
5. 找到 NapCat 生成的配置文件 `onebot11_你的QQ号.json`
6. 把该文件路径填写到系统配置页的“NapCat 配置路径”

常见路径示例：

```text
C:\ProgramData\NapCatQQ Desktop\runtime\NapCatQQ\config\onebot11_你的QQ号.json
```

注意：

- 这只是常见路径，不同电脑可能不同
- 默认 NapCat 路径留空，需要由用户自行填写

### 2. 配置金数据

在系统配置页填写或确认：

- 成电杯赛事群群号
- NapCat 配置路径
- 金数据首页，默认 `https://jinshuju.net/home`
- 金数据浏览器 Profile 目录
- QQ 通知模板

然后点击：

- `检查金数据登录`
- 或 `登录并刷新表单列表`

首次使用时，系统会打开可见浏览器完成登录。

### 3. 绑定 4 张表

4 张表都支持两种绑定方式：

- 从“已发现表单”下拉选择
- 手动填写表单标题或 `entries_url`

推荐优先使用下拉选择。

### 4. 保存配置

配置保存位置：

- 源码模式：`data/config.json`
- 桌面版：`%LOCALAPPDATA%\UESTC TT Manager\data\config.json`

## 日常使用流程

### 流程 A：维护本地资格名单

1. 在“资格名单维护”中多行输入新增资格人员姓名
2. 点击 `从资格赛报名表匹配 QQ`
3. 系统导出资格赛报名表并尝试按 `姓名 / 学院 / QQ号` 匹配
4. 处理结果会分成
  - 已直接匹配
  - 待人工确认
  - 未匹配
5. 点击 `合并更新到本地资格名单`

本地主表位置：

- 源码模式：`data/qualification_master.xlsx`
- 桌面版：`%LOCALAPPDATA%\UESTC TT Manager\data\qualification_master.xlsx`

附加功能：

- 刷新本地资格名单
- 导出本地资格名单 Excel
- 勾选删除资格名单成员

### 流程 B：比对“单打报名但不在资格赛报名表”

点击：

- `比对：单打报名但没在资格赛报名表出现`

关键输出：

- `registered_singles_not_in_qualification_form.csv`
- `matched.csv`
- `qualification_duplicates.csv`
- `form_duplicates.csv`
- `summary.json`

### 流程 C：比对“有资格但没报单打”

点击：

- `比对：有资格但没报单打`

关键输出：

- `qualified_not_registered_singles.csv`
- `matched.csv`
- `qualification_duplicates.csv`
- `form_duplicates.csv`
- `summary.json`

### 流程 D：QQ 预检与通知

建议先完成“有资格但没报单打”的比对，再做通知。

流程：

1. 点击 `对“有资格但没报单打”名单做 QQ 预检`
2. 系统检查
  - NapCat 配置是否可读
  - OneBot 连接是否正常
  - QQ 号是否合法
  - 是否能在指定赛事群中定位到成员
  - 是否满足群临时会话条件
3. 默认只勾选 `precheck_ok` 的对象
4. 点击 `给勾选对象发通知`

### 流程 E：生成优赛上传表

1. 提供最终的单打 / 双打 / 团体报名文件
2. 点击 `查重并生成 sheet_output`
3. 检查重复项摘要
4. 确认后点击 `确认删除重复项并生成优赛上传表`

关键输出：

- `sheet_output.xlsx`
- `duplicate_review.csv`
- `duplicate_summary.json`
- `upload_preview.xlsx`
- `优赛上传表.xlsx`

## 常见问题

### 1. 金数据导出失败

优先检查：

- 是否仍处于已登录状态
- 金数据 Profile 目录是否可用
- 绑定的表单是否正确

调试文件通常位于对应任务的 `runs/.../exports/.../` 目录中。

### 2. QQ 预检通过但无法发送

常见原因：

- 群成员未找到
- 当前 QQ 环境不支持该对象的群临时会话
- NapCat 未正常在线

## 导出与输出目录

金数据表单导出后，文件会保留两份：

- 当前任务 `runs/...` 目录中的快照
- 固定归档目录 `data/form_exports/`

页面中提供“打开导出文件夹”按钮，直接打开归档目录。

## 测试

在项目根目录执行：

```powershell
pytest app\tests -q
python -m compileall app
python .\desktop\app_host.py --smoke-test
```

## 桌面版构建

### 构建桌面分发目录

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop\build_desktop.ps1
```

构建脚本会自动：

1. 安装 `requirements.txt`
2. 安装桌面打包依赖
3. 用 `--no-deps` 安装 `pywebview`
4. 下载并使用 `desktop/build_assets/ms-playwright/` 中的 Playwright Chromium
5. 使用 PyInstaller 构建桌面分发目录

输出目录：

```text
dist-desktop\UESTC_TT_Manager\
```

### 构建安装包

前提：

- 已构建 `dist-desktop\UESTC_TT_Manager\`
- 本机已安装 Inno Setup

执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop\build_installer.ps1
```

输出安装包：

```text
release\UESTC_TT_Manager_Setup.exe
```

## 隐私与仓库建议

以下内容不要提交到公开仓库：

- `browser_state/`
- `runs/`
- `data/config.json`
- `data/qualification_master.xlsx`
- `data/form_exports/`
- 任何真实报名数据、资格名单、导出快照
- NapCat token、QQ 配置、个人账号信息

## 上游依赖说明

本项目 vendored 了一个上游转换器：

- `vendor/UESTC_TT_registration_converter`

它用于最终报名表转换和查重，本系统在其外层增加了 Web 化适配和本地流程编排。
