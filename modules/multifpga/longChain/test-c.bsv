`include "awb/provides/soft_connections.bsh"
`include "awb/provides/soft_services.bsh"

`define NUM_CONNS 16
`define WIDTH 32

module [CONNECTED_MODULE] mkC (Empty);
  for(Integer i=0; i < `NUM_CONNS; i = i + 1) 
    begin   
      Connection_Send#(Bit#(`WIDTH)) sendX <- mkConnection_Send("fromB" + integerToString(i+1));
      Connection_Receive#(Bit#(`WIDTH)) recvX <- mkConnection_Receive("fromD" + integerToString(i));
      Reg#(Bit#(10)) reflectCounter <- mkReg(0);
      rule reflect;
         sendX.send(recvX.receive);
         reflectCounter <= reflectCounter + 1;
         recvX.deq;
         if(truncate(recvX.receive) != reflectCounter)
           begin
             $display("Error (Module C) %d: got %d expected %d", i,  recvX.receive, reflectCounter);
             $finish;
           end
      endrule
    end
endmodule

