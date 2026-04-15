# 使用说明

本文档面向实际使用者，按“从启动到完成一轮比赛报名数据处理”的顺序说明。

## 一、启动系统

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --host 127.0.0.1 --port 8050 --reload
```

浏览器访问：

[http://127.0.0.1:8050](http://127.0.0.1:8050)

## 二、首次配置

### 1. NapCat

本项目不会预填任何机器专属的 NapCat 路径。你需要在本机自己完成 NapCat 配置后，再把配置文件路径填进页面。

建议步骤：

1. 登录 QQ 桌面端
2. 启动 NapCat
3. 打开 NapCat WebUI
4. 启用 OneBot 11 的 WS 服务端
5. 找到 NapCat 生成的 `onebot11_你的QQ号.json`
6. 把该文件的本机路径填到页面的“NapCat 配置路径”

常见路径示例：

```text
C:\ProgramData\NapCatQQ Desktop\runtime\NapCatQQ\config\onebot11_你的QQ号.json
```

### 2. 金数据

在页面的“系统配置”区域填写：

- 成电杯赛事群群号
- NapCat 配置路径
- 金数据主页
- 金数据 Profile 目录
- 通知模板

然后点击：

- `检查金数据登录`
- 或 `登录并刷新表单列表`

首次使用时，系统会打开可见浏览器，你在浏览器中完成登录即可。

### 3. 绑定表单

需要绑定四张表：

- 资格赛报名表
- 正赛单打报名表
- 正赛双打报名表
- 正赛团体报名表

推荐优先使用“已发现表单”下拉框选择。

## 三、维护本地资格名单

主表位置：

```text
data/qualification_master.xlsx
```

操作流程：

1. 在“资格名单维护”里按行输入新增资格人员姓名
2. 点击 `从资格赛报名表匹配 QQ`
3. 检查匹配结果
4. 如有重名，手动选择正确候选项
5. 点击 `合并更新到本地资格名单`

辅助操作：

- `刷新本地资格名单`
- `导出本地资格名单 Excel`
- `删除勾选成员`

## 四、单打报名比对

### 1. 报了单打，但没在资格赛报名表中出现

点击：

- `比对：单打报名但没在资格赛报名表出现`

输出目录类似：

```text
runs/compare-singles-qualification-form-时间戳/
```

### 2. 有资格，但没报单打

点击：

- `比对：有资格但没报单打`

输出目录类似：

```text
runs/compare-qualified-singles-时间戳/
```

## 五、QQ 预检与通知

建议先完成“有资格但没报单打”比对，再进行通知。

操作流程：

1. 点击 `对“有资格但没报单打”名单做 QQ 预检`
2. 查看预检结果
3. 保留默认勾选的 `precheck_ok` 对象，或手动调整
4. 点击 `给勾选对象发通知`

## 六、优赛上传表生成

操作流程：

1. 提供单打、双打、团体最终报名文件
2. 点击 `查重并生成 sheet_output`
3. 查看重复摘要
4. 点击 `确认删除重复项并生成优赛上传表`

主要输出：

- `sheet_output.xlsx`
- `duplicate_review.csv`
- `duplicate_summary.json`
- `upload_preview.xlsx`
- `优赛上传表.xlsx`

## 七、导出表单归档

导出已绑定表单后，系统会把文件归档到：

```text
data/form_exports/
```

页面里有“快捷打开导出文件夹”按钮，可以直接打开这个目录。

## 八、常见问题

### 1. clone 到新电脑后为什么还要重新配置

因为下面这些内容天然是本机相关的：

- NapCat 配置文件路径
- 金数据登录态
- 赛事群群号
- 你自己的表单绑定

项目本身支持迁移，但这些运行期配置必须在新设备上重新填写。

### 2. 金数据导出失败

优先检查：

- 是否仍处于已登录状态
- 绑定的表单是否正确
- 金数据 Profile 目录是否仍然可用

### 3. QQ 预检成功但无法发送

常见原因：

- 群成员未找到
- 当前 QQ 环境不支持该对象的群临时会话
- NapCat 未正常在线
