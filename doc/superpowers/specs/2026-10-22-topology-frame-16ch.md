# 拓扑矩阵帧 payload 扩展（16 路）— 决策记录

日期：2026-10-22｜分支 `p1-static-core`｜状态：已实施（T3）

## 背景

V1.9 §17（P106）冻结的是**帧结构**：`SOF 55AA | Ver | Type | Len(2,LE) | Seq(2,LE) | Payload | CRC(2,LE)`，
除 SOF 外多字节小端，CRC-16/CCITT-FALSE（poly 0x1021 / init 0xFFFF）。**payload 内部语义不在 V1.9 冻结范围内**，
原 4 字节布局（mat_lo/mat_hi/open/ts0）是 2026-10-11 的工程决策，只能承载 4 路 16 bit 矩阵。
16 路需 256 bit = 32 字节，原布局会**静默截断**，因此本次扩展 payload 定义。

## 决策

帧 `Type=1`（拓扑矩阵帧，`protocol.TYPE_MATRIX`）的 payload 固定为：

| 偏移 | 长度 | 内容 |
|------|------|------|
| 0 .. N*N/8-1 | N*N/8（4 路 2B / 16 路 32B） | 连接矩阵 M[i][j]，行 major；byte k = `matrix[8k+7:8k]`，row0 的 b0..b7 落在 byte0（与旧 mat_lo/mat_hi 顺序兼容） |
| N*N/8 .. +1 | 2 | `open_flags` 小端（16 位，N_CH<16 时高位为 0） |
| +2 .. +3 | 2 | `stuck_low_mask` 小端 |
| +4 | 1 | `cls` 分类：0 PASS / 1 OPEN / 2 MISWIRE / 3 BRIDGE / 4 ANOMALY / 5 NO_REF（未学习） |
| +5 | 1 | 时间戳低 8 位 ts0 |

- 帧总长 = 2 + (6 + payload) + 2：4 路 **18 B**，16 路 **48 B**。
- CRC 覆盖 Ver..Payload（不含 SOF/CRC 本身），参数与发送顺序（低字节先发）不变。
- 4 路黄金帧随本次扩展更新：`55AA0101080000 0004280000000000BE E338`（seq=0）。

## 理由与权衡

- 保持 Type=1 单一矩阵帧，上位机只按 `Len` 解析，不需要枚举新 Type。
- `cls` 与 `stuck_low_mask` 直接进帧，上位机可区分 PASS/OPEN/MISWIRE/BRIDGE/ANOMALY 与卡低通道，不必二次推断。
- 115200 下 48 B 帧约 4.2 ms，远小于扫描周期预算；比赛版可提高波特率或批量发送，不影响本定义。
- 代价：旧 14 B 帧不兼容（无上位机在用），已在 protocol.py/TB/测试中一次性切换并双向锁死。

## 验证

- `tests/test_matrix_payload.py`：payload 长度（4 路 8B / 16 路 38B）、4 路黄金帧、4/16 路往返解析、分类枚举。
- `sim/tb_uart_packet_tx.v`：线级 8N1 解码 18 B × 2 帧（seq 递增）+ 独立 CRC 复算，与 `protocol.build_frame` 双向锁定。
- `rtl/uart_packet_tx.v`：`MAT_BYTES/PAYLOAD_LEN/BODY_LEN/FRAME_LEN` 全部由 `N_CH` 推导，4/16 路同一套 RTL。
