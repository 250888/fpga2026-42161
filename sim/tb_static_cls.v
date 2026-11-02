`timescale 1ns / 1ps

//==============================================================================
// 静态核心集成 TB — LEARN + Golden Map 分类进帧（V1.9 P059/P060）
//
// DUT = xunji_top_loopback（N_CH=4，快速参数），线束模型可切换故障模式：
//   mode0 正常交叉（a0→b2,a1→b0,a2→b3,a3→b1）
//   mode1 双射换位（a0→b0,a1→b2）          → 期望 MISWIRE
//   mode2 a0 开路                          → 期望 OPEN
//   mode3 a0 同时接 b2/b3（degA>1）        → 期望 BRIDGE
//
// 流程：扫描 → 按 btn[1]（LEARN，上升沿）→ 参考矩阵应被接受 → 切模式重扫 → 检查分类。
// 分类编码：0 PASS / 1 OPEN / 2 MISWIRE / 3 BRIDGE / 4 ANOMALY / 5 NO_REF。
//==============================================================================
module tb_static_cls;

`ifdef DUMP_VCD
    initial begin
        $dumpfile("build/tb_static_cls.vcd");
        $dumpvars(0, tb_static_cls);
    end
`endif

    localparam [15:0] EXP_CROSS = 16'b0010_1000_0001_0100;  // row3..row0
    localparam [2:0]  C_PASS = 3'd0, C_OPEN = 3'd1, C_MISWIRE = 3'd2,
                      C_BRIDGE = 3'd3;

    reg         clk = 0;
    reg         rst_n = 0;
    reg  [7:0]  sw = 8'h00;
    reg  [4:0]  btn = 5'h00;
    reg  [1:0]  mode = 2'd0;

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

    always #5 clk = ~clk;

    // 线束模型（loopback：A 被拉低 → 对应 B 的 b_raw=0 → b_conn=1）
    always @(*) begin
        b_raw = 16'hFFFF;
        case (mode)
            2'd0: begin
                if (a_ctrl_n[0] === 1'b0) b_raw[2] = 1'b0;
                if (a_ctrl_n[1] === 1'b0) b_raw[0] = 1'b0;
                if (a_ctrl_n[2] === 1'b0) b_raw[3] = 1'b0;
                if (a_ctrl_n[3] === 1'b0) b_raw[1] = 1'b0;
            end
            2'd1: begin   // 双射换位：a0→b0、a1→b2
                if (a_ctrl_n[0] === 1'b0) b_raw[0] = 1'b0;
                if (a_ctrl_n[1] === 1'b0) b_raw[2] = 1'b0;
                if (a_ctrl_n[2] === 1'b0) b_raw[3] = 1'b0;
                if (a_ctrl_n[3] === 1'b0) b_raw[1] = 1'b0;
            end
            2'd2: begin   // a0 开路
                if (a_ctrl_n[1] === 1'b0) b_raw[0] = 1'b0;
                if (a_ctrl_n[2] === 1'b0) b_raw[3] = 1'b0;
                if (a_ctrl_n[3] === 1'b0) b_raw[1] = 1'b0;
            end
            2'd3: begin   // a0 同时接 b2/b3
                if (a_ctrl_n[0] === 1'b0) begin
                    b_raw[2] = 1'b0;
                    b_raw[3] = 1'b0;
                end
                if (a_ctrl_n[1] === 1'b0) b_raw[0] = 1'b0;
                if (a_ctrl_n[2] === 1'b0) b_raw[3] = 1'b0;
                if (a_ctrl_n[3] === 1'b0) b_raw[1] = 1'b0;
            end
        endcase
    end

    integer fails;
    integer timeout;

    task scan_once;
        begin
            btn[0] = 1'b1;
            repeat (3) @(posedge clk);
            btn[0] = 1'b0;
            timeout = 0;
            while (dut.u_core.scan_done_pulse !== 1'b1 && timeout < 20000) begin
                @(posedge clk);
                timeout = timeout + 1;
            end
            if (dut.u_core.scan_done_pulse !== 1'b1) begin
                $display("FAIL scan timeout mode=%0d", mode);
                $fatal;
            end
            @(posedge clk);
            @(posedge clk);
        end
    endtask

    task press_learn;
        begin
            btn[1] = 1'b1;
            repeat (3) @(posedge clk);
            btn[1] = 1'b0;
            repeat (2) @(posedge clk);
        end
    endtask

    task expect_cls;
        input [8*16-1:0] tag;
        input [2:0]      exp;
        begin
            if (dut.u_core.cmp_cls !== exp) begin
                $display("FAIL %0s cls=%0d exp=%0d (matrix=%b ref_valid=%b)",
                         tag, dut.u_core.cmp_cls, exp,
                         dut.u_core.conn_matrix, dut.u_core.reference_valid);
                fails = fails + 1;
            end else begin
                $display("ok   %0s cls=%0d", tag, dut.u_core.cmp_cls);
            end
        end
    endtask

    initial begin
        $display("=== tb_static_cls start ===");
        fails = 0;
        repeat (20) @(posedge clk);
        rst_n = 1;
        repeat (20) @(posedge clk);

        // ① 正常线束扫描 → 矩阵正确、未学习时 reference_valid=0
        scan_once;
        if (dut.u_core.conn_matrix !== EXP_CROSS ||
            dut.u_core.reference_valid !== 1'b0 || dut.u_core.idle_ok !== 1'b1) begin
            $display("FAIL baseline matrix=%b valid=%b idle=%b",
                     dut.u_core.conn_matrix, dut.u_core.reference_valid, dut.u_core.idle_ok);
            fails = fails + 1;
        end else
            $display("ok   baseline matrix=%b", dut.u_core.conn_matrix);

        // ② LEARN：接受参考矩阵
        press_learn;
        if (dut.u_core.reference_valid !== 1'b1 || dut.u_core.m_ref !== EXP_CROSS) begin
            $display("FAIL learn valid=%b m_ref=%b",
                     dut.u_core.reference_valid, dut.u_core.m_ref);
            fails = fails + 1;
        end else
            $display("ok   learn accepted");

        // ③ 双射换位 → MISWIRE
        mode = 2'd1;
        scan_once;
        expect_cls("miswire", C_MISWIRE);

        // ④ a0 开路 → OPEN
        mode = 2'd2;
        scan_once;
        expect_cls("open", C_OPEN);

        // ⑤ a0 双连 → BRIDGE
        mode = 2'd3;
        scan_once;
        expect_cls("bridge", C_BRIDGE);

        // ⑥ 回到正常线束 → PASS
        mode = 2'd0;
        scan_once;
        expect_cls("pass", C_PASS);

        if (fails != 0)
            $fatal(1, "STATIC CLS FAIL (%0d checks)", fails);
        $display("PASS");
        $finish;
    end

endmodule
