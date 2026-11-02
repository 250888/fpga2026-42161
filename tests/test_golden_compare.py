# tests/test_golden_compare.py — golden_compare / learn_gate 结构与验证管线红线
#
# 红线（AGENTS.md §6.1）：矩阵比较/LEARN 语义由 V1.9 P059/P060 冻结，
# 分类枚举不得静默变更；新增 TB 必须进 SIM_TOPS。
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
RTL = REPO / "rtl"
SIM = REPO / "sim"
CLI = REPO / "src" / "xunji" / "cli.py"


def _t(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_模块存在且端口齐全():
    gc = _t(RTL / "golden_compare.v")
    head = gc[gc.find("module "):gc.find(");", gc.find("module "))]
    for name in ("m_ref", "m_test", "missing", "extra", "cls"):
        assert name in head, f"golden_compare 缺端口 {name}"

    lg = _t(RTL / "learn_gate.v")
    head = lg[lg.find("module "):lg.find(");", lg.find("module "))]
    for name in ("learn", "idle_ok", "m_scan", "reference_valid", "m_ref"):
        assert name in head, f"learn_gate 缺端口 {name}"


def test_分类规则与V19_P060一致():
    """deg>1 优先 BRIDGE；双射换位 MISWIRE；仅缺失且空行 OPEN；其余 ANOMALY。"""
    src = _t(RTL / "golden_compare.v")
    assert "m_ref & ~m_test" in src, "missing 必须按 M_ref & ~M_test 计算"
    assert "~m_ref & m_test" in src, "extra 必须按 ~M_ref & M_test 计算"
    assert "any_gt1" in src and "BRIDGE" in src, "缺 deg>1 优先 BRIDGE 的判据"
    # 分类常量语义（与 TB 的 C_* 对齐）
    for token in ("PASS", "OPEN", "MISWIRE", "BRIDGE", "ANOMALY"):
        assert token in src, f"分类枚举缺 {token}"


def test_LEARN需idle_ok与行列度双1():
    src = _t(RTL / "learn_gate.v")
    assert "idle_ok" in src, "LEARN 必须要求 IDLE_CHECK 通过"
    assert "all_one" in src, "LEARN 必须要求行列连接度均为 1"


def test_TB已注册():
    cli = _t(CLI)
    assert "tb_golden_compare" in cli, "cli.py SIM_TOPS 未注册 tb_golden_compare"
    tb = _t(SIM / "tb_golden_compare.v")
    for case in ("PASS", "OPEN", "MISWIRE", "BRIDGE", "ANOMALY", "learn/accept"):
        assert case in tb, f"TB 缺场景 {case}"
