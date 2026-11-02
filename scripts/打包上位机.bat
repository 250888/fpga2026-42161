@echo off
chcp 65001 >nul
rem ============================================================================
rem  瞬迹 · 打包上位机（极薄入口）
rem  双击本文件 = 调用同目录的 打包上位机.ps1，生成桌面上的成品 zip。
rem  只做一件事：
rem    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0打包上位机.ps1"
rem  （chcp 65001 + UTF-8 无 BOM，保证中文文件名参数不乱码；pause 让窗口留驻可看结果）
rem ============================================================================
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0打包上位机.ps1" %*
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo [错误] 打包失败，退出码 %RC% 。请把上面的输出发给维护者。
pause
exit /b %RC%
