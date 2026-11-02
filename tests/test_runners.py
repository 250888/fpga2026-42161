# tests/test_runners.py — 子进程封装：退出码/超时/UTF-8 安全（设计 §3、§4 I3/M7）
import sys
from xunji.hdl.runners import run_tool

def test_中文输出不崩溃且完整还原(tmp_path):
    fake = tmp_path / "fake.py"
    fake.write_text("import sys; sys.stdout.reconfigure(encoding='utf-8'); print('错误：模块 a.v 第 3 行'); sys.exit(1)", encoding="utf-8")
    r = run_tool([sys.executable, str(fake)], timeout=30)
    assert r.code == 1
    assert "错误：模块 a.v 第 3 行" in r.out

def test_超时返回非零且标记(tmp_path):
    fake = tmp_path / "slow.py"
    fake.write_text("import time; time.sleep(10)", encoding="utf-8")
    r = run_tool([sys.executable, str(fake)], timeout=2)
    assert r.code != 0 and r.timed_out

def test_退出码与stdout捕获(tmp_path):
    fake = tmp_path / "ok.py"
    fake.write_text("import sys; print('ALL GOOD'); sys.exit(0)", encoding="utf-8")
    r = run_tool([sys.executable, str(fake)], timeout=30)
    assert r.code == 0 and "ALL GOOD" in r.out and not r.timed_out

def test_工具不存在返回127(tmp_path):
    r = run_tool([str(tmp_path / "no_such_tool.exe")], timeout=10)
    assert r.code == 127 and not r.timed_out
