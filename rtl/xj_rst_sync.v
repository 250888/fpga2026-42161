//==============================================================================
// Reset synchronizer（V1.9 §4.2 P030 原文实现）
//
// EGO1 S6 / FPGA_RESET(P15) 4.7 kΩ 上拉到 3.3 V、按下接地 → 板级低有效 rst_n。
// 不能把外部 rst_n 直接当作各模块的异步复位释放信号：
//   外部按下 → 立即进入复位（异步拉低）
//   释放     → 只在 sys_clk 边沿同步解除
// 核心模块统一使用内部高有效 rst。
// FPGA 尚未配置时，A 端安全由 LVC07 输入 10 kΩ 外部上拉保证。
//==============================================================================

module xj_rst_sync (
    input  wire clk,
    input  wire rst_n,
    output wire rst
);

    (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO" *) reg [1:0] rst_pipe = 2'b00;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            rst_pipe <= 2'b00;
        else
            rst_pipe <= {rst_pipe[0], 1'b1};
    end

    assign rst = ~rst_pipe[1];

endmodule
