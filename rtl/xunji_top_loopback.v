//==============================================================================
// 瞬迹 - 自回环开发顶层（无 LVC14 的纯数字验证）
//
// V1.9 P049：自回环开发不要把调试极性参数带进最终硬件 Top。
//   无 LVC14 时，回环模型直接给的是线束电平：导通（被拉低）→ b_raw=0，
//   开路/上拉 → b_raw=1；与真实前端「导通=1」正好相反，故在此**反相一次**：
//       b_conn = ~b_sync
//
// 铁律：整个工程的极性反相只允许出现在这一行；核心与 hw 顶层都不许反相。
//      调试完成后烧板必须用 xunji_top_hw，不得把本 wrapper 当生产 Top。
//==============================================================================

module xunji_top_loopback #(
    parameter N_CH          = 16,
    parameter CLK_FREQ_HZ   = 100_000_000,
    parameter BAUD_RATE     = 115_200,
    parameter SCAN_SETTLE   = 500,
    parameter GLITCH_CYCLES = 50
)(
    input  wire        sys_clk,          // 100 MHz（P17）
    input  wire        rst_n,            // 低有效复位（P15）

    output wire [15:0] a_ctrl_n,         // J5-1..16  → LVC07（0=拉低，1=释放）
    input  wire [15:0] b_raw,            // J5-17..32 ← 回环线（无 LVC14）

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

    // ★ 全工程唯一的极性反相点 ★
    wire [15:0] b_conn;
    assign b_conn = ~b_sync;

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
