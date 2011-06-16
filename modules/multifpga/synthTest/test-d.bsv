`include "asim/provides/soft_connections.bsh"

module [CONNECTED_MODULE] mkD (Empty);
  Connection_Send#(Bit#(32)) aliveOut <- mkConnection_Send("fromD");
  Connection_Receive#(Bit#(32)) aliveIn <- mkConnection_Receive("fromB");

  Reg#(Bool) sendToken <- mkReg(True);
  
  rule sendBiscuit(sendToken);
    sendToken <= False;
    aliveOut.send(0);
    $display("FPGA1 sends the biscuit");
  endrule
  
  rule sayHello;
    aliveIn.deq();
    aliveOut.send(aliveIn.receive);
    $display("FPGA1 says Wazzup!");
  endrule

endmodule

