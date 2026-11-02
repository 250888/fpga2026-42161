# P0 —— ego1.xdc 按 V1.9 §4.1 表3 重写 + 顶层双 wrapper 对齐

- 日期：2026-10-08
- 分支：`p0-xdc-wrappers`（worktree：`.worktrees/p0-xdc-wrappers/`）
- 依据：`doc/瞬迹_完整可行技术路线_EGO1开发板版_V1.9.docx` §4.1 表3、§4.2 冻结 XDC、P048–P050 极性归属、§4.3 设计冻结；`doc/HANDOFF_AI.md` §6 任务队列 P0-3/P0-4
- 上游：`AGENTS.md` §3（worktree → 计划 → TDD → 逐任务提交 → 验证）

## 1. 目标与非目标

**目标**

1. `constrs/ego1.xdc` 完全对齐 V1.9 §4.2：端口 `sys_clk`/`rst_n`/`a_ctrl_n[15:0]`/`b_raw[15:0]`/`uart_tx`/`uart_rx`，J5 针号按表3，`DRIVE 4` + `SLEW SLOW`，10 ns 时钟。
2. 顶层拆成两个 wrapper，极性反相只允许出现在 loopback wrapper：
   - `xunji_top_hw`：`assign b_conn = b_sync;`（生产 Top，合成用）
   - `xunji_top_loopback`：`assign b_conn = ~b_sync;`（自回环开发用，仿真 TB 用）
   - 共享 `xunji_core`：只读 `b_conn`，**不出现任何极性反相**。
3. 顶层端口名与 XDC `get_ports` 一一对应（无未约束端口，即无 UCIO-1 DRC）。
4. 同步器补齐 V1.9 §4.2 P030 要求的 `ASYNC_REG="TRUE"`、`SHREG_EXTRACT="NO"` 属性（reset synchronizer 抽成共享模块 `xj_rst_sync`）。

**非目标（本次不做，见 §5）**

- P1 静态扫描四阶段/多数表决/`golden_compare`/LEARN（`topology_scanner` 除「去掉内部反相」外行为不动）。
- N_CH 从 4 扩到 16（wrapper 参数默认仍为 4；16 路在 P1 连同 TB 扩展一起做）。
- `b_raw → 第一级同步器 D 端` 的 path exception：V1.9 P029 要求「等 RTL 实例名固定后、用 `report_cdc` 复核目标数=16 再写」，而本机 Vivado 暂不可用（见 §6），因此**故意暂缺**，保留未约束告警比写过宽 false-path 安全。
- `uart_packet_tx` 的 `A5 5A`/CRC8 遗留帧协议（已立项，非 P0）。

## 2. 架构

```
b_raw[15:0] ─┬─ input_sync(2-flop, ASYNC_REG) ─ b_sync[15:0]
             │        ├─ xunji_top_hw:         b_conn =  b_sync
             │        └─ xunji_top_loopback:   b_conn = ~b_sync   ← 反相只在这一行
rst_n ───────┴─ xj_rst_sync(ASYNC_REG) ─ rst(高有效，同步释放)
                                                      │
                              xunji_core(sys_clk, rst, a_ctrl_n, b_conn, led, uart, sw, btn)
                                  └─ glitch_filter → topology_scanner(row_bits = b_filtered，无反相)
                                  └─ drive_controller → a_ctrl_n（复位/默认 16'hFFFF 全释放）
```

技术栈不变：Verilog-2001、Verilator 5.050 lint、iverilog+vvp sim、pytest（host 侧结构/约束一致性测试）、Vivado 2024.2 xsim（本机损坏，见 §6）。

## 3. 任务清单（逐任务：红 → 绿 → 提交）

### T1 XDC 红线测试（先写失败测试）

- 文件：新增 `tests/test_xdc.py`
- 断言：
  1. 表3 的 32 路 J5 映射（`a_ctrl_n[0..15]`=B16 B17 A15 A16 A13 A14 B18 A18 F13 F14 B13 B14 D14 C14 B11 A11；`b_raw[0..15]`=E15 E16 D15 C15 H16 G16 F15 F16 H14 G14 E17 D17 K13 J13 H17 G17）逐条存在且唯一。
  2. `sys_clk`=P17、`rst_n`=P15、`uart_tx`=T4、`uart_rx`=N5。
  3. 所有 `PACKAGE_PIN` 全局不重复（32+4 共 36 针）。
  4. 全部端口 `IOSTANDARD LVCMOS33`；`a_ctrl_n[*]` 有 `DRIVE 4` 与 `SLEW SLOW`。
  5. `create_clock` 周期 10.000 命中 `sys_clk`。
- 验证：`uv run pytest -q tests/test_xdc.py` → **红**（当前为 `clk_100mhz`/`a_out`/`b_in` 旧草稿）。

### T2 重写 `constrs/ego1.xdc`

- 文件：`constrs/ego1.xdc` 整体重写
- 内容分三段：
  1. **冻结段**：V1.9 §4.2 原样（时钟/复位/32 路 J5/DRIVE 4/SLEW SLOW/UART）。
  2. **暂定段**：`led[15:0]`、`btn[4:0]`、`sw[7:0]` 沿用现草稿板载脚，注释明确标注「V1.9 §4.2 未冻结（HANDOFF §4.3 遗留1），待文档冻结后转正」——V1.9 是唯一基线，未冻结的板载 I/O 不得伪装成冻结约束。
  3. 注释写明「J5 上板前须按 EGO1 V2.2 手册 §14 逐针复核并留勾选记录；禁止 DRC 失败后试错换脚」。
- 验证：`uv run pytest -q tests/test_xdc.py` → **绿**；`uv run pytest -q` → 25+ 全绿。
- 提交：`test(xdc): 表3 管脚红线测试`、`feat(xdc): 按 V1.9 §4.1 表3 重写 ego1.xdc`

### T3 结构红线测试（先写失败测试）

- 文件：新增 `tests/test_top.py`
- 断言：
  1. `rtl/xunji_top_hw.v` 含 `assign b_conn = b_sync;` 且**不含** `~b_sync`。
  2. `rtl/xunji_top_loopback.v` 含 `assign b_conn = ~b_sync;`。
  3. `rtl/xunji_core.v` 与 `rtl/topology_scanner.v` 中不存在对 `b_conn`/`b_filtered` 的反相（不出现 `~b_filtered`、`~b_conn`）——极性单点处理。
  4. `rtl/input_sync.v` 含 `ASYNC_REG` 与 `SHREG_EXTRACT`；`rtl/xj_rst_sync.v` 同。
  5. 两个 wrapper 的端口名集合**相同**，且与 `constrs/ego1.xdc` 的 `get_ports` 名字集合**完全相等**（无未约束端口、无多余约束）。
  6. `scripts/create_project.tcl` 的 synth top = `xunji_top_hw`、sim top = `tb_xunji_loopback`，且该模块分别在 `rtl/`、`sim/` 中真实存在；`scripts/simulate.tcl`、`src/xunji/cli.py` 的 sim/xsim top 同名。
- 验证：`uv run pytest -q tests/test_top.py` → **红**。

### T4 RTL 重构（最少实现）

- `git mv rtl/xj_top.v rtl/xunji_core.v`：
  - 模块名 `xunji_core`；端口 `sys_clk`（原 `clk_100mhz`）、`rst`（原内部 `sys_rst`，复位同步器上移到 wrapper）、`a_ctrl_n`（原 `a_out`）、`b_conn`（原 `b_in`，**已是极性归一化信号**）；`led/uart_tx/uart_rx/sw/btn` 不变。
  - 内部删除 `rst_sync` 块（改由 `xj_rst_sync` 提供）、删除 `input_sync` 实例（上移到 wrapper）；`glitch_filter` 直接吃 `b_conn`。
- 新增 `rtl/xj_rst_sync.v`：V1.9 P030 的 2 级 reset synchronizer 原文实现（`ASYNC_REG`/`SHREG_EXTRACT`，异步拉低、同步释放）。
- 新增 `rtl/xunji_top_hw.v`、`rtl/xunji_top_loopback.v`：端口 `sys_clk/rst_n/a_ctrl_n/b_raw/led/uart_tx/uart_rx/sw/btn`，参数透传 `N_CH/CLK_FREQ_HZ/BAUD_RATE/SCAN_SETTLE/GLITCH_CYCLES`（默认与现 `xj_top` 一致，N_CH=4）。
- `rtl/topology_scanner.v`：`row_bits = ~b_filtered` → `row_bits = b_filtered`，头注释同步（连接语义由 wrapper 保证，核心不反相）。
- `rtl/drive_controller.v`：输出端口 `a_out` → `a_ctrl_n`（复位/默认 `16'hFFFF` 不变）。
- `rtl/input_sync.v`：加 `(* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO" *)`。
- `sim/tb_xj_top.v` → `git mv` 为 `sim/tb_xunji_loopback.v`：
  - DUT 换 `xunji_top_loopback`，层级引用改 `dut.u_core.*`；
  - `b_in` 改名 `b_raw`（回环模型不变：默认全 1，导通拉 0）；
  - **新增极性交叉检查**：同一 `b_raw` 下实例化 `xunji_top_hw`（btn/sw 绑 0），断言 `hw_dut.b_conn === ~dut.b_conn` 且 `hw_dut.b_conn === hw_dut.b_sync`，复位释放后与扫描结束前各查一次，失败 `$fatal`。
- 验证：`uv run pytest -q` → 绿；`uv run xunji lint` → 0；`uv run xunji sim` → G2 三重判定通过（含新极性断言）。
- 提交：`refactor(top): 拆分 xunji_core 与 hw/loopback 双 wrapper，极性单点处理`

### T5 管线与脚本跟随改名

- `src/xunji/cli.py`：lint 改为对 `xunji_top_hw` 与 `xunji_top_loopback` **各跑一次**（任一失败即 1）；sim `-s tb_xunji_loopback`、产物 `build/tb_xunji_loopback.vvp`；xsim `xelab tb_xunji_loopback -s tb_xunji_loopback_snap`（该层本机不可用，仅做名称跟随，不宣称验证过）。
- `scripts/create_project.tcl`：synth top `xunji_top_hw`，sim top `tb_xunji_loopback`。
- `scripts/simulate.tcl`：sim top 同上。
- `scripts/build.tcl`：bitfile 名 `xunji_top_hw.bit`。
- `scripts/lint.vlt`：豁免文件名 `*rtl?xj_top.v` → `*rtl?xunji_core.v`（理由文字同步）。
- `README.md`：目录树与「仿真」行的 `tb_xj_top` → `tb_xunji_loopback`。
- 验证：`uv run pytest -q`、`uv run xunji lint`、`uv run xunji sim` 三层全绿（xsim 记为已知阻塞）。
- 提交：`refactor(pipeline): lint 双顶层 + sim/xsim 顶层名跟随 wrapper 改名`

### T6 收尾：文档回写与完成前验证

- `doc/实施计划.md`：新增 P0 完成记录（表3 已落地、双 wrapper、N_CH 仍为 4、LED 段暂定）。
- `doc/HANDOFF_AI.md`：状态快照行 + §5.2 差距表前两行改为已完成；任务队列 P0-3/P0-4 标记完成；§4.3 遗留 1 更新为「XDC 中以暂定段保留，待文档冻结」。
- 逐项核对 §4 验收清单 → 全部有本次会话的命令输出证据后才提交收尾。
- 提交：`docs(handoff): 回写 P0 完成状态`

## 4. 每步可运行的验证命令

```bat
uv run pytest -q                      :: 全部测试（提交前必跑）
uv run pytest -q tests/test_xdc.py    :: T1/T2
uv run pytest -q tests/test_top.py    :: T3/T4
uv run xunji lint                     :: Verilator 双顶层，退出码 0
uv run xunji sim                      :: iverilog+vvp，G2 三重判定
uv run xunji xsim                     :: 已知阻塞（§6），不得作为完成依据
```

## 5. 明确不做（防蔓延）

- 不改 `topology_scanner` 的状态机结构、时序参数、矩阵位序。
- 不改 `uart_packet_tx` 帧协议、不改 `protocol.py`。
- 不新增 XDC 的 path exception / false_path（理由见 §1）。
- 不动 `vivado/`、`build/`、`.worktrees/` 产物。

## 6. 环境事实（本次会话已确认）

- pytest 25 项、`xunji lint`、`xunji sim` 在本 worktree 基线全绿。
- `xunji xsim` 不可用：`D:\Xilinx\Vivado\Vivado\2024.2` 的产品级 `lib/win64.o` 载荷缺失，`xvlog.exe` 唯一缺失导入 `xv_xsimverific.dll` 在 C:/D:/E: 全机不存在，全机也只有这一份 Vivado 安装，无安装包归档 → 离线不可修复（退出码 0xC0000135）。修复需重装 Vivado 2024.2 或从完好机器拷贝 `Xilinx` 目录，属对外/大体积动作，待用户拍板。

## 7. 验收清单（完成后逐项打勾，须有本次会话命令输出）

- [ ] `uv run pytest -q` 全绿（25 → 含新增 test_xdc / test_top）
- [ ] `uv run xunji lint` 退出码 0（hw 与 loopback 两个顶层）
- [ ] `uv run xunji sim` G2 通过（拓扑矩阵 + 新增极性交叉断言）
- [ ] `constrs/ego1.xdc` 32 路 J5 针号与 V1.9 表3 逐条一致，无重复针
- [ ] `xunji_core`/`topology_scanner` 源码中无极性反相；反相只在 `xunji_top_loopback`
- [ ] 顶层端口集合 == XDC `get_ports` 集合
- [ ] 文档回写完成；`xunji xsim` 阻塞状态在 HANDOFF 中留痕
