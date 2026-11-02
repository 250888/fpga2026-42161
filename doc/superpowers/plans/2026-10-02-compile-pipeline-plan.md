# 三层验证流水线 实现计划（v2）

> **面向 AI 代理的工作者**：必需子技能：superpowers:subagent-driven-development（SDD）逐任务实现。步骤用 `- [ ]` 跟踪。
> **规格唯一来源**：`doc/superpowers/specs/2026-10-02-compile-pipeline-design.md`（"设计"）。冲突 → 停下问。
> **v2 变更**：修复计划复审 REJECT 的 C1-C4/I1-I7/Minor 全部发现；新增任务 0（worktree+账本）与任务 8（最终审查+合并）。

**目标**：RTL 可编译可仿真——G1 verilator lint、G2 iverilog/vvp PASS、G3 一条命令+失败注入、G4 xsim 终审、G5 红灯独立提交、G6 worktree 分支合并。

**证据目录**：`doc/reports/2026-10-02-compile/`（每任务 mkdir 保障存在）。**G2/G4 判定（写死）**：`退出码0 ∧ 有行 strip()=="PASS" ∧ 无行 startswith("FAIL")`（xsim 只取后两条）。

**全局约束**：
- 不改 RTL 行为（V1.9 红线）；TB 允许改失败路径/波形宏；lint 告警只许用 `scripts/lint.vlt` 豁免（逐条注明理由），**涉 RTL 语义 → 停下报告**。
- cmd.exe；subprocess 显式 `encoding="utf-8", errors="replace"`；文件清单代替通配符。
- 每任务一个提交（Conventional Commits 中文）；红灯测试独立提交；**绝不在 main 直接开工**（任务 0 建 worktree）。
- 逐任务复审 + 最终审查由 SDD 流程内置（本计划不重复派发指令）。

---

## 任务 0：文档入库 + worktree + 账本 + 基线（G6 起点）

- [ ] **步骤 0.5：在 main 上提交设计与计划文档**（N3：文档是共享资产，评审已过；"不在 main 实现"指代码）

```bat
cd /d D:\UserFolders\Desktop\嵌赛FPGA\瞬迹
git add doc\superpowers\ doc\HANDOFF_AI.md doc\实施计划.md
git commit -m "docs(specs): 编译流水线设计与实现计划（双轮独立复审通过）"
```

- [ ] **步骤 1：验证忽略规则**（using-git-worktrees 步骤 1b 前置）

```bat
git check-ignore -v .worktrees
git check-ignore -v .superpowers
```
预期：`.gitignore:17:.worktrees/`；`.superpowers/` 未忽略则**追加进 .gitignore 并入步骤 0.5 提交**（SDD 账本为 gitignore 临时文件——不入库，恢复靠本会话+git log）。

- [ ] **步骤 2：建 worktree 与分支**

```bat
git worktree add .worktrees/feature/compile-pipeline -b feature/compile-pipeline
cd /d D:\UserFolders\Desktop\嵌赛FPGA\瞬迹\.worktrees\feature\compile-pipeline
uv sync
```

- [ ] **步骤 3：基线测试（起飞前审查）**

```bat
uv run pytest -q
```
预期：15 passed（既有基线全绿）。红了 → 停下报告，不开工。

- [ ] **步骤 4：建账本**（SDD 恢复地图，文件第一行必须是计划路径）

```bat
mkdir .superpowers\sdd 2>nul
echo # SDD ledger — plan: doc/superpowers/plans/2026-10-02-compile-pipeline-plan.md> .superpowers\sdd\progress.md
echo Task 0: worktree ready (.worktrees/feature/compile-pipeline, baseline 15 passed)>> .superpowers\sdd\progress.md
```

后续所有任务在此 worktree 内执行（本计划余下步骤的 cwd 都指它）。

---

## 任务 1：T0 安装探针（iverilog + verilator）

**文件**：证据 `doc/reports/2026-10-02-compile/toolchain_versions.txt`

- [ ] **步骤 0：建证据目录**

```bat
mkdir doc\reports\2026-10-02-compile 2>nul
```

- [ ] **步骤 1：执行安装**

```bat
D:\msys64\usr\bin\pacman.exe -Sy --noconfirm --needed mingw-w64-ucrt-x86_64-iverilog mingw-w64-ucrt-x86_64-verilator
```
预期：退出码 0。
失败分支（按序）：① 签名校验失败 → `D:\msys64\usr\bin\pacman.exe -S --noconfirm msys2-keyring`（msys 仓库包，**不带 mingw 前缀**）后重试原命令；② 仍失败（签名阻断任何 -S）→ 报告 BLOCKED，走 Plan B（msys2 仓库直下 `.pkg.tar.zst` 手动解包，或 oss-cad-suite 走 ghfast.top），**不擅自换方案**。

- [ ] **步骤 2：验证与留档（含爆炸半径探针）**

```bat
D:\msys64\ucrt64\bin\iverilog.exe -V > doc\reports\2026-10-02-compile\toolchain_versions.txt 2>&1
D:\msys64\ucrt64\bin\verilator.exe --version >> doc\reports\2026-10-02-compile\toolchain_versions.txt 2>&1
D:\msys64\usr\bin\pacman.exe -Q mingw-w64-ucrt-x86_64-iverilog mingw-w64-ucrt-x86_64-verilator >> doc\reports\2026-10-02-compile\toolchain_versions.txt 2>&1
D:\msys64\ucrt64\bin\uv.exe --version >> doc\reports\2026-10-02-compile\toolchain_versions.txt 2>&1
```
预期：四段输出均非空（最后一行验证 uv 宿主未被波及）。
**顺手验证（设计残余提醒）**：`D:\Xilinx\Vivado\Vivado\2024.2\bin\xvlog.bat -help | findstr /i sv` 只做记录，不阻塞。

- [ ] **步骤 3：提交**

```bat
git add doc/reports/2026-10-02-compile/
git commit -m "chore(toolchain): 安装探针记录 iverilog/verilator 版本与 uv 完好（T0）"
```

---

## 任务 2：filelist.py（TDD，红灯独立提交）

**文件**：`tests/test_filelist.py`；`src/xunji/hdl/__init__.py`、`src/xunji/hdl/filelist.py`
**接口规格**：`write_lists(repo_root: Path, out_dir: Path) -> tuple[Path, Path]`（返回 rtl.f、sim.f 路径）。**无跳过规则——只收 `*.v` 一层，不含子目录。**

- [ ] **步骤 1：写失败测试**（完整代码；`rtl_f, _ =` 解包与实现签名一致——C1 已修）

```python
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
```

- [ ] **步骤 2：确认红灯 + 独立提交（G5）**

```bat
uv run pytest tests\test_filelist.py -v
git add tests\test_filelist.py
git commit -m "test(filelist): 红灯——filelist 生成规则用例（TDD step1）"
```
预期：FAIL，`ModuleNotFoundError: No module named 'xunji.hdl'`（功能缺失型）。

- [ ] **步骤 3：（占位——checkout 复现统一放在各任务"步骤 5 绿灯提交"之后执行，见各任务末尾的 G5 复现步骤）**

- [ ] **步骤 4：实现（最少代码）**

`src/xunji/hdl/__init__.py`：空文件。
`src/xunji/hdl/filelist.py`：

```python
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
```

- [ ] **步骤 5：确认绿灯 + 提交**

```bat
uv run pytest tests\ -q
git add src\xunji\hdl tests\test_filelist.py
git commit -m "feat(hdl): filelist 生成器——rtl.f/sim.f 双清单（TDD）"
```
预期：全绿（既有 15 + 新 6）。

- [ ] **步骤 6：G5 红灯 checkout 复现（I5，实现提交之后执行）**

```bat
for /f %i in ('git log --format^=%%H -2') do @set SHA2=%i
git log --oneline -3   :: 确认红灯 SHA = "test(filelist): 红灯" 那个提交，记为 RED_SHA
git checkout <RED_SHA>
uv run pytest tests\test_filelist.py -q   :: 必须红：ModuleNotFoundError xunji.hdl
git checkout feature/compile-pipeline
uv run pytest tests\ -q                   :: 切回后必须恢复全绿
```
把两段输出（红/绿）记入执行报告 = G5 复现证据。

---

## 任务 3：runners.py（TDD，红灯独立提交）

**文件**：`tests/test_runners.py`；`src/xunji/hdl/runners.py`
**接口规格**：`run_tool(cmd: list[str], *, timeout: int, cwd: str | None = None) -> RunResult`；`RunResult(code:int, out:str, timed_out:bool)`

- [ ] **步骤 1：写失败测试**

```python
# tests/test_runners.py — 子进程封装：退出码/超时/UTF-8 安全（设计 §3、§4 I3/M7）
import sys
from xunji.hdl.runners import run_tool

def test_中文输出不崩溃且完整还原(tmp_path):
    fake = tmp_path / "fake.py"
    fake.write_text("import sys; print('错误：模块 a.v 第 3 行'); sys.exit(1)", encoding="utf-8")
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
```

- [ ] **步骤 2：确认红灯 + 独立提交（G5）**

```bat
uv run pytest tests\test_runners.py -v
git add tests\test_runners.py
git commit -m "test(runners): 红灯——子进程封装用例（TDD step1）"
```

- [ ] **步骤 3：实现**

```python
# src/xunji/hdl/runners.py
# 子进程统一出口：UTF-8 replace 防 GBK 崩溃（设计 I3）、超时、退出码透传
import subprocess
from dataclasses import dataclass

@dataclass
class RunResult:
    code: int
    out: str
    timed_out: bool = False

def run_tool(cmd: list[str], *, timeout: int, cwd: str | None = None) -> RunResult:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return RunResult(code=p.returncode, out=p.stdout + p.stderr)
    except subprocess.TimeoutExpired as e:
        out = e.stdout or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        return RunResult(code=124, out=out + f"\n[TIMEOUT after {timeout}s]", timed_out=True)
    except FileNotFoundError:
        return RunResult(code=127, out=f"工具不存在: {cmd[0]}")
```

- [ ] **步骤 4：确认绿灯 + 提交**

```bat
uv run pytest tests\ -q
git add src\xunji\hdl\runners.py tests\test_runners.py
git commit -m "feat(hdl): 子进程封装——UTF-8/超时/退出码（TDD）"
```

- [ ] **步骤 5：G5 红灯 checkout 复现（同任务 2 步骤 6 手法）**

```bat
git log --oneline -3   :: 记下 "test(runners): 红灯" 的 RED_SHA
git checkout <RED_SHA>
uv run pytest tests\test_runners.py -q   :: 必须红：ModuleNotFoundError xunji.hdl.runners
git checkout feature/compile-pipeline
uv run pytest tests\ -q                   :: 恢复全绿
```
红/绿两段输出记入执行报告。

---

## 任务 4：cli 接线 lint/sim + 真实跑通（G1/G2/G3）

**文件**：修改 `src/xunji/cli.py`；新建 `scripts/lint.vlt`；证据目录

**实现约定（来自设计，已定死无裁量）**：
- 工具探测：`shutil.which` 优先，兜底绝对路径 `D:\msys64\ucrt64\bin\{verilator,iverilog,vvp}.exe`；code 127 → 打印安装命令。
- 超时：verilator lint 120s、iverilog 编译 120s、vvp 60s。
- lint 命令（**显式携带 lint.vlt——C4 已修**）：
  `verilator --lint-only --language 1364-2005 -Wall --top-module xj_top -f build/rtl.f scripts/lint.vlt`，cwd=仓库根。
- sim：编译用**显式文件列表**（读 `build/sim.f` 逐行作为参数——与下方 `_cmd_sim` 代码一致；cmd 下 `-c` 清单文件同样合法但本计划统一显式列表，避免两套写法），`iverilog -g2005 -s tb_xj_top -o build/tb_xj_top.vvp <files...>`（cwd=仓库根，超时120）→ `vvp build/tb_xj_top.vvp`（超时60）→ G2 三重判定。
- `build/` 与清单在仓库根下（xsim 层例外见任务 6）。

- [ ] **步骤 1：scripts/lint.vlt**

```
// scripts/lint.vlt — Verilator 豁免（显式可审计，不关 -Wall）
// 用法示例（被 lint 命令显式携带）：lint_off -rule UNUSED -file "rtl/*.v"
// 首版无豁免；出现告警时逐条加并注明规则+理由，涉 RTL 语义则停下报告
```

- [ ] **步骤 2：cli.py 完整接线（C2 已修——全部代码给全）**

在 `main()` 现有 subparsers 处添加（与 sync 并列）：

```python
    sub.add_parser("lint", help="Verilator lint（纯 RTL，秒级反馈）")
    sub.add_parser("sim", help="iverilog+vvp 快速仿真（非终审；终审以 xsim 为准）")
```

分发段（与现有 `if args.command == "sync": ...` 并列）：

```python
    if args.command == "sync":
        ...  # 既有代码不动
    elif args.command == "lint":
        return _cmd_lint(_repo_root())
    elif args.command == "sim":
        return _cmd_sim(_repo_root())
    return 0
```

新增函数（放 `sync_to_build` 之后）：

```python
def _hdl_tools() -> tuple[str, str, str]:
    """verilator/iverilog/vvp 路径：PATH 优先，兜底 msys2 绝对路径。"""
    import shutil
    fallback = {
        "verilator": r"D:\msys64\ucrt64\bin\verilator.exe",
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


def _cmd_lint(repo: Path) -> int:
    from .hdl.filelist import write_lists
    from .hdl.runners import run_tool
    verilator, _, _ = _hdl_tools()
    rtl_f, _ = write_lists(repo, repo / "build")
    cmd = [verilator, "--lint-only", "--language", "1364-2005", "-Wall",
           "--top-module", "xj_top",
           "-f", str(rtl_f.relative_to(repo)),
           str(repo / "scripts" / "lint.vlt")]
    r = run_tool(cmd, timeout=120, cwd=str(repo))
    print(r.out)
    if r.code == 127:
        print("未安装 verilator：D:\\msys64\\usr\\bin\\pacman.exe -Sy --noconfirm --needed "
              "mingw-w64-ucrt-x86_64-verilator")
    return 0 if r.code == 0 else 1


def _cmd_sim(repo: Path) -> int:
    from .hdl.filelist import write_lists
    from .hdl.runners import run_tool
    _, iverilog, vvp = _hdl_tools()
    _, sim_f = write_lists(repo, repo / "build")
    files = [ln for ln in sim_f.read_text(encoding="utf-8").splitlines() if ln.strip()]
    out_vvp = repo / "build" / "tb_xj_top.vvp"
    # ① 编译（cmd 不展开通配符 → 显式文件列表）
    r = run_tool([iverilog, "-g2005", "-s", "tb_xj_top", "-o", str(out_vvp)] + files,
                 timeout=120, cwd=str(repo))
    if r.code != 0:
        print(r.out)
        return 1
    # ② 运行
    r = run_tool([vvp, str(out_vvp)], timeout=60, cwd=str(repo))
    print(r.out)
    # ③ G2 三重判定
    return 0 if _g2_pass(r.out, r.code) else 1
```

- [ ] **步骤 3：真实运行 G1/G2 + 版本行落档（I1）**

```bat
uv run xunji lint > doc\reports\2026-10-02-compile\lint_g1.txt 2>&1
echo lint_exit=%ERRORLEVEL%>> doc\reports\2026-10-02-compile\lint_g1.txt
verilator --version >> doc\reports\2026-10-02-compile\lint_g1.txt 2>&1

uv run xunji sim > doc\reports\2026-10-02-compile\sim_g2.txt 2>&1
echo sim_exit=%ERRORLEVEL%>> doc\reports\2026-10-02-compile\sim_g2.txt
iverilog -V >> doc\reports\2026-10-02-compile\sim_g2.txt 2>&1
```
预期：lint_exit=0；sim_exit=0 且 sim_g2.txt 含整行 PASS、无 FAIL 行。
**lint 若红**：只许在 `scripts/lint.vlt` 加豁免（注明规则+理由）；涉 RTL 语义 → 停下报告。
（注：PATH 若无 verilator/iverilog，用绝对路径调用生成版本行。）

- [ ] **步骤 4：G3 失败注入（双入口，输出落文件——I2 已修）**

```bat
python -c "from pathlib import Path; p=Path('rtl/xj_top.v'); p.write_text(p.read_text(encoding='utf-8').replace('endmodule',''), encoding='utf-8')"
uv run xunji lint > doc\reports\2026-10-02-compile\g3_injection.txt 2>&1
echo lint_inject_exit=%ERRORLEVEL%>> doc\reports\2026-10-02-compile\g3_injection.txt
uv run xunji sim >> doc\reports\2026-10-02-compile\g3_injection.txt 2>&1
echo sim_inject_exit=%ERRORLEVEL%>> doc\reports\2026-10-02-compile\g3_injection.txt
git checkout -- rtl\xj_top.v
uv run xunji lint > nul 2>&1
echo lint_restored_exit=%ERRORLEVEL%>> doc\reports\2026-10-02-compile\g3_injection.txt
git status --short
```
预期：两个 inject_exit 均非 0；lint_restored_exit=0；`git status --short` 对 rtl/ 无残留（恢复可验证）。

- [ ] **步骤 5：提交**

```bat
git add src\xunji\cli.py scripts\lint.vlt doc\reports\2026-10-02-compile\
git commit -m "feat(cli): lint/sim 子命令接线，G1/G2/G3 实测通过"
```

---

## 任务 5：TB 失败路径 $fatal + DUMP_VCD 宏

**文件**：修改 `sim/tb_xj_top.v`（授权范围：设计 §1.3）

- [ ] **步骤 1：mismatch 分支改 $fatal（逐字对照，C2/M 拼写已修）**

改前（现 89-91 行）：

```verilog
            $display("FAIL mismatch");
        end
        repeat(20) @(posedge clk);
        $finish;
```

改后：

```verilog
            $display("FAIL mismatch");
        end
        repeat(5) @(posedge clk);
        if (/* mismatch 分支置位的标志，按 TB 实际结构 */ 1'b1)
            $fatal(1, "TOPOLOGY MISMATCH");
        else
            $finish;
```
（实现者按 TB 实际控制流落地：**成功路径走 `$finish` + 整行 `PASS`；mismatch 路径 `$display("FAIL ...")` 后 `$fatal(1, ...)` 使 vvp 退出码非零**；若 TB 结构不适合 if/else，用 `disable`/标志位等价结构，语义必须满足前述两句。）

- [ ] **步骤 2：波形宏**（加在模块体首部）

```verilog
`ifdef DUMP_VCD
    initial begin
        $dumpfile("build/tb_xj_top.vcd");
        $dumpvars(0, tb_xj_top);
    end
`endif
```

- [ ] **步骤 3：正反双向验证 + 重采 G2 证据（I4 已修）**

```bat
uv run xunji sim > doc\reports\2026-10-02-compile\sim_g2.txt 2>&1
echo sim_exit=%ERRORLEVEL%>> doc\reports\2026-10-02-compile\sim_g2.txt
```
（改 TB 后重采，覆盖旧证据；预期仍 PASS、exit 0。）
反向验证（**注入锚点=86 行比较条件**，替换为 `1'b0` 使 mismatch 必触发；预期 vvp 打印 FAIL 且因 $fatal 非零退出）。
先创建一次性注入脚本（避免 cmd 引号嵌套问题）：

```python
# scripts/_inject_tb.py（一次性，验证后删除）
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "sim" / "tb_xj_top.v"
t = p.read_text(encoding="utf-8")
old = "if (dut.conn_matrix === EXPECT && dut.open_flags === 4'b0000)"
assert old in t, "锚点未命中，停下检查 TB 结构"
p.write_text(t.replace(old, "if (1'b0)"), encoding="utf-8")
print("injected")
```

```bat
python scripts\_inject_tb.py
uv run xunji sim > doc\reports\2026-10-02-compile\g5_tb_inject.txt 2>&1
echo sim_inject_exit=%ERRORLEVEL%>> doc\reports\2026-10-02-compile\g5_tb_inject.txt
git checkout -- sim\tb_xj_top.v
del scripts\_inject_tb.py
uv run xunji sim > nul 2>&1
echo sim_restored_exit=%ERRORLEVEL%>> doc\reports\2026-10-02-compile\g5_tb_inject.txt
git status --short
```
预期：`sim_inject_exit` 非 0 且文件内含 FAIL 行；`sim_restored_exit=0`；`git status --short` 对 sim/ 干净。
顺序裁定：**先提交步骤 1+2，再做注入-恢复**，保证 `git checkout` 恢复到"已改好的 TB"。

- [ ] **步骤 4：提交（步骤 1+2 先行）**

```bat
git add sim\tb_xj_top.v doc\reports\2026-10-02-compile\
git commit -m "fix(tb): mismatch 走 \$fatal 非零退出；DUMP_VCD 宏隔离波形"
```

---

## 任务 6：xsim 终审子命令（G4）

**文件**：修改 `src/xunji/cli.py`（`_cmd_xsim` + 接线）

**设计裁定（已定死）**：
- 复用 `sync_to_build(repo, r"D:\xunjiji")`；**xsim 层 cwd=镜像根 D:\xunjiji、产物落镜像根**（N2 例外条款）。
- 前置清理：镜像根下 `xsim.dir`、`xvlog.log`、`xelab.log`、`xsim.log` 残留删除（三件套前）。
- xvlog 直接传文件路径（相对镜像根，如 `rtl\xj_top.v`——清单行原样平移，因 sync 保留 rtl/sim 子结构）。
- Vivado 缺失 → 打印提示 return **2**（与失败 1 区分）。
- $fatal 兼容分支（I6 预写）：若 xvlog 默认模式拒收 `$fatal` → **TB 编译改用 `xvlog.bat -sv <tb>` 单独编译**（RTL 仍默认模式），此为唯一允许的适配，不改判定规则。
- PASS 判定：`_g2_pass(out, code, require_code=False)`。

- [ ] **步骤 1：实现 `_cmd_xsim` 并接线**

```python
# subparser 追加：
    sub.add_parser("xsim", help="Vivado xsim 终审仿真（分钟级，最终权威）")
# 分发追加：
    elif args.command == "xsim":
        return _cmd_xsim(_repo_root())

VIVADO_BIN = r"D:\Xilinx\Vivado\Vivado\2024.2\bin"
XJ_BUILD = r"D:\xunjiji"

def _cmd_xsim(repo: Path) -> int:
    import os
    from .hdl.runners import run_tool
    xvlog = Path(VIVADO_BIN) / "xvlog.bat"
    if not xvlog.exists():
        print(f"Vivado 不可用（{xvlog}），跳过终审层；lint/sim 不受影响")
        return 2
    # ① 镜像 + 前置清理
    sync_to_build(repo, Path(XJ_BUILD))
    for f in ("xsim.dir", "xvlog.log", "xelab.log", "xsim.log"):
        p = Path(XJ_BUILD) / f
        if p.is_dir():
            import shutil; shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    # ② xvlog：RTL+TB 显式路径（相对镜像根）
    rtl_files = sorted(str(p.relative_to(repo)) for p in (repo / "rtl").glob("*.v"))
    tb_files = sorted(str(p.relative_to(repo)) for p in (repo / "sim").glob("*.v"))
    r = run_tool([str(xvlog)] + rtl_files + tb_files, timeout=300, cwd=XJ_BUILD)
    if r.code != 0:
        # $fatal 兼容分支：拒收则 TB 单独 -sv 重试一次
        r2 = run_tool([str(xvlog)] + rtl_files, timeout=300, cwd=XJ_BUILD)
        r = run_tool([str(xvlog), "-sv"] + tb_files, timeout=300, cwd=XJ_BUILD)
        if r2.code != 0 or r.code != 0:
            print(r2.out + r.out); return 1
    # ③ xelab
    r = run_tool([str(Path(VIVADO_BIN) / "xelab.bat"), "tb_xj_top", "-s", "tb_xj_top_snap"],
                 timeout=600, cwd=XJ_BUILD)
    if r.code != 0:
        print(r.out); return 1
    # ④ xsim runall（输出含 TB 的 PASS/FAIL 行）
    r = run_tool([str(Path(VIVADO_BIN) / "xsim.bat"), "tb_xj_top_snap", "-runall"],
                 timeout=600, cwd=XJ_BUILD)
    print(r.out)
    # ⑤ G4 判定（不要求退出码）
    return 0 if _g2_pass(r.out, r.code, require_code=False) else 1
```
（实现者可按需微调 import 位置，语义不得变；xvlog 批处理的 cwd/参数实测若有出入，以"实际跑通 + 判定规则不变"为准并把实测命令写进报告。）

- [ ] **步骤 2：实测 + 证据落档**

```bat
uv run xunji xsim > doc\reports\2026-10-02-compile\xsim_g4.txt 2>&1
echo xsim_exit=%ERRORLEVEL%>> doc\reports\2026-10-02-compile\xsim_g4.txt
```
预期：xsim_g4.txt 含整行 PASS、无 FAIL 开头行（分钟级）。

- [ ] **步骤 3：提交**

```bat
git add src\xunji\cli.py doc\reports\2026-10-02-compile\
git commit -m "feat(cli): xsim 终审子命令——sync 复用+三件套直跑（G4）"
```

---

## 任务 7：防线固化与文档同步

**文件**：`.gitignore`、`AGENTS.md`、`README.md`、`scripts/lint_waivers.vlt`

- [ ] **步骤 1：.gitignore 增补**

```
# 中间产物（三层验证流水线）
build/
*.f
*.vvp
xsim.dir/
```

- [ ] **步骤 2：AGENTS.md §3.7 提交前清单替换**

原文："提交前必跑：`uv run pytest`（全绿）。改了 RTL 还要跑 Vivado 仿真。"
改为："提交前必跑：`uv run pytest`（全绿）→ `uv run xunji lint` → `uv run xunji sim`（改 RTL 必跑；任一红禁提交）。合并/交付前必跑 `uv run xunji xsim` 终审。"
§5 网络注记：`gh-proxy.com` 失效，改用 `ghfast.top`。

- [ ] **步骤 3：README 快速命令增补（I7，三行原文 + 可证伪检查）**

在快速开始代码块追加：

```bat
uv run xunji lint   :: Verilator lint（秒级，纯 RTL）
uv run xunji sim    :: iverilog 快速仿真（秒级，非终审）
uv run xunji xsim   :: Vivado xsim 终审（分钟级，最终权威）
```

验证：

```bat
findstr /c:"xunji lint" README.md && findstr /c:"xunji xsim" README.md
```
预期：两行均命中。

- [ ] **步骤 4：scripts/lint_waivers.vlt 占位（Minor）**

```
// scripts/lint_waivers.vlt — 快层(lint/sim)与终审(xsim)分歧 waiver 记录（设计 §1.2）
// 格式：# <日期> <工具版本> <现象> <豁免理由> —— 未记录的分歧视为缺陷
// 当前无分歧
```

- [ ] **步骤 5：提交**

```bat
git add .gitignore AGENTS.md README.md scripts\lint_waivers.vlt
git commit -m "docs: 固化 lint/sim 提交前防线；waiver 占位；镜像地址更新"
```

---

## 任务 8：最终审查 + 合并收尾（G6）

- [ ] **步骤 1：账本补全 + 全链证据终验**

```bat
uv run pytest -q
uv run xunji lint
uv run xunji sim
git log --oneline > doc\reports\2026-10-02-compile\commits.txt
```
三条命令全绿 + commits.txt 含全部任务提交。

- [ ] **步骤 2：SDD 最终审查**（按 SDD 流程：`review-package` 生成整分支审查包 → 派最终代码审查者，最强模型；指向账本中延后/搁置项）

- [ ] **步骤 3：按 finishing-a-development-branch 收尾**
测试全绿 → 三选项（合并回 main / 推送 PR / 保留分支）——无人审批流程下按本计划预授权：**选项 1 本地合并**（合并结果上重跑 pytest+lint+sim 全绿才删 worktree/分支）；合并后 `origin`（git_server）推送。

---

## 验收对照（设计 §1.2）

| 证据 | 文件/位置 |
|------|----------|
| G1 | `lint_g1.txt`（exit=0 + verilator 版本行） |
| G2 | `sim_g2.txt`（exit=0 + 整行 PASS + 无 FAIL，任务 5 后重采） |
| G3 | `g3_injection.txt`（双入口 inject 非 0 + 恢复 0 + git status 干净） |
| G4 | `xsim_g4.txt`（PASS 行两条判定 + exit 记录） |
| G5 | 任务 2/3 红灯独立提交 SHA（checkout 可复现红） |
| G6 | worktree 分支 → SDD 逐任务审查 → 最终审查 → 合并 main + push git_server |
