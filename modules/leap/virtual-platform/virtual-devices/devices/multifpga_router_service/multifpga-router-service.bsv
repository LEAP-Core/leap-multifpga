`include "asim/provides/virtual_platform.bsh"
`include "asim/provides/virtual_devices.bsh"
`include "asim/provides/low_level_platform_interface.bsh"
`include "asim/provides/rrr.bsh"
`include "asim/provides/umf.bsh"
`include "asim/provides/channelio.bsh"
`include "asim/provides/physical_platform.bsh"
`include "asim/provides/soft_connections.bsh"
`include "asim/provides/multifpga_switch.bsh"

`include "asim/provides/multifpga_router_service.bsh"

import FIFOF::*;

`include "multifpga_routing.bsh"


module [CONNECTED_MODULE] mkMultifpgaRouterServices#(VIRTUAL_PLATFORM vplat) (Empty);
  let m <- mkCommunicationModule(vplat);
endmodule 