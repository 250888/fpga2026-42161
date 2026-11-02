# 生成 lint/仿真两份 filelist；内容一律相对仓库根（cmd 不展开通配符的解法）
# 只收 *.v 一层，不含子目录（规格：无跳过规则）
from pathlib import Path

def write_lists(repo_root: Path, out_dir: Path) -> tuple[Path, Path]:
    repo_root, out_dir = Path(repo_root), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rtl = sorted(p.relative_to(repo_root).as_posix()
                 for p in (repo_root / "rtl").glob("*.v"))
    tb = sorted(p.relative_to(repo_root).as_posix()
                for p in (repo_root / "sim").glob("*.v"))
    rtl_f = out_dir / "rtl.f"
    sim_f = out_dir / "sim.f"
    rtl_f.write_text("\n".join(rtl) + "\n", encoding="utf-8")
    sim_f.write_text("\n".join(rtl + tb) + "\n", encoding="utf-8")
    return rtl_f, sim_f
