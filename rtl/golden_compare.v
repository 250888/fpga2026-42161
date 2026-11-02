//==============================================================================
// Golden Map 比较（V1.9 P060 冻结分类）
//
//   missing = M_ref & ~M_test   （应有却缺失）
//   extra   = ~M_ref & M_test   （不应有却出现）
//   degA/degB 由 matrix_degree 统计；分类优先级（从高到低）：
//     PASS     : M_test == M_ref
//     BRIDGE   : 任一 degA>1 或 degB>1（V1.9「优先判 BRIDGE/TOPOLOGY_ANOMALY」）
//     MISWIRE  : 无 deg>1，缺失与额外并存，且参考矩阵涉及的每个有效行/列实测度仍为 1
//                （= 双射换位，不限于「两根互换」）
//     OPEN     : 只有缺失、没有额外，且每个缺失行实测没有任何连接
//     ANOMALY  : 其余混合/无法唯一解释物理位置
//
// 说明：不开夸大——ANOMALY 只表示「矩阵层面无法唯一解释」，不是已定位物理短路点。
//==============================================================================

module golden_compare #(
    parameter N_CH = 4
)(
    input  wire [N_CH*N_CH-1:0] m_ref,
    input  wire [N_CH*N_CH-1:0] m_test,
    output wire [N_CH*N_CH-1:0] missing,
    output wire [N_CH*N_CH-1:0] extra,
    output wire [N_CH-1:0]      a_eq1,
    output wire [N_CH-1:0]      a_gt1,
    output wire [N_CH-1:0]      a_zero,
    output wire [N_CH-1:0]      b_eq1,
    output wire [N_CH-1:0]      b_gt1,
    output wire [N_CH-1:0]      b_zero,
    output wire                 all_one_test,
    output reg  [2:0]           cls
);

    localparam [2:0] C_PASS    = 3'd0;
    localparam [2:0] C_OPEN    = 3'd1;
    localparam [2:0] C_MISWIRE = 3'd2;
    localparam [2:0] C_BRIDGE  = 3'd3;
    localparam [2:0] C_ANOMALY = 3'd4;

    assign missing = m_ref & ~m_test;
    assign extra   = ~m_ref & m_test;

    matrix_degree #(.N_CH(N_CH)) u_deg (
        .m(m_test),
        .a_eq1(a_eq1), .a_gt1(a_gt1), .a_zero(a_zero),
        .b_eq1(b_eq1), .b_gt1(b_gt1), .b_zero(b_zero),
        .all_one(all_one_test)
    );

    wire any_gt1     = (|a_gt1) | (|b_gt1);
    wire any_missing = |missing;
    wire any_extra   = |extra;

    // 缺失行是否仍有实测连接：OPEN 要求缺失行实测「没有任何连接」
    reg missing_row_busy;
    // 双射判定：参考矩阵涉及的每个行/列，实测连接度仍恰为 1
    reg miswire_ok;

    integer i, j;
    reg ref_used;

    always @(*) begin
        missing_row_busy = 1'b0;
        miswire_ok       = 1'b1;
        for (i = 0; i < N_CH; i = i + 1) begin
            if ((|missing[i*N_CH +: N_CH]) && !a_zero[i])
                missing_row_busy = 1'b1;
            ref_used = |m_ref[i*N_CH +: N_CH];
            if (ref_used && !a_eq1[i])
                miswire_ok = 1'b0;
        end
        for (j = 0; j < N_CH; j = j + 1) begin
            ref_used = 1'b0;
            for (i = 0; i < N_CH; i = i + 1)
                ref_used = ref_used | m_ref[i*N_CH + j];
            if (ref_used && !b_eq1[j])
                miswire_ok = 1'b0;
        end
    end

    always @(*) begin
        if (m_test == m_ref)
            cls = C_PASS;
        else if (any_gt1)
            cls = C_BRIDGE;
        else if (any_missing && any_extra && miswire_ok)
            cls = C_MISWIRE;
        else if (any_missing && !any_extra && !missing_row_busy)
            cls = C_OPEN;
        else
            cls = C_ANOMALY;
    end

endmodule
