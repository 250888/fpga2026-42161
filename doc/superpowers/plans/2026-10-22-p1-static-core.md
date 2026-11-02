# P1 静态核心实施计划（2026-10-22）

分支 `p1-static-core`（worktree `.worktrees/p1-static-core/`）；基线 `686848b`。
依据：V1.9 P057（四阶段参数）、P059（LEARN 合法性/M 位序）、P060（golden_compare 分类）、
R6/R8 模块表；AGENTS.md §3（worktree → plan → TDD → 验证 → 提交）。

## 目标

把演示级「SETTLE + 单点采样」的 4 路扫描，升级为 V1.9 冻结的静态核心：
IDLE_CHECK + 四阶段 + SAMPLE_WINDOW 多数表决 + RELEASE/GUARD，产出稳定连接矩阵、
stuck_low_mask、release_timeout；再补 golden_compare + LEARN 合法性；通道数 4→16。

## 冻结参数（V1.9 P057，参数化但默认值不可无依据改）

| 参数 | 默认 | 语义 |
|------|------|------|
| SETTLE | 500 拍（5 µs） | DRIVE 后等待稳定 |
| SAMPLE_CYCLES | 101 拍（1.01 µs，奇数防平票） | 采样窗长度 |
| 多数表决 | 1 的票数 > 50 | row_bits 判决 |
| GUARD_STABLE | 8 拍 | 释放后 b_conn 全 0 连续稳定拍数 |
| GUARD_TIMEOUT | 500 拍 | 释放后兜底，超时置 release_timeout |

IDLE_CHECK：全部 A 释放，等待 SETTLE 后 b_conn 必须全 0；否则置 stuck_low_mask，
该通道在矩阵中**强制为 0**（V1.9「禁止当成正常连接边」），idle_ok=0。

## 模块与接口

`rtl/topology_scanner.v`（= V1.9 R6 static_sampler 的实现，模块名沿用以免破坏 wrapper/XDC/红线测试）：

```
topology_scanner #(N_CH, SETTLE, SAMPLE_CYCLES, GUARD_STABLE, GUARD_TIMEOUT, IDLE_SETTLE)
  in : clk, rst, start, b_filtered[N_CH-1:0]
  out: busy, done_pulse, scan_idx[3:0], drive_en, drive_level,
       conn_matrix[N_CH*N_CH-1:0], open_flags[N_CH-1:0],
       stuck_low_mask[N_CH-1:0], idle_ok, release_timeout
```

FSM：IDLE → IDLE_CHECK → (DRIVE → SETTLE → SAMPLE → RELEASE/GUARD → NEXT)×N_CH → DONE → IDLE。
M[i][j]：i=A 行、j=B 列，row-major 存储；row_bits[0]=B1（V1.9 P059）。

## 任务与验证

### T1 静态扫描 FSM（已完成，2026-10-22）

- [x] `sim/tb_static_sampler.v` 先行（红：`parameter GUARD_STABLE not found`）：4 场景 ——
      ①正常交叉矩阵；②采样窗内 1 拍毛刺不改变判决；③空闲期某 B 卡高 → stuck_low_mask 且该列强制 0；
      ④释放后卡高 → release_timeout。
- [x] 重写 `rtl/topology_scanner.v`：IDLE_CHECK + 四阶段 + 101 拍多数表决 + GUARD(8/500) + 三个新输出。
- [x] `rtl/xunji_core.v` 接线新输出（LED 语义重排：idle_ok / release_timeout / stuck / open）。
      **N_CH 默认仍为 4**：4→16 必须与 UART 拓扑帧 payload 扩展同批做（当前 uart_packet_tx 固定 4×4/4B），
      否则会静默截断 256 bit 矩阵——归入 T2/T3，先改 V1.9 §17 文档。
- [x] `src/xunji/cli.py` SIM_TOPS 增加 `tb_static_sampler`；新增 `tests/test_static_sampler.py`（5 项红线）。
- 验证：pytest **66 passed** → lint 双顶层 exit 0 → sim 三 TB PASS → xsim 终审 PASS。提交。

### T2 golden_compare + LEARN（已完成，2026-10-22）

- [x] `rtl/matrix_degree.v`：degA/degB 的 =1 / >1 / =0 三类标记 + `all_one`（P060 公共判据）。
- [x] `rtl/golden_compare.v`：`missing=M_ref&~M_test`、`extra=~M_ref&M_test`；分类优先级
      PASS → BRIDGE（任一 deg>1）→ MISWIRE（缺失+额外且参考有效行/列实测度仍为 1 的双射换位）
      → OPEN（只有缺失且缺失行实测全空）→ ANOMALY（其余混合）。分类不夸大物理短路位置。
- [x] `rtl/learn_gate.v`：`idle_ok && all_one` 才接受 M_ref 并置 reference_valid；否则拒绝且不覆盖。
- [x] `sim/tb_golden_compare.v`：5 类黄金向量 + 3 条 LEARN 路径（接受/IDLE 拒绝/度非 1 拒绝）。
- [x] cli SIM_TOPS 登记；`tests/test_golden_compare.py` 红线；清单测试改为「SIM_TOPS = sim/ 全部 tb_*」自维护。
- 调试：xsim 下 TB 与 DUT 同 delta 更新 `m_scan`/`learn`，组合度标记未结算导致误接受 →
      TB 在拉 learn 前加 1 ns 结算（硬件语义：矩阵稳定后才按 LEARN）。iverilog 未暴露该竞争。
- 验证：pytest **70 passed** / lint 双顶层 exit 0 / sim 4 TB PASS / xsim 终审 4 TB PASS。

### T3 N_CH 4→16 + 帧载荷扩展（已完成，2026-10-22）

- [x] 决策记录 `doc/superpowers/specs/2026-10-22-topology-frame-16ch.md`：§17 只冻结帧结构，
      payload 语义是工程决策；新 payload = `MAT(N*N/8) + open(2) + stuck(2) + cls(1) + ts0(1)`
      （4 路 8B/帧 18B；16 路 38B/帧 48B），Type=1 与 CRC 参数不变。
- [x] `protocol.py`：`matrix_payload/parse_matrix_payload`、`MATRIX_PAYLOAD_TAIL`、`CLASS_*`（含 NO_REF=5）；
      `tests/test_matrix_payload.py` 锁长度/黄金帧/往返/枚举。
- [x] `rtl/uart_packet_tx.v` 重写为 N_CH 通用：MAT_BYTES/PAYLOAD_LEN/BODY_LEN/FRAME_LEN 由 N_CH 推导；
      matrix 字节序 `matrix[8k+7:8k]`（与旧 mat_lo/mat_hi 兼容）；新增 `stuck_low_mask`/`cls` 输入。
- [x] `sim/tb_uart_packet_tx.v` 改为 18B×2 帧线级解码，黄金帧与 Python `build_frame` 双向锁定。
- [x] `xunji_core` / 双 wrapper 默认 `N_CH=16`；core 暂以 `cls=5`（NO_REF）上报，T4 接 golden_compare 后替换。
- [x] 顺手修 lint：`row >= N_CH - 1` 在 N_CH=16 下触发 WIDTHEXPAND → 改位宽对齐的 `N_LAST`。
- 验证：pytest **75 passed** / lint 双顶层 exit 0 / sim 四 TB PASS。
  **xsim 本次不可用**：应用控制策略拦截 xelab 生成的 `xsimk.exe`（D:/C:/E: 三处实测均被拦，
  「应用程序控制策略已阻止此文件」），非 RTL/测试失败；T1/T2 的 xsim 证据在此策略生效前已取得。
  恢复方式见交接包「失败与弯路」——需放行 xsimk.exe 或换机器后再跑终审。

### T4 core 集成（已完成 RTL 侧，2026-10-22）

- [x] `xunji_core` 实例化 `learn_gate`（`btn[1]` 上升沿 → learn_pulse，避免按住连续学习）与
      `golden_compare`（m_test=conn_matrix，m_ref=learn 输出）。
- [x] 帧内 cls = `reference_valid ? cmp_cls : 3'd5`（未学习上报 NO_REF，不伪装 PASS）。
- [x] LED[7] 改为 reference_valid（已学习指示灯）。
- [x] `sim/tb_static_cls.v`：正常→LEARN→MISWIRE/OPEN/BRIDGE→PASS 全链路集成验证。
- [x] lint 豁免 learn_gate 的 matrix_degree 明细输出（只消费 all_one）。
- 验证：pytest **79 passed** / lint 双顶层 0 / sim **五 TB** PASS。
- 待办：xsim 终审（环境阻塞未解）；上板 4 路回环 → FE-16 16 路；报告 §27 GO 回填。

## 风险

| 风险 | 处理 |
|------|------|
| start 为电平，按住会连续扫描 | 保持既有语义；如影响演示再加边沿触发（需文档） |
| N_CH 16 后矩阵 256b，UART 帧变长 | T3 一并核对 payload 长度与 115200 传输时间 |
| 少数表决与 glitch_filter 叠加 | TB 直接驱动模块级 b_filtered，隔离静态判决 |
