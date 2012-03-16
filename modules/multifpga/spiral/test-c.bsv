`include "awb/provides/soft_connections.bsh"
`include "awb/provides/soft_services.bsh"
`include "awb/provides/test_d.bsh"
`include "awb/provides/test_common.bsh"

`define NUM_CONNS 2
`define WIDTH 32

module [CONNECTED_MODULE] mkC (Empty);
  for(Integer i=0; i < `NUM_CONNS; i = i + 1) 
    begin   
      mkForward("spiralOutCB" + integerToString(i),"spiralOutDC" + integerToString(i));
      mkForward("spiralInCD" + integerToString(i),"spiralInBC" + integerToString(i));
    end
endmodule

