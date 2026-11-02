# Run 4ch topology simulation
set script_dir [file dirname [file normalize [info script]]]
set root_dir   [file normalize [file join $script_dir ..]]
set xpr        [file join $root_dir vivado XunJi.xpr]

if {![file exists $xpr]} {
    source [file join $script_dir create_project.tcl]
} else {
    catch {close_project}
    open_project $xpr
}

# Ensure sim top（自回环 wrapper + 极性交叉检查，见 sim/tb_xunji_loopback.v）
set_property top tb_xunji_loopback [get_filesets sim_1]
update_compile_order -fileset sim_1

launch_simulation -simset sim_1 -mode behavioral
run all

puts "INFO: Simulation finished"
