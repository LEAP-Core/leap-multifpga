`include "awb/provides/soft_connections.bsh"
`include "awb/provides/soft_services.bsh"
`include "awb/provides/test_d.bsh"
`include "awb/provides/test_common.bsh"

`define NUM_CONNS 2
`define WIDTH 32

module [CONNECTED_MODULE] mkA (Empty);
  for(Integer i=0; i < `NUM_CONNS; i = i + 1) 
    begin   
      mkForward("spiralOutAD" + integerToString(i),"spiralOutBA" + integerToString(i));
      mkForward("spiralInAB" + integerToString(i),"spiralInDA" + integerToString(i));
    end
endmodule

