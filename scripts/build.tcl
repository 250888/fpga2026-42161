# Synthesis + Implementation + Bitstream
set script_dir [file dirname [file normalize [info script]]]
set root_dir   [file normalize [file join $script_dir ..]]
set xpr        [file join $root_dir vivado XunJi.xpr]

if {![file exists $xpr]} {
    source [file join $script_dir create_project.tcl]
} else {
    catch {close_project}
    open_project $xpr
}

reset_run synth_1
launch_runs synth_1 -jobs 4
wait_on_run synth_1

set synth_status [get_property STATUS [get_runs synth_1]]
puts "INFO: synth_1 STATUS = $synth_status"
if {[string match "*ERROR*" $synth_status]} {
    puts "ERROR: Synthesis failed"
    exit 1
}

reset_run impl_1
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1

set impl_status [get_property STATUS [get_runs impl_1]]
puts "INFO: impl_1 STATUS = $impl_status"

open_run impl_1
report_utilization -file [file join $root_dir vivado utilization.rpt]
report_timing_summary -file [file join $root_dir vivado timing.rpt]

set bitfile [file join $root_dir vivado XunJi.runs impl_1 xunji_top_hw.bit]
puts "INFO: Bitstream => $bitfile"
