`include "awb/provides/soft_connections.bsh"
`include "awb/provides/soft_services.bsh"

`define NUM_CONNS 16
`define WIDTH 32

module [CONNECTED_MODULE] mkC (Empty);
  Connection_Send#(Bit#(250)) sendX <- mkConnection_Send("Test");

  for(Integer i=0; i < `NUM_CONNS; i = i + 1) 
    begin   
      Connection_Send#(Bit#(`WIDTH)) sendX <- mkConnection_Send("fromB" + integerToString(i+1));
      Connection_Receive#(Bit#(`WIDTH)) recvX <- mkConnection_Receive("fromD" + integerToString(i));
      Reg#(Bit#(32)) reflectCounter <- mkReg(0);
      rule reflect;
         sendX.send(recvX.receive);
         reflectCounter <= reflectCounter + 1;
         recvX.deq;
         $display("TESTC:  %d fired got %d", i, recvX.receive);
         if(truncate(recvX.receive) != reflectCounter)
           begin
             $display("Error (Module C) %d: got %d expected %d", i,  recvX.receive, reflectCounter);
             $finish;
           end
      endrule
    end
endmodule

