`include "asim/provides/soft_connections.bsh"

module [CONNECTED_MODULE] mkC (Empty);
  Connection_Receive#(Bit#(32)) aliveIn <- mkConnection_Receive("fromD");
  Connection_Send#(Bit#(32)) aliveOut <- mkConnection_Send("fromB");

  rule sayHello;
    aliveIn.deq();
    aliveOut.send(aliveIn.receive() + 7);
    $display("FPGA0: %d + 7 = %d",aliveIn.receive(),aliveIn.receive()+7);
  endrule

endmodule

