// ============================================================================
// 瞬迹 FE-16 前端板 · 外壳（参数化，3D 打印）
//
// 用法：装 OpenSCAD → 打开本文件 → F6 渲染 → F7 导出 STL。
//   只出底壳： 把最后一行的 lid(); 注释掉
//   只出上盖： 把最后一行的 base(); 注释掉
//
// 坐标系：X 右、Y 向里、Z 向上。
//   板坐标 = (0,0) 在板的左下角；**J5 侧是 y=0 的那条边**（贴 Y=0 墙）。
//   外壳在板坐标外再包一层 CLEAR + WALL。
//
// 板子实测（来自 pcb/frontend16/fe16_design.py）：
//   96 × 96 mm，厚 1.6；安装孔 3.2 于 (4,4)(92,4)(4,92)(92,92)
//   J5 (2×18) pin1 @ (26.4, 6.5)，列距 2.54 → x 26.4..69.58
//   JA (2×10) pin1 @ (10.27,22.0) 竖排 → y 22.0..44.86，x 7.73/10.27
//   JB (2×10) 镜像 → y 22.0..44.86，x 83.19/85.73
//   TP 测试点：TP1-16(A) 底排 y=77；TP17-32(B) y=83；TP33-48(b_raw) y=17
// ============================================================================

$fn = 64;

// ---------------- 板子 ----------------
BOARD      = 96;
PCB_T      = 1.6;
CLEAR      = 0.5;    // 板边与内壁间隙（每边）
WALL       = 2.2;
FLOOR      = 2.0;
PCB_Z      = 5.0;    // PCB 底面离外壳底面 → 板下留 3mm 给焊点
INTERIOR_H = 20.0;   // 内腔净高（从外壳底面算到内腔顶）
LID_T      = 2.0;
LID_LIP    = 1.6;    // 上盖插入内腔的凸缘
LID_CLR    = 0.35;   // 凸缘与内壁的配合间隙
LID_BORDER = 7.0;    // 上盖边框宽（中间开观察窗）

INNER = BOARD + 2*CLEAR;      // 96.9
OUTER = INNER + 2*WALL;       // 101.3

// ---------------- 安装孔 ----------------
MH          = [[4,4],[92,4],[4,92],[92,92]];
MH_D        = 3.2;    // 板上安装孔（M3 通孔）
MH_D_CLEAR  = 3.4;    // 上盖过孔（M3 间隙）
STANDOFF_D  = 7.0;
SCREW_PILOT = 2.6;    // M3 自攻底孔
SCREW_DEPTH = 6.0;

// ---------------- 接口开口 ----------------
J5_X0 = 26.4 - 1.0;  J5_X1 = 69.58 + 1.0;
JA_Y0 = 22.0 - 1.0;  JA_Y1 = 44.86 + 1.0;
JB_Y0 = 22.0 - 1.0;  JB_Y1 = 44.86 + 1.0;
SLOT_Z0 = PCB_Z + PCB_T + 1.0;   // 板面上方留 1mm
SLOT_H  = 12.0;                  // 开口高（IDC 简牛 ~9mm，留余量）

// ---------------- 坐标换算 ----------------
function bx(x) = WALL + CLEAR + x;   // 板 x → 外壳 x
function by(y) = WALL + CLEAR + y;   // 板 y → 外壳 y

// ============================ 底壳 ============================
module base() {
    difference() {
        union() {
            // 外形 + 内腔
            difference() {
                cube([OUTER, OUTER, FLOOR + INTERIOR_H]);
                translate([WALL, WALL, FLOOR])
                    cube([INNER, INNER, INTERIOR_H + 1]);
            }
            // 四个 PCB 支撑柱（带自攻底孔）
            for (p = MH)
                translate([bx(p[0]), by(p[1]), FLOOR])
                    cylinder(d = STANDOFF_D, h = PCB_Z - FLOOR);
        }

        // 自攻螺丝底孔
        for (p = MH)
            translate([bx(p[0]), by(p[1]), PCB_Z - SCREW_DEPTH])
                cylinder(d = SCREW_PILOT, h = SCREW_DEPTH + 0.2);

        // --- J5 侧（Y=0 墙）：2×18 排线出口 ---
        translate([bx(J5_X0), -1, SLOT_Z0])
            cube([J5_X1 - J5_X0, WALL + 2, SLOT_H]);

        // --- JA 侧（X=0 墙）：A 端线束出口 ---
        translate([-1, by(JA_Y0), SLOT_Z0])
            cube([WALL + 2, JA_Y1 - JA_Y0, SLOT_H]);

        // --- JB 侧（X=OUTER 墙）：B 端线束出口 ---
        translate([OUTER - WALL - 1, by(JB_Y0), SLOT_Z0])
            cube([WALL + 2, JB_Y1 - JB_Y0, SLOT_H]);

        // --- 散热槽（左右两侧各 3 条，不挡线束）---
        for (i = [0:2])
            translate([-1, by(64) + i*6, FLOOR + 6])
                cube([WALL + 2, 3, 8]);
        for (i = [0:2])
            translate([OUTER - WALL - 1, by(64) + i*6, FLOOR + 6])
                cube([WALL + 2, 3, 8]);
    }
}

// ============================ 上盖 ============================
module lid() {
    difference() {
        union() {
            cube([OUTER, OUTER, LID_T]);
            // 插入内腔的凸缘
            translate([WALL + LID_CLR, WALL + LID_CLR, -LID_LIP])
                cube([INNER - 2*LID_CLR, INNER - 2*LID_CLR, LID_LIP]);
        }
        // 中央观察窗：能直接看到板子 / 夹示波器探头 / 换电阻
        translate([LID_BORDER, LID_BORDER, -LID_LIP - 1])
            cube([OUTER - 2*LID_BORDER, OUTER - 2*LID_BORDER,
                  LID_T + LID_LIP + 2]);
        // 四个螺丝过孔（从盖面拧进底壳支柱）
        for (p = MH)
            translate([bx(p[0]), by(p[1]), -LID_LIP - 1])
                cylinder(d = MH_D_CLEAR, h = LID_T + LID_LIP + 2);
    }
}

// ============================ 输出 ============================
// 摆在一起便于检查；导出时只留一个
translate([-OUTER - 10, 0, 0]) base();
lid();

// 调试：把板子和关键接口的投影画出来看开口对不对
// color("green", 0.3) translate([WALL+CLEAR, WALL+CLEAR, PCB_Z])
//     cube([BOARD, BOARD, PCB_T]);
