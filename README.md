# 成电杯报名数据管理系统

本项目是一个本地单用户 Web 工具，用来把金数据表单导出、正赛资格名单维护、单打报名比对、NapCat QQ 通知、优赛上传表生成串成一套可重复执行的流程。

## 功能概览

- 绑定金数据中的 4 张表：
  - 资格赛报名表
  - 正赛单打报名表
  - 正赛双打报名表
  - 正赛团体报名表
- 从金数据导出表单快照到本地 `runs/` 目录，并额外归档到 `data/form_exports/`
- 维护本地资格名单主表 `data/qualification_master.xlsx`
- 批量输入姓名，从资格赛报名表中匹配 `姓名 / 学院 / QQ号`
- 比对两类异常：
  - 报了正赛单打，但没有出现在资格赛报名表
  - 有正赛资格，但没有报名正赛单打
- 对“有资格但没报名单打”的对象做 NapCat 预检和选择性通知
- 导入最终的单打 / 双打 / 团体报名文件
- 调用 vendored `UESTC_TT_registration_converter` 做转换、查重、删重确认
- 生成最终 `优赛上传表.xlsx`

## 技术栈

- 后端：FastAPI
- 前端：Jinja2 模板 + 原生 JavaScript
- 金数据访问：Playwright 持久化登录态
- QQ 通知：NapCat OneBot 11 WebSocket
- Excel 处理：openpyxl、pandas

## 环境要求

- Windows
- Python 3.10 及以上
- 已安装 Chromium 对应的 Playwright 依赖
- 已登录金数据账号
- 已登录 QQ 桌面端，并已配置 NapCat

## 安装

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

## 启动

在项目根目录执行：

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8050 --reload
```

浏览器打开：

[http://127.0.0.1:8050](http://127.0.0.1:8050)

## 首次启动

页面顶部已经提供了“首次启动说明”和“当前配置检查”，新设备建议按这个顺序完成。

### 1. 配置 NapCat

本项目不再内置任何机器专属的 NapCat 路径。首次使用时，需要你在页面里自行填写本机配置文件路径。

推荐流程：

1. 正常安装并登录 QQ 桌面端
2. 安装并启动 NapCat
3. 打开 NapCat WebUI
4. 启用 OneBot 11 的 WS 服务端
5. 找到 NapCat 生成的配置文件 `onebot11_你的QQ号.json`
6. 把这个文件的本机路径填到页面里的“NapCat 配置路径”

常见配置文件位置类似：

```text
C:\ProgramData\NapCatQQ Desktop\runtime\NapCatQQ\config\onebot11_你的QQ号.json
```

这只是常见位置，不同设备、不同安装方式、不同 QQ 号都可能不同。

### 2. 配置金数据

在页面的“系统配置”中填写或确认：

- 成电杯赛事群群号
- NapCat 配置路径
- 金数据主页，默认是 `https://jinshuju.net/home`
- 金数据浏览器 Profile 目录
- QQ 通知模板

然后点击：

- `检查金数据登录`
- 或 `登录并刷新表单列表`

如果是首次使用，系统会用可见浏览器打开金数据；你在浏览器里完成登录后即可继续。

### 3. 绑定 4 张表

每张表都支持两种方式：

- 从“已发现表单”下拉选择
- 手动输入表单标题或 `entries_url`

推荐优先使用下拉选择。

### 4. 保存配置

点击 `保存配置` 后，配置会写入：

```text
data/config.json
```

## 主要使用流程

### 流程 A：维护本地资格名单

1. 在“资格名单维护”里多行输入新增资格人员姓名
2. 点击 `从资格赛报名表匹配 QQ`
3. 系统会导出资格赛报名表并按姓名匹配
4. 结果会分成：
   - 已直接匹配
   - 待人工确认
   - 未匹配
5. 点击 `合并更新到本地资格名单`
6. 主表会写回：
   - `data/qualification_master.xlsx`

同时会生成一次快照：

- `runs/qualification-apply-时间戳/qualification_snapshot.xlsx`

### 流程 B：导出本地资格名单

在“资格名单维护”中点击：

- `导出本地资格名单 Excel`

下载的文件就是当前主表：

- `data/qualification_master.xlsx`

### 流程 C：做单打报名比对

#### C1. 报了单打，但没在资格赛报名表里出现

点击：

- `比对：单打报名但没在资格赛报名表出现`

输出目录类似：

- `runs/compare-singles-qualification-form-时间戳/`

关键输出：

- `registered_singles_not_in_qualification_form.csv`
- `matched.csv`
- `qualification_duplicates.csv`
- `form_duplicates.csv`
- `summary.json`

#### C2. 有资格，但没报单打

点击：

- `比对：有资格但没报单打`

输出目录类似：

- `runs/compare-qualified-singles-时间戳/`

关键输出：

- `qualified_not_registered_singles.csv`
- `matched.csv`
- `qualification_duplicates.csv`
- `form_duplicates.csv`
- `summary.json`

### 流程 D：QQ 通知

1. 先完成“有资格但没报单打”比对
2. 点击 `对“有资格但没报单打”名单做 QQ 预检`
3. 系统会检查：
   - NapCat 配置是否可读
   - OneBot 连接是否成功
   - 群成员是否能在指定赛事群中定位
   - 是否可发群临时会话
4. 表格中默认只会勾选 `precheck_ok` 的对象
5. 点击 `给勾选对象发通知`

### 流程 E：优赛上传表生成

1. 在“优赛上传表”中填写最终报名文件路径，或直接上传文件
2. 点击 `查重并生成 sheet_output`
3. 页面会展示重复组摘要
4. 确认后点击 `确认删除重复项并生成优赛上传表`

输出目录会包含：

- `sheet_output.xlsx`
- `duplicate_review.csv`
- `duplicate_summary.json`
- `upload_preview.xlsx`
- `优赛上传表.xlsx`

## 导出归档目录

导出已绑定表单后，文件会保留两份：

- 任务运行目录中的快照
- 固定归档目录 `data/form_exports/`

页面里有“快捷打开导出文件夹”按钮，可以直接打开这个归档目录。

## 目录说明

### 重要目录

- `app/`
  - Web 应用代码
- `data/`
  - 本地配置、资格名单主表、导出归档目录
- `browser_state/`
  - 金数据 Playwright 登录态
- `runs/`
  - 每次任务的输出目录
- `vendor/UESTC_TT_registration_converter/`
  - vendored 上游转换器代码

### 重要文件

- `app/main.py`
  - FastAPI 入口
- `data/config.json`
  - 系统配置
- `data/qualification_master.xlsx`
  - 本地资格名单主表
- `requirements.txt`
  - Python 依赖

## 常见问题

### 1. 别人 clone 仓库后能不能直接用

核心代码和数据目录是相对项目根目录工作的，不绑定某个用户名目录。

但首次使用时仍需要在新设备上自行配置：

- NapCat 配置路径
- 金数据登录态
- 成电杯赛事群群号
- 四张金数据表绑定

### 2. 金数据导出失败

优先检查：

- 是否仍处于已登录状态
- 浏览器 Profile 路径是否正确
- 目标表单是否绑定正确

调试文件通常会落在对应 `runs/.../exports/.../` 目录中。

### 3. 匹配 QQ 时提示缺少列

通常是金数据导出表头和预期列名不一致。当前系统已兼容常见列名：

- `姓名`
- `QQ号`
- `学院`
- `学院部门（教学科研单位、研究机构）`

### 4. QQ 预检成功但无法发送

常见原因：

- 群成员未找到
- 当前 QQ 环境不支持该对象的群临时会话
- NapCat 未正常在线

## 测试

在项目根目录执行：

```powershell
pytest app\tests -q
python -m compileall app
```

## 隐私与仓库建议

以下内容不建议上传到公开仓库：

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
