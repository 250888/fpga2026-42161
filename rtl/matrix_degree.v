//==============================================================================
// 矩阵连接度检查（V1.9 P060 degA/degB 的可执行化）
//
// 输入 N_CH×N_CH 连接矩阵（row-major：m[i*N_CH + j]，i=A 行、j=B 列），
// 逐行/逐列统计连接度，给出「=1 / >1 / =0」三类标记：
//   a_eq1/a_gt1/a_zero —— A 行连接度；b_eq1/b_gt1/b_zero —— B 列连接度
// all_one = 全部行、列的连接度都恰好为 1（LEARN 合法性与 MISWIRE 双射判定的公共判据）。
//==============================================================================

module matrix_degree #(
    parameter N_CH = 4
)(
    input  wire [N_CH*N_CH-1:0] m,
    output reg  [N_CH-1:0]      a_eq1,
    output reg  [N_CH-1:0]      a_gt1,
    output reg  [N_CH-1:0]      a_zero,
    output reg  [N_CH-1:0]      b_eq1,
    output reg  [N_CH-1:0]      b_gt1,
    output reg  [N_CH-1:0]      b_zero,
    output wire                 all_one
);

    integer i, j;
    reg [N_CH:0] cnt;

    always @(*) begin
        for (i = 0; i < N_CH; i = i + 1) begin
            cnt = 0;
            for (j = 0; j < N_CH; j = j + 1)
                cnt = cnt + m[i*N_CH + j];
            a_eq1[i]  = (cnt == 1);
            a_gt1[i]  = (cnt > 1);
            a_zero[i] = (cnt == 0);
        end
        for (j = 0; j < N_CH; j = j + 1) begin
            cnt = 0;
            for (i = 0; i < N_CH; i = i + 1)
                cnt = cnt + m[i*N_CH + j];
            b_eq1[j]  = (cnt == 1);
            b_gt1[j]  = (cnt > 1);
            b_zero[j] = (cnt == 0);
        end
    end

    assign all_one = (&a_eq1) & (&b_eq1);

endmodule
