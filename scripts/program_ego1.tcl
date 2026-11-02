# 烧录 EGO1（XC7A35T）：把 bit 通过板载 USB-JTAG 写进 FPGA
# 用法：vivado -mode batch -source program_ego1.tcl
set bit_file "C:/xjbuild/vivado/XunJi.runs/impl_1/xunji_top_hw.bit"

puts "== open hw manager =="
open_hw_manager

puts "== connect hw server =="
if {[catch {connect_hw_server -url localhost:3121} err]} {
    puts "connect localhost:3121 failed: $err"
    puts "trying default..."
    connect_hw_server
}

puts "== targets =="
foreach t [get_hw_targets] { puts "  target: $t" }
if {[llength [get_hw_targets]] == 0} {
    error "no hw target found (check USB-JTAG driver / board power)"
}

open_hw_target

puts "== devices =="
foreach d [get_hw_devices] { puts "  device: $d" }
set dev [lindex [get_hw_devices] 0]
if {$dev eq ""} { error "no hw device found" }

current_hw_device $dev
refresh_hw_device -update_hw_probes false [current_hw_device]

puts "== program =="
set_property PROGRAM.FILE $bit_file [current_hw_device]
program_hw_devices [current_hw_device]
refresh_hw_device [current_hw_device]

puts "== done: [get_property PROGRAM.FILE [current_hw_device]] =="
close_hw_manager
