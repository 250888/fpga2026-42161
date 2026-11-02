`timescale 1ns / 1ps

//==============================================================================
// 4 路自回环拓扑扫描 + 极性归属交叉检查
//
// DUT = xunji_top_loopback（无 LVC14 的纯数字回环，内部 b_conn = ~b_sync）
// 参照 = xunji_top_hw（生产 Top，内部 b_conn = b_sync），喂同一份 b_raw
// 断言：两个 wrapper 的 b_conn 恒为互补，且 hw 顶层自身不反相。
//       —— 这条正是 V1.9 P048/P049「反相只许在 loopback wrapper」的可执行化。
//==============================================================================
module tb_xunji_loopback;

`ifdef DUMP_VCD
    initial begin
        $dumpfile("build/tb_xunji_loopback.vcd");
        $dumpvars(0, tb_xunji_loopback);
    end
`endif

    reg         clk = 0;
    reg         rst_n = 0;
    reg  [7:0]  sw = 8'h00;
    reg  [4:0]  btn = 5'h00;

    wire [15:0] a_ctrl_n;
    reg  [15:0] b_raw;

    wire [15:0] led;
    wire        uart_tx;
    wire        uart_rx = 1'b1;

    xunji_top_loopback #(
        .N_CH(4),
        .CLK_FREQ_HZ(100_000_000),
        .BAUD_RATE(115_200),
        .SCAN_SETTLE(50),
        .GLITCH_CYCLES(5)
    ) dut (
        .sys_clk(clk),
        .rst_n(rst_n),
        .a_ctrl_n(a_ctrl_n),
        .b_raw(b_raw),
        .led(led),
        .uart_tx(uart_tx),
        .uart_rx(uart_rx),
        .sw(sw),
        .btn(btn)
    );

    // 生产顶层参照实例：同一 b_raw / 同一 rst_n，但 btn/sw 绑 0（不启动扫描）
    wire [15:0] a_ctrl_n_hw;
    wire [15:0] led_hw;
    wire        uart_tx_hw;
    xunji_top_hw #(
        .N_CH(4),
        .CLK_FREQ_HZ(100_000_000),
        .BAUD_RATE(115_200),
        .SCAN_SETTLE(50),
        .GLITCH_CYCLES(5)
    ) hw_dut (
        .sys_clk(clk),
        .rst_n(rst_n),
        .a_ctrl_n(a_ctrl_n_hw),
        .b_raw(b_raw),
        .led(led_hw),
        .uart_tx(uart_tx_hw),
        .uart_rx(uart_rx),
        .sw(8'h00),
        .btn(5'h00)
    );

    always #5 clk = ~clk;

    // 回环模型（无 LVC14）：默认线束电平全 1 = 开路；A 被拉低则对应 B 被拉到 0
    always @(*) begin
        b_raw = 16'hFFFF;
        if (a_ctrl_n[0] === 1'b0) b_raw[2] = 1'b0;
        if (a_ctrl_n[1] === 1'b0) b_raw[0] = 1'b0;
        if (a_ctrl_n[2] === 1'b0) b_raw[3] = 1'b0;
        if (a_ctrl_n[3] === 1'b0) b_raw[1] = 1'b0;
    end

    localparam [15:0] EXPECT = {4'b0010, 4'b1000, 4'b0001, 4'b0100};

    integer timeout;
    reg done_seen;
    reg mismatch;

    task check_polarity;
        begin
            if (hw_dut.b_conn !== ~dut.b_conn) begin
                $display("FAIL polarity: hw.b_conn=%b lb.b_conn=%b (应互补)",
                         hw_dut.b_conn, dut.b_conn);
                $fatal;
            end
            if (hw_dut.b_conn !== hw_dut.b_sync) begin
                $display("FAIL polarity: 生产顶层 b_conn 被反相 hw.b_conn=%b b_sync=%b",
                         hw_dut.b_conn, hw_dut.b_sync);
                $fatal;
            end
            if (dut.b_conn !== ~dut.b_sync) begin
                $display("FAIL polarity: loopback 顶层必须 b_conn = ~b_sync");
                $fatal;
            end
        end
    endtask

    initial begin
        $display("=== tb_xunji_loopback start ===");
        rst_n = 0;
        repeat (20) @(posedge clk);
        rst_n = 1;
        repeat (20) @(posedge clk);
        check_polarity;

        btn[0] = 1'b1;
        repeat (10) @(posedge clk);
        btn[0] = 1'b0;

        $display("t=%0t after start: busy=%b st=%0d a=%h",
                 $time, dut.u_core.scan_busy, dut.u_core.u_scan.state, a_ctrl_n);

        done_seen = 0;
        timeout = 0;
        while (timeout < 30000 && !done_seen) begin
            @(posedge clk);
            timeout = timeout + 1;
            if (dut.u_core.scan_done_pulse === 1'b1)
                done_seen = 1;
            if (timeout % 2000 == 0)
                $display("t=%0t to=%0d busy=%b st=%0d idx=%0d a=%h bf=%h",
                         $time, timeout, dut.u_core.scan_busy, dut.u_core.u_scan.state,
                         dut.u_core.scan_idx, a_ctrl_n, dut.u_core.b_filt);
        end

        if (!done_seen) begin
            $display("FAIL timeout busy=%b st=%0d",
                     dut.u_core.scan_busy, dut.u_core.u_scan.state);
            $fatal;
        end

        @(posedge clk);
        check_polarity;
        $display("conn_matrix = %b", dut.u_core.conn_matrix);
        $display("open_flags  = %b", dut.u_core.open_flags);
        $display("expected    = %b", EXPECT);
        if (dut.u_core.conn_matrix === EXPECT && dut.u_core.open_flags === 4'b0000) begin
            $display("PASS");
            mismatch = 1'b0;
        end else begin
            $display("FAIL mismatch");
            mismatch = 1'b1;
        end
        repeat (5) @(posedge clk);
        if (mismatch)
            $fatal(1, "TOPOLOGY MISMATCH");
        else
            $finish;
    end

endmodule
