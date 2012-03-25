`include "asim/provides/soft_connections.bsh"
`include "asim/provides/stats_service.bsh"
`include "awb/provides/librl_bsv_base.bsh"

module [CONNECTED_MODULE] mkC (Empty);
  Connection_Receive#(Bit#(32)) aliveIn <- mkConnection_Receive("fromD");
  Connection_Send#(Bit#(32)) aliveOut <- mkConnection_Send("fromB");
  Connection_Receive#(Bit#(320)) aliveInWide <- mkConnection_Receive("fromD_Wide");
  Connection_Send#(Bit#(320)) aliveOutWide <- mkConnection_Send("fromB_Wide");
  STAT statCount <- mkStatCounter(statName("TESTC_COUNT", "Number of values processed by test c"));


  rule sayHello;
    aliveIn.deq();
    aliveOut.send(aliveIn.receive() + 7);
    aliveInWide.deq();
    aliveOutWide.send(aliveInWide.receive() + 7);
    $display("FPGA0: %d + 7 = %d",aliveIn.receive(),aliveIn.receive()+7);
    statCount.incr;
  endrule

endmodule

