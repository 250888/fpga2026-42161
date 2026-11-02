//==============================================================================
// UART transmitter (8N1)
// Bit timing: DIV = CLK_FREQ/BAUD cycles per bit
//==============================================================================

module uart_tx #(
    parameter CLK_FREQ = 100_000_000,
    parameter BAUD     = 115_200
)(
    input  wire       clk,
    input  wire       rst,
    input  wire       tx_start,
    input  wire [7:0] tx_data,
    output reg        tx_busy,
    output reg        tx
);

    localparam integer DIV = CLK_FREQ / BAUD;

    reg [15:0] baud_cnt;
    reg [3:0]  bit_pos;   // 0 = start, 1..8 = data[0..7], 9 = stop, 10 = stop 完结
    reg [7:0]  data_r;

    always @(posedge clk) begin
        if (rst) begin
            tx       <= 1'b1;
            tx_busy  <= 1'b0;
            baud_cnt <= 16'd0;
            bit_pos  <= 4'd0;
            data_r   <= 8'h00;
        end else if (!tx_busy) begin
            if (tx_start) begin
                data_r   <= tx_data;
                bit_pos  <= 4'd0;
                baud_cnt <= 16'd0;
                tx_busy  <= 1'b1;
                tx       <= 1'b0;                 // start bit
            end else begin
                tx <= 1'b1;
            end
        end else begin
            if (baud_cnt == DIV - 1) begin
                baud_cnt <= 16'd0;
                bit_pos  <= bit_pos + 4'd1;
                case (bit_pos + 4'd1)
                    4'd1: tx <= data_r[0];
                    4'd2: tx <= data_r[1];
                    4'd3: tx <= data_r[2];
                    4'd4: tx <= data_r[3];
                    4'd5: tx <= data_r[4];
                    4'd6: tx <= data_r[5];
                    4'd7: tx <= data_r[6];
                    4'd8: tx <= data_r[7];
                    // 停止位开始：busy 必须继续覆盖完整 1 个 bit 时间。
                    // 若在此清 busy，上层在停止位起始后 3 拍即可发下一字节，
                    // 停止位被截成 30ns → 标准 8N1 接收机 framing error（任务5b 修复）。
                    4'd9: tx <= 1'b1;
                    4'd10: begin                 // 停止位满 1 bit，帧间空闲开始
                        tx      <= 1'b1;
                        tx_busy <= 1'b0;
                        bit_pos <= 4'd0;
                    end
                    default: tx <= 1'b1;
                endcase
            end else begin
                baud_cnt <= baud_cnt + 16'd1;
            end
        end
    end

endmodule
