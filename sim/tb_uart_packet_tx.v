`timescale 1ns / 1ps

//==============================================================================
// uart_packet_tx + uart_tx 线级联调 TB — V1.9 §17 帧结构 + 16 路扩展 payload
//
// 帧结构（§17 冻结）：55 AA | Ver | Type | Len(2,LE) | Seq(2,LE) | Payload | CRC(2,LE)
// Payload（2026-10-22 扩展，specs/2026-10-22-topology-frame-16ch.md）：
//   MAT(N*N/8) + open(2) + stuck(2) + cls(1) + ts0(1)
//   N_CH=4 → 8B payload / 18B 帧；N_CH=16 → 38B payload / 48B 帧。
//
// TB 对 tx 线做 8N1 逐位采样解码（数据位中点 + 停止位中点必须为高），
// 黄金帧由 protocol.build_frame 生成，tests/test_matrix_payload.py 双向锁定：
//   seq0 = 55AA 0101 0800 0000 0428 0000 0000 00BE E338
//   seq1 = 55AA 0101 0800 0100 0428 0000 0000 00BE A657
// 核对：结构字段 → 逐字节黄金比对 → TB 内独立串行注入式 CRC-16 复算。
//==============================================================================
module tb_uart_packet_tx;

    localparam integer FRAME_LEN = 18;      // 4 路：2+14+2
    localparam integer BODY_LEN  = 14;      // Ver..Payload
    localparam [8*FRAME_LEN-1:0] GOLDEN0 =
        144'h55AA01010800000004280000000000BEE338;
    localparam [8*FRAME_LEN-1:0] GOLDEN1 =
        144'h55AA01010800010004280000000000BEA657;
    localparam real BIT_NS = 8680.555556;   // 1e9 / 115200

`ifdef DUMP_VCD
    initial begin
        $dumpfile("build/tb_uart_packet_tx.vcd");
        $dumpvars(0, tb_uart_packet_tx);
    end
`endif

    reg         clk = 0;
    reg         rst = 1;
    reg         trigger = 0;
    reg  [15:0] matrix = 16'h2804;
    reg  [3:0]  open_flags = 4'h0;
    reg  [3:0]  stuck_low_mask = 4'h0;
    reg  [2:0]  cls = 3'd0;
    reg  [63:0] timestamp = 64'hDEADBEEFCAFEBABE;

    wire        tx_start;
    wire [7:0]  tx_data;
    wire        tx_busy;
    wire        tx_line;

    always #5 clk = ~clk;

    uart_packet_tx #(.N_CH(4)) u_pkt (
        .clk(clk),
        .rst(rst),
        .trigger(trigger),
        .matrix(matrix),
        .open_flags(open_flags),
        .stuck_low_mask(stuck_low_mask),
        .cls(cls),
        .timestamp(timestamp),
        .tx_start(tx_start),
        .tx_data(tx_data),
        .tx_busy(tx_busy)
    );

    uart_tx #(.CLK_FREQ(100_000_000), .BAUD(115_200)) u_uart (
        .clk(clk),
        .rst(rst),
        .tx_start(tx_start),
        .tx_data(tx_data),
        .tx_busy(tx_busy),
        .tx(tx_line)
    );

    //---- 8N1 线级采样接收器 ----
    reg [7:0] rx [0:47];
    integer   recv_n = 0;

    task uart_recv;
        output [7:0] b;
        integer i;
        begin
            @(negedge tx_line);
            #(BIT_NS * 1.5);
            for (i = 0; i < 8; i = i + 1) begin
                b[i] = tx_line;
                #(BIT_NS);
            end
            if (tx_line !== 1'b1) begin
                $display("FAIL framing: byte[%0d] 停止位中点采到低电平", recv_n);
                $fatal;
            end
            rx[recv_n] = b;
            recv_n = recv_n + 1;
        end
    endtask

    //---- 独立 CRC-16/CCITT-FALSE（串行注入式） ----
    function [15:0] crc16_ref;
        input [15:0] crc_in;
        input [7:0]  data;
        integer k;
        reg [15:0] c;
        reg fb;
        begin
            c = crc_in;
            for (k = 7; k >= 0; k = k - 1) begin
                fb = c[15] ^ data[k];
                c = c << 1;
                if (fb)
                    c = c ^ 16'h1021;
            end
            crc16_ref = c;
        end
    endfunction

    task check_frame;
        input integer  base;
        input [8*FRAME_LEN-1:0] golden;
        input [8*8-1:0] tag;
        integer i;
        integer j;
        reg [7:0] g;
        reg [7:0] b;
        reg [15:0] crc;
        begin
            if (rx[base] !== 8'h55 || rx[base+1] !== 8'hAA) begin
                $display("FAIL %0s SOF got=%02h%02h", tag, rx[base], rx[base+1]);
                $fatal;
            end
            if (rx[base+2] !== 8'h01 || rx[base+3] !== 8'h01) begin
                $display("FAIL %0s Ver/Type got=%02h/%02h", tag, rx[base+2], rx[base+3]);
                $fatal;
            end
            // Len = payload 8 字节（小端）
            if (rx[base+4] !== 8'h08 || rx[base+5] !== 8'h00) begin
                $display("FAIL %0s Length(LE) got=%02h%02h", tag, rx[base+4], rx[base+5]);
                $fatal;
            end
            // payload：matrix(04 28) open(00 00) stuck(00 00) cls(00) ts0(BE)
            if (rx[base+8] !== 8'h04 || rx[base+9] !== 8'h28 ||
                rx[base+10] !== 8'h00 || rx[base+11] !== 8'h00 ||
                rx[base+12] !== 8'h00 || rx[base+13] !== 8'h00 ||
                rx[base+14] !== 8'h00 || rx[base+15] !== 8'hBE) begin
                $display("FAIL %0s payload got=%02h%02h%02h%02h%02h%02h%02h%02h", tag,
                         rx[base+8], rx[base+9], rx[base+10], rx[base+11],
                         rx[base+12], rx[base+13], rx[base+14], rx[base+15]);
                $fatal;
            end
            for (i = 0; i < FRAME_LEN; i = i + 1) begin
                j = base + i;
                g = golden[8*FRAME_LEN - 1 - 8*i -: 8];
                if (rx[j] !== g) begin
                    $display("FAIL %0s byte[%0d] got=%02h want=%02h", tag, i, rx[j], g);
                    $fatal;
                end
            end
            crc = 16'hFFFF;
            for (i = 2; i <= BODY_LEN + 1; i = i + 1) begin
                b = rx[base+i];
                crc = crc16_ref(crc, b);
            end
            if (rx[base+BODY_LEN+2] !== crc[7:0] ||
                rx[base+BODY_LEN+3] !== crc[15:8]) begin
                $display("FAIL %0s CRC got=%02h%02h want=%02h%02h", tag,
                         rx[base+BODY_LEN+2], rx[base+BODY_LEN+3],
                         crc[7:0], crc[15:8]);
                $fatal;
            end
        end
    endtask

    // 看门狗：两帧 36 字节 × 10 bit × 8.68 µs ≈ 3.2 ms，放宽到 12 ms
    initial begin
        #12_000_000;
        $display("FAIL timeout recv_n=%0d", recv_n);
        $fatal;
    end

    integer k;
    reg [7:0] rb;

    initial begin
        repeat (4) @(posedge clk);
        rst <= 1'b0;
        repeat (2) @(posedge clk);

        trigger <= 1'b1;
        @(posedge clk);
        trigger <= 1'b0;
        for (k = 0; k < FRAME_LEN; k = k + 1)
            uart_recv(rb);
        check_frame(0, GOLDEN0, "frame0");

        wait (u_pkt.state == 3'd0);
        trigger <= 1'b1;
        @(posedge clk);
        trigger <= 1'b0;
        for (k = 0; k < FRAME_LEN; k = k + 1)
            uart_recv(rb);
        check_frame(FRAME_LEN, GOLDEN1, "frame1");

        $display("PASS");
        $finish;
    end

endmodule
