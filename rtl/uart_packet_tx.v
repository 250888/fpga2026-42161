//==============================================================================
// UART packet TX — 扫描完成后发送拓扑矩阵帧
//
// 帧格式冻结自 V1.9 §17（除 SOF 外多字节小端，CRC-16/CCITT-FALSE）：
//   55 AA | Ver(1) | Type(1) | Len(2,LE) | Seq(2,LE) | Payload | CRC(2,LE)
//
// Payload（2026-10-22 扩展，决策记录 specs/2026-10-22-topology-frame-16ch.md）：
//   MAT[N_CH*N_CH/8] + open(2,LE) + stuck(2,LE) + cls(1) + ts0(1)
//   4 路 = 8B（帧 18B）；16 路 = 38B（帧 48B）。byte k = matrix[8k+7:8k]，行 major。
//   cls: 0 PASS / 1 OPEN / 2 MISWIRE / 3 BRIDGE / 4 ANOMALY / 5 NO_REF（未学习）。
//
// 握手（任务3 修复点）：旧实现于 tx_busy 升起前 1 拍抢发下一字节 → 每 2 字节丢 1；
// 现用 LOAD→ACK（等 busy 抬起）→ DRAIN（等 busy 落下）三拍握手。
// 停止位覆盖（任务5b）：uart_tx 的 busy 覆盖完整停止位，否则背靠背字节 framing error。
//==============================================================================

module uart_packet_tx #(
    parameter N_CH = 16
)(
    input  wire                 clk,
    input  wire                 rst,
    input  wire                 trigger,
    input  wire [N_CH*N_CH-1:0] matrix,
    input  wire [N_CH-1:0]      open_flags,
    input  wire [N_CH-1:0]      stuck_low_mask,
    input  wire [2:0]           cls,
    input  wire [63:0]          timestamp,
    output reg                  tx_start,
    output reg  [7:0]           tx_data,
    input  wire                 tx_busy
);

    localparam [7:0] VERSION = 8'd1;
    localparam [7:0] FTYPE   = 8'd1;                 // 拓扑矩阵帧（protocol.TYPE_MATRIX）
    localparam [7:0] MAT_BYTES   = N_CH * N_CH / 8;  // 4 路 2B / 16 路 32B
    localparam [7:0] PAYLOAD_LEN = MAT_BYTES + 8'd6;
    localparam [7:0] BODY_LEN    = 8'd6 + PAYLOAD_LEN;   // Ver..Payload 字节数
    localparam [7:0] FRAME_LEN   = 8'd2 + BODY_LEN + 8'd2;

    localparam [2:0] S_IDLE  = 3'd0,
                     S_PREP  = 3'd1,      // 逐字节算 CRC（body）
                     S_LOAD  = 3'd2,      // 装一字节 + tx_start 单拍
                     S_ACK   = 3'd3,      // 等 uart_tx 抬 tx_busy
                     S_DRAIN = 3'd4;      // 等 tx_busy 落下再发下一字节

    reg [2:0]  state;
    reg [15:0] seq_q;
    reg [15:0] frame_seq;
    reg [15:0] crc_r;
    reg [7:0]  pidx;         // PREP body 索引
    reg [7:0]  sidx;         // 线上字节索引
    reg [7:0]  open_lo, open_hi, stuck_lo, stuck_hi, cls_r, ts0_r;
    // 矩阵快照（2026-10-24 审查 B1）：SW0 常开时一轮扫描 ≈112 µs，而 48B@115200
    // 一帧 ≈4.17 ms，期间约 37 次重扫会改写 matrix。不锁存的话 S_PREP 算 CRC 与
    // S_LOAD 发实体字节读的是不同版本的矩阵，上位机必然 CRC 拒绝。
    reg [N_CH*N_CH-1:0] matrix_r;

    // 16 位零扩展（位宽对齐后再拆小端字节；N_CH=4 时高位为 0）
    wire [15:0] open_ext  = 16'h0000 | open_flags;
    wire [15:0] stuck_ext = 16'h0000 | stuck_low_mask;

    // payload 内各段偏移（相对 payload 起点）
    localparam [7:0] OFF_OPEN  = MAT_BYTES;
    localparam [7:0] OFF_STUCK = MAT_BYTES + 8'd2;
    localparam [7:0] OFF_CLS   = MAT_BYTES + 8'd4;
    localparam [7:0] OFF_TS0   = MAT_BYTES + 8'd5;

    // body = Version..Payload（CRC 覆盖范围），索引 0..BODY_LEN-1
    function [7:0] body_byte;
        input [7:0] i;
        begin
            if (i < 8'd6) begin
                case (i)
                    8'd0:    body_byte = VERSION;
                    8'd1:    body_byte = FTYPE;
                    8'd2:    body_byte = PAYLOAD_LEN;
                    8'd3:    body_byte = 8'h00;
                    8'd4:    body_byte = frame_seq[7:0];
                    8'd5:    body_byte = frame_seq[15:8];
                    default: body_byte = 8'h00;
                endcase
            end else if (i < 8'd6 + MAT_BYTES) begin
                // 矩阵：byte k 取 matrix_r[8k+7:8k]（快照，见 B1）
                body_byte = matrix_r[(i - 8'd6) * 8 +: 8];
            end else begin
                case (i - 8'd6)
                    OFF_OPEN:         body_byte = open_lo;
                    OFF_OPEN  + 8'd1: body_byte = open_hi;
                    OFF_STUCK:        body_byte = stuck_lo;
                    OFF_STUCK + 8'd1: body_byte = stuck_hi;
                    OFF_CLS:          body_byte = cls_r;
                    OFF_TS0:          body_byte = ts0_r;
                    default:          body_byte = 8'h00;
                endcase
            end
        end
    endfunction

    // 线上字节：SOF(2) + body(BODY_LEN) + CRC 低/高
    function [7:0] send_byte;
        input [7:0] i;
        begin
            if (i == 8'd0)
                send_byte = 8'h55;
            else if (i == 8'd1)
                send_byte = 8'hAA;
            else if (i < 8'd2 + BODY_LEN)
                send_byte = body_byte(i - 8'd2);
            else if (i == 8'd2 + BODY_LEN)
                send_byte = crc_r[7:0];
            else
                send_byte = crc_r[15:8];
        end
    endfunction

    // CRC-16/CCITT-FALSE 逐字节（xor-first，与 protocol.py 逐行同构）
    function [15:0] crc16_update;
        input [15:0] crc_in;
        input [7:0]  data;
        integer k;
        reg [15:0] c;
        begin
            c = crc_in ^ {data, 8'h00};
            for (k = 0; k < 8; k = k + 1) begin
                if (c[15])
                    c = (c << 1) ^ 16'h1021;
                else
                    c = (c << 1);
            end
            crc16_update = c;
        end
    endfunction

    always @(posedge clk) begin
        if (rst) begin
            tx_start  <= 1'b0;
            tx_data   <= 8'h00;
            state     <= S_IDLE;
            seq_q     <= 16'd0;
            frame_seq <= 16'd0;
            crc_r     <= 16'd0;
            pidx      <= 8'd0;
            sidx      <= 8'd0;
            open_lo   <= 8'h00;
            open_hi   <= 8'h00;
            stuck_lo  <= 8'h00;
            stuck_hi  <= 8'h00;
            cls_r     <= 8'h00;
            ts0_r     <= 8'h00;
            matrix_r  <= {N_CH*N_CH{1'b0}};
        end else begin
            tx_start <= 1'b0;   // 默认拉低，仅 LOAD 拍置位

            case (state)
                S_IDLE: begin
                    if (trigger) begin
                        // 16 位零扩展后按小端拆字节（N_CH=4 时高位为 0）
                        open_lo   <= open_ext[7:0];
                        open_hi   <= open_ext[15:8];
                        stuck_lo  <= stuck_ext[7:0];
                        stuck_hi  <= stuck_ext[15:8];
                        cls_r     <= {5'b0, cls};
                        ts0_r     <= timestamp[7:0];
                        matrix_r  <= matrix;
                        frame_seq <= seq_q;
                        seq_q     <= seq_q + 16'd1;
                        crc_r     <= 16'hFFFF;
                        pidx      <= 8'd0;
                        state     <= S_PREP;
                    end
                end

                S_PREP: begin
                    crc_r <= crc16_update(crc_r, body_byte(pidx));
                    if (pidx >= BODY_LEN - 8'd1) begin
                        sidx  <= 8'd0;
                        state <= S_LOAD;
                    end else begin
                        pidx <= pidx + 8'd1;
                    end
                end

                S_LOAD: begin
                    if (!tx_busy) begin
                        tx_data  <= send_byte(sidx);
                        tx_start <= 1'b1;
                        sidx     <= sidx + 8'd1;
                        state    <= S_ACK;
                    end
                end

                S_ACK: begin
                    if (tx_busy)
                        state <= S_DRAIN;
                end

                S_DRAIN: begin
                    if (!tx_busy) begin
                        if (sidx >= FRAME_LEN)
                            state <= S_IDLE;
                        else
                            state <= S_LOAD;
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
