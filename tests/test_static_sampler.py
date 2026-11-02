# tests/test_static_sampler.py — 静态扫描 FSM 冻结参数与验证管线红线（V1.9 P057/P059）
#
# 红线（AGENTS.md §6.5）：V1.9 静态时序参数属「须有实测依据才能调」的参数，
# 不得在无示波器/Vivado 依据时静默漂移；改参数必须先改文档并在此同步说明。
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
RTL = REPO / "rtl"
SIM = REPO / "sim"
CLI = REPO / "src" / "xunji" / "cli.py"

SCANNER = RTL / "topology_scanner.v"


def _t(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_默认参数与V19一致():
    """V1.9 P057：SETTLE=500 / SAMPLE=101（奇数防平票）/ GUARD 稳定 8 / 超时 500。"""
    src = _t(SCANNER)
    params = dict(re.findall(r"parameter\s+(\w+)\s*=\s*(\d+)", src))
    assert params.get("SETTLE") == "500", f"SETTLE 漂移: {params.get('SETTLE')}"
    assert params.get("SAMPLE_CYCLES") == "101", f"SAMPLE_CYCLES 漂移: {params.get('SAMPLE_CYCLES')}"
    assert int(params.get("SAMPLE_CYCLES", "0")) % 2 == 1, "采样窗必须为奇数拍（V1.9 防 50/50 平票）"
    assert params.get("GUARD_STABLE") == "8", f"GUARD_STABLE 漂移: {params.get('GUARD_STABLE')}"
    assert params.get("GUARD_TIMEOUT") == "500", f"GUARD_TIMEOUT 漂移: {params.get('GUARD_TIMEOUT')}"


def test_四阶段与IDLE_CHECK都存在():
    """V1.9 P057：IDLE_CHECK + DRIVE→SETTLE→SAMPLE→RELEASE/GUARD。"""
    src = _t(SCANNER)
    for token in ("IDLE_CHECK", "DRIVE", "SETTLE", "SAMPLE", "RELEASE", "GUARD"):
        assert token in src, f"扫描 FSM 缺阶段标记 {token}"


def test_输出stuck_low与release_timeout():
    """V1.9 R6/P057：stuck_low_mask 单独输出；释放超时单独报错。"""
    src = _t(SCANNER)
    head = src[src.find("module "):src.find(");", src.find("module "))]
    assert "stuck_low_mask" in head, "缺 stuck_low_mask 输出"
    assert "release_timeout" in head, "缺 release_timeout 输出"
    assert "idle_ok" in head, "缺 idle_ok 输出（IDLE_CHECK 结论）"


def test_多数表决实现为票数大于半数():
    """V1.9 P057：SAMPLE_WINDOW 内逐位计数，1 的票数 > 50 才判 1。"""
    src = _t(SCANNER)
    assert re.search(r"SAMPLE_CYCLES\s*/\s*2", src), "多数表决阈值应写成 SAMPLE_CYCLES/2"
    assert "vote" in src.lower(), "缺逐位票数计数（vote）"


def test_仿真顶层已注册():
    """新增 TB 必须进 SIM_TOPS，否则 sim/xsim 永远不跑它。"""
    cli = _t(CLI)
    assert "tb_static_sampler" in cli, "cli.py SIM_TOPS 未注册 tb_static_sampler"
    tb = SIM / "tb_static_sampler.v"
    assert tb.exists(), "缺 sim/tb_static_sampler.v"
    for case in ("matrix/normal", "glitch-immune", "stuck-low", "release_timeout"):
        assert case in _t(tb), f"TB 缺场景 {case}"
