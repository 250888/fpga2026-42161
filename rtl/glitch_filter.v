//==============================================================================
// Digital glitch filter
// Output follows input only if stable for FILTER_CYC consecutive cycles.
// For static topology scan this debounces slow edges and rejects short noise.
//==============================================================================

module glitch_filter #(
    parameter WIDTH      = 16,
    parameter FILTER_CYC = 50
)(
    input  wire             clk,
    input  wire             rst,
    input  wire [WIDTH-1:0] d_in,
    output reg  [WIDTH-1:0] d_out
);

    reg [WIDTH-1:0] candidate;
    reg [15:0]      counter [0:WIDTH-1];

    integer i;

    always @(posedge clk) begin
        if (rst) begin
            d_out    <= {WIDTH{1'b0}};
            candidate<= {WIDTH{1'b0}};
            for (i = 0; i < WIDTH; i = i + 1)
                counter[i] <= 16'd0;
        end else begin
            for (i = 0; i < WIDTH; i = i + 1) begin
                if (d_in[i] == candidate[i]) begin
                    if (counter[i] < FILTER_CYC)
                        counter[i] <= counter[i] + 16'd1;
                    else
                        d_out[i] <= candidate[i];
                end else begin
                    candidate[i] <= d_in[i];
                    counter[i]   <= 16'd0;
                end
            end
        end
    end

endmodule
