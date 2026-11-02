//==============================================================================
// 瞬迹 - 生产顶层（真实前端：LVC07 + LVC14 + 上拉）
//
// V1.9 P048：真实 LVC07+LVC14 前端本身已满足「导通=1、开路=0」：
//   A 拉低 → LVC07 把线束拉低 → LVC14 输入低 → 输出高 → b_raw=1 → b_conn=1（导通）
//   线束开路 → B 由 Rp 上拉 → LVC14 输出低 → b_raw=0 → b_conn=0（开路）
// 因此本顶层固定 b_conn = b_sync，**不做任何反相**。
//
// 极性处理只允许出现在这里和 xunji_top_loopback 两处之一；核心只认 b_conn。
//==============================================================================

module xunji_top_hw #(
    parameter N_CH          = 16,
    parameter CLK_FREQ_HZ   = 100_000_000,
    parameter BAUD_RATE     = 115_200,
    parameter SCAN_SETTLE   = 500,
    parameter GLITCH_CYCLES = 50
)(
    input  wire        sys_clk,          // 100 MHz（P17）
    input  wire        rst_n,            // 低有效复位（P15）

    output wire [15:0] a_ctrl_n,         // J5-1..16  → LVC07（0=拉低，1=释放）
    input  wire [15:0] b_raw,            // J5-17..32 ← LVC14 输出

    output wire [15:0] led,
    output wire        uart_tx,
    input  wire        uart_rx,
    input  wire [7:0]  sw,
    input  wire [4:0]  btn
);

    wire rst;
    xj_rst_sync u_rst (
        .clk(sys_clk), .rst_n(rst_n), .rst(rst)
    );

    // b_raw 与 sys_clk 异步：两级同步器后才进入逻辑（V1.9 §4.2 P029）
    wire [15:0] b_sync;
    input_sync #(.WIDTH(16)) u_sync (
        .clk(sys_clk), .rst(rst), .d_in(b_raw), .d_out(b_sync)
    );

    wire [15:0] b_conn;
    assign b_conn = b_sync;

    xunji_core #(
        .N_CH(N_CH),
        .CLK_FREQ_HZ(CLK_FREQ_HZ),
        .BAUD_RATE(BAUD_RATE),
        .SCAN_SETTLE(SCAN_SETTLE),
        .GLITCH_CYCLES(GLITCH_CYCLES)
    ) u_core (
        .sys_clk(sys_clk),
        .rst(rst),
        .a_ctrl_n(a_ctrl_n),
        .b_conn(b_conn),
        .led(led),
        .uart_tx(uart_tx),
        .uart_rx(uart_rx),
        .sw(sw),
        .btn(btn)
    );

endmodule
