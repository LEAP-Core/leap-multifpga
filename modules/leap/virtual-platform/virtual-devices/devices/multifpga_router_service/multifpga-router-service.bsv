`include "asim/provides/virtual_platform.bsh"
`include "asim/provides/virtual_devices.bsh"
`include "asim/provides/low_level_platform_interface.bsh"
`include "asim/provides/rrr.bsh"
`include "asim/provides/umf.bsh"
`include "asim/provides/channelio.bsh"
`include "asim/provides/physical_platform.bsh"
`include "asim/provides/soft_connections.bsh"

`include "asim/provides/multifpga_router_service.bsh"

`ifdef ROUTING_KNOWN
    `include "multifpga_routing.bsh"
`else
    // define a null routing module
     module [CONNECTED_MODULE] mkCommunicationModule#(VIRTUAL_PLATFORM vplat) (Empty);
         // Intentionally empty
     endmodule
`endif
 
//XXX insert module for creating umf packets here.



module [CONNECTED_MODULE] mkMultifpgaRouterServices#(VIRTUAL_PLATFORM vplat) (Empty);
  let m <- mkCommunicationModule(vplat);
endmodule 