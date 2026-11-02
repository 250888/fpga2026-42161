//==============================================================================
// 2-flop synchronizer for asynchronous external inputs（V1.9 §4.2 P029/P030）
//
// - b_raw 来自线束前端，与 100 MHz sys_clk 异步，必须先过两级同步再进逻辑。
// - 同步寄存器必须标 ASYNC_REG=TRUE、SHREG_EXTRACT=NO（禁止被吸收成 SRL）。
// - 16 路 b_raw 是 16 个彼此独立的异步事件通道，不当作需要同拍一致性的总线。
// - 时序上只允许把 b_raw → 第一级 D 端视为异步路径；第一级→第二级不得 false-path。
//==============================================================================

module input_sync #(
    parameter WIDTH = 16
)(
    input  wire             clk,
    input  wire             rst,
    input  wire [WIDTH-1:0] d_in,
    output wire [WIDTH-1:0] d_out
);

    (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO" *) reg [WIDTH-1:0] stage1;
    (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO" *) reg [WIDTH-1:0] stage2;

    always @(posedge clk) begin
        if (rst) begin
            stage1 <= {WIDTH{1'b0}};
            stage2 <= {WIDTH{1'b0}};
        end else begin
            stage1 <= d_in;
            stage2 <= stage1;
        end
    end

    assign d_out = stage2;

endmodule
