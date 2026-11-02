#!/usr/bin/env python3
"""把仓库同步到 ASCII 构建区 C:\\xjbuild，可选一条龙跑 Vivado 构建。

背景（2026-10-11 实测坐实）：中文路径下 Vivado 2026.1 综合在 RTL
elaboration 结束处无声崩溃（无 ERROR、无事件日志，3 次复现）；同份
源码放纯 ASCII 路径一次通过。构建固定走工作流 A：本脚本同步 +
C:\\xjbuild 出 bit。

用法：
    uv run python scripts/sync_to_build.py            # 只同步
    uv run python scripts/sync_to_build.py --build    # 同步 + 全链出 bit
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
DST = Path(r"C:\xjbuild")
EXCLUDE_DIRS = {".git", "git_server", "vivado", "__pycache__", ".pytest_cache", ".mypy_cache"}
VIVADO = r"C:\AMDDesignTools\2026.1\Vivado"
BIT = DST / "vivado" / "XunJi.runs" / "impl_1" / "xunji_top_hw.bit"


def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in EXCLUDE_DIRS}


def sync() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    for item in SRC.iterdir():
        if item.name in EXCLUDE_DIRS:
            continue
        if item.is_dir():
            shutil.copytree(item, DST / item.name, dirs_exist_ok=True, ignore=_ignore)
        else:
            shutil.copy2(item, DST / item.name)
    print(f"SYNC_OK -> {DST}")


def build() -> None:
    import time
    vivado = Path(VIVADO) / "bin" / "vivado.bat"
    if not vivado.exists():
        print(f"BUILD_FAIL: 找不到 {vivado}", file=sys.stderr)
        sys.exit(1)
    t0 = time.time()
    # 直接调 vivado.bat，不套 cmd /c + settings64：
    #   - Windows 上 subprocess 会对字符串参数二次转义，cmd /c 里的 "..." 会变成
    #     \"...，命令直接失效（2026-10-24 实测 BUILD_FAIL）。
    #   - 2026.1 的 vivado.bat 自带环境，build.tcl 只跑 Vivado 命令，不需要 settings64。
    subprocess.run(
        [
            str(vivado), "-mode", "batch",
            "-source", "scripts/build.tcl",
            "-log", "C:/xjbuild/vivado_build.log",
            "-journal", "C:/xjbuild/vivado_build.jou",
        ],
        cwd=DST,
    )  # 退出码不作判据（Vivado 在部分无害告警下也返回 1），以 bit 新鲜度为准
    # 必须验证 bit 是本次新生成的：旧 bit 存在不算成功。
    # （2026-10-24 踩坑：PATH 里 vivado 先解析到损坏的 2024.2，构建根本没跑，
    #   脚本只看到旧 bit 就报 BUILD_OK，导致烧录了过期 bit。）
    if BIT.exists() and BIT.stat().st_mtime >= t0 - 1:
        print(f"BUILD_OK bit = {BIT} ({BIT.stat().st_size} bytes)")
    else:
        print(
            "BUILD_FAIL: bitstream 未重新生成（PATH 里的 vivado 可能指向损坏版本，"
            "或综合/实现失败）。查 C:/xjbuild/vivado_build.log",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build", action="store_true", help="同步后跑 Vivado 全链出 bit")
    args = ap.parse_args()
    sync()
    if args.build:
        build()


if __name__ == "__main__":
    main()
