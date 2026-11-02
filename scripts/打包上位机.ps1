#Requires -Version 7.0
<#
.SYNOPSIS
    「瞬迹」上位机成品打包 —— 给队友的一键成品 zip。

.DESCRIPTION
    收集 doc\ 下的上位机与两份文档，生成一键启动器「打开上位机.bat」与 README.txt，
    一并打成 zip 输出到桌面：上位机_YYYYMMDD_HHmm.zip。

    打包清单与容错：
      - doc\上位机.html         必需；缺失立即中止
      - doc\上位机使用说明.md    可选；缺失仅警告并在清单标注「缺失」，不中断
      - doc\答辩演示脚本.md      可选；同上

    生成的启动器「稳妥方案」要点（bat 内也有同样注释）：
      - 中文文件名不直接写进 bat 的可执行行，而是用 UTF-8 百分号编码常量
        %E4%B8%8A%E4%BD%8D%E6%9C%BA.html，交给内联 Python 解码还原为真实文件名
        —— 既彻底避开 cmd 对中文/编码的解析差异，URL 百分号编码也顺带完成；
      - 起服务 / 等待 1 秒 / 开浏览器 / 退出关服务，全部由一条内联 Python 完成：
        HTTP 服务跑在同一 Python 进程的守护线程里，窗口关闭或按回车即整体退出，
        不留残留进程；
      - Python 探测顺序：python -> py -3，且都用实跑探测，避开应用商店假占位程序；
      - 端口固定 8899，只绑定 127.0.0.1。

.NOTES
    全程 UTF-8、控制台中文输出；只读源文件，不改仓库内容，不做 git 提交。
#>
[CmdletBinding()]
param(
    # zip 输出目录，默认当前用户桌面
    [string]$OutDir = 'C:\Users\clocker\Desktop'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------- 控制台输出统一 UTF-8，保证中文不乱码 ----------
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

function Say  ([string]$msg) { Write-Host $msg }
function Warn ([string]$msg) { Write-Host "[警告] $msg" -ForegroundColor Yellow }
function Fail ([string]$msg) { Write-Host "[错误] $msg" -ForegroundColor Red }
function Rule ([string]$t) {
    Write-Host ''
    Write-Host ('=' * 72)
    Write-Host "  $t"
    Write-Host ('=' * 72)
}

# ---------- 路径与时间戳 ----------
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DocDir   = Join-Path $RepoRoot 'doc'
$Now      = Get-Date
$Stamp    = $Now.ToString('yyyyMMdd_HHmm')
$TimeStr  = $Now.ToString('yyyy-MM-dd HH:mm:ss')

Rule '瞬迹 · 上位机成品打包'
Say "脚本位置   : $PSCommandPath"
Say "仓库根目录 : $RepoRoot"
Say "文档目录   : $DocDir"
Say "打包时间   : $TimeStr"

# ---------- 收集打包清单 ----------
# 上位机.html          —— 单文件 Web Serial 上位机（深色版）
# 瞬迹诊断工作台.html   —— GPT 版诊断工作台（含诊断聚焦、故障注入、CSV/JSON 回放）
# 两者共用同一套串口协议；诊断工作台已用真机四类故障帧联调通过
$required = @('上位机.html', '瞬迹诊断工作台.html')
$optional = @('上位机使用说明.md', '答辩演示脚本.md',
              '工作台_使用与录屏指南.md', '启动工作台.py', '打开工作台.bat', '工作台_预览.png')

$rows = foreach ($name in ($required + $optional)) {
    $src = Join-Path $DocDir $name
    if (Test-Path -LiteralPath $src -PathType Leaf) {
        $item = Get-Item -LiteralPath $src
        [pscustomobject]@{
            Name    = $name
            Src     = $src
            Present = $true
            Bytes   = $item.Length
            Hash    = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
            State   = '已收录'
        }
    }
    else {
        [pscustomobject]@{
            Name    = $name
            Src     = $src
            Present = $false
            Bytes   = [long]0
            Hash    = '-'
            State   = '缺失(未随包)'
        }
    }
}

Rule '打包前清单 · 源文件（doc\）'
foreach ($r in $rows) {
    if ($r.Present) {
        Say ('  {0,-20} {1,-14} {2,12} 字节  SHA256={3}' -f $r.Name, $r.State, $r.Bytes, $r.Hash)
    }
    else {
        Say ('  {0,-20} {1,-14} {2,12}        {3}' -f $r.Name, $r.State, '-', '-')
        if ($required -notcontains $r.Name) {
            Warn "缺少 $($r.Name) —— 继续打包，清单中标注为「缺失」。补上后重新运行本脚本即可纳入。"
        }
    }
}

# 校验全部必需文件都在（现为两个 HTML 本体）
$missingRequired = @($rows | Where-Object { ($required -contains $_.Name) -and (-not $_.Present) })
if ($missingRequired.Count -gt 0) {
    foreach ($m in $missingRequired) { Fail "必需文件缺失：$(Join-Path $DocDir $m.Name)" }
    Fail '无法打包。'
    exit 1
}

# ---------- 暂存目录（放 E: 盘，遵守「产物落盘优先 E:\d」）----------
$Stage = Join-Path (Split-Path -Parent $RepoRoot) ('.pack_stage_' + $Stamp + '_' + (Get-Random -Maximum 99999))
if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
New-Item -ItemType Directory -Path $Stage -Force | Out-Null
Say ''
Say "暂存目录   : $Stage"

# ---------- 复制源文件（带 SHA256 复核，防并发编辑导致的脏拷贝）----------
foreach ($r in $rows) {
    if (-not $r.Present) { continue }
    $dst = Join-Path $Stage $r.Name
    Copy-Item -LiteralPath $r.Src -Destination $dst -Force
    $dstHash = (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash
    if ($dstHash -ne $r.Hash) {
        Warn "$($r.Name) 复制后 SHA256 与源不一致（源文件可能正被编辑），重试一次……"
        Start-Sleep -Milliseconds 300
        Copy-Item -LiteralPath $r.Src -Destination $dst -Force
        $dstHash = (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash
        if ($dstHash -ne $r.Hash) {
            Warn "$($r.Name) 二次复制后仍不一致，以暂存区实际内容为准继续打包。"
        }
        $r.Hash  = $dstHash
        $r.Bytes = (Get-Item -LiteralPath $dst).Length
    }
}

# ---------- 生成一键启动器（UTF-8 无 BOM + CRLF；bat 绝不能带 BOM）----------
# 说明：可执行行全部 ASCII；中文文件名以百分号编码常量交给 Python 解码。
$batText = (@'
@echo off
chcp 65001 >nul
rem ============================================================================
rem  瞬迹 FE-16 上位机 · 一键启动器（双击即用）
rem  双击本文件 -> 在本目录起本地静态服务(默认 127.0.0.1:8899) -> 约 1 秒后自动打开浏览器
rem  关闭本窗口 / 在窗口里按回车 = 停止本地服务并退出，不留残留进程
rem
rem  【稳妥方案 · 为什么这样写】
rem   1) 中文文件名"上位机.html"不直接出现在任何可执行行里，而是以 UTF-8
rem      百分号编码常量写入（下方 %%E4%%B8%%8A%%E4%%BD%%8D%%E6%%9C%%BA.html，
rem      bat 里百分号要写成两个 %%），交给 Python 的 unquote 解码还原为真实文件名。
rem      这样 cmd 完全不碰中文/编码问题；交给浏览器的 URL 也天然就是百分号编码形式。
rem   2) 起服务、等待 1 秒、开浏览器、退出关服务，全部由一条内联 Python 完成：
rem      HTTP 服务跑在同一 Python 进程的守护线程里 -- 按回车或直接关窗口，
rem      进程一退服务即停，不会有"残留 python 占着端口"。
rem   3) Python 探测顺序：先 python 后 py -3，且都用实跑探测（不只是看 PATH
rem      里有没有同名文件），避开 Windows 应用商店那个只会弹商店的 python 占位程序。
rem   4) 服务目录 = 本 bat 所在目录；若该目录没有 html（比如本 bat 放在仓库
rem      scripts\ 目录下），自动回退到上一级 doc\ 目录，自定位、无需手工改路径。
rem   5) 只绑定 127.0.0.1（本机回环地址），服务不会暴露到局域网。
rem   6) 端口默认 8899；起服务前先探测端口是否被占，被占则给出明确提示并退出
rem      （不会静默抢端口）。想换端口：先 set XUNJI_PORT=8897 再双击本 bat。
rem ============================================================================
setlocal
cd /d "%~dp0"

rem ---- 探测可用的 Python 3（实跑探测，两步回退）----
set "PY_EXE="
python -c "import sys;sys.exit(0 if sys.version_info>=(3,6) else 1)" >nul 2>nul && set "PY_EXE=python"
if not defined PY_EXE (
    py -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,6) else 1)" >nul 2>nul && set "PY_EXE=py -3"
)
if not defined PY_EXE (
    echo [错误] 未找到可用的 Python 3。请安装 python.org 的 Python，或确认 py -3 在 PATH 中。
    pause
    exit /b 1
)

rem ---- 起本地静态服务并打开浏览器（内联 Python，设计说明见上方注释）----
%PY_EXE% -c "import os,sys,time,threading,socketserver,http.server,webbrowser,urllib.parse,socket;name=urllib.parse.unquote('%%E4%%B8%%8A%%E4%%BD%%8D%%E6%%9C%%BA.html');base=os.getcwd();cand=[base,os.path.join(base,'..','doc')];tgt=next((d for d in cand if os.path.isfile(os.path.join(d,name))),None);sys.exit('[ERROR] '+name+' not found under '+base) if tgt is None else os.chdir(tgt);port=int(os.environ.get('XUNJI_PORT','8899'));probe=socket.socket();busy=probe.connect_ex(('127.0.0.1',port))==0;probe.close();sys.exit('[ERROR] port '+str(port)+' is already in use. Close the other local-server window/process first, or set XUNJI_PORT=8897 and retry.') if busy else None;socketserver.TCPServer.allow_reuse_address=True;httpd=socketserver.ThreadingTCPServer(('127.0.0.1',port),http.server.SimpleHTTPRequestHandler);httpd.daemon_threads=True;threading.Thread(target=httpd.serve_forever,daemon=True).start();url='http://127.0.0.1:'+str(port)+'/'+urllib.parse.quote(name);print('[OK] local server up: '+url+'  (dir: '+os.getcwd()+')');time.sleep(1.0);webbrowser.open(url);input('Press ENTER to stop the local server and exit...');httpd.shutdown();print('[OK] server stopped, bye.')"

endlocal
'@) -replace "`r?`n", "`r`n"

$batPath = Join-Path $Stage '打开上位机.bat'
[System.IO.File]::WriteAllText($batPath, $batText, [System.Text.UTF8Encoding]::new($false))

# ---------- 生成 README.txt（UTF-8 带 BOM，记事本稳开；纯文本）----------
$gitHash = '未知'
try {
    $g = & git -C $RepoRoot rev-parse --short HEAD 2>$null
    if (($LASTEXITCODE -eq 0) -and $g) { $gitHash = "$g" }
}
catch { }

$docLines = foreach ($r in $rows) {
    if ($required -contains $r.Name) { continue }   # 两个 HTML 本体已在上面逐项列出
    $note = if ($r.Present) { '已随包' } else { '缺失：源仓库尚未提供，补上后重新打包即可纳入' }
    '  {0,-20} {1}' -f $r.Name, $note
}
$docBlock = $docLines -join "`r`n"

# 两个 HTML 本体的字节数与 SHA256（写进 README，作为「手上这份包是哪一版」的凭据）
$verLines = foreach ($nm in $required) {
    $r = $rows | Where-Object { $_.Name -eq $nm } | Select-Object -First 1
    if ($r -and $r.Present) { '  {0,-20} : {1,7} 字节  SHA256={2}' -f $nm, $r.Bytes, $r.Hash }
}
$verBlock = $verLines -join "`r`n"

$readme = @"
================================================================
「瞬迹」FE-16 线束拓扑上位机 · 成品包
================================================================

【这是什么】
本包含【两套】可用的网页界面，用 Chrome/Edge 的 Web Serial API 直连 FPGA 串口
（115200 8N1），把 16x16 线束拓扑实时可视化。零安装，可直接从 U 盘运行，
两套都内置「演示模式」（无硬件排练）。

  A. 瞬迹诊断工作台 —— 推荐用于答辩与录屏
     信息更全：诊断聚焦会直接列出「哪两个 A→B 连接对缺失/新增」，并按状态
     给出建议检查方向；带故障注入工具栏、自动演示流程、CSV/JSON 会话导出与回放。
     已用真机四类故障（PASS / OPEN / MISWIRE / BRIDGE）的原始帧联调通过。

  B. 上位机 —— 单文件精简版
     深色高饱和界面，主打实时连接数历史条（断线帧会留下缺口）、
     毫秒级事件时间线与一键证据导出。协议与 A 完全相同。

两套共用同一套帧协议（55 AA | Ver | Type | Len 38 | Seq | Payload | CRC-16/CCITT-FALSE），
接同一块板子、同一个 COM 口，可任选其一使用（不要同时连接同一个串口）。

【怎么用】
1. 解压本 zip 到任意目录（路径可以含中文）。
2. 二选一双击（两个启动器各自独立，端口不冲突）：
   - 「打开工作台.bat」 → 打开 A. 瞬迹诊断工作台（推荐，答辩/录屏用这个）
   - 「打开上位机.bat」 → 打开 B. 上位机精简版（固定 127.0.0.1:8899）
   两者都会：启动只绑定 127.0.0.1 的本地静态服务 → 约 1 秒后自动开浏览器 →
   关掉黑窗口（或在窗口里按回车）即停服务，不留后台进程。
3. 浏览器若没自动弹出：工作台启动器会在窗口里打印实际地址（随机空闲端口，
   形如 http://127.0.0.1:52341/...），直接复制访问即可；
   上位机则是固定 http://127.0.0.1:8899/ ，在目录列表里点「上位机.html」。
4. 页面里点「连接串口」，选中 FPGA 对应的 COM 口；没接硬件就点「演示 / 模拟演示」排练。
   注意：同一个 COM 口同一时刻只能被一个页面占用，切换两套界面时先断开再换。

【用什么浏览器】
Google Chrome 或 Microsoft Edge（较新版本）。只有它们支持 Web Serial API，
才能真正连上串口；别的浏览器只能看界面。
注意：不要直接双击 上位机.html 用 file:// 方式打开——那样串口权限可能不可用，
请一律通过「打开上位机.bat」走 http://127.0.0.1 访问。

【环境要求】
- Windows 10 / 11；
- Chrome 或 Edge 浏览器；
- Python 3（启动器用它起本地服务；python.org 安装版或 py -3 启动器形式均可）。

【包内文件】
  —— A. 瞬迹诊断工作台（推荐）——
  瞬迹诊断工作台.html       工作台本体（单文件，内联 CSS/JS）
  打开工作台.bat            一键启动器（随机空闲端口 + 自动开浏览器）
  启动工作台.py             上述启动器调用的 Python 脚本
  工作台_预览.png           界面预览图（不用开浏览器也能先看一眼）
  工作台_使用与录屏指南.md   含真机操作顺序、快捷键、2 分钟视频分镜、验证范围

  —— B. 上位机精简版 ——
  上位机.html               上位机本体（单文件，内联 CSS/JS）
  打开上位机.bat            一键启动器（固定 127.0.0.1:8899）
$docBlock
  README.txt                本文件（就是这份说明）

【常见问题】
- 启动器提示端口 8899 被占用（port 8899 is already in use）：
  说明已有别的本地服务在用这个端口（比如另一个 http.server 窗口还没关）。
  先关掉那个窗口/进程再双击本 bat；或在 cmd 里先执行 set XUNJI_PORT=8897
  再运行本 bat，改用其他端口。
- 页面能打开但「连接串口」列表是空的：确认 FPGA 已上电、USB 串口线已插好，
  并用 Chrome/Edge 最新版本；别的浏览器不支持 Web Serial API。

【版本与打包信息】
  版本       : v1.0（git 提交 $gitHash）
  打包时间   : $TimeStr
$verBlock

（本包由 瞬迹/scripts/打包上位机.ps1 自动生成）
================================================================
"@

$readmePath = Join-Path $Stage 'README.txt'
[System.IO.File]::WriteAllText($readmePath, ($readme -replace "`r?`n", "`r`n"), [System.Text.UTF8Encoding]::new($true))

# ---------- 打包后清单：暂存区（= zip 内容，含 SHA256）----------
Rule '打包后清单 · 待打包文件（暂存区，内容即 zip 内文件）'
foreach ($f in Get-ChildItem -LiteralPath $Stage -File | Sort-Object Name) {
    $h = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
    Say ('  {0,-20} {1,12} 字节  SHA256={2}' -f $f.Name, $f.Length, $h)
}

# ---------- 压成 zip ----------
if (-not (Test-Path -LiteralPath $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}
$ZipPath = Join-Path $OutDir ("上位机_$Stamp.zip")
if (Test-Path -LiteralPath $ZipPath) {
    Warn "同名 zip 已存在，将覆盖：$ZipPath"
    Remove-Item -LiteralPath $ZipPath -Force
}
[System.IO.Compression.ZipFile]::CreateFromDirectory($Stage, $ZipPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)

Rule '打包后清单 · zip 内条目（解压后）'
$zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
    foreach ($e in $zip.Entries | Sort-Object FullName) {
        Say ('  {0,-20} {1,12} 字节（压缩后 {2} 字节）' -f $e.FullName, $e.Length, $e.CompressedLength)
    }
}
finally { $zip.Dispose() }

$zipItem = Get-Item -LiteralPath $ZipPath
$zipHash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash

Rule '打包完成'
Say "输出文件   : $ZipPath"
Say "zip 大小   : $($zipItem.Length) 字节"
Say "zip SHA256 : $zipHash"

# ---------- 清理暂存目录（位于 E: 盘的自建临时目录，安全）----------
Remove-Item -LiteralPath $Stage -Recurse -Force
Say "已清理暂存 : $Stage"
Say ''
Say '下一步：把 zip 拷给队友。解压后：'
Say '  · 答辩/录屏 → 双击「打开工作台.bat」（瞬迹诊断工作台，功能最全）'
Say '  · 只想看精简界面 → 双击「打开上位机.bat」'
exit 0
