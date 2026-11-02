//==============================================================================
// 瞬迹 - 核心（由 xunji_top_hw / xunji_top_loopback 共享）
// Board: EGO1 (Artix-7 XC7A35T-1CSG324C) @ 100 MHz
//
// 端口语义（V1.9 §4.2、P048–P050）：
//   sys_clk    100 MHz 单时钟（节拍一律 clock-enable，不派生新时钟）
//   rst        高有效，已由 rtl/xj_rst_sync 做「异步拉低、同步释放」
//   a_ctrl_n   A 端激励：0 = LVC07 拉低线束，1 = 释放；复位/默认全 1
//   b_conn     极性归一化后的 B 端：1 = 导通，0 = 开路/失连
//
// 铁律：本模块只使用 b_conn，不读取 b_raw，也不做任何极性反相——
//       反相只允许出现在 xunji_top_loopback（V1.9 P048/P049）。
//
// External:
//   a_ctrl_n[15:0] -> LVC07 open-drain buffer inputs（0 = 拉低线束）
//   b_conn[15:0]   <- 来自 wrapper（hw: b_sync；loopback: ~b_sync）
//   uart_tx        -> 板载 USB-UART（FPGA 视角 T4）
//
// Phase-1 不引出独立 OE 脚；LVC07 OE 在前端板上硬接高（开漏 1 即高阻）。
//==============================================================================

module xunji_core #(
    parameter N_CH          = 16,
    parameter CLK_FREQ_HZ   = 100_000_000,
    parameter BAUD_RATE     = 115_200,
    parameter SCAN_SETTLE   = 500,
    parameter GLITCH_CYCLES = 50
)(
    input  wire        sys_clk,
    input  wire        rst,

    output wire [15:0] a_ctrl_n,         // A drive (0 = pull low)
    input  wire [15:0] b_conn,           // 已同步、已归一化的连接状态

    output wire [15:0] led,
    output wire        uart_tx,
    input  wire        uart_rx,
    input  wire [7:0]  sw,
    input  wire [4:0]  btn
);

    wire [63:0] timestamp;
    timestamp_counter u_ts (
        .clk(sys_clk), .rst(rst), .en(1'b1), .timestamp(timestamp)
    );

    wire [15:0] b_filt;
    glitch_filter #(.WIDTH(16), .FILTER_CYC(GLITCH_CYCLES)) u_gf (
        .clk(sys_clk), .rst(rst), .d_in(b_conn), .d_out(b_filt)
    );

    wire                 scan_busy;
    wire                 scan_done_pulse;
    wire [3:0]           scan_idx;
    wire                 scan_drive_en;
    wire                 scan_drive_level;
    wire [N_CH*N_CH-1:0] conn_matrix;
    wire [N_CH-1:0]      open_flags;
    wire [N_CH-1:0]      stuck_low_mask;
    wire                 idle_ok;
    wire                 release_timeout;

    // ---- 机械输入两级同步（2026-10-24 审查 W5）----
    // btn/sw 与 sys_clk 异步：直接进 FSM 或做单拍边沿检测有亚稳态/抖动风险。
    wire [4:0] btn_s;
    wire [7:0] sw_s;
    input_sync #(.WIDTH(5)) u_sync_btn (
        .clk(sys_clk), .rst(rst), .d_in(btn), .d_out(btn_s)
    );
    input_sync #(.WIDTH(8)) u_sync_sw (
        .clk(sys_clk), .rst(rst), .d_in(sw), .d_out(sw_s)
    );

    // 电平启动：SW0 常开时扫描会连续重跑（每轮 ≈112 µs，见 topology_scanner
    // S_IDLE → start=1 立即重启）。因此 uart_packet_tx 必须对 matrix 做快照
    // （2026-10-24 审查 B1），否则 48B 帧的 4.17 ms 里矩阵会被改写约 37 次。
    wire scan_start = btn_s[0] | sw_s[0];

    topology_scanner #(
        .N_CH(N_CH),
        .SETTLE(SCAN_SETTLE)
    ) u_scan (
        .clk(sys_clk),
        .rst(rst),
        .start(scan_start),
        .b_filtered(b_filt[N_CH-1:0]),
        .busy(scan_busy),
        .done_pulse(scan_done_pulse),
        .scan_idx(scan_idx),
        .drive_en(scan_drive_en),
        .drive_level(scan_drive_level),
        .conn_matrix(conn_matrix),
        .open_flags(open_flags),
        .stuck_low_mask(stuck_low_mask),
        .idle_ok(idle_ok),
        .release_timeout(release_timeout)
    );

    // ---- 最近一次「完整扫描」的快照（2026-10-24 审查 A2）----
    // SW0 常开时扫描连续重跑，若用 ~scan_busy 互锁 BTN1，学习窗口只有每轮 1 个
    // 时钟（≈112 µs 里 10 ns），等于永远学不到。这里在 done_pulse 拍锁存整轮
    // 矩阵与 idle_ok，LEARN 无论何时按都基于「最近一次完整扫描」。
    reg [N_CH*N_CH-1:0] last_matrix;
    reg                 last_idle_ok;
    always @(posedge sys_clk) begin
        if (rst) begin
            last_matrix  <= {N_CH*N_CH{1'b0}};
            last_idle_ok <= 1'b0;
        end else if (scan_done_pulse) begin
            last_matrix  <= conn_matrix;
            last_idle_ok <= idle_ok;
        end
    end

    drive_controller #(.N_CH(N_CH)) u_drv (
        .clk(sys_clk),
        .rst(rst),
        .scan_idx(scan_idx),
        .drive_en(scan_drive_en),
        .drive_level(scan_drive_level),
        .a_ctrl_n(a_ctrl_n)
    );

    wire       tx_start;
    wire [7:0] tx_data;
    wire       tx_busy;

    uart_tx #(.CLK_FREQ(CLK_FREQ_HZ), .BAUD(BAUD_RATE)) u_uart (
        .clk(sys_clk),
        .rst(rst),
        .tx_start(tx_start),
        .tx_data(tx_data),
        .tx_busy(tx_busy),
        .tx(uart_tx)
    );

    // ---- LEARN：btn[1] 上升沿触发（按住不重复学习），V1.9 P059 ----
    reg btn1_q;
    always @(posedge sys_clk) begin
        if (rst)
            btn1_q <= 1'b0;
        else
            btn1_q <= btn_s[1];
    end
    // 用同步后的按键 + 最近一次完整扫描的矩阵（A2），不再用 ~scan_busy 互锁
    wire learn_pulse = btn_s[1] & ~btn1_q;

    wire [N_CH*N_CH-1:0] m_ref;
    wire                 reference_valid;
    wire                 learn_accept, learn_reject;

    learn_gate #(.N_CH(N_CH)) u_learn (
        .clk(sys_clk),
        .rst(rst),
        .learn(learn_pulse),
        .idle_ok(last_idle_ok),
        .m_scan(last_matrix),
        .reference_valid(reference_valid),
        .m_ref(m_ref),
        .learn_accept_pulse(learn_accept),
        .learn_reject_pulse(learn_reject)
    );

    // ---- Golden Map 比较：始终比较「本轮扫描矩阵 vs 参考矩阵」，V1.9 P060 ----
    wire [N_CH*N_CH-1:0] cmp_missing, cmp_extra;
    wire [N_CH-1:0]      cmp_a_eq1, cmp_a_gt1, cmp_a_zero;
    wire [N_CH-1:0]      cmp_b_eq1, cmp_b_gt1, cmp_b_zero;
    wire                 cmp_all_one;
    wire [2:0]           cmp_cls;

    golden_compare #(.N_CH(N_CH)) u_cmp (
        .m_ref(m_ref),
        .m_test(conn_matrix),
        .missing(cmp_missing),
        .extra(cmp_extra),
        .a_eq1(cmp_a_eq1),
        .a_gt1(cmp_a_gt1),
        .a_zero(cmp_a_zero),
        .b_eq1(cmp_b_eq1),
        .b_gt1(cmp_b_gt1),
        .b_zero(cmp_b_zero),
        .all_one_test(cmp_all_one),
        .cls(cmp_cls)
    );

    // 未学习（reference_valid=0）时上报 NO_REF，绝不把「没学参考」伪装成 PASS
    wire [2:0] frame_cls = reference_valid ? cmp_cls : 3'd5;

    uart_packet_tx #(.N_CH(N_CH)) u_pkt (
        .clk(sys_clk),
        .rst(rst),
        .trigger(scan_done_pulse),
        .matrix(conn_matrix),
        .open_flags(open_flags),
        .stuck_low_mask(stuck_low_mask),
        .cls(frame_cls),
        .timestamp(timestamp),
        .tx_start(tx_start),
        .tx_data(tx_data),
        .tx_busy(tx_busy)
    );

    // LED 语义（暂定段，V1.9 未冻结板载 I/O）：
    //   [0] 扫描中  [1] 扫描完成脉冲  [2] UART 忙  [3] IDLE_CHECK 通过
    //   [4] 释放超时  [5] 有通道卡低  [6] 任一 A 行无连接  [7] 已学习参考
    //   [15:8] 时间戳高位（千 Hz 级方波，常亮不闪）
    assign led[0]    = scan_busy;
    assign led[1]    = scan_done_pulse;
    assign led[2]    = tx_busy;
    assign led[3]    = idle_ok;
    assign led[4]    = release_timeout;
    assign led[5]    = |stuck_low_mask;
    assign led[6]    = |open_flags;
    assign led[7]    = reference_valid;
    assign led[15:8] = timestamp[15:8];

endmodule
