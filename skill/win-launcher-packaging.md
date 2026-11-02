# Skill 5 — 中文文件名上位机的一键打包与启动器

## 适用场景

要交付一个「双击就能跑」的上位机（单文件 HTML / Python 脚本 + 依赖），
但项目里**文件名和路径都是中文**，Windows 的 `cmd.exe` 与 `.bat` 在中文上有编码陷阱。

不适用：纯英文路径的交付物（直接 zip 就行）。

## 核心问题

`.bat` 文件由 `cmd.exe` 按**当前 ANSI 代码页**（中文 Windows 是 GBK/936）解析。
把中文写进 bat 的可执行行，在不同机器、不同代码页下会变成乱码甚至命令不存在。

## 使用方法

### 1. bat 里**不写中文**，改用百分号编码常量

```bat
@echo off
chcp 65001 >nul
:: 上位机.html 的 UTF-8 百分号编码
set "F=%%E4%%B8%%8A%%E4%%BD%%8D%%E6%%9C%%BA.html"
:: 用内联 Python 还原（Python 读 env 时是 UTF-8，不受 cmd 代码页影响）
python -c "import os,urllib.parse,webbrowser;webbrowser.open(urllib.parse.unquote(os.environ['F']))"
```

要点：
- `%%` 在 bat 里是转义后的 `%`，所以百分号编码要写成 `%%E4`
- 还原交给 Python，**不要**在 bat 里 `start` 一个中文路径

### 2. Python 侧统一用 `encoding="utf-8"` 读写

```python
open(path, encoding="utf-8")
subprocess.run([...], capture_output=True, text=True, encoding="utf-8")
```

不要依赖 `locale.getpreferredencoding()`。

### 3. 打包时记录源文件哈希

打包前后对源文件算 SHA256，确保「压进去的」就是「验证过的」：

```python
h = hashlib.sha256(open(src, "rb").read()).hexdigest()
```

解压后对同一文件再算一次，与记录一致才算打包成功。

### 4. 端口占用要给出可操作的报错

Web Serial / WebSocket 类上位机经常遇到端口被占（串口助手没关）。
启动器里捕获异常并打印「关掉 XX 再重试」，同时支持环境变量覆盖端口。

## 失效条件

- 目标机器没有 Python → 启动器退化方案是直接在浏览器打开 html，或打包成 exe
- 需要**免安装且无依赖** → 只能走单文件 HTML + Web Serial（浏览器能力受限）
- 中文路径出现在**第三方 exe** 的入参里 → 部分老程序本身不支持，无解

## 已验证效果

本项目上位机（单文件 HTML + Web Serial）打包后：
- 解压哈希与源一致
- 中文文件名在中文 Windows 上双击正常启动
- 端口被占时给出明确提示

## 提炼来源

`scripts/打包上位机.ps1` / `打开上位机.bat`（本仓库），
以及第一次把中文直接写进 bat 导致乱码的失败尝试。
