//==============================================================================
// Global 64-bit hardware timestamp
// Ticks once per clk (100 MHz -> 10 ns resolution)
//==============================================================================

module timestamp_counter (
    input  wire        clk,
    input  wire        rst,
    input  wire        en,
    output reg  [63:0] timestamp
);

    always @(posedge clk) begin
        if (rst)
            timestamp <= 64'd0;
        else if (en)
            timestamp <= timestamp + 64'd1;
    end

endmodule
