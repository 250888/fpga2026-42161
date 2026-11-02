//==============================================================================
// Drive controller — A 端开漏式激励（V1.9 §4.1 语义）
// a_ctrl_n[i] = 0 : 拉低线束（LVC07 输入低）
// a_ctrl_n[i] = 1 : 释放（LVC07 开漏 = 高阻）
//
// 红线（AGENTS.md §6.2）：复位态与空闲/安全态一律 16'hFFFF（全释放），
// 任何情况下不得在复位期间把 A 端拉低。
//==============================================================================

module drive_controller #(
    parameter N_CH = 4
)(
    input  wire        clk,
    input  wire        rst,
    input  wire [3:0]  scan_idx,
    input  wire        drive_en,
    input  wire        drive_level,
    output reg  [15:0] a_ctrl_n
);

    integer i;

    always @(posedge clk) begin
        if (rst) begin
            a_ctrl_n <= 16'hFFFF;
        end else if (drive_en && (scan_idx < N_CH)) begin
            for (i = 0; i < 16; i = i + 1) begin
                if (i == scan_idx)
                    a_ctrl_n[i] <= drive_level;
                else
                    a_ctrl_n[i] <= 1'b1;
            end
        end else begin
            a_ctrl_n <= 16'hFFFF;
        end
    end

endmodule
