# 瞬迹（XunJi）— 基于 FPGA 的线束拓扑重建与 μs 级瞬态开路诊断装置

> 主控：EGO1 **Artix-7 XC7A35T-1CSG324C** @ 100 MHz ｜ 工具链：**Vivado 2026.1**
> 赛事：第十届全国大学生嵌入式芯片与系统设计竞赛 · FPGA 创新设计赛道（AMD）
> 许可证：[MIT](LICENSE)
> 大模型协作记录：[`report/llm-collaboration-log.md`](report/llm-collaboration-log.md) ｜ 技能包：[`skill/`](skill/)

## 一句话主线

**静态重建「线怎么接」，动态捕获「线什么时候断」。**

16 路逐路扫描重建 16×16 连接矩阵；与学习到的参考矩阵比对，输出五级故障判定
（PASS / OPEN / MISWIRE / BRIDGE / ANOMALY）并定位到具体线号；
再由 CD4066 阵列注入 μs 级瞬态断线，FPGA 以 100 MHz 采样捕获。

## 实测指标

| 指标 | 值 |
|---|---|
| 通道数 | 16 |
| 单轮扫描周期 | 112 μs |
| 帧长 / 波特率 / 帧率 | 48 B / 115200 bps / 240 fps |
| 资源（XC7A35T） | LUT **2119**（10.19%）· FF **1564**（3.76%）· BRAM 0 · DSP 0 |
| 时序 | WNS **+1.408 ns**，全部约束满足 |
| 回归 | iverilog 6/6 testbench · pytest **84** 项 |
| 实测结果 | 16/16 通道全通；四类故障（拔线/接反/短接/混合）全部正确分类并定位 |

## 快速开始

```bat
uv sync                                   :: 安装依赖（Python 3.12）
uv run pytest -q                          :: 全部测试（84 项）
uv run python -m xunji.cli sim            :: iverilog 仿真（6 个 testbench）
uv run python -m xunji.cli lint           :: RTL 风格检查
uv run python scripts\sync_to_build.py --build   :: 综合+实现，产出 .bit
```

> 注意：本机部分环境下 `uv run xunji` 启动器会被策略拦截，
> 请统一用 `uv run python -m xunji.cli <子命令>`。

烧录（EGO1，JTAG）：

```bat
C:\AMDDesignTools\2026.1\Vivado\bin\vivado.bat -mode batch -source scripts\program_ego1.tcl
```

> ⚠ JTAG 配置是**易失**的：每次断电/重新插拔后必须重新烧录。
> 且 LEARN 的参考矩阵存在 FPGA 寄存器里，重烧后需重新按学习键（板载 **S1**）。

## 目录结构

主办方推荐结构见指南 §3.3.5.4；本仓库**保留中文目录名**（更贴合队内协作习惯），
按指南「采用其他组织方式须给出目录对照说明」的要求对照如下：

| 本项目路径 | 作用 | 对应推荐结构 |
|---|---|---|
| `rtl/` | Verilog 源码（15 个文件） | `src/` |
| `sim/` | testbench（6 个） | `sim/` |
| `tests/` | pytest（84 项，含黄金帧回归） | `sim/`（验证） |
| `src/xunji/` | 主机侧 Python 包（协议解析 / CLI） | `src/`（软件） |
| `constrs/` | EGO1 XDC | `build/` |
| `scripts/` | Vivado Tcl · 构建 · 报告与海报生成 · 烧录 | `build/` |
| `pcb/` | 前端板参数化生成脚本 + KiCad 工程 + Gerber | `board/`（自制硬件） |
| `firmware/` | Arduino Nano 4066 脉冲源固件 | `board/` |
| `doc/` | 设计报告、上位机、证据 hex、原理图与 PCB 图、外壳模型 | `report/` + `data/` |
| **`skill/`** | **技能包（指南要求）** | `skill/` |
| **`report/`** | **大模型协作记录（指南要求）** | `report/` |

## 关键设计

### 双端有源扫描拓扑

```
a_ctrl_n → LVC07(开漏) → RS 330Ω → JA → 被测线束 → JB → RP 4.7kΩ 上拉
        → LVC14(施密特反相) → b_raw → FPGA
```

- A 端开漏激励：多路同时存在时不会发生推挽竞争；串阻把单路短路电流限制在约 10 mA
- B 端上拉 + 施密特反相：抑制长线束慢边沿抖动
- 仅用 32 根信号线完成 16×16 全连接矩阵重建

### 三层滤波

空闲稳定窗 500 周期（5 μs）→ 101 拍多数表决 → 8 拍去毛刺。

### 单时钟、纯 clock-enable

全系统仅 100 MHz 一个时钟域；`b_raw` / `uart_rx` 均经两级同步器；
复位经异步拉低、同步释放。

### 帧矩阵快照

在发送触发沿锁存矩阵，保证一帧内 CRC 与负载**同源**（这是本项目最重要的一个缺陷修复）。

## 故障判定语义

| cls | 含义 | 判据 |
|---|---|---|
| 0 | PASS | 与参考矩阵完全一致 |
| 3 | BRIDGE | 任一方向度 > 1（短接优先） |
| 2 | MISWIRE | 有缺失也有额外，且仍是双射（接反/换位） |
| 1 | OPEN | 只有缺失、没有额外，且缺失行实测为空 |
| 4 | ANOMALY | 混合、无法唯一解释（**不夸大**：拒绝硬套类型） |
| 5 | NO_REF | 尚未学习 |

## 硬件

- **主控**：EGO1（XC7A35T），100 MHz → P17，复位 P15，UART T4/N5
- **前端板 FE-16**：96×96 mm 双层板，LVC07×3 + LVC14×3 + 49 颗电阻 + 7 颗电容，
  JA/JB 为 2×10 接口，J5 2×18 与主控对接，TP1–TP50 测试点
- **故障注入**：CD4066 ×4（32 路开关）+ Arduino Nano

## 复现步骤（从零开始）

1. **装环境**：Python 3.12 + `uv`；Vivado 2026.1
2. **拉代码**：`git clone <repo>` → `uv sync`
3. **验软件**：`uv run pytest -q`（应 84 passed）→ `uv run python -m xunji.cli sim`（应 6/6 PASS）
4. **做硬件**：按 `pcb/frontend16/` 的脚本生成 Gerber 打板并焊装（BOM 见 `doc/`）
5. **出 bit**：`uv run python scripts\sync_to_build.py --build`
6. **上板**：烧录 `program_ego1.tcl` → 拨扫描开关 → 串口 115200 收帧
7. **学参考**：接 1:1 线束全通后，按板载 **S1** 学习 → `cls` 由 5 变 0
8. **做故障**：拔线 → `cls=1`；交换两根 → `cls=2`；短接两根 → `cls=3`
9. **看结果**：`uv run python -m xunji.cli read --port COM<x> --frames 3`

## 文档索引

| 文件 | 内容 |
|---|---|
| [`report/llm-collaboration-log.md`](report/llm-collaboration-log.md) | 大模型协作记录（提示词 / 自我纠错轨迹 / 失误清单） |
| [`skill/README.md`](skill/README.md) | 技能包索引与复用验证 |
| `doc/瞬迹_作品报告.pdf` | 作品设计报告（提交版） |
| `doc/瞬迹_海报_中英_终版.pptx` | **提交用海报（定稿，中英各一页）** |
| `doc/瞬迹_海报_中文版_含校徽.pdf` · `doc/XUNJI_Poster_English_含校徽.pdf` | 海报的 PDF 定稿（含校徽与队伍信息，仅用于上传与展示；决赛现场 A4 打印版需去掉队伍信息） |
| `doc/证据/` | 四类故障的原始帧证据（hex） |
| `doc/photous/` | 实物照片与演示截图 |
| `AGENTS.md` | 开发规范（AI 协作者必读） |

## 许可证

[MIT](LICENSE) —— 允许再分发，欢迎复用 `skill/` 中的经验。
