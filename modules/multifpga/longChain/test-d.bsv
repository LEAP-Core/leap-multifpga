`include "awb/provides/soft_connections.bsh"
`include "awb/provides/soft_services.bsh"

`define NUM_CONNS 16
`define WIDTH 32

module [CONNECTED_MODULE] mkD (Empty);
     
  Connection_Send#(Bit#(`WIDTH)) send0 <- mkConnection_Send("fromD0");
  Connection_Receive#(Bit#(`WIDTH)) recvLast <- mkConnection_Receive("fromB" + integerToString(`NUM_CONNS));
  Reg#(Bit#(10)) counter   <- mkReg(0);
  Reg#(Bit#(10)) rxCounter <- mkReg(0);


  rule tokenSts;
     counter <= counter + 1;
     send0.send(signExtend(counter));
  endrule

  rule sinkLast;
    rxCounter <= rxCounter + 1;
    recvLast.deq;
    if(truncate(recvLast.receive) != rxCounter)
      begin
        $display("Error last: got %d expected %d", recvLast.receive, rxCounter);
        $finish;
      end
    if(rxCounter + 1 == 0)
      begin
         $display("PASSED");
        $finish;
      end 
  endrule


  for(Integer i=1; i < `NUM_CONNS; i = i + 1) 
    begin   
      Connection_Send#(Bit#(`WIDTH)) sendX <- mkConnection_Send("fromD" + integerToString(i));
      Connection_Receive#(Bit#(`WIDTH)) recvX <- mkConnection_Receive("fromB" + integerToString(i));
      Reg#(Bit#(10)) reflectCounter <- mkReg(0);
      rule reflect;
         sendX.send(recvX.receive);
         reflectCounter <= reflectCounter + 1;
         recvX.deq;
         if(truncate(recvX.receive) != reflectCounter)
           begin
             $display("Error (Module D) %d: got %d expected %d", i,  recvX.receive, reflectCounter);
             $finish;
           end
      endrule
    end

endmodule


