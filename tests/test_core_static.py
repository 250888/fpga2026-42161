# tests/test_core_static.py — core 静态集成红线（T4）
#
# 红线：LEARN 必须走 btn[1] 上升沿 → learn_gate；分类必须来自 golden_compare 且
# reference_valid=0 时上报 NO_REF(5)，不得把「未学习」伪装成 PASS。
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "rtl" / "xunji_core.v"
SIM = REPO / "sim"


def _t(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _code(p: Path) -> str:
    src = _t(p)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def test_core实例化learn与compare():
    src = _code(CORE)
    assert "learn_gate" in src, "core 未实例化 learn_gate"
    assert "golden_compare" in src, "core 未实例化 golden_compare"
    # LEARN 用「最近一次完整扫描」的快照：SW0 常开时扫描连续重跑，直接学 conn_matrix
    # 会撞上执行中的半成品，而 ~scan_busy 互锁又会让窗口只剩 1 个时钟（2026-10-24 A2）。
    assert re.search(r"\.m_scan\s*\(\s*last_matrix\s*\)", src), \
        "LEARN 必须学习最近一次完整扫描的矩阵"
    assert re.search(r"last_matrix\s*<=\s*conn_matrix", src), \
        "last_matrix 必须来自扫描矩阵，不能是别的来源"
    assert re.search(r"\.m_test\s*\(\s*conn_matrix\s*\)", src), "比较必须针对本轮扫描矩阵"


def test_LEARN走btn1上升沿():
    src = _code(CORE)
    # btn 经两级同步后是 btn_s（2026-10-24 W5），两者都算接了 btn[1]
    assert re.search(r"btn(?:_s)?\[1\]", src), "LEARN 未接 btn[1]"
    assert "learn_pulse" in src, "LEARN 必须做边沿检测（按住不应连续学习）"


def test_未学习时报NO_REF():
    src = _code(CORE)
    assert re.search(r"reference_valid\s*\?\s*cmp_cls\s*:\s*3'd5", src), \
        "reference_valid=0 时必须上报 NO_REF(5)，不得伪装 PASS"


def test_集成TB已注册():
    tb = SIM / "tb_static_cls.v"
    assert tb.exists(), "缺 sim/tb_static_cls.v"
    src = _t(tb)
    for case in ("miswire", "open", "bridge", "pass"):
        assert case in src, f"集成 TB 缺场景 {case}"
    assert "tb_static_cls" in _t(REPO / "src" / "xunji" / "cli.py"), "cli SIM_TOPS 未登记 tb_static_cls"
