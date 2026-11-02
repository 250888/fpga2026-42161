# tests/test_filelist.py — filelist 生成规则（设计 §3、§4）
from pathlib import Path
from xunji.hdl.filelist import write_lists

def _mk_repo(tmp_path: Path) -> Path:
    for d in ("rtl", "sim"):
        (tmp_path / d).mkdir()
    (tmp_path / "rtl" / "a.v").write_text("module a(); endmodule\n")
    (tmp_path / "rtl" / "b.v").write_text("module b(); endmodule\n")
    (tmp_path / "sim" / "tb_a.v").write_text("module tb_a(); endmodule\n")
    return tmp_path

def test_rtl清单不含sim目录(tmp_path):
    repo = _mk_repo(tmp_path)
    rtl_f, _ = write_lists(repo, repo / "build")
    assert all("sim" not in ln for ln in rtl_f.read_text(encoding="utf-8").splitlines())

def test_sim清单含RTL后接TB(tmp_path):
    repo = _mk_repo(tmp_path)
    _, sim_f = write_lists(repo, repo / "build")
    lines = sim_f.read_text(encoding="utf-8").splitlines()
    assert lines[-1].replace("\\", "/").endswith("sim/tb_a.v")
    assert all(ln.replace("\\", "/").startswith("rtl/") for ln in lines[:-1])

def test路径相对仓库根非绝对(tmp_path):
    repo = _mk_repo(tmp_path)
    rtl_f, _ = write_lists(repo, repo / "build")
    assert all(not Path(ln).is_absolute()
               for ln in rtl_f.read_text(encoding="utf-8").splitlines())

def test清单落build目录(tmp_path):
    repo = _mk_repo(tmp_path)
    write_lists(repo, repo / "build")
    assert (repo / "build" / "rtl.f").exists()
    assert (repo / "build" / "sim.f").exists()

def test_从子目录调用仍落build(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    monkeypatch.chdir(repo / "rtl")
    write_lists(repo, repo / "build")
    assert (repo / "build" / "rtl.f").exists()

def test_只收一层v不收子目录(tmp_path):
    repo = _mk_repo(tmp_path)
    (repo / "rtl" / "nested").mkdir()
    (repo / "rtl" / "nested" / "deep.v").write_text("module deep(); endmodule\n")
    rtl_f, _ = write_lists(repo, repo / "build")
    assert "deep" not in rtl_f.read_text(encoding="utf-8")
