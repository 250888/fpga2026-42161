# 「代码先能编译」三层验证流水线 — 设计文档

> **流程**：superpowers brainstorming 产物（2026-10-02）。按用户指令，审批环节由独立子代理复审替代人工审查。
> **复审状态**：v1 独立复审 APPROVE-WITH-FIXES（3 Critical / 6 Important / 9 Minor）→ 本版已逐条修订，见文末 §7 处置表。
> **目标一句话**：让 `瞬迹` 仓库的 RTL 在本机**可编译、可仿真、有回归防线**，秒级反馈 + Vivado 终审两层兼得。

---

## 1. 上下文与需求

### 1.1 现状（已核实）

- `rtl/` 8 模块 + `sim/tb_xj_top.v`，**纯 Verilog-2001**，无 SV 关键字、无 Xilinx 原语（子代理全文件扫描确认）→ 三层工具全部可处理。
- 历史仅验证过 Vivado 2024.2 综合；**新仓库尚未跑过任何编译/仿真**。
- 本机无 iverilog/verilator/yosys；msys2 官方源可达（实测 1.6–3.7 MB/s）；`D:\msys64\ucrt64\bin` 内住有 `uv.exe` —— 对该树做 pacman 是有爆炸半径的变更（见 §1.3 安全边界）。
- Vivado xvlog/xelab/xsim 可用（xvlog -version 实测 2024.2.0）。
- Python 侧已有 uv 包 `xunji`（protocol/cli，15 pytest 全绿）。
- cmd.exe shell：**不展开 `*` 通配符** → 必须 filelist 或显式文件清单。

### 1.2 成功标准（验收即证据；证据统一落 `doc/reports/2026-10-02-compile/`，随 G6 入库）

| # | 标准 | 证据形式（可证伪的精确规则） |
|---|------|---------|
| G1 | Verilator lint 通过 | `verilator --lint-only --language 1364-2005 -Wall --top-module xj_top -f <rtl清单>` **退出码 0**（权威信号=退出码，文本计数为辅）+ 工具版本行 `verilator --version` |
| G2 | iverilog 编译 + vvp 仿真 PASS | 三者同时成立：vvp 退出码 0 **且** 输出存在整行 `PASS` **且** 不存在任何以 `FAIL` 开头的行；附 `iverilog -V` 版本行 |
| G3 | 一条命令入口 | `uv run xunji lint` / `uv run xunji sim` 实测输出 + 失败注入（故意破坏时非零退出） |
| G4 | Vivado xsim 终审可复跑 | xvlog/xelab/xsim 三件套在镜像目录直跑，**取 G2 判据中的 PASS 行两条**（有整行 PASS 且无 FAIL 开头行），不要求退出码（xsim 对 $finish/$fatal 退出码行为与 vvp 不同） |
| G5 | TDD 红灯证据 | **红灯测试以独立提交 SHA 入库**（checkout 该 SHA 时 pytest 必须红），可 `git stash` 复现 |
| G6 | 全部入 git（worktree 分支→复审→合并） | git log / diff；证据目录同批入库 |

**工具版本快照**（每份证据附带）：`verilator --version`、`iverilog -V` 首行、`pacman -Q mingw-w64-ucrt-x86_64-iverilog mingw-w64-ucrt-x86_64-verilator`。msys2 是 rolling release：**工具升级视为环境变更，须重跑全链**。

**分歧处理规则**：快层（lint/sim）红而终审（xsim）绿 → 必须在 `scripts/lint_waivers.vlt` 同级显式文件写 waiver 注释（注明工具版本与理由），不允许口头忽略；反方向（快绿终红）→ 视为真实缺陷立即修。

### 1.3 约束（硬边界）

- **V1.9 冻结语义不动**：不改 RTL 行为/接口/极性。**授权范围含：`sim/tb_xj_top.v` 的失败路径与波形宏修改**（TB 非冻结对象；C2 需要 mismatch 走非零退出）。
- 安装安全边界：只安装 `mingw-w64-ucrt-x86_64-iverilog` 与 `mingw-w64-ucrt-x86_64-verilator` 两个指定包，**不执行全量 `-Syu` 升级**（避免波及 msys 基础系统与 uv 宿主）；回滚命令 `pacman -Rns mingw-w64-ucrt-x86_64-iverilog mingw-w64-ucrt-x86_64-verilator`。
- 终审口径以 Vivado 为准；iverilog/verilator 是快速反馈层。
- 网络：github.com 不通（镜像用 `ghfast.top`，`gh-proxy.com` 已死）；msys2 官方源可达。
- cmd.exe 为默认 shell。

## 2. 方案对比（brainstorming：4 方案 + 推荐）

### 方案 A（推荐）：msys2 装 iverilog+verilator，`xunji` CLI 统一三层入口

- 安装：`D:\msys64\usr\bin\pacman.exe -Sy --noconfirm --needed mingw-w64-ucrt-x86_64-iverilog mingw-w64-ucrt-x86_64-verilator`
  （取舍：不用 `-Syu` 全升——防爆炸半径；若因签名校验失败中断，先 `pacman -S --noconfirm msys2-keyring`——**注意：msys 仓库包，不带 mingw 前缀**——后重试；签名阻断导致任何 `pacman -S` 都取不到包时，从 msys2 仓库直下 `msys2-keyring-*.pkg.tar.zst` 手动安装，与 Plan B 合流；**T0 安装探针任务先行实测**）
- `xunji lint`（verilator）/ `xunji sim`（iverilog+vvp 快层）/ `xunji xsim`（xvlog/xelab/xsim 终审）
- **优点**：秒级反馈；iverilog 4 态语义贴近 xsim 终审口径；Python 统一入口跨 shell 一致；CI 可复用同命令。
- **缺点**：多装两个工具（几十 MB，官方源实测可达）。

### 方案 B：只用 Vivado xsim —— batch 分钟级杀死 TDD 循环，无秒级 lint 防线。排除。

### 方案 C：oss-cad-suite 全家桶 —— 1 GB+ 下载走 ghfast 不稳，msys2 源可达时无性价比。排除。

### 方案 D（复审 M5 补入）：只装 verilator 一个工具（`--lint-only` + `--binary --timing` 仿真）

- 优点：单包干两层。
- **排除理由**：`sim/tb_xj_top.v:39` 用 `=== 1'b0` 对 X 态敏感；verilator 是 2 态初始化（X→0），会改变 TB 语义、制造与 xsim 的假分歧；iverilog 4 态才贴近终审口径。且 verilator 5.x 对 `#delay` TB 的 timing 支持仍与 xsim 有行为差。**保留 verilator 专职 lint 层**。

**决策**：方案 A。yosys（综合快检）作为可选第 4 层延后（依赖 1–2 GB，YAGNI）。

## 3. 架构与组件

```
uv run xunji lint|sim|xsim
  src/xunji/hdl/
  ├── filelist.py   产出两份清单（I1）：rtl.f（纯 RTL→lint 专用）、sim.f（RTL+TB→仿真用，TB 在后）
  │                 路径规则（I2）：清单内容一律相对**各自运行根**——lint/sim 层相对仓库根、
  │                 xsim 层相对镜像根（sync 保留 rtl/sim 子结构，相对路径原样平移）；
  │                 工作目录（N2 例外条款）：lint/sim → chdir 仓库根；xsim → chdir D:\xunjiji 镜像根
  ├── runners.py    子进程封装：显式 encoding="utf-8", errors="replace"（I3，防 GBK 崩溃）；
  │                 分层超时（M7）：lint 120s / iverilog 编译 120s / vvp 60s / xsim 600s；退出码+输出捕获
  └── cli.py 扩展    lint / sim / xsim 子命令；help 写死"sim=快层非终审，xsim=终审"（M3）
scripts/
  ├── lint.vlt          Verilator 豁免（显式可审计，不关 -Wall；**lint 命令显式携带此文件参数**）
  └── lint_waivers.vlt  快层/终审分歧 waiver 记录（见 §1.2 分歧规则）
sim/tb_xj_top.v     加 `ifdef DUMP_VCD 波形宏；mismatch 失败路径改走 $fatal（非零退出）（C2）
中间产物（I5，N2 例外）：lint/sim 落仓库根 build/（gitignore 增补 build/、*.f、*.vvp、xsim.dir/）；
xsim 产物落镜像根 D:\xunjiji（三件套前先清理其 xsim.dir/xvlog.log 残留）；
证据统一落 doc/reports/2026-10-02-compile/
```

**xsim 路径策略（C3 裁决，选 (a)）**：xsim 层**复用既有 `xunji sync` 到 `D:\xunjiji`**（与 AGENTS.md §2/§5 约定同源），在镜像目录里直跑 `xvlog.bat → xelab.bat → xsim.bat`（M6：runners 直接把 .v 文件路径作为参数传给 xvlog，不依赖 xvlog 的 `-f` 清单语法）；`scripts/simulate.tcl`（project 流）**保留**用于综合前的工程化仿真，与裸三件套并存（快/全两用，同源同清单）；**删除 %TEMP% junction 方案**。§6 含"同步修订 AGENTS.md/README"。

**错误处理**：工具缺失 → 报"未安装+确切安装命令"；编译/仿真失败 → UTF-8 replace 解码透传输出 + 非零退出；Vivado 不可用 → xsim 层降级提示（lint/sim 仍独立可用）。

**语言标准口径（M9）**：三层统一按 Verilog-2001/2005 兼容子集——lint 钉 `--language 1364-2005`、sim 钉 `-g2005`、xsim 用 xvlog 默认（.v→2001，其 SystemVerilog 兼容模式支持 TB 的 `$fatal`）；守则：**不引入 `logic`/`always_ff` 等 SV 关键字**（RTL 层），TB 允许 `$fatal`。

## 4. 测试策略（TDD，红灯独立提交=G5）

- **T0 安装探针（先行）**：实测执行 §2 安装命令；成功 → 记录 `pacman -Q` 版本入证据；失败 → keyring 先行修复 → 再失败走 Plan B（msys2 仓库直下 `.pkg.tar.zst` 手动解包 / oss-cad-suite 走 ghfast）。
- `tests/test_filelist.py`（红灯先行）：rtl.f 不含 `sim/`（I1）；路径相对仓库根（I2）；**从仓库子目录调用时清单仍有效**（I2 cwd 用例）；跳过规则。
- `tests/test_runners.py`（红灯先行）：假可执行测退出码/超时捕获；**含中文行的输出不崩溃**（I3）；UTF-8 输出完整还原。
- CLI 集成：`uv run xunji lint/sim` 实测（G1/G2/G3 证据）+ 故意破坏注入测非零退出（G3）。
- RTL 回归黄金判据：`tb_xj_top` 拓扑矩阵断言（A0→B2 交叉）PASS 行规则。

## 5. 破坏型路线调整候选（已迁出本 spec）

> 前沿调研（去多数表决/CARRY4 TDC/CD4066 多阈值/ML 分类/SSTDR-lite）**整体迁至 `doc/HANDOFF_AI.md` 研究候选章节**（M4），本 spec 只保留此引用。均为需先修订 V1.9 冻结文档的独立研究项，不属于本流水线范围。

## 6. 范围与非目标

- **做**：
  1. T0 安装探针（iverilog+verilator，含回滚/降级路径）
  2. `filelist.py` + `runners.py` + cli 三子命令（lint/sim/xsim）+ TDD 测试（红灯独立提交）
  3. `scripts/lint.vlt`、`lint_waivers.vlt`、`.gitignore` 增补（build/、*.f、*.vvp、xsim.dir/）
  4. TB 修改：`DUMP_VCD` 宏 + mismatch 走 `$fatal`（授权范围见 §1.3）
  5. xsim 层接 `xunji sync`（镜像目录直跑三件套）
  6. **防线固化**：`uv run xunji lint && uv run xunji sim` 写入 AGENTS.md §3.7 提交前清单 + README 快速命令（I6）；证据落 `doc/reports/2026-10-02-compile/`
  7. worktree 分支 → 逐任务子代理复审 → 合并
- **不做**（YAGNI）：yosys（延后）、cocotb（现有 TB 带层级探针，重写收益为负）、CI workflow（无远端 forge）、RTL 行为修改、V1.9 语义变更、方案 D。
