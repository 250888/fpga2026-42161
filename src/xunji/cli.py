# 瞬迹主机侧 CLI —— Vivado 构建目录镜像与常用入口。
#
# Vivado 2024.2 对中文路径不友好：构建统一在英文目录（默认 D:\xunjiji）进行。
# xunji sync 把仓库内 {rtl, sim, constrs, scripts} 镜像过去，目标侧同名子目录
# 整体替换以清除上游已删文件，随后可在构建目录里直接跑 create_project/simulate/build.tcl。
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

# 需要镜像进英文构建目录的源目录（与 scripts/*.tcl 的输入一致）
MIRROR_DIRS = ("rtl", "sim", "constrs", "scripts")
_SKIP_DIRS = {".Xil", ".git", "__pycache__"}


def sync_to_build(repo_root: Path, build_root: Path) -> list[str]:
    """把仓库的 MIRROR_DIRS 镜像到 build_root，返回被处理的目录名列表。"""
    repo_root = Path(repo_root)
    build_root = Path(build_root)
    synced: list[str] = []
    for name in MIRROR_DIRS:
        src = repo_root / name
        if not src.is_dir():
            continue
        dst = build_root / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(
            src,
            dst,
            ignore=shutil.ignore_patterns(*_SKIP_DIRS, "*.pyc"),
        )
        synced.append(name)
    return synced


def _repo_root() -> Path:
    # src/xunji/cli.py -> 仓库根
    return Path(__file__).resolve().parents[2]


def _hdl_tools() -> tuple[str, str, str]:
    """verilator/iverilog/vvp 路径：PATH 优先，兜底 msys2 绝对路径。"""
    import shutil
    fallback = {
        # 注意：msys2 的 verilator 是无扩展名 Perl 脚本，cmd/which 都执行不了，
        # 必须直接落 verilator_bin.exe（实测 Verilator 5.050 可用）。
        "verilator": r"D:\msys64\ucrt64\bin\verilator_bin.exe",
        "iverilog": r"D:\msys64\ucrt64\bin\iverilog.exe",
        "vvp": r"D:\msys64\ucrt64\bin\vvp.exe",
    }
    verilator = shutil.which("verilator") or fallback["verilator"]
    iverilog = shutil.which("iverilog") or fallback["iverilog"]
    vvp = shutil.which("vvp") or fallback["vvp"]
    return verilator, iverilog, vvp


def _g2_pass(out: str, code: int, require_code: bool = True) -> bool:
    """G2 判定：退出码0 ∧ 整行 PASS 存在 ∧ 无 FAIL 开头行（xsim 层 require_code=False）。"""
    lines = out.splitlines()
    has_pass = any(ln.strip() == "PASS" for ln in lines)
    has_fail = any(ln.startswith("FAIL") for ln in lines)
    return (code == 0 or not require_code) and has_pass and not has_fail


def _fix_tool_env() -> None:
    """子进程工具环境修正（本机实测问题，2026-10-02 任务4）：
    - PATH 前置 msys2 ucrt64\\bin：PATH 里 IntelFPGA quartus\\bin64 排在 msys2 前，
      ivl.exe 会加载 Quartus 旧版 libstdc++-6.dll（缺 _ZSt28__throw_bad_array_new_lengthv）
      → 启动即 0xC0000139，iverilog 编译静默失败。仅影响 xunji 自身及其子进程。
    - 补 VERILATOR_ROOT：verilator_bin.exe 不经 Perl 包装时找不到自带 include 目录。
    """
    msys_bin = r"D:\msys64\ucrt64\bin"
    path = os.environ.get("PATH", "")
    if not path.lower().startswith(msys_bin.lower()):
        os.environ["PATH"] = msys_bin + os.pathsep + path
    os.environ.setdefault("VERILATOR_ROOT", r"D:\msys64\ucrt64\share\verilator")


# 顶层命名（V1.9 P048–P050）：生产 Top 与自回环 Top 各自独立过 lint，
# 共享同一个 xunji_core；仿真/终审顺序跑全部 TB：
#   tb_xunji_loopback（回环模型）+ tb_static_sampler（P1 静态扫描四阶段）+
#   tb_golden_compare（P1 Golden Map 分类与 LEARN 合法性）+ tb_static_cls（T4 core 集成）+
#   tb_uart_packet_tx（§17 帧黄金向量，2026-10-11 计划）
LINT_TOPS = ("xunji_top_hw", "xunji_top_loopback")
SIM_TOPS = ("tb_xunji_loopback", "tb_static_sampler", "tb_golden_compare",
            "tb_static_cls", "tb_uart_packet_tx", "tb_uart_packet_tx16")


def _cmd_lint(repo: Path) -> int:
    from .hdl.filelist import write_lists
    from .hdl.runners import run_tool
    _fix_tool_env()
    verilator, _, _ = _hdl_tools()
    rtl_f, _ = write_lists(repo, repo / "build")
    failed = []
    for top in LINT_TOPS:
        cmd = [verilator, "--lint-only", "--language", "1364-2005", "-Wall",
               "--top-module", top,
               "-f", str(rtl_f.relative_to(repo)),
               str(repo / "scripts" / "lint.vlt")]
        r = run_tool(cmd, timeout=120, cwd=str(repo))
        print(f"--- lint top={top} (exit {r.code}) ---")
        print(r.out)
        if r.code == 127:
            print("未安装 verilator：D:\\msys64\\usr\\bin\\pacman.exe -Sy --noconfirm --needed "
                  "mingw-w64-ucrt-x86_64-verilator")
            return 1
        if r.code != 0:
            failed.append(top)
    return 0 if not failed else 1


# Vivado xsim 终审（G4）固定路径：三件套安装目录与镜像根。
# N2 例外条款：xsim 层 cwd=镜像根、产物落镜像根（唯一不遵守"产物全落 build/"的层）。
# 本机 2024.2 换机后损坏（xvlog.exe 启动 0xC0000135 缺 DLL，离线不可修），三件套改走 2026.1。
VIVADO_BIN = r"C:\AMDDesignTools\2026.1\Vivado\bin"
XJ_BUILD = r"D:\xunjiji"


def _cmd_xsim(repo: Path) -> int:
    from .hdl.runners import run_tool
    # 三件套一次判全（缺任一即整层跳过，避免跑到一半才发现缺工具）
    trio = [Path(VIVADO_BIN) / name for name in ("xvlog.bat", "xelab.bat", "xsim.bat")]
    missing = [str(p) for p in trio if not p.exists()]
    if missing:
        print(f"Vivado 不可用（缺 {', '.join(missing)}），跳过终审层；lint/sim 不受影响")
        return 2
    xvlog = trio[0]
    # ① 镜像 + 前置清理（残留会污染 xsim.dir 快照/日志）
    sync_to_build(repo, Path(XJ_BUILD))
    for f in ("xsim.dir", "xvlog.log", "xelab.log", "xsim.log"):
        p = Path(XJ_BUILD) / f
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    # ② xvlog：RTL+TB 显式路径（相对镜像根，sync 保留 rtl/sim 子结构）
    rtl_files = sorted(str(p.relative_to(repo)) for p in (repo / "rtl").glob("*.v"))
    tb_files = sorted(str(p.relative_to(repo)) for p in (repo / "sim").glob("*.v"))
    r = run_tool([str(xvlog)] + rtl_files + tb_files, timeout=300, cwd=XJ_BUILD)
    if r.code != 0 and not r.timed_out:
        # $fatal 兼容分支（I6 预写）：默认模式拒收 $fatal → RTL 默认、TB 单独 -sv 重试一次
        r2 = run_tool([str(xvlog)] + rtl_files, timeout=300, cwd=XJ_BUILD)
        r = run_tool([str(xvlog), "-sv"] + tb_files, timeout=300, cwd=XJ_BUILD)
        if r2.code != 0 or r.code != 0:
            print(r2.out + r.out)
            return 1
    elif r.timed_out:
        # 超时（124）不触发 $fatal 兼容重试：直接快速失败，不再多等 600s 重试周期
        print(r.out)
        return 1
    # ③ 每个 TB 各自 xelab 快照 + xsim runall + G4 判定（全过才 0）
    # 实测适配：RTL 无 `timescale、TB 有 `timescale 1ns/1ps → XSIM 43-4099 报错；
    # xelab --timescale 1ns/1ps 与 TB 声明一致（不改 RTL/TB/判定规则，仅加工具旗标）。
    for top in SIM_TOPS:
        print(f"--- xsim top={top} ---")
        r = run_tool([str(Path(VIVADO_BIN) / "xelab.bat"), top, "-s", f"{top}_snap",
                      "--timescale", "1ns/1ps"],
                     timeout=600, cwd=XJ_BUILD)
        if r.code != 0:
            print(r.out)
            return 1
        # xsim runall（stdout 含 TB 的 PASS/FAIL 行）
        r = run_tool([str(Path(VIVADO_BIN) / "xsim.bat"), f"{top}_snap", "-runall"],
                     timeout=600, cwd=XJ_BUILD)
        print(r.out)
        # G4 判定（不要求退出码）
        if not _g2_pass(r.out, r.code, require_code=False):
            return 1
    return 0


def _cmd_sim(repo: Path) -> int:
    from .hdl.filelist import write_lists
    from .hdl.runners import run_tool
    _fix_tool_env()
    _, iverilog, vvp = _hdl_tools()
    _, sim_f = write_lists(repo, repo / "build")
    files = [ln for ln in sim_f.read_text(encoding="utf-8").splitlines() if ln.strip()]
    # ① 每个 TB 各自编译-运行-G2 判定（cmd 不展开通配符 → 显式文件列表；全过才 0）
    for top in SIM_TOPS:
        print(f"--- sim top={top} ---")
        out_vvp = repo / "build" / f"{top}.vvp"
        r = run_tool([iverilog, "-g2005", "-s", top, "-o", str(out_vvp)] + files,
                     timeout=120, cwd=str(repo))
        if r.code != 0:
            print(r.out)
            if r.code == 127:  # 工具缺失：与 _cmd_lint 对称，打印安装命令
                print("未安装 iverilog：D:\\msys64\\usr\\bin\\pacman.exe -Sy --noconfirm --needed "
                      "mingw-w64-ucrt-x86_64-iverilog")
            return 1
        # ② 运行
        r = run_tool([vvp, str(out_vvp)], timeout=60, cwd=str(repo))
        print(r.out)
        if r.code == 127:  # vvp 与 iverilog 同包；缺工具走 FAIL（非 0）→ 下方返回 1
            print("未安装 vvp：D:\\msys64\\usr\\bin\\pacman.exe -Sy --noconfirm --needed "
                  "mingw-w64-ucrt-x86_64-iverilog")
        # ③ G2 三重判定
        if not _g2_pass(r.out, r.code):
            return 1
    return 0


def _cmd_read(args) -> int:
    """串口监听 + §17 帧重组 + 矩阵展开（2026-10-24 审查 B2）。

    protocol.parse_frame 只能解析"已经拿到手的整帧"，读 COM 口必须自己做
    SOF 搜索 + Len 定长 + CRC 校验，否则字节流错位。本命令补齐主机侧最后一环。
    """
    try:
        import serial
    except ImportError:
        print("缺少 pyserial（pyproject.toml 已声明），先 uv sync", file=sys.stderr)
        return 1
    from . import protocol as P

    n_ch = args.n_ch
    cls_names = {
        P.CLASS_PASS: "PASS", P.CLASS_OPEN: "OPEN", P.CLASS_MISWIRE: "MISWIRE",
        P.CLASS_BRIDGE: "BRIDGE", P.CLASS_ANOMALY: "ANOMALY",
        P.CLASS_NO_REF: "NO_REF",
    }
    buf = bytearray()
    good = 0
    bad = 0
    max_payload = n_ch * n_ch // 8 + 6
    saved: list[bytes] = []

    try:
        with serial.Serial(args.port, args.baud, timeout=0.4) as ser:
            # 运行时输出一律 ASCII：中文在 GBK 控制台/被管道捕获时会乱码。
            print(f"open {args.port} @ {args.baud}, waiting {args.frames} frame(s) "
                  f"(Ctrl-C to stop)")
            try:
                while good < args.frames:
                    buf.extend(ser.read(4096))
                    while good < args.frames:
                        i = buf.find(P.SOF)
                        if i < 0:
                            # 保留可能的半截 SOF（末尾 0x55）
                            if buf and buf[-1] == P.SOF[0]:
                                del buf[:-1]
                            else:
                                buf.clear()
                            break
                        if i:
                            del buf[:i]
                        if len(buf) < 6:
                            break
                        ln = int.from_bytes(buf[4:6], "little")
                        # Len 上限（2026-10-24 审查 A3）：单帧 payload 不会超过
                        # max_payload+64。假 SOF 把 Len 读成 0xFFFF 时若不设限，
                        # 会一直等 65 KB 且期间误组帧。
                        if ln > max_payload + 64:
                            del buf[:1]          # 丢掉假 SOF 的头，重新搜索
                            continue
                        total = 8 + ln + 2       # SOF + hdr(6) + payload + CRC
                        if len(buf) < total:
                            break
                        frame = bytes(buf[:total])
                        del buf[:total]
                        try:
                            ver, ft, seq, payload = P.parse_frame(frame)
                        except ValueError as e:
                            bad += 1
                            print(f"  [bad {bad:02d}] {total}B dropped: {e}")
                            continue
                        good += 1
                        saved.append(frame)
                        print(f"  [{good:02d}] {total}B ver={ver} type={ft} "
                              f"seq={seq} payload={len(payload)}B CRC=OK")
                        if len(payload) != max_payload:
                            print(f"       payload size mismatch for N_CH={n_ch}, skip")
                            continue
                        d = P.parse_matrix_payload(payload, n_ch)
                        pairs = [f"A{a}->B{b}"
                                 for a in range(n_ch) for b in range(n_ch)
                                 if (d["matrix"] >> (a * n_ch + b)) & 1]
                        print(f"       cls={d['cls']} ({cls_names.get(d['cls'], '?')}) "
                              f"open=0x{d['open_flags']:04X} "
                              f"stuck=0x{d['stuck_low_mask']:04X} "
                              f"ts0=0x{d['ts0']:02X}")
                        print(f"       connections={len(pairs)}: "
                              + (", ".join(pairs) if pairs else "-"))
            except KeyboardInterrupt:
                print("\nstopped")
    except serial.SerialException as e:
        print(f"serial open failed: {e}", file=sys.stderr)
        return 1

    if args.save and saved:
        Path(args.save).write_text(
            "\n".join(f.hex() for f in saved) + "\n", encoding="utf-8")
        print(f"saved {len(saved)} frame(s) -> {args.save}")
    print(f"done: good={good} bad={bad}")
    return 0 if good else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xunji", description="瞬迹主机侧工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser("sync", help="把 rtl/sim/constrs/scripts 镜像到英文构建目录")
    p_sync.add_argument(
        "--dest",
        default=r"D:\xunjiji",
        help="构建目录（默认 D:\\xunjiji，规避 Vivado 中文路径问题）",
    )

    sub.add_parser("lint", help="Verilator lint（纯 RTL，秒级反馈）")
    sub.add_parser("sim", help="iverilog+vvp 快速仿真（非终审；终审以 xsim 为准）")
    sub.add_parser("xsim", help="Vivado xsim 终审仿真（分钟级，最终权威）")

    p_read = sub.add_parser(
        "read", help="串口监听：SOF 搜索 + Len 定长 + CRC 校验 + 矩阵展开")
    p_read.add_argument("--port", required=True, help="串口号，如 COM4")
    p_read.add_argument("--baud", type=int, default=115_200)
    p_read.add_argument("--n-ch", type=int, default=16, choices=(4, 16))
    p_read.add_argument("--frames", type=int, default=3, help="收满几帧后退出")
    p_read.add_argument("--save", help="把原始帧存成 hex（每行一帧）用于存证")

    args = parser.parse_args(argv)

    if args.command == "sync":
        src = _repo_root()
        dst = Path(args.dest)
        synced = sync_to_build(src, dst)
        print(f"已镜像 {len(synced)} 个目录 {synced} -> {dst}")
        if not synced:
            print("警告：没有可镜像的源目录", file=sys.stderr)
            return 1
        print("下一步：在构建目录运行 scripts/create_project.tcl（或 simulate/build.tcl）")
    elif args.command == "lint":
        return _cmd_lint(_repo_root())
    elif args.command == "sim":
        return _cmd_sim(_repo_root())
    elif args.command == "xsim":
        return _cmd_xsim(_repo_root())
    elif args.command == "read":
        return _cmd_read(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
