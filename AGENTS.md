# AGENTS.md — 瞬迹（XunJi）开发规范

> 本文是本仓库所有 AI 协作者与新会话的**开工必读**。
> 流程规范依据 superpowers 技能族（`C:\Users\38074\.agents\skills\`）撰写；
> 技术决策依据 `doc/瞬迹_完整可行技术路线_EGO1开发板版_V1.9.docx`（唯一基线）。

---

## 1. 项目与基线（30 秒）

- **瞬迹**：FPGA 并行时序分析 —— 静态重建线束拓扑（线怎么接），动态捕获 μs 级瞬态开路（线什么时候断）。
- **板卡**：EGO1 Artix-7 XC7A35T-1CSG324C @ 100 MHz；Vivado 2024.2。
- **唯一技术基线**：`doc/瞬迹_完整可行技术路线_EGO1开发板版_V1.9.docx`。
  冻结依据 = §4.3 设计冻结表 + §26 十条修正 + §27 GO/NO-GO 检查表。
  改接口/极性/记录语义**必须先改文档**并说明，不可只改代码。
- **交接口径**：`doc/HANDOFF_AI.md`（历史状态与任务队列 P0–P3）。

## 2. 仓库结构（uv 包化）

```
瞬迹/  (= git 仓库根)
├── AGENTS.md            # 本文件
├── README.md            # 项目总览与快速开始
├── pyproject.toml       # uv 项目（xunji 包 + dev 组）
├── .python-version      # 3.12
├── src/xunji/           # 主机侧 Python 包
│   ├── protocol.py      # UART 帧协议（V1.9 §17 冻结）
│   └── cli.py           # xunji sync：镜像 rtl/sim/constrs/scripts 到英文构建目录
├── tests/               # pytest（TDD 起点）
├── rtl/                 # Verilog 源
├── sim/                 # Testbench
├── constrs/             # EGO1 XDC（J5 待按 §4.1 表3 重写）
├── scripts/             # Vivado Tcl（create_project / simulate / build）
├── doc/                 # V1.9 基线、HANDOFF、实施计划、tools/、reports/
└── vivado/              # 生成的 Vivado 工程（gitignore；旧草稿产物在 vivado/legacy/）
```

- **弃用目录**：`../_archive_deprecated/`（旧练习代码与脚本，见其 README，勿引用）。
- **Vivado 中文路径**：构建一律在英文目录（默认 `D:\xunjiji`），用 `uv run xunji sync` 镜像后执行 Tcl。

## 3. 开发流程（superpowers 技能族）

每个功能/修复按顺序走以下流程。**技能名是硬引用**，需要细节时读对应 `SKILL.md`。

### 3.1 隔离工作区 — `using-git-worktrees`（强制）

除文档/错别字类小改动外，一切实现**必须在隔离工作区进行**：

1. **步骤 0 检测**：`git rev-parse --git-dir` vs `--git-common-dir`；相等=普通检出，需建 worktree。
2. 本仓库约定：worktree 一律放 **`.worktrees/<分支名>/`**（已在 `.gitignore`）。
3. 创建前必须验证忽略生效：`git check-ignore -q .worktrees`，未忽略先改 `.gitignore` 并提交。
4. `git worktree add .worktrees/<分支名> -b <分支名>`，进入后 `uv sync` 并跑 `uv run pytest` 确认**基线全绿**再开工。
5. 收尾走 3.6，只清理 `.worktrees/` 下的工作树。

### 3.2 先写计划 — `writing-plans`

- 多步骤任务先写实现计划，保存到 **`doc/superpowers/plans/YYYY-MM-DD-<feature>.md`**。
- 计划必须含：目标/架构/技术栈、逐任务的文件清单、**每步可运行的验证命令**（"确认可用"不算验证条件）。
- 禁止占位符（"TODO/后续/类似任务 N"）。小步任务：写失败测试→确认失败→最少实现→确认通过→提交。

### 3.3 执行计划 — `executing-plans`（或子代理用 `subagent-driven-development`）

- 每任务节奏：标记进行中 → 实现 → **运行验证** → **单独提交**（消息引用任务编号）→ 标记完成。
- 未经用户明确同意，**绝不在 main/master 上直接实现**（3.1 的 feature 分支是默认路径）。
- 遇阻塞（缺依赖、测试连续失败 2 次、指令不清）→ **停下来问**，不硬闯。

### 3.4 测试先行 — `test-driven-development`（铁律）

```
没有失败的测试，就不写生产代码
```

- 红→绿→重构：先写测试，**亲眼看它失败**（失败原因须是功能缺失），再写最少实现让它通过。
- Bug 修复 = 先写重现该 bug 的失败测试。
- 例外（一次性原型/生成代码/配置文件）需用户许可。
- 危险信号：先写代码后补测试、测试立即通过、"就这一次"。

### 3.5 调试 — `systematic-debugging`

不做根因调查，不许提修复方案。四阶段：根因调查（读错误/复现/查变更/追数据流）→ 模式分析 → 单一假设最小验证 → 用 TDD 落实修复。
**同一问题修复 3 次失败 = 架构问题**，停下来与用户讨论，不试第 4 次。

### 3.6 收尾分支 — `finishing-a-development-branch`

1. 先跑完整测试套件，全绿才谈收尾。
2. 展示三选项给用户选：① 本地合并回基础分支 ② 推送并建 PR ③ 保留分支。
3. 选项①：合并后**在合并结果上重跑测试**，全绿才删分支；失败则原地保留现场。
4. 只清理 `.worktrees/` 下的工作树（`git worktree remove` + `prune`）。

### 3.7 完成前验证 — `verification-before-completion`（铁律）

```
没有新鲜的验证证据，不许宣称完成
```

- 说"测试通过"前必须**本次会话运行过**该命令并读过输出。
- 禁用词："应该/大概/似乎/看起来对了/太好了"。
- 需求完成 = 逐项核对清单，不是"测试通过了"。
- 提交前必跑：`uv run pytest`（全绿）→ `uv run xunji lint` → `uv run xunji sim`（改 RTL 必跑；任一红禁提交）。合并/交付前必跑 `uv run xunji xsim` 终审。

### 3.8 代码评审

- **主动评审** `requesting-code-review`：完成重大功能、合并 main 前，派 code-reviewer 子代理（给出 BASE/HEAD SHA 与需求上下文，不给会话历史）。
- **接收评审** `receiving-code-review`：先对照代码验证再实施；反馈不明确先澄清；有理有据地反驳；确认正确的直接改，不写"你说得太对了"。
- **并行子代理** `dispatching-parallel-agents`：仅当多个任务**互相独立、无共享状态**时并行分派；返回后审查汇总、检查冲突、跑完整套件。

## 4. 提交与 Git 规范

- 提交信息：**Conventional Commits**，正文中文，如 `feat(protocol): 实现 CRC-16/CCITT-FALSE 帧校验`。
- 粒度：每任务一个提交；工作树内容**不得**被提交（`.worktrees/`、`vivado/`、`.venv/` 已 ignore）。
- 远端：本地服务仓库 `git_server/`（gitignore；`git init --bare`），remote 名 `origin`。
- 对外动作（推送、报名、下单）需用户拍板；删除/覆盖类操作先确认。

## 5. 本机环境约定（Windows / cmd.exe）

- 终端是 **cmd.exe**：用 `dir`/`type`/`where`，不用 `ls`/`cat`/`which`；`cd` 用绝对路径，复合命令用 `&&`。
- `uv` 在 `D:\msys64\ucrt64\bin\uv.exe`（PATH 内）；Python 3.12（`.python-version`）。
- Vivado：`D:\Xilinx\Vivado\Vivado\2024.2\bin\vivado.bat -mode batch -source <tcl> -nolog -nojournal`。
- 内联 `python -c` 多行中文脚本在 cmd 下不可靠：**写成临时 .py 文件执行**，输出重定向到文件再读，防 GBK 乱码。
- 网络受限：github.com 直连不通（走 `ghfast.top` 镜像）；pip 已配阿里云镜像，**不要**加 `-i` 参数。

## 6. 技术红线（V1.9 冻结，违者必须先改文档）

1. J5/XDC、A/B 针序、`b_conn` 语义、reset/CDC 原则、数据记录语义**不得无依据反复变更**（§26）。
2. 复位/安全态 `a_ctrl_n` 全 1；生产 Top `b_conn=b_sync`（导通=1）；反相只许在 loopback wrapper。
3. 仅 100 MHz 单时钟，节拍一律 clock-enable；`b_raw`/`uart_rx` 两级同步器。
4. Sequence **≠** 物理先后；动态路径不复用静态长毛刺；10 ns 计数颗粒 ≠ 100 ns 波形采样。
5. 资源/时序报告注明**含/不含 ILA**；调参（SETTLE/Rp/MIN_PULSE/波特率/队列深度）须有实测依据。
6. 上板前 J5 必须按 **EGO1 V2.2 官方手册**逐针复核（§27-GO），并留勾选记录。

## 7. 验收锚点

- **仿真**：V1.9 §27 GO/NO-GO 表逐项（`doc/` 内可查 extract 工具）。
- **上板**：§21 阶段 1→10 顺序推进（1 路→4 路→16 路，不跳步）。
- **提交**：作品截止 2026-11-04 18:00；决赛 2026-11-20~22 南京。

---

### 快速命令

```bat
uv sync                          :: 安装依赖（首次）
uv run pytest -q                 :: 全部测试（提交前必跑）
uv run xunji sync --dest D:\xunjiji   :: 镜像源到英文构建目录
```

```bat
:: Vivado 仿真/综合（在 D:\xunjiji\scripts 下）
"D:\Xilinx\Vivado\Vivado\2024.2\bin\vivado.bat" -mode batch -source simulate.tcl -nolog -nojournal
"D:\Xilinx\Vivado\Vivado\2024.2\bin\vivado.bat" -mode batch -source build.tcl -nolog -nojournal
```
