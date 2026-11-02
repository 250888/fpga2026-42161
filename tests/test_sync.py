# xunji sync 构建目录镜像测试
# 约定：将仓库内 {rtl, sim, constrs, scripts} 镜像到英文构建目录（默认 D:\xunjiji），
# 目标侧同名子目录整体替换（清残留），并跳过 .Xil/.git 等垃圾目录。
from pathlib import Path

from xunji.cli import MIRROR_DIRS, sync_to_build


def _make_src(tmp_path: Path) -> Path:
    src = tmp_path / "repo"
    (src / "rtl").mkdir(parents=True)
    (src / "constrs").mkdir()
    (src / "rtl" / "xj_top.v").write_text("module xj_top(); endmodule\n", encoding="utf-8")
    (src / "constrs" / "ego1.xdc").write_text("set_property -dict {}\n", encoding="utf-8")
    return src


class TestSyncToBuild:
    def test_镜像指定目录(self, tmp_path):
        src = _make_src(tmp_path)
        build = tmp_path / "build"
        sync_to_build(src, build)
        assert (build / "rtl" / "xj_top.v").read_text(encoding="utf-8").startswith("module")
        assert (build / "constrs" / "ego1.xdc").exists()
        # 未列入镜像范围的目录不搬运
        assert not (build / "doc").exists()

    def test_清除目标侧残留文件(self, tmp_path):
        src = _make_src(tmp_path)
        build = tmp_path / "build"
        stale = build / "rtl"
        stale.mkdir(parents=True)
        (stale / "deleted_upstream.v").write_text("stale\n", encoding="utf-8")
        sync_to_build(src, build)
        assert not (build / "rtl" / "deleted_upstream.v").exists()
        assert (build / "rtl" / "xj_top.v").exists()

    def test_跳过垃圾目录(self, tmp_path):
        src = _make_src(tmp_path)
        junk = src / "rtl" / ".Xil"
        junk.mkdir()
        (junk / "tmp.txt").write_text("junk\n", encoding="utf-8")
        build = tmp_path / "build"
        sync_to_build(src, build)
        assert not (build / "rtl" / ".Xil").exists()

    def test_镜像范围恰为四个源目录(self):
        # rtl/sim/constrs/scripts —— 与 Vivado Tcl 脚本的输入一致
        assert MIRROR_DIRS == ("rtl", "sim", "constrs", "scripts")
