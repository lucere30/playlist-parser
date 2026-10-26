@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 歌单解析器

set "PY="
py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY (
  echo 没有找到 Python。请先安装 Python 3.10 或更新版本（安装时勾选 Add python.exe to PATH），然后再双击本文件。
  start "" "https://www.python.org/downloads/windows/"
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo 第一次运行：正在创建独立的 Python 环境...
  %PY% -m venv .venv || (echo 创建环境失败 & pause & exit /b 1)
)
echo 正在检查依赖...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt || (echo 安装依赖失败，请检查网络后重试 & pause & exit /b 1)

echo.
echo 解析页面会在浏览器里打开。用完关掉这个窗口即可。
".venv\Scripts\python.exe" -m plparse.web
pause
