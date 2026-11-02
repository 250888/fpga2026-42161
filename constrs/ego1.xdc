##==============================================================================
## 瞬迹（XunJi）— EGO1 引脚约束
## 板卡：EGO1 Artix-7 XC7A35T-1CSG324C @ 100 MHz
##
## 【唯一针脚基准】V1.9 §4.1 表3 —— 引自 EGO1 V2.2 用户手册 §14「通用扩展 I/O」。
## 【冻结块】下列 1～6 段 = V1.9 §4.2 冻结约束，逐字对应；端口名即 V1.9 冻结名。
##
## ⚠ 红线（AGENTS.md §6 / V1.9 §26）：
##   1. 上板前必须按 EGO1 V2.2 官方手册逐针复核表3 全部 36 针并留勾选记录。
##   2. 禁止「DRC 失败后换一个能过的封装脚」；要改针脚先改 V1.9 文档。
##   3. J5 的 33/34=GND、35/36=3.3V 不进逻辑端口，本文件不得为其分配 PACKAGE_PIN。
##==============================================================================

##------------------------------------------------------------------------------
## 0. 配置电压（消除实现 DRC 的 CFGBVS-1 唯一告警）
##    EGO1 的 VCCO bank（14/15/34/35）全部 3.3V，CFGBVS 取 VCCO。
##------------------------------------------------------------------------------
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]

##------------------------------------------------------------------------------
## 1. 系统时钟：板载 100 MHz（周期 10 ns）
##------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN P17 IOSTANDARD LVCMOS33 } [get_ports {sys_clk}]
create_clock -add -name sys_clk_pin -period 10.000 -waveform {0 5.000} [get_ports {sys_clk}]

##------------------------------------------------------------------------------
## 2. 复位：EGO1 S6 / FPGA_RESET（P15，4.7 kΩ 上拉，按下接地）→ 低有效 rst_n
##    RTL 侧先经 2 级 reset synchronizer（rtl/xj_rst_sync.v），核心用内部 rst。
##------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN P15 IOSTANDARD LVCMOS33 } [get_ports {rst_n}]

##------------------------------------------------------------------------------
## 3. J5 A 端激励 a_ctrl_n[15:0] = J5 物理针 1..16（V1.9 §4.1 表3）
##    语义：0 = LVC07 拉低线束；1 = 释放（高阻）。复位/安全态全 1。
##------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN B16 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[0]}]
# J5-1  A1
set_property -dict { PACKAGE_PIN B17 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[1]}]
# J5-2  A2
set_property -dict { PACKAGE_PIN A15 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[2]}]
# J5-3  A3
set_property -dict { PACKAGE_PIN A16 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[3]}]
# J5-4  A4
set_property -dict { PACKAGE_PIN A13 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[4]}]
# J5-5  A5
set_property -dict { PACKAGE_PIN A14 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[5]}]
# J5-6  A6
set_property -dict { PACKAGE_PIN B18 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[6]}]
# J5-7  A7
set_property -dict { PACKAGE_PIN A18 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[7]}]
# J5-8  A8
set_property -dict { PACKAGE_PIN F13 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[8]}]
# J5-9  A9
set_property -dict { PACKAGE_PIN F14 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[9]}]
# J5-10 A10
set_property -dict { PACKAGE_PIN B13 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[10]}]
# J5-11 A11
set_property -dict { PACKAGE_PIN B14 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[11]}]
# J5-12 A12
set_property -dict { PACKAGE_PIN D14 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[12]}]
# J5-13 A13
set_property -dict { PACKAGE_PIN C14 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[13]}]
# J5-14 A14
set_property -dict { PACKAGE_PIN B11 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[14]}]
# J5-15 A15
set_property -dict { PACKAGE_PIN A11 IOSTANDARD LVCMOS33 } [get_ports {a_ctrl_n[15]}]
# J5-16 A16

##------------------------------------------------------------------------------
## 4. J5 B 端检测 b_raw[15:0] = J5 物理针 17..32（V1.9 §4.1 表3）
##    b_raw 与 sys_clk 异步 → rtl/input_sync.v 两级同步后才产生 b_sync；
##    生产 Top b_conn=b_sync（导通=1/开路=0），反相只允许出现在 loopback wrapper。
##------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN E15 IOSTANDARD LVCMOS33 } [get_ports {b_raw[0]}]
# J5-17 B1
set_property -dict { PACKAGE_PIN E16 IOSTANDARD LVCMOS33 } [get_ports {b_raw[1]}]
# J5-18 B2
set_property -dict { PACKAGE_PIN D15 IOSTANDARD LVCMOS33 } [get_ports {b_raw[2]}]
# J5-19 B3
set_property -dict { PACKAGE_PIN C15 IOSTANDARD LVCMOS33 } [get_ports {b_raw[3]}]
# J5-20 B4
set_property -dict { PACKAGE_PIN H16 IOSTANDARD LVCMOS33 } [get_ports {b_raw[4]}]
# J5-21 B5
set_property -dict { PACKAGE_PIN G16 IOSTANDARD LVCMOS33 } [get_ports {b_raw[5]}]
# J5-22 B6
set_property -dict { PACKAGE_PIN F15 IOSTANDARD LVCMOS33 } [get_ports {b_raw[6]}]
# J5-23 B7
set_property -dict { PACKAGE_PIN F16 IOSTANDARD LVCMOS33 } [get_ports {b_raw[7]}]
# J5-24 B8
set_property -dict { PACKAGE_PIN H14 IOSTANDARD LVCMOS33 } [get_ports {b_raw[8]}]
# J5-25 B9
set_property -dict { PACKAGE_PIN G14 IOSTANDARD LVCMOS33 } [get_ports {b_raw[9]}]
# J5-26 B10
set_property -dict { PACKAGE_PIN E17 IOSTANDARD LVCMOS33 } [get_ports {b_raw[10]}]
# J5-27 B11
set_property -dict { PACKAGE_PIN D17 IOSTANDARD LVCMOS33 } [get_ports {b_raw[11]}]
# J5-28 B12
set_property -dict { PACKAGE_PIN K13 IOSTANDARD LVCMOS33 } [get_ports {b_raw[12]}]
# J5-29 B13
set_property -dict { PACKAGE_PIN J13 IOSTANDARD LVCMOS33 } [get_ports {b_raw[13]}]
# J5-30 B14
set_property -dict { PACKAGE_PIN H17 IOSTANDARD LVCMOS33 } [get_ports {b_raw[14]}]
# J5-31 B15
set_property -dict { PACKAGE_PIN G17 IOSTANDARD LVCMOS33 } [get_ports {b_raw[15]}]
# J5-32 B16

##------------------------------------------------------------------------------
## 5. A 端只驱动 LVC07 逻辑输入：低驱动能力 + 慢沿降低数字噪声（V1.9 §4.2）
##------------------------------------------------------------------------------
set_property DRIVE 4  [get_ports {a_ctrl_n[*]}]
set_property SLEW SLOW [get_ports {a_ctrl_n[*]}]

##------------------------------------------------------------------------------
## 6. 板载 USB-UART（FPGA 视角命名，V1.9 §4.1）
##    板级网络 UART_RX = T4 = FPGA 发送 uart_tx；UART_TX = N5 = FPGA 接收 uart_rx
##------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN T4 IOSTANDARD LVCMOS33 } [get_ports {uart_tx}]
set_property -dict { PACKAGE_PIN N5 IOSTANDARD LVCMOS33 } [get_ports {uart_rx}]

##------------------------------------------------------------------------------
## 7. 【暂定段，非冻结】板载 LED / 按键 / 拨码
##
## V1.9 §4.2 的冻结 XDC 未包含板载 I/O（HANDOFF §4.3 遗留1：演示要 LEARN/状态，
## 但文档未冻结是「补约束」还是「全走 UART」）。本段沿用阶段一草稿针脚，只为让
## 工程无未约束端口（否则 Vivado 报 UCIO-1/NSTD-1 DRC 直接挡下）。
## 待 V1.9 文档拍板后：要么转正进冻结段，要么从顶层端口删除本段——届时同步改
## tests/test_xdc.py 的暂定段断言，不允许只改 XDC。
##------------------------------------------------------------------------------
## 按键 BTNC/BTND/BTNL/BTNR/BTNU（官方丝印 S0..S4，手册：默认低、按下=高）
## 管脚 2026-10-11 对照 EGO1 V2.2 官方手册「通用I/O接口」修正：btn[4] 旧稿 V2
## 实为 SW_DIP5，官方为 U4。
set_property PACKAGE_PIN R11 [get_ports {btn[0]}]
set_property PACKAGE_PIN R17 [get_ports {btn[1]}]
set_property PACKAGE_PIN R15 [get_ports {btn[2]}]
set_property PACKAGE_PIN V1  [get_ports {btn[3]}]
set_property PACKAGE_PIN U4  [get_ports {btn[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {btn[*]}]

## 拨码开关 SW0..SW7
set_property PACKAGE_PIN R1 [get_ports {sw[0]}]
set_property PACKAGE_PIN N4 [get_ports {sw[1]}]
set_property PACKAGE_PIN M4 [get_ports {sw[2]}]
set_property PACKAGE_PIN R2 [get_ports {sw[3]}]
set_property PACKAGE_PIN P2 [get_ports {sw[4]}]
set_property PACKAGE_PIN P3 [get_ports {sw[5]}]
set_property PACKAGE_PIN P4 [get_ports {sw[6]}]
set_property PACKAGE_PIN P5 [get_ports {sw[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {sw[*]}]

## LED LD0..LD15（官方手册：LED 在 FPGA 输出高电平时点亮）
## 管脚 2026-10-11 对照 EGO1 V2.2 官方手册「通用I/O接口」修正 3 处：
## led[12] 旧稿 G4→J4、led[14] 旧稿 H2→G4、led[15] 旧稿 H1→F6。
set_property PACKAGE_PIN K3 [get_ports {led[0]}]
set_property PACKAGE_PIN M1 [get_ports {led[1]}]
set_property PACKAGE_PIN L1 [get_ports {led[2]}]
set_property PACKAGE_PIN K6 [get_ports {led[3]}]
set_property PACKAGE_PIN J5 [get_ports {led[4]}]
set_property PACKAGE_PIN H5 [get_ports {led[5]}]
set_property PACKAGE_PIN H6 [get_ports {led[6]}]
set_property PACKAGE_PIN K1 [get_ports {led[7]}]
set_property PACKAGE_PIN K2 [get_ports {led[8]}]
set_property PACKAGE_PIN J2 [get_ports {led[9]}]
set_property PACKAGE_PIN J3 [get_ports {led[10]}]
set_property PACKAGE_PIN H4 [get_ports {led[11]}]
set_property PACKAGE_PIN J4 [get_ports {led[12]}]
set_property PACKAGE_PIN G3 [get_ports {led[13]}]
set_property PACKAGE_PIN G4 [get_ports {led[14]}]
set_property PACKAGE_PIN F6 [get_ports {led[15]}]
set_property IOSTANDARD LVCMOS33 [get_ports {led[*]}]

##------------------------------------------------------------------------------
## 8. 【故意暂缺】b_raw → 第一级同步器 D 端的 path exception
## V1.9 §4.2/P029：等 RTL 实例名固定后、用 report_cdc 复核「命中目标数=16」再写；
## 且只许 false-path 到第一级 D 端，不得把第一级→第二级一并掩盖。
## 本机 Vivado 暂不可用（xv_xsimverific.dll 缺失），无法 report_cdc 复核 →
## 宁可保留未约束告警，也不写未经验证的过宽 exception。
##------------------------------------------------------------------------------
