# AI 交接包 — 嵌赛 FPGA /「瞬迹」

> ⚠ **2026-10-02 起，本文件已随项目迁入 `瞬迹/doc/`；开发流程规范见仓库根 `AGENTS.md`（superpowers 技能族）。**  
> ⚠ 目录地图（§3）与构建路径（§5.3）已按 uv 包化重组更新，**以文末「2026-10-02 重组」变更记录为准**；其余技术内容不变。

> **读者**：接手本项目的下一个 AI（或新会话里的我）。  
> **目标**：读完本文件 + 指定材料后，无需翻聊天记录即可继续开工。  
> **生成日期**：2026-09-14  
> **状态快照（2026-10-11 更新）**：V1.9 技术路线已定稿审计；**P0 代码侧完成** —— `constrs/ego1.xdc`
> 已按 §4.1 表3 重写，顶层已拆 `xunji_top_hw` / `xunji_top_loopback` 双 wrapper（反相只剩 loopback 一处），
> 见 `doc/实施计划.md`「P0 记录」与 `doc/superpowers/plans/2026-10-08-p0-xdc-wrappers.md`。
> 验证：pytest 41 全绿 + lint 双顶层 + sim PASS + **`xunji xsim` PASS（2026-10-11 解除阻塞，见 §7）**。
> **2026-10-11：`uart_packet_tx` 帧协议已对齐 V1.9 §17（55 AA/CRC-16，分支 `uart-frame-v19`），
> 四层现为 pytest 49 + 双顶层 lint + sim/xsim 双 TB PASS。正式 RTL 仍是演示级 4 路，P1 静态核心未做。**
> **2026-10-11：J5 逐针复核完成（§27-GO，四方 36/36 全一致 0 差异）——V2.2 正式版手册与官方原理图
> 已归档 `../资料/EGO1板卡/`，勾选记录 `doc/reports/2026-10-11-j5-pin-review/`（可复跑脚本+输出）。**
> **2026-10-12：FE-16 16路前端 PCB 完成（用户「开始画pcb」按 V1.9 方案，EDA 决策全权委托）——
> `pcb/frontend16/` 生成器 + 五步流水线（gen→dsn→Freerouting→ses→pytest），DRC 0 / ERC 0 / 61 测试全绿；
> 160×90 四孔、122 位号、84 网、0.25mm 线宽 / 0.27 规划净距；符号引脚 1 顶置、连接器行=排线物理列。
> 预览 `doc/FE16预览.html`；验证工具 KiCad 10.0.7 绿色版（原选 8 系，版本偏差已记录）。提交 1ab55a3+fc083de，未推送。**
> **2026-10-13：板框 160×90 → **96×96**（用户「最好 <10×10cm，嘉立创免费券」），网表/位号/BOM
> 不变仅几何重排；LCEDA 云端导入定性不可用（保存零流量、重载树空 boards=[]）→ 弃云端，走
> 本地 KiCad 管线交 Gerber：`pcb/frontend16/xunji_fe16_gerber_96x96.zip`（9 层+drill 共 11 文件，
> kicad-cli DRC --severity-all **0 violation / 0 未连接**，pytest 12 passed，布线 1903 段/164 过孔）。
> 下单（免费券）留用户拍板。**
> **2026-10-22：P1 静态核心 T1 完成（分支 `p1-static-core`）—— 静态扫描升级为 V1.9 冻结四阶段：
> IDLE_CHECK（全 A 释放后 b_conn 必须全 0，否则 stuck_low_mask + 该列强制 0）+ DRIVE→SETTLE(500)
> →SAMPLE(101 拍逐位计票，票数>50)→RELEASE/GUARD(稳定 8 拍/TIMEOUT 500 置 release_timeout)；
> 新增 `sim/tb_static_sampler.v`（正常矩阵/1 拍毛刺免疫/卡低/释放超时 4 场景，sim+xsim 双 PASS）。
> 验证：pytest 66 / lint 双顶层 0 告警 / sim 三 TB PASS / xsim 终审三 TB PASS。
> **N_CH 仍为 4**：4→16 与 UART 拓扑帧 payload 扩展同批做（先改 V1.9 §17）。下一步 T2：golden_compare + LEARN。**
> **2026-10-22：P1 T2 完成（同分支）—— 新增 `matrix_degree`（degA/degB 的 =1/>1/=0 标记 + all_one）、
> `golden_compare`（missing/extra + PASS/BRIDGE/MISWIRE/OPEN/ANOMALY 分类，按 V1.9 P060 优先级）、
> `learn_gate`（idle_ok && all_one 才接受参考矩阵，否则拒绝不覆盖）；黄金向量 TB 5 类 + 3 条 LEARN 路径。
> 验证：pytest 70 / lint 0 / sim 四 TB PASS / xsim 终审四 TB PASS。**尚未接进 core（LEARN 按键与结果上报归 T4）**。**
> **2026-10-22：P1 T3 完成 —— N_CH 4→16 + 拓扑帧载荷扩展**：§17 只冻结帧结构，payload 语义为工程决策；
> 新 payload = MAT(N*N/8)+open(2)+stuck(2)+cls(1)+ts0(1)（4 路 18B / 16 路 48B，Type=1 与 CRC 不变），
> 决策记录 `doc/superpowers/specs/2026-10-22-topology-frame-16ch.md`；`uart_packet_tx` 改 N_CH 通用，
> core/双 wrapper 默认 16 路。验证：pytest 75 / lint 0 / sim 四 TB PASS。
> **xsim 本次被环境拦截**（应用控制策略阻止 xelab 生成的 `xsimk.exe`，D:/C:/E: 三处实测）；
> core 仍以 cls=5（NO_REF）占位，T4 接 golden_compare/LEARN 后替换并上板。**
> **2026-10-22：P1 T4（RTL 侧）完成** —— core 接 `learn_gate`（btn[1] 上升沿）与 `golden_compare`，
> 帧内 cls = `reference_valid ? cmp_cls : 5(NO_REF)`；LED[7]=已学习；新增 `sim/tb_static_cls.v`
> 全链路（正常→LEARN→MISWIRE/OPEN/BRIDGE→PASS）。验证：pytest 79 / lint 0 / sim **五 TB** PASS。
> **P1 静态核心 RTL 到此闭环**；剩余：xsim 终审（环境阻塞）、上板 4 路→FE-16 16 路、报告回填。**

---

## 1. 30 秒项目摘要

| 项 | 内容 |
|----|------|
| 项目名 | **瞬迹** — 基于 FPGA 并行时序分析的线束拓扑重建与动态互连瞬态诊断系统 |
| 队名 | **瞬狙**（2026-10-11 用户拍板，此前候选「线所未见」/「迹不可失」作废） |
| 赛事 | 第十届（2026）全国大学生嵌入式大赛 **FPGA 创新设计赛道**（教育部 A 类） |
| 板卡 | **EGO1**，Artix-7 **XC7A35T-1CSG324C**，100 MHz（P17） |
| 一句话 | 静态重建「线怎么接」，动态捕获「线什么时候断」 |
| 第一版 DUT | **16 芯、无源、低压、点到点、一对一线束**（一对多/多分支不做正常工况） |
| 核心卖点 | 16 路真并行 Event Detector + 统一 64 位时间戳 + μs 级间歇开路 + Pre-trigger 黑匣子 + MCU 公平基线 |

**已废弃方向**：原「声声不息」SoundAlert（FPGA 声音识别）已整目录删除，勿复活。

---

## 2. 硬时间点（写在最前面）

| 节点 | 日期 | 备注 |
|------|------|------|
| **报名截止** | **2026-09-22 24:00** | 官网 www.socchina.net；队内是否已报名**需向用户确认** |
| 作品提交 | 2026-11-04 18:00 | 报告、PPT、演示视频、仿真、源码等 |
| 初赛 | 2026-11 中旬 | 线上 |
| 决赛 | 2026-11-20~22 | 南京；有 **FPGA 基础编程考核**（门槛） |

评分参考：基本功能 ~25–38、创新 ~42–55、设计完整性 10、文档 10；强调**真实上板、实测、基线对比、资源优化、可复现、Skill**。

---

## 3. 目录地图（以工作区为准）

```
D:\UserFolders\Desktop\嵌赛FPGA\
├── README.md                          # 工作区总览
├── HANDOFF_AI.md                      # ← 本交接包（建议保留在根目录）
├── 瞬迹_完整可行技术路线_EGO1开发板版_V1.9.docx   # ★ 主技术路线（唯一基线）
├── 瞬迹_完整可行技术路线_队内实施稿.docx          # 队内沟通稿，非基线
├── scripts/
│   ├── extract_v19.py                 # 抽取 V1.9 正文/表格
│   ├── extract_v13.py, docx_*.txt     # 历史版本抽取（参考）
├── 嵌赛FPGA资料/                       # 竞赛规则、评分、选题、安装指南
└── 瞬迹/                               # 工程目录
    ├── README.md
    ├── doc/
    │   ├── 技术路线_V1.2_原文提取.txt  # 旧版；正式以 V1.9 docx 为准
    │   └── 实施计划.md
    ├── src/rtl/                        # 阶段一 RTL（见 §5）
    ├── src/sim/tb_xj_top.v
    ├── constrs/ego1.xdc                # ⚠ 旧草稿管脚，未对齐 V1.9 §4.1
    ├── scripts/{create_project,simulate,build}.tcl
    └── vivado/xj_top.bit               # 旧草稿约束下的产物
```

**英文构建副本**（历史原因）：`D:\xunjiji`（Vivado 对中文路径不友好；曾用 `C:\xunjiji_build` junction）。后续建议统一在无中文路径下重建工程，或先验证中文路径可用再回桌面目录。

---

## 4. 文档基线（必读）

### 4.1 唯一权威

**`瞬迹_完整可行技术路线_EGO1开发板版_V1.9.docx`**

- 版本标题：V1.9（最终开工前严格审计版）
- 159 段 + 29 表；已做过一轮全文数值/极性/资源审计
- **开工冻结依据**：§4.3 设计冻结表、§26 十条修正、§27 GO/NO-GO 检查表

**不要**再混用 V1.2/V1.3 docx 或 `doc/技术路线_V1.2_原文提取.txt` 做决策；它们只可 diff 参考（V1.3/V1.2 文件可能已被移走）。

### 4.2 V1.9 已审计通过的关键事实（可信）

- J5：2×18=36 针；**1–32=I/O，33/34=GND，35/36=3.3V**
- **§4.1 表3**：J5 物理针 ↔ 信号名（`a_ctrl_n` / `b_raw`）↔ PACKAGE_PIN 完整映射（32 路）
- UART：板级 UART_RX=**T4**（FPGA **发送**）；UART_TX=**N5**（FPGA **接收**）；顶层按 FPGA 视角 `uart_tx→T4`、`uart_rx→N5`
- 复位：P15 低有效 `rst_n`；须 2 级 reset synchronizer；复位/安全态 **`a_ctrl_n` 全 1 释放**
- 极性：真实前端 LVC07+LVC14 ⇒ **导通 `b_conn=1`、开路 `=0`**；生产 Top `b_conn=b_sync`；仅 loopback wrapper 才反相
- 时钟：**仅 100 MHz**；10 MHz 波形等效用 clock-enable，不新建逻辑时钟
- 静态扫描：IDLE_CHECK → DRIVE → SETTLE(500) → SAMPLE(101, 票>50) → RELEASE/GUARD(稳定 8 / 超时 500)
- 动态：DYNAMIC_ARM（expected_mask 稳定 8 拍）→ MONITOR；`candidate_start` 锁存真实起点；`fault_confirm` 即触发黑匣子，不等恢复
- 事件：128 bit = T_start64 + Dur32 + Seq16 + Flags8 + Ch4 + Rsv4；Sequence **≠** 物理先后
- 并发：每路 2-depth 本地队列 + 轮询仲裁 → 全局 FIFO；overrun/overflow 实验须为 0
- 分类：Missing/Extra + degA/degB；混合/无法解释 → `TOPOLOGY_ANOMALY`；LEARN 仅接受行列连接度均为 1
- BRAM：Pre-trigger ~20×RAMB36 + FIFO ~4；UART 115200 仅 bring-up（80KB≈6.9s）
- 协议：SOF `55 AA` + Ver + Type + Len + Seq + Payload + **CRC-16/CCITT-FALSE**（0x1021, init 0xFFFF）
- A/B 20Pin：1–16=信号，**17–20=NC**，DUT 口不进 3.3V/GND

### 4.3 V1.9 文档侧遗留（接手可改，非阻塞）

1. **§4.2 冻结 XDC 无 LED/按键**：演示要 LEARN/状态，文档未冻结板载 I/O — 需补约束或写死「全走 UART」。
   **2026-10-08 处理**：`constrs/ego1.xdc` 先以「【暂定段，非冻结】」保留板载 LED/按键/拨码（沿用阶段一草稿脚，
   否则 Vivado UCIO-1/NSTD-1 DRC 直接挡下），并由 `tests/test_xdc.py` 锁定不许静默漂移；
   **转正或删除仍待文档拍板**。
2. ~~**J5 表称引自 EGO1 V2.2 §14，工作区无该手册 PDF** — 上板前必须官方手册逐针复核并留勾选记录。~~
   **2026-10-11 闭环**：v2.2 正式版手册（封面 ver2.2）+ 官方原理图已归档 `../资料/EGO1板卡/`；
   四方比对 36/36 全一致，勾选记录见 `doc/reports/2026-10-11-j5-pin-review/`。
3. 轻微：表8 回环行仍标「LVC14 输入」列；「6. 暂时不要购买」标题层级编号。

---

## 5. 工程现状（`瞬迹/`）

### 5.1 已有并验证过的

| 项 | 结果 |
|----|------|
| 阶段一 TB | `tb_xunji_loopback`（原 `tb_xj_top`）**PASS**：4 路交叉 A0→B2… 矩阵正确 + 与 `xunji_top_hw` 的极性交叉断言（2026-10-08 复跑） |
| 综合/实现 | Vivado **2024.2**，0 error；WNS≈+5.4 ns |
| 资源 | LUT 149 · FF 197 · BRAM 0 · DSP 0（XC7A35T <1%） |
| 比特流 | `瞬迹/vivado/xj_top.bit`（**旧草稿 J5 脚**，不能当 V1.9 正式版） |
| RTL 模块 | `xunji_top_hw, xunji_top_loopback, xunji_core, xj_rst_sync, topology_scanner, drive_controller, timestamp_counter, input_sync, glitch_filter, uart_tx, uart_packet_tx`（原 `xj_top` 已并入 `xunji_core`） |

### 5.2 与 V1.9 的差距（正式接手的第一优先级）

**当前 RTL = 演示级 4 路自回环，不是 V1.9 冻结架构。**

| V1.9 要求 | 现状 |
|-----------|------|
| 端口 `sys_clk` / `a_ctrl_n` / `b_raw` / `b_conn` | ✅ **2026-10-08 完成**：`xunji_top_*` 端口即 V1.9 冻结名，核心只读 `b_conn`，`topology_scanner` 不再 `~b_filtered` |
| 表3 正式 PACKAGE_PIN | ✅ **2026-10-08 完成**：`constrs/ego1.xdc` 冻结段 = V1.9 §4.2 原文（N18/L17 等试错脚废除）；板载 I/O 为暂定段 |
| IDLE_CHECK + 四阶段 + 多数表决 | ✅ **2026-10-22 完成**：IDLE_CHECK（stuck_low_mask/idle_ok）+ DRIVE/SETTLE(500)/SAMPLE(101, >50)/RELEASE-GUARD(8/500) + release_timeout；TB 4 场景 sim+xsim 双 PASS |
| hw / loopback 双 wrapper，`b_conn` 语义 | ✅ **2026-10-08 完成**：`xunji_top_hw`（`b_conn=b_sync`）+ `xunji_top_loopback`（`b_conn=~b_sync`，唯一反相点）+ `xj_rst_sync`；TB 带极性交叉断言 |
| golden_compare、LEARN、STUCK_LOW | ✅ **2026-10-22 完成模块级**：`matrix_degree` + `golden_compare`（PASS/BRIDGE/MISWIRE/OPEN/ANOMALY）+ `learn_gate`（idle_ok && all_one 才接受）；**未接 core**（LEARN 按键/结果上报 T4） |
| DYNAMIC_ARM、Event Detector×16、队列/FIFO | 无 |
| Pre-trigger、Trigger Manager、128b 事件 | 无 |
| 安全态 `safe_mode_ctrl`（复位全 1） | 无独立模块；`drive_controller` 默认 0xFFFF 方向对，但未成冻结架构 |
| LED/LEARN 冻结约束 | 无 |

### 5.3 构建命令（英文路径）

```powershell
# 推荐
Set-Location D:\xunjiji\scripts   # 或在无中文路径重建后
& "D:\Xilinx\Vivado\Vivado\2024.2\bin\vivado.bat" -mode batch -source simulate.tcl -nolog -nojournal
& "D:\Xilinx\Vivado\Vivado\2024.2\bin\vivado.bat" -mode batch -source build.tcl -nolog -nojournal
```

- 工程脚本：`create_project.tcl` / `simulate.tcl` / `build.tcl`（已适配 `info script` 相对路径）
- 跑完若在中文目录：把 `*.bit`、`utilization.rpt`、`timing.rpt` 拷回 `瞬迹/vivado/`

---

## 6. 建议任务队列（按优先级）

### P0 — 报名与基线落地

1. **向用户确认**官网报名是否完成（截止 9/22）。 → **✅ 2026-10-11 用户答复：已报名；队名同日拍板「瞬狙」**。  
2. 用 **EGO1 V2.2 手册 §14** 复核 V1.9 表3 全部 PACKAGE_PIN，记录核对结果。 → **✅ 2026-10-11 完成**（四方 36/36 全一致；勾选记录 `doc/reports/2026-10-11-j5-pin-review/`，含可复跑 `check_j5_pins.py`）。  
3. 按表3 **重写 `ego1.xdc`**（含 §4.2 的 `a_ctrl_n`/`b_raw`/DRIVE 4/SLEW SLOW；并冻结 LED/LEARN 方案）。 → **✅ 2026-10-08 完成**（commit 6b4e374 + 红线测试 3ea0a96；LED/LEARN 仍留暂定段，非冻结）。  
4. 顶层端口与 wrapper 对齐 V1.9：`xunji_top_hw`（`b_conn=b_sync`）+ `xunji_top_loopback`（内部反相）。 → **✅ 2026-10-08 完成**（commit 118816c/4540a55 + 红线测试 072ca61；极性反相全工程仅 loopback 一处）。  

### P1 — 静态核心（§8 + §27 对应 TB）

5. 重写静态扫描：`IDLE_CHECK` + 四阶段 + SAMPLE 101 多数表决 + GUARD。  
6. `golden_compare`：Missing/Extra、degA/degB、OPEN/MISWIRE/BRIDGE/`TOPOLOGY_ANOMALY`、LEARN 合法性。  
7. 仿真先行（V1.9 三件事-C 清单）：复位/CDC、扫描 FSM、LVC14 极性 TB、Golden 位序、… 再 4 路板级自回环。  

### P2 — 动态与黑匣子

8. DYNAMIC_ARM、Event Detector、2-depth Queue、Arbiter、FIFO、active_fault_mask/STOP 截断。  
9. Trigger Manager + BRAM 环形缓存 + 128b 事件打包。  
10. UART 协议（55 AA + CRC16-CCITT）与分块上传。  

### P3 — 硬件与实验

11. 下单（V1.9 表6）；1 路物理链路 → 4 路 → 16 路 PCB。 → **✅ 2026-10-12 设计侧完成：FE-16（16 路）全套交付 `pcb/frontend16/`（DRC/ERC 0、61 测试全绿，commit 1ab55a3/fc083de）；下单动作待用户拍板**。  
12. 4066 故障源 + 示波器三点观测（4066 控制 / B 模拟 / b_raw）。  
13. 实验矩阵、MCU 基线、资源/时序报告；上位机 PySide6。  
14. 演示视频 / 报告 / PPT / Skill 沉淀（§24）。  

### 验收锚点

- 仿真：§27 GO 表逐项  
- 上板：§21 阶段 1→10  
- 演示：§22 六步  

---

## 7. 协作约定（给接手 AI）

1. **技术决策以 V1.9 docx 为准**；改接口/极性/记录语义必须改文档并说明，不可只改代码。  
2. **允许调参**（SETTLE、Rp、MIN_PULSE、波特率、队列深度）仅当有示波器/Vivado 实测依据。  
3. **禁止**：DRC 失败后试错换脚；动态路径复用静态长毛刺；把 Sequence 当物理先后；把 10 ns 说成整机精度；一对多当第一版正常拓扑。  
4. 报告资源/时序注明 **含/不含 ILA**。  
5. 重大进度写回：`瞬迹/doc/实施计划.md` + 本文件 §0/状态行；可用任务工具建 T 清单。  
6. 对用户输出：中文；关键结论先给判定再展开。  
7. 删除/覆盖类操作先确认；报名、下单、推远端等对外动作必须用户拍板。  

### 环境速查

- OS：Windows；PowerShell  
- Vivado：**`C:\AMDDesignTools\2026.1\Vivado\bin\`（2026-10-11 起 `VIVADO_BIN` 指向此处）**  
  - **2026-10-11：已激活 Node-Locked BASIC tier 许可证**（HOSTID=`e8b0c58fb217`，8 条 INCREMENT 到 2027-10-10，VLM View License Status 确认）；`xvlog/xelab/xsim` 实测 rc=0，`xunji xsim` 首次在本机 PASS。`.lic` 备份在 `Downloads\vivado_2026.1_node_locked.lic`，已装入 `%APPDATA%\XilinxLicense\`。  
  - **旧 `D:\Xilinx\Vivado\Vivado\2024.2` 已损坏弃用**（2026-10-08 诊断：`lib/win64.o` 缺 `xv_xsimverific.dll`，xvlog.exe 启动 0xC0000135，全机无此文件离线不可修；User PATH 仍残留旧条目，未删）。  
- Python：`$env:MIMO_PYTHON`（有 python-docx 等）  
- **2026-10-22 环境阻塞：`xunji xsim` 终审不可用** —— xelab 生成的 `xsimk.exe` 被应用控制策略拦截
  （`D:\xunjiji` / `C:\xjbuild` / `E:\d` 三处实测「应用程序控制策略已阻止此文件」；同策略也拦
  worktree 内 `uv run xunji` 的 launcher，故统一用 `uv run python -m xunji.cli`）。
  T1/T2 的 xsim 证据在该策略生效前取得；恢复需放行 xsimk.exe 或换机器。lint + iverilog sim 不受影响。  
- 已有（2026-10-11 用户答复）：报名已确认；物料已下单（实物未到）；**EGO1 V2.2 正式版手册（封面 ver2.2）与官方原理图已归档 `../资料/EGO1板卡/`**；J5 逐针复核已完成（GO，见 `doc/reports/2026-10-11-j5-pin-review/`）
- 无（均已有主）：队名=**瞬狙**；依元素「EGo1-开发包 v1.61」需本人登录下载（证据链已闭合，仅可选复核）

---

## 8. 立刻可以问用户的 3 个问题

> **2026-10-11 状态**：三问均已获用户答复关闭；**队名同日拍板「瞬狙」——全部关闭，无遗留问题**。

1. ~~报名（9/22 截止）是否已完成？~~ — **已报名确认（2026-10-11 用户答复）**；队名已拍板：**瞬狙**（2026-10-11）。  
2. ~~EGO1 V2.2 用户手册能否放到工作区？~~ — **已在 `../资料/`（NJUPT 镜像），用户授权用于 J5 上板前逐针复核签字（2026-10-11）；复核同日完成（GO，四方 36/36），v2.2 正式版亦已归档**。  
3. ~~下一步优先？~~ — **用户拍板：先对齐 uart_packet_tx 帧协议 §17（55 AA/CRC-16）→ 已完成**；物料已下单。剩余队列：J5 逐针复核签字 → LED/LEARN 文档冻结 → P1 静态核心（IDLE_CHECK/golden_compare/LEARN）。  

---

## 9. 变更记录

| 日期 | 内容 |
|------|------|
| 2026-09-14 | 初版交接包：V1.9 终审后、阶段一旧草稿 bit 已生成、正式重构未开始 |
| 2026-10-02 | **项目重组**：本文件迁入 `瞬迹/doc/`；正式仓库 = `瞬迹/`（git init + `git_server/` 裸仓库）；uv 包化（`src/xunji`：protocol=V1.9 §17 帧协议、`xunji sync`=构建目录镜像，15 项 pytest 全绿）；RTL/TB 提升到根 `rtl/`、`sim/`；旧 Vivado 工程进 `vivado/legacy/`；弃用旧目录进 `../_archive_deprecated/`；新增根级 `AGENTS.md`（superpowers 流程）。**P0 仍未开始**（XDC 草稿、RTL 未按 V1.9 重构）。 |
| 2026-10-08 | **P0 代码侧完成（分支 `p0-xdc-wrappers`，基线 c241840）**：① 按 V1.9 §4.1 表3 整文件重写 `constrs/ego1.xdc`（冻结段 1–6 + 暂定段 LED/按键/拨码 + 故意暂缺的 CDC path exception；红线测试 7 项）；② `xj_top` 拆为 `xunji_core` + `xunji_top_hw`（`b_conn=b_sync`）+ `xunji_top_loopback`（`b_conn=~b_sync` 唯一反相点）+ `xj_rst_sync`，`topology_scanner` 不再取反（红线测试 8 项，含变异检查）；③ lint 双顶层、sim/xsim 与 Tcl/CLI 顶层名跟随改名；`tb_xj_top`→`tb_xunji_loopback`。**验证：pytest 41 passed / lint exit 0（双顶层）/ sim PASS（EXPECT 0010100000010100）**；`xunji xsim` 因 Vivado 缺 `xv_xsimverific.dll` 离线不可修（见 §7）。计划 `doc/superpowers/plans/2026-10-08-p0-xdc-wrappers.md`。 *仍未完成：手册逐针复核、报名确认、LED/LEARN 文档冻结、N_CH 4→16、uart_packet_tx 帧协议对齐 §17* |
| 2026-10-11 | **`xunji xsim` 终审解除阻塞（提交 2a4a890）**：换电脑后新装 Vivado/Vitis **2026.1**（`C:\AMDDesignTools\2026.1`）并激活 Node-Locked BASIC tier 许可证（AMD 官网 entitlenow 生成，HOSTID=MAC `e8b0c58fb217`，VLM Copy License 装入 `%APPDATA%\XilinxLicense\`）；`cli.py` 的 `VIVADO_BIN` 由损坏的 2024.2 切到 2026.1。**验证：pytest 41 / lint 0 / sim PASS / xsim PASS（tb_xunji_loopback，G4 首次本机跑通）**。User PATH 的 2024.2 旧条目保留未删。 |
| 2026-10-11 | **uart_packet_tx 帧协议对齐 V1.9 §17（分支 `uart-frame-v19`，基线 24532b8；同日 P0 分支已 ff 合并 main 并推 git_server）**：帧头 A5 5A→**55 AA**，帧型 `Ver/Type/Len(2,LE)/Seq(2,LE)/Payload/CRC(2,LE)`，CRC8→**CRC-16/CCITT-FALSE**（poly 0x1021/init FFFF，xor-first 与 protocol.py 逐行同构，低字节先发）；Ver=1、Type=1（拓扑矩阵帧，protocol.py 新增 `TYPE_MATRIX`）、Seq 计数器首帧 0、载荷语义不变。新增 `sim/tb_uart_packet_tx.v`（黄金向量 14 B × 2 帧与 protocol.build_frame 双向锁定 + 独立 CRC 复算），cli `SIM_TOPS` 双 TB（sim/xsim 每 top 独立 G2/G4）。**顺手修复既有握手 bug：旧实现于 tx_busy 升起前 1 拍抢发下一字节，每 2 字节丢 1（硬件上一直存在，回环 TB 从不解码 UART 故未暴露）→ LOAD/ACK/DRAIN 三拍握手**。**合并前 code review（REQUEST CHANGES→已修复）追加 blocker：`uart_tx` 旧实现停止位开始沿即清 tx_busy，背靠背字节停止位仅 30 ns（应为 8.68 µs），8N1 接收机 framing error——TB 重写为真实 uart_tx + tx 线中点采样解码复现红，修复为 busy 覆盖完整停止位（bit_pos=10 完结拍）后线级解码 PASS**；另加固 SIM_TOPS 红线、撤销过期 BLKSEQ 豁免、sim/xsim 分 top 标签。验证：**pytest 49 / lint 0 / sim 双 PASS / xsim 双 PASS（线级解码）**。计划 `doc/superpowers/plans/2026-10-11-uart-frame-v19.md`。 *同日用户答复：报名已确认、物料已下单、手册授权 J5 复核；仍未完成：J5 逐针复核签字、LED/LEARN 文档冻结、N_CH 4→16、P1 静态核心、队名拍板* |
| 2026-10-11 | **J5 上板前逐针复核完成（§27-GO，四方 36/36 全一致，0 差异）**：比对源 = ①EGO1 V2.2 正式版手册（2026-10-11 经 ghfast.top 自官方开发包公开副本归档，封面「2018.04 ver2.2」，J5 表 p20–21）②南邮 eelab 转存 18 页件 ③V1.9 §4.1 表3 ④`constrs/ego1.xdc`；1–32 针四方 ball/网络标号/端口映射全中，33–36 电源针经官方《EGO1電路圖.pdf》p6 目验（35/36→+3.3V、33/34→接地符号），XDC 无 33–36 条目且全文件无重复 PACKAGE_PIN。**版本自证闭环**：南邮件全文无版本字样（网页转存），V2.2 实证 = 依元素官方文档站 `e-elements.readthedocs.io/zh/ego1_v2.2/`（源分支 `AJetfire/EES@EGo1_V2.2`）+ 官方开发包 PDF 封面；v2.2 与南邮件 J5 表 32/32 全同。勾选记录与可复跑脚本：`doc/reports/2026-10-11-j5-pin-review/`。 *仍未完成：LED/LEARN 文档冻结、N_CH 4→16、P1 静态核心、队名拍板* |
| 2026-10-11 | **队名拍板：瞬狙**（用户答复）；此前候选「线所未见」/「迹不可失」作废。同日 J5 复核记录提交并推送 git_server（93ff465）。 |
| 2026-10-11 | **烧录上板闭环 + 工作流 A 落地 + 段7 管脚修正（用户拍板提交）**：①**烧录链路跑通**：hw_server 3121 → batch `program_hw_devices` → `End of startup status: HIGH`，IDCODE 0362D093=XC7A35T；COM4@115200 收到 §17 首帧 14B `55 AA 01 01 04 00 00 00 FF FF 00 E2 9E 33`，CRC-16/CCITT-FALSE 复算 MATCH；扫描行为=**复位后自动跑一次**（`scan_start=btn[0]|sw[0]`，uart_rx P0 未接接收器，再触发=重上电/重烧）。②**中文路径=综合无声崩溃根因坐实**（elaboration 后截断、无 ERROR，3 次复现；纯 ASCII 一次通过）→ **工作流 A（用户拍板）**：`scripts/sync_to_build.py` 增量同步至 `C:\xjbuild`，`--build` 一条龙出 bit（settings64 链残留 RC=1，成败以 bit 文件为准）。③**段7 暂定段 4 处管脚对齐 EGO1 V2.2 官方「通用I/O接口」**：led[12] G4→J4、led[14] H2→G4、led[15] H1→F6、btn[4] V2→U4（V2 实为 SW_DIP5）；同文件 32 行行尾 `#` 注释移出 Tcl 语句（行中 `#` 被当参数 → [Common 17-161] 静默丢约束 → DRC NSTD/UCIO）；tests/test_xdc.py 期望同步。**验证：pytest 49 绿 → C:\xjbuild 重建 bit（时序 met=1）→ 重烧 → 板上 LD8–LD15 八灯全亮（用户照片确认，官方丝印 (0)(K2)…(7)(F6) 全中；LED 高电平点亮、timestamp 高位千 Hz 方波=常亮不闪属预期）**。④HTML 接线交付物 `doc/接线与代码对照.html` 入库。 *仍未完成：LED/LEARN 文档冻结、N_CH 4→16、P1 静态核心* |
| 2026-10-02 | **三层验证流水线建成（G1-G6 达成）**：`xunji lint`（Verilator 5.050）/`xunji sim`（iverilog 13.0，PASS 三重判定）/`xunji xsim`（Vivado 2024.2 终审，D:\xunjiji 镜像）三命令全绿；TB mismatch 走 `$fatal` 非零退出；`scripts/lint.vlt` 5 条豁免收窄到文件级；SDD 子代理驱动 9 任务全部审查通过，合并 main 并推送 git_server（b961810）；证据 `doc/reports/2026-10-02-compile/`（G1-G5 齐备）；账本 `.superpowers/sdd/2026-10-02-compile-pipeline/`。 *遗留：uart_packet_tx 帧（A5 5A/CRC8）与 V1.9 §17（55 AA/CRC-16）不一致待立项* |

## 10. 研究候选（前沿调研产出，2026-10-02）

> 来源：并行调研子代理（学术 API + 厂商官网 + GitHub）。**均为破坏型路线调整候选，实施前必须先修订 V1.9 冻结文档**（AGENTS.md §6 红线）；不属于当前编译流水线范围。

1. **去多数表决 → 全边沿捕获 + 事件宽度直方图**：行业军用 IFDIS 金标准 50 ns；现方案 100MHz+多数表决系统性滤掉 <30 ns 事件——采样率不是瓶颈，判决逻辑才是。纯 FPGA 零硬件成本，对标指标可写进论文。
2. **CARRY4 进位链 TDC 时间戳**（码密度法标定）：10 ns → ps 级；XC7A35T 有国内成熟先例；同时服务瞬态精细时序与可选 TDR 飞行时间。
3. **CD4066 切换 2-3 个上拉电阻 → B 端多阈值**：感知接触电阻 mΩ→Ω"软退化前奏"（LVC14 单阈值对此全盲）；仅需少量电阻。
4. **上位机轻量 ML 分类**（KNN/CNN 级，输入=事件宽度/间隔分布）：AUTOTESTCON 2024、Measurement 2021 有模板；FPGA 不负担推理。
5. **SSTDR-lite 正交码并行反射**（FPGA 数字 I/O TDR 可行性见 IEEE TIM 2021）：加分项/论文章节，工程量大。

关键参照：Universal Synaptics IFDIS（MIL-PRF-32516）、Auzanneau 2025 反射测量综述（DOI 10.1016/j.measen.2025.101981）；术语注意：不用自造缩写"LVOT"，用"低压四线导通/接触电阻测试"。

---

*接手检查（2026-10-02 起）：读 `瞬迹/AGENTS.md` → 读本文件 → 读 V1.9 的 §4.3/§21/§26/§27 → `git log`/目录对照 → 向用户确认 §8 三问 → 按 AGENTS.md §3 工作流从 P0 开干。*
