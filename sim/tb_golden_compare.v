`timescale 1ns / 1ps

//==============================================================================
// golden_compare + learn_gate 模块级 TB（V1.9 P059 / P060）
//
// 冻结语义：
//   missing = M_ref & ~M_test（应有却缺失）
//   extra   = ~M_ref & M_test（不应有却出现）
//   degA/degB = 每行/每列连接度；deg>1 优先判 BRIDGE；
//   无 deg>1、无零度、缺失+额外并存且是双射 → MISWIRE(PERMUTATION)；
//   仅缺失且缺失行实测全空 → OPEN；其余混合/无法唯一解释 → TOPOLOGY_ANOMALY。
//
// LEARN 合法性（P059）：仅当 IDLE_CHECK 通过（idle_ok=1）且 M_scan 行列连接度均为 1
// 才接受参考矩阵（reference_valid=1）；否则拒绝。
//==============================================================================
module tb_golden_compare;

`ifdef DUMP_VCD
    initial begin
        $dumpfile("build/tb_golden_compare.vcd");
        $dumpvars(0, tb_golden_compare);
    end
`endif

    localparam N = 4;

    // 参考矩阵：a0→b2, a1→b0, a2→b3, a3→b1（行 major，row0 在最低位）
    localparam [N*N-1:0] REF     = {4'b0010, 4'b1000, 4'b0001, 4'b0100};
    localparam [N*N-1:0] OPENM   = {4'b0010, 4'b1000, 4'b0001, 4'b0000};  // a0 整行缺失
    localparam [N*N-1:0] MISWIRE = {4'b0010, 4'b1000, 4'b0100, 4'b0001};  // a0/a1 换位（双射）
    localparam [N*N-1:0] BRIDGE  = {4'b0010, 4'b1000, 4'b0001, 4'b1100};  // a0 同时连 b2/b3
    localparam [N*N-1:0] REF2    = {4'b0000, 4'b0000, 4'b0001, 4'b0100};  // 仅 a0→b2、a1→b0
    localparam [N*N-1:0] ANOMALY = {4'b0000, 4'b1000, 4'b0001, 4'b0100};  // 额外 a2→b3（无缺失）

    localparam [2:0] C_PASS = 3'd0, C_OPEN = 3'd1, C_MISWIRE = 3'd2,
                     C_BRIDGE = 3'd3, C_ANOMALY = 3'd4;

    reg  [N*N-1:0] m_ref;
    reg  [N*N-1:0] m_test;

    wire [N*N-1:0] missing;
    wire [N*N-1:0] extra;
    wire [N-1:0]   a_eq1, a_gt1, a_zero;
    wire [N-1:0]   b_eq1, b_gt1, b_zero;
    wire [2:0]     cls;
    wire           all_one_test;

    golden_compare #(.N_CH(N)) u_gc (
        .m_ref(m_ref),
        .m_test(m_test),
        .missing(missing),
        .extra(extra),
        .a_eq1(a_eq1),
        .a_gt1(a_gt1),
        .a_zero(a_zero),
        .b_eq1(b_eq1),
        .b_gt1(b_gt1),
        .b_zero(b_zero),
        .all_one_test(all_one_test),
        .cls(cls)
    );

    // ---------------- learn_gate ----------------
    reg         clk = 0;
    reg         rst = 1;
    reg         learn = 0;
    reg         idle_ok = 0;
    reg  [N*N-1:0] m_scan;
    wire        reference_valid;
    wire [N*N-1:0] m_ref_out;
    wire        learn_accept;
    wire        learn_reject;

    learn_gate #(.N_CH(N)) u_lg (
        .clk(clk),
        .rst(rst),
        .learn(learn),
        .idle_ok(idle_ok),
        .m_scan(m_scan),
        .reference_valid(reference_valid),
        .m_ref(m_ref_out),
        .learn_accept_pulse(learn_accept),
        .learn_reject_pulse(learn_reject)
    );

    always #5 clk = ~clk;

    // 粘滞记录 learn 结果脉冲（避免与采样沿竞争）
    reg accept_seen, reject_seen;
    always @(posedge clk) begin
        if (learn_accept) accept_seen <= 1'b1;
        if (learn_reject) reject_seen <= 1'b1;
    end

    integer fails;

    task check_cls;
        input [8*20-1:0] name;
        input [N*N-1:0]  test_mat;
        input [2:0]      exp_cls;
        begin
            m_test = test_mat;
            #1;
            if (cls !== exp_cls) begin
                $display("FAIL %0s: cls=%0d exp=%0d", name, cls, exp_cls);
                fails = fails + 1;
            end else begin
                $display("ok   %0s cls=%0d missing=%b extra=%b", name, cls, missing, extra);
            end
        end
    endtask

    task learn_pulse;
        input      idle_v;
        input [N*N-1:0] scan_mat;
        begin
            accept_seen = 1'b0;
            reject_seen = 1'b0;
            idle_ok = idle_v;
            m_scan  = scan_mat;
            #1;                          // 组合逻辑结算后再拉 learn（硬件上矩阵先稳定）
            learn   = 1'b1;
            repeat (2) @(posedge clk);   // 电平保持 2 拍，规避采样竞争
            learn   = 1'b0;
            @(posedge clk);
            @(posedge clk);              // 等脉冲记录落地
        end
    endtask

    initial begin
        $display("=== tb_golden_compare start ===");
        fails = 0;
        m_ref = REF;

        // ---- 分类 ----
        check_cls("PASS", REF, C_PASS);
        check_cls("OPEN/a0-row-empty", OPENM, C_OPEN);
        check_cls("MISWIRE/permutation", MISWIRE, C_MISWIRE);
        check_cls("BRIDGE/degA>1", BRIDGE, C_BRIDGE);

        m_ref = REF2;
        check_cls("ANOMALY/extra-only", ANOMALY, C_ANOMALY);
        m_ref = REF;

        // ---- LEARN 合法性 ----
        rst = 1;
        repeat (4) @(posedge clk);
        rst = 0;

        learn_pulse(1'b1, REF);            // 合格参考：应接受
        if (reference_valid !== 1'b1 || m_ref_out !== REF || accept_seen !== 1'b1) begin
            $display("FAIL learn/accept: valid=%b ref=%b accept=%b",
                     reference_valid, m_ref_out, accept_seen);
            fails = fails + 1;
        end else
            $display("ok   learn/accept ref=%b", m_ref_out);

        learn_pulse(1'b0, REF);            // IDLE_CHECK 失败：拒绝，但不清已有参考
        if (reference_valid !== 1'b1 || m_ref_out !== REF || reject_seen !== 1'b1) begin
            $display("FAIL learn/reject-idle: valid=%b ref=%b reject=%b",
                     reference_valid, m_ref_out, reject_seen);
            fails = fails + 1;
        end else
            $display("ok   learn/reject-idle (参考保留)");

        learn_pulse(1'b1, BRIDGE);         // 行列度非 1：拒绝，同样不清参考（W1）
        if (reference_valid !== 1'b1 || m_ref_out !== REF || reject_seen !== 1'b1) begin
            $display("FAIL learn/reject-deg: valid=%b ref=%b", reference_valid, m_ref_out);
            fails = fails + 1;
        end else
            $display("ok   learn/reject-deg (参考保留)");

        if (fails != 0)
            $fatal(1, "GOLDEN COMPARE FAIL (%0d checks)", fails);
        $display("PASS");
        $finish;
    end

endmodule
