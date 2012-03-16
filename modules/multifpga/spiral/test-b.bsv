`include "awb/provides/soft_connections.bsh"
`include "awb/provides/soft_services.bsh"
`include "awb/provides/test_d.bsh"
`include "awb/provides/test_common.bsh"

`define NUM_CONNS 2


module [CONNECTED_MODULE] mkB (Empty);
  for(Integer i=0; i < `NUM_CONNS; i = i + 1) 
    begin   
      mkForward("spiralOutBA" + integerToString(i),"spiralOutCB" + integerToString(i));
      mkForward("spiralInBC" + integerToString(i),"spiralInAB" + integerToString(i));
    end
endmodule

