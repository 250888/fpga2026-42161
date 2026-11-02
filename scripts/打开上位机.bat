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