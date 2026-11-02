# J5 上板前四方逐针复核（AGENTS §6 红线 6 / §27-GO 的可复跑证据）
#
# 用法: D:/Embedded/Python/python.exe check_j5_pins.py   （需 python-docx、pypdf）
# 四方基准:
#   ① EGO1 V2.2 官方手册（资料/EGO1板卡/Ego1_UserManual_v2.2.pdf，封面 2018.04 ver2.2）
#   ② 南邮 eelab 转存 18 页件（资料/EGO1板卡/EGo1_用户手册_全文提取.txt，无版本标记）
#   ③ V1.9 §4.1 表3（doc/瞬迹_完整可行技术路线_EGO1开发板版_V1.9.docx）
#   ④ 实施约束（constrs/ego1.xdc）
# 任何一项不一致 → 打印 ✗ 并以退出码 1 结束。
import re
import sys
from pathlib import Path

import docx
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent          # doc/reports/2026-10-11-j5-pin-review/
REPO = HERE.parents[2]                          # 瞬迹/（git 仓库根）
WS = HERE.parents[3]                            # 工作区根（含 资料/）
MATS = WS / "资料" / "EGO1板卡"
ROW_RE = re.compile(r"^\s*(\d{1,2})\s+(\S+)\s+([A-Z]\d{1,2})\s*$")


def parse_v22() -> dict:
    """V2.2 正式版手册 J5 表（第 20-21 页，2x18 标号/原理图标号/FPGA IO PIN）。"""
    r = PdfReader(MATS / "Ego1_UserManual_v2.2.pdf")
    cover = r.pages[0].extract_text() or ""
    if "ver2.2" not in cover:
        raise SystemExit("V2.2 手册封面缺 ver2.2 字样，版本自证失败")
    rows = {}
    for pi in (19, 20):
        for ln in (r.pages[pi].extract_text() or "").splitlines():
            m = ROW_RE.match(ln.strip())
            if m and 1 <= int(m.group(1)) <= 32:
                rows.setdefault(int(m.group(1)), (m.group(2), m.group(3)))
    return rows


def parse_njupt() -> dict:
    """南邮转存件提取文本的 J5 表（页 17-18）。"""
    txt = (MATS / "EGo1_用户手册_全文提取.txt").read_text(encoding="utf-8")
    rows = {}
    for part in txt.split("2x18 标号 原理图标号 FPGA IO PIN")[1:]:
        for ln in part.splitlines():
            m = ROW_RE.match(ln.strip())
            if m and 1 <= int(m.group(1)) <= 32:
                rows.setdefault(int(m.group(1)), (m.group(2), m.group(3)))
    return rows


def parse_v19() -> dict:
    """V1.9 §4.1 表3：针号 → (项目信号, 原理图标号, PACKAGE_PIN, 备注)。"""
    d = docx.Document(REPO / "doc" / "瞬迹_完整可行技术路线_EGO1开发板版_V1.9.docx")
    rows = {}
    for row in d.tables[3].rows[1:]:
        c = [x.text.strip() for x in row.cells]
        rows[int(c[0])] = (c[1], c[2], c[3], c[4])
    return rows


def parse_xdc() -> dict:
    """J5 注释行：针号 → (端口[位号], ball)。"""
    src = (REPO / "constrs" / "ego1.xdc").read_text(encoding="utf-8")
    rows = {}
    for m in re.finditer(
        r"PACKAGE_PIN\s+(\w+).*?get_ports\s+\{\s*(\w+\[\d+\])\s*\}.*?#\s*J5-(\d+)", src
    ):
        rows[int(m.group(3))] = (m.group(2), m.group(1))
    return rows, src


def main() -> int:
    v22, nj, v19 = parse_v22(), parse_njupt(), parse_v19()
    xdc, xdc_src = parse_xdc()
    fails = []

    hdr = f"{'针':>3} {'V2.2':>6} {'南邮':>6} {'表3':>6} {'XDC':>6} {'原理图标号':>10} {'端口/信号':>16} 判定"
    print(hdr)
    print("-" * len(hdr))
    for n in range(1, 37):
        a, b, c, x = v22.get(n), nj.get(n), v19.get(n), xdc.get(n)
        ok = True
        if n <= 32:
            balls = [a[1] if a else None, b[1] if b else None,
                     c[2] if c else None, x[1] if x else None]
            want_port = f"a_ctrl_n[{n-1}]" if n <= 16 else f"b_raw[{n-17}]"
            # ball 四方一致；网络标号两手册一致；表3 信号含端口；XDC 端口/球位对号
            ok = (
                None not in balls and len(set(balls)) == 1
                and a[0] == b[0] == c[1]
                and want_port in c[0] and x[0] == want_port
            )
        else:  # 33..36：电源针，两手册与 XDC 均不得出现，表3 记 GND/3.3V
            ok = a is None and b is None and x is None and c is not None and c[1] in ("GND", "3.3V")
        if not ok:
            fails.append(n)
        net = (c[1] if c else "—") if n <= 32 else (v19[n][1] if n in v19 else "—")
        port = (x[0] if x else "—") if n <= 32 else (v19[n][0] if n in v19 else "—")
        col = lambda v, i=1: (v[i] if v else "—")
        print(f"{n:>3} {col(a):>6} {col(b):>6} {col(c,2):>6} {col(x):>6} {net:>10} {port:>16} "
              f"{'✓' if ok else '✗'}")

    # 重复 ball 检测：必须用 \w+ 整词捕获后再计数（子串 count 会把 H1 误配到 H17）
    all_balls = re.findall(r"PACKAGE_PIN\s+(\w+)", xdc_src)
    dups = sorted({p for p in all_balls if all_balls.count(p) > 1})
    counts = (len(v22), len(nj), len(v19), len(xdc))
    if dups:
        fails.append(f"重复ball:{dups}")
    if counts != (32, 32, 36, 32):
        fails.append(f"覆盖数异常:{counts}")
    print()
    print(f"覆盖针数 V2.2={counts[0]}/32 南邮={counts[1]}/32 表3={counts[2]}/36 XDC={counts[3]}/32；"
          f"全文件重复 PACKAGE_PIN: {dups or '无'}")
    if fails:
        print(f"结论: FAIL — 不一致项 {fails}")
        return 1
    print("结论: PASS — 四方 36/36 全一致，0 差异")
    return 0


if __name__ == "__main__":
    sys.exit(main())
