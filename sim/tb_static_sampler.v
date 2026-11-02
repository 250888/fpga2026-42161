`timescale 1ns / 1ps

//==============================================================================
// 静态扫描 FSM 模块级 TB（V1.9 P057 / R6）
//
// 直接驱动 topology_scanner 的 b_filtered（隔离 glitch_filter 与极性 wrapper），
// 验证四件事：
//   ① 正常交叉矩阵：IDLE_CHECK 通过、四阶段扫描、M[i][j] row-major 位序正确
//   ② 采样窗内 1 拍毛刺不改变多数表决判决
//   ③ 空闲期某路卡高 → stuck_low_mask 置位、idle_ok=0、该列矩阵强制 0
//   ④ 释放后卡高 → release_timeout 置位（GUARD_TIMEOUT 兜底）
//
// 参数取小值加速（SETTLE=10 / SAMPLE=5 / GUARD_STABLE=3 / GUARD_TIMEOUT=20）；
// V1.9 默认值（500/101/8/500）由 tests/test_static_sampler.py 红线锁定。
//==============================================================================
module tb_static_sampler;

`ifdef DUMP_VCD
    initial begin
        $dumpfile("build/tb_static_sampler.vcd");
        $dumpvars(0, tb_static_sampler);
    end
`endif

    localparam N = 4;

    // 回环模型映射：a0→b2, a1→b0, a2→b3, a3→b1
    localparam [N*N-1:0] EXP_CROSS = {4'b0010, 4'b1000, 4'b0001, 4'b0100};
    // mode2：b3 空闲卡高，a2→b3 被强制 0
    localparam [N*N-1:0] EXP_STUCK = {4'b0010, 4'b0000, 4'b0001, 4'b0100};

    reg         clk = 0;
    reg         rst = 1;
    reg         start = 0;
    reg  [N-1:0] b_conn;

    wire        busy;
    wire        done_pulse;
    wire [3:0]  scan_idx;
    wire        drive_en;
    wire        drive_level;
    wire [N*N-1:0] conn_matrix;
    wire [N-1:0]   open_flags;
    wire [N-1:0]   stuck_low_mask;
    wire        idle_ok;
    wire        release_timeout;

    // 故障注入控制
    reg  [2:0]  mode;          // 0=正常 1=毛刺 2=空闲卡高 3=全程卡高 4=驱动后卡高
    reg         glitch_pulse;
    reg         glitch_done;   // 保证毛刺只有 1 拍
    reg         has_driven;    // 本扫描是否驱动过（区分 idle 与释放阶段）

    always @(posedge clk) begin
        if (rst || !busy)
            has_driven <= 1'b0;
        else if (drive_en === 1'b1)
            has_driven <= 1'b1;
    end

    topology_scanner #(
        .N_CH(N),
        .SETTLE(10),
        .SAMPLE_CYCLES(5),
        .GUARD_STABLE(3),
        .GUARD_TIMEOUT(20),
        .IDLE_SETTLE(10)
    ) dut (
        .clk(clk),
        .rst(rst),
        .start(start),
        .b_filtered(b_conn),
        .busy(busy),
        .done_pulse(done_pulse),
        .scan_idx(scan_idx),
        .drive_en(drive_en),
        .drive_level(drive_level),
        .conn_matrix(conn_matrix),
        .open_flags(open_flags),
        .stuck_low_mask(stuck_low_mask),
        .idle_ok(idle_ok),
        .release_timeout(release_timeout)
    );

    always #5 clk = ~clk;

    // 线束模型：被驱动的 A 通道 ↔ 交叉映射的 B 通道导通（b_conn=1）
    always @(*) begin
        b_conn = {N{1'b0}};
        if (drive_en === 1'b1 && drive_level === 1'b0) begin
            case (scan_idx)
                4'd0:    b_conn[2] = 1'b1;
                4'd1:    b_conn[0] = 1'b1;
                4'd2:    b_conn[3] = 1'b1;
                4'd3:    b_conn[1] = 1'b1;
                default: b_conn    = {N{1'b0}};
            endcase
        end
        if (mode == 3'd1 && glitch_pulse === 1'b1)
            b_conn[1] = 1'b1;      // 未连接列上的 1 拍毛刺
        if (mode == 3'd2)
            b_conn[3] = 1'b1;      // 空闲期卡高
        if (mode == 3'd3)
            b_conn[1] = 1'b1;      // 全程卡高（含空闲，已被 stuck_low 标记）
        if (mode == 3'd4 && busy && has_driven && !drive_en)
            b_conn[0] = 1'b1;      // 驱动过之后才卡高：非 stuck 的释放失败
    end

    integer wait_cycles;
    integer fails;

    task check_vec;
        input [8*24-1:0] name;
        input [N*N-1:0]  got;
        input [N*N-1:0]  exp;
        begin
            if (got !== exp) begin
                $display("FAIL %0s: got=%b exp=%b", name, got, exp);
                fails = fails + 1;
            end else begin
                $display("ok   %0s = %b", name, got);
            end
        end
    endtask

    task check_bit;
        input [8*24-1:0] name;
        input            got;
        input            exp;
        begin
            if (got !== exp) begin
                $display("FAIL %0s: got=%b exp=%b", name, got, exp);
                fails = fails + 1;
            end else begin
                $display("ok   %0s = %b", name, got);
            end
        end
    endtask

    task do_reset;
        begin
            rst = 1;
            start = 0;
            glitch_pulse = 0;
            repeat (4) @(posedge clk);
            rst = 0;
            repeat (2) @(posedge clk);
        end
    endtask

    // 触发一次扫描并等待 done（超时直接 $fatal，避免挂死）
    task run_scan;
        input [2:0] m;
        begin
            mode = m;
            glitch_pulse = 0;
            glitch_done  = 0;
            do_reset;
            start = 1;
            repeat (3) @(posedge clk);   // 电平保持数拍，避免与 DUT 采样竞争
            start = 0;
            wait_cycles = 0;
            while (done_pulse !== 1'b1 && wait_cycles < 400) begin
                @(posedge clk);
                wait_cycles = wait_cycles + 1;
                // mode1：在 row0 的采样窗内注入 1 拍毛刺（仅一次）
                if (mode == 3'd1 && dut.state == 4'd4 && dut.row == 4'd0
                    && glitch_done === 1'b0) begin
                    glitch_pulse <= 1'b1;
                    glitch_done  <= 1'b1;
                end else begin
                    glitch_pulse <= 1'b0;
                end
            end
            if (done_pulse !== 1'b1) begin
                $display("FAIL timeout: mode=%0d busy=%b state=%0d row=%0d",
                         mode, busy, dut.state, dut.row);
                $fatal;
            end
            @(posedge clk);      // 等 done 后一拍，矩阵已稳定
            glitch_pulse = 0;
        end
    endtask

    initial begin
        $display("=== tb_static_sampler start ===");
        fails = 0;
        mode = 0;
        glitch_pulse = 0;

        // ① 正常交叉矩阵
        run_scan(3'd0);
        check_vec("matrix/normal", conn_matrix, EXP_CROSS);
        check_bit("open_flags=0", |open_flags, 1'b0);
        check_bit("stuck_low=0", |stuck_low_mask, 1'b0);
        check_bit("idle_ok", idle_ok, 1'b1);
        check_bit("release_timeout=0", release_timeout, 1'b0);

        // ② 采样窗内 1 拍毛刺：多数表决必须免疫
        run_scan(3'd1);
        check_vec("matrix/glitch-immune", conn_matrix, EXP_CROSS);
        check_bit("glitch: stuck_low=0", |stuck_low_mask, 1'b0);

        // ③ 空闲期 b3 卡高：STUCK_LOW + 该列强制 0
        run_scan(3'd2);
        check_vec("matrix/stuck-low", conn_matrix, EXP_STUCK);
        check_vec("stuck_low_mask", stuck_low_mask, 4'b1000);
        check_bit("idle_ok=0", idle_ok, 1'b0);
        check_bit("open_flags[2]=1", open_flags[2], 1'b1);

        // ④ 全程卡高通道：idle 已标记 stuck_low，释放守卫应忽略它，
        //    不再每行走满超时（2026-10-24 审查 W4 修正后的行为）
        run_scan(3'd3);
        check_bit("release_timeout=0(stuck已标记)", release_timeout, 1'b0);

        // ⑤ 驱动过之后才卡高：不是 stuck，释放守卫必须真的超时报警
        run_scan(3'd4);
        check_bit("release_timeout", release_timeout, 1'b1);

        if (fails != 0)
            $fatal(1, "STATIC SAMPLER FAIL (%0d checks)", fails);
        $display("PASS");
        $finish;
    end

endmodule
