// This file is effectively a stub for the generated router code. 

`include "asim/provides/virtual_platform.bsh"
`include "asim/provides/virtual_devices.bsh"
`include "asim/provides/low_level_platform_interface.bsh"
`include "asim/provides/rrr.bsh"
`include "asim/provides/soft_connections.bsh"

`include "asim/provides/multifpga_router_service.bsh"

// some useful modules




`ifdef ROUTING_KNOWN
    `include "multifpga_routing.bsh"
`else
    // define a null routing module
     module [CONNECTED_MODULE] mkCommunicationModule#(VIRTUAL_PLATFORM vplat) (Empty);
         // Intentionally empty
     endmodule
`endif


module [CONNECTED_MODULE] mkMultifpgaRouterServices#(VIRTUAL_PLATFORM vplat) (Empty);
  let m <- mkCommunicationModule(vplat);
endmodule 