# Create Vivado project for XunJi (EGO1)
# Run from scripts/: vivado -mode batch -source create_project.tcl

set script_dir [file dirname [file normalize [info script]]]
set root_dir   [file normalize [file join $script_dir ..]]
set proj_dir   [file join $root_dir vivado]
set con_dir    [file join $root_dir constrs]
set part       "xc7a35tcsg324-1"
set proj_name  "XunJi"

file mkdir $proj_dir

# Close any open project first
catch {close_project}

create_project $proj_name $proj_dir -part $part -force

# RTL（仓库根 rtl/，uv 化重组后不再嵌在 src/ 下）
set rtl_files [glob -nocomplain [file join $root_dir rtl *.v]]
if {[llength $rtl_files] > 0} {
    add_files -norecurse $rtl_files
}
# 合成顶层 = 生产 Top（V1.9 P048：b_conn=b_sync，反相只在 loopback wrapper）
# 两个 wrapper 的端口集合与 constrs/ego1.xdc 完全一致，换顶层不需要换约束
set_property top xunji_top_hw [current_fileset]

# Constraints
set xdc_files [glob -nocomplain [file join $con_dir *.xdc]]
if {[llength $xdc_files] > 0} {
    add_files -fileset constrs_1 -norecurse $xdc_files
}

# Sim（仓库根 sim/）
set sim_files [glob -nocomplain [file join $root_dir sim *.v]]
if {[llength $sim_files] > 0} {
    add_files -fileset sim_1 -norecurse $sim_files
    set_property top tb_xunji_loopback [get_filesets sim_1]
}

update_compile_order -fileset sources_1
update_compile_order -fileset sim_1

set xpr [file join $proj_dir ${proj_name}.xpr]
puts "INFO: Project created at $xpr"
