//==============================================================================
// LEARN 合法性门（V1.9 P059）
//
// LEARN 不是「随便插一根线就学」：参考线束必须先通过 IDLE_CHECK（idle_ok=1），
// 且满足第一版一对一线束范围（M_scan 所有 A 行、B 列连接度均为 1），
// 才接受为参考矩阵并置 reference_valid=1；否则拒绝，**不覆盖已有 M_ref，
// 也不清 reference_valid**（2026-10-24 审查 W1：拒绝若清 valid，扫描中点一次
// LEARN 就会把已学参考静默丢掉，帧 cls 变 5）。
//==============================================================================

module learn_gate #(
    parameter N_CH = 4
)(
    input  wire                 clk,
    input  wire                 rst,
    input  wire                 learn,          // 电平/脉冲均可，由 core 给单拍
    input  wire                 idle_ok,        // 上一轮扫描的 IDLE_CHECK 结论
    input  wire [N_CH*N_CH-1:0] m_scan,         // 本轮扫描矩阵
    output reg                  reference_valid,
    output reg  [N_CH*N_CH-1:0] m_ref,
    output reg                  learn_accept_pulse,
    output reg                  learn_reject_pulse
);

    wire [N_CH-1:0] a_eq1, a_gt1, a_zero;
    wire [N_CH-1:0] b_eq1, b_gt1, b_zero;
    wire            all_one;

    matrix_degree #(.N_CH(N_CH)) u_deg (
        .m(m_scan),
        .a_eq1(a_eq1), .a_gt1(a_gt1), .a_zero(a_zero),
        .b_eq1(b_eq1), .b_gt1(b_gt1), .b_zero(b_zero),
        .all_one(all_one)
    );

    always @(posedge clk) begin
        if (rst) begin
            reference_valid     <= 1'b0;
            m_ref               <= {N_CH*N_CH{1'b0}};
            learn_accept_pulse  <= 1'b0;
            learn_reject_pulse  <= 1'b0;
        end else begin
            learn_accept_pulse <= 1'b0;
            learn_reject_pulse <= 1'b0;
            if (learn) begin
                if (idle_ok && all_one) begin
                    m_ref              <= m_scan;
                    reference_valid    <= 1'b1;
                    learn_accept_pulse <= 1'b1;
                end else begin
                    // 拒绝时只发 reject 脉冲：保留上一次有效参考与 reference_valid
                    // （W1）。坏参考不覆盖 M_ref，好参考也不会被误清。
                    learn_reject_pulse <= 1'b1;
                end
            end
        end
    end

endmodule
