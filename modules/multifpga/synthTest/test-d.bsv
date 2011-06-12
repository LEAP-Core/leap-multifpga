`include "asim/provides/soft_connections.bsh"

module [CONNECTED_MODULE] mkD (Empty);
  Connection_Send#(Bool) aliveOut <- mkConnection_Send("fromD");
  Connection_Receive#(Bool) aliveIn <- mkConnection_Receive("fromB");

  Reg#(Bool) sendToken <- mkReg(True);
  
  rule sendBiscuit(sendToken);
    sendToken <= False;
    aliveOut.send(True);
    $display("FPGA1 sends the biscuit");
  endrule
  
  rule sayHello;
    aliveIn.deq();
    aliveOut.send(True);
    $display("FPGA1 says Wazzup!");
  endrule

endmodule

