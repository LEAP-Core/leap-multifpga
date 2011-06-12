`include "asim/provides/soft_connections.bsh"

module [CONNECTED_MODULE] mkC (Empty);
  Connection_Receive#(Bool) aliveIn <- mkConnection_Receive("fromD");
  Connection_Send#(Bool) aliveOut <- mkConnection_Send("fromB");

  rule sayHello;
    aliveIn.deq();
    aliveOut.send(True);
    $display("FPGA0 says Wazzup!");
  endrule

endmodule

