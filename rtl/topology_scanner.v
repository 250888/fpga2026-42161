//==============================================================================
// 静态扫描器（V1.9 R6「static_sampler」的实现；模块名沿用 topology_scanner，
// 以免牵动 wrapper / XDC / 红线测试的既有引用）
//
// 冻结算法（V1.9 P057 / P059 / P060）：
//   IDLE_CHECK：全部 A 释放并等待 IDLE_SETTLE 后，b_conn 必须全 0；
//               仍有 1 → 置 stuck_low_mask（对地短接/前端异常），该通道在
//               矩阵中强制为 0（V1.9「禁止把它当成正常连接边」），idle_ok=0。
//   每个 A 通道四阶段：
//     DRIVE（拉低 A）→ SETTLE（SETTLE 拍）→ SAMPLE（SAMPLE_CYCLES 拍逐位计票，
//     1 的票数 > SAMPLE_CYCLES/2 才判 1）→ RELEASE/GUARD（b_conn 回到全 0
//     并连续稳定 GUARD_STABLE 拍；GUARD_TIMEOUT 拍兜底并置 release_timeout）。
//
// 位序（V1.9 P059 冻结）：M[i][j]，i=A 行、j=B 列，row-major；
//   conn_matrix[row*N_CH +: N_CH]，row_bits[0] 固定代表 B1。
//
// 本模块只读 b_filtered（= 极性归一化后的 b_conn，1=导通），**不做任何反相**。
//==============================================================================

module topology_scanner #(
    parameter N_CH          = 4,
    parameter SETTLE        = 500,
    parameter SAMPLE_CYCLES = 101,   // 奇数拍，避免多数表决 50/50 平票
    parameter GUARD_STABLE  = 8,
    parameter GUARD_TIMEOUT = 500,
    parameter IDLE_SETTLE   = 500
)(
    input  wire                 clk,
    input  wire                 rst,
    input  wire                 start,
    input  wire [N_CH-1:0]      b_filtered,
    output reg                  busy,
    output reg                  done_pulse,
    output reg  [3:0]           scan_idx,
    output reg                  drive_en,
    output reg                  drive_level,
    output reg  [N_CH*N_CH-1:0] conn_matrix,
    output reg  [N_CH-1:0]      open_flags,
    output reg  [N_CH-1:0]      stuck_low_mask,
    output reg                  idle_ok,
    output reg                  release_timeout
);

    localparam S_IDLE       = 4'd0;
    localparam S_IDLE_CHECK = 4'd1;
    localparam S_DRIVE      = 4'd2;
    localparam S_SETTLE     = 4'd3;
    localparam S_SAMPLE     = 4'd4;
    localparam S_DECIDE     = 4'd5;
    localparam S_RELEASE    = 4'd6;
    localparam S_NEXT       = 4'd7;
    localparam S_DONE       = 4'd8;

    localparam VW = (SAMPLE_CYCLES <= 1) ? 1 : $clog2(SAMPLE_CYCLES + 1);
    localparam [VW-1:0] MAJORITY = SAMPLE_CYCLES/2;   // 判决阈值：票数 > 50
    localparam [3:0]    N_LAST   = N_CH - 1;          // 末通道下标（位宽与 row 对齐）

    reg [3:0]  state;
    reg [3:0]  row;
    reg [15:0] wait_cnt;      // SETTLE / IDLE_CHECK / GUARD 超时共用
    reg [15:0] stable_cnt;    // 释放后连续稳定拍数
    reg [VW-1:0] sample_cnt;
    reg [VW-1:0] vote [0:N_CH-1];

    integer i;

    always @(posedge clk) begin
        if (rst) begin
            state           <= S_IDLE;
            busy            <= 1'b0;
            done_pulse      <= 1'b0;
            scan_idx        <= 4'd0;
            drive_en        <= 1'b0;
            drive_level     <= 1'b1;
            conn_matrix     <= {N_CH*N_CH{1'b0}};
            open_flags      <= {N_CH{1'b0}};
            stuck_low_mask  <= {N_CH{1'b0}};
            idle_ok         <= 1'b0;
            release_timeout <= 1'b0;
            row             <= 4'd0;
            wait_cnt        <= 16'd0;
            stable_cnt      <= 16'd0;
            sample_cnt      <= {VW{1'b0}};
            for (i = 0; i < N_CH; i = i + 1)
                vote[i] <= {VW{1'b0}};
        end else begin
            done_pulse <= 1'b0;

            case (state)
                S_IDLE: begin
                    busy        <= 1'b0;
                    drive_en    <= 1'b0;
                    drive_level <= 1'b1;
                    if (start) begin
                        busy            <= 1'b1;
                        row             <= 4'd0;
                        scan_idx        <= 4'd0;
                        conn_matrix     <= {N_CH*N_CH{1'b0}};
                        open_flags      <= {N_CH{1'b0}};
                        stuck_low_mask  <= {N_CH{1'b0}};
                        idle_ok         <= 1'b0;
                        release_timeout <= 1'b0;
                        wait_cnt        <= 16'd0;
                        stable_cnt      <= 16'd0;
                        state           <= S_IDLE_CHECK;
                    end
                end

                // 全 A 释放：等待稳定后 b_conn 必须全 0（V1.9 IDLE_CHECK）
                S_IDLE_CHECK: begin
                    drive_en    <= 1'b0;
                    drive_level <= 1'b1;
                    if (wait_cnt >= IDLE_SETTLE) begin
                        if (b_filtered == {N_CH{1'b0}}) begin
                            idle_ok        <= 1'b1;
                            stuck_low_mask <= {N_CH{1'b0}};
                        end else begin
                            idle_ok        <= 1'b0;
                            stuck_low_mask <= b_filtered;
                        end
                        wait_cnt <= 16'd0;
                        state    <= S_DRIVE;
                    end else begin
                        wait_cnt <= wait_cnt + 16'd1;
                    end
                end

                S_DRIVE: begin
                    drive_en    <= 1'b1;
                    drive_level <= 1'b0;
                    scan_idx    <= row;
                    wait_cnt    <= 16'd0;
                    state       <= S_SETTLE;
                end

                S_SETTLE: begin
                    if (wait_cnt >= SETTLE) begin
                        for (i = 0; i < N_CH; i = i + 1)
                            vote[i] <= {VW{1'b0}};
                        sample_cnt <= {VW{1'b0}};
                        state      <= S_SAMPLE;
                    end else begin
                        wait_cnt <= wait_cnt + 16'd1;
                    end
                end

                // 采样窗：逐位计票（V1.9 SAMPLE_CYCLES 拍）
                S_SAMPLE: begin
                    for (i = 0; i < N_CH; i = i + 1) begin
                        if (b_filtered[i])
                            vote[i] <= vote[i] + {{(VW-1){1'b0}}, 1'b1};
                    end
                    if (sample_cnt >= SAMPLE_CYCLES - 1)
                        state <= S_DECIDE;
                    else
                        sample_cnt <= sample_cnt + {{(VW-1){1'b0}}, 1'b1};
                end

                // 多数表决：票数 > SAMPLE_CYCLES/2 且非卡低通道才判连接
                S_DECIDE: begin
                    for (i = 0; i < N_CH; i = i + 1) begin
                        conn_matrix[row*N_CH + i] <=
                            (vote[i] > MAJORITY) && !stuck_low_mask[i];
                    end
                    wait_cnt   <= 16'd0;
                    stable_cnt <= 16'd0;
                    state      <= S_RELEASE;
                end

                // 释放并守卫：b_conn 回全 0 且连续稳定 GUARD_STABLE 拍
                // 注意要排除 stuck_low 通道——它们即使全 A 释放也恒读 1，
                // 用裸 `b_filtered == 0` 会让每一行都走满 501 拍超时（W4）。
                S_RELEASE: begin
                    drive_en    <= 1'b0;
                    drive_level <= 1'b1;
                    if ((b_filtered & ~stuck_low_mask) == {N_CH{1'b0}}) begin
                        if (stable_cnt >= GUARD_STABLE - 1)
                            state <= S_NEXT;
                        else
                            stable_cnt <= stable_cnt + 16'd1;
                        wait_cnt <= 16'd0;
                    end else begin
                        stable_cnt <= 16'd0;
                        if (wait_cnt >= GUARD_TIMEOUT) begin
                            release_timeout <= 1'b1;
                            state           <= S_NEXT;
                        end else begin
                            wait_cnt <= wait_cnt + 16'd1;
                        end
                    end
                end

                S_NEXT: begin
                    if (row >= N_LAST) begin
                        state <= S_DONE;
                    end else begin
                        row      <= row + 4'd1;
                        wait_cnt <= 16'd0;
                        state    <= S_DRIVE;
                    end
                end

                S_DONE: begin
                    drive_en    <= 1'b0;
                    drive_level <= 1'b1;
                    busy        <= 1'b0;
                    for (i = 0; i < N_CH; i = i + 1) begin
                        open_flags[i] <= ~(|conn_matrix[i*N_CH +: N_CH]);
                    end
                    done_pulse <= 1'b1;
                    state      <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
