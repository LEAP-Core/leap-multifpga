`include "asim/provides/soft_connections.bsh"
`include "asim/dict/STATS_TESTC.bsh"
`include "asim/provides/stats_service.bsh"
`include "awb/provides/librl_bsv_base.bsh"

module [CONNECTED_MODULE] mkC (Empty);
  Connection_Receive#(Bit#(32)) aliveIn <- mkConnection_Receive("fromD");
  Connection_Send#(Bit#(32)) aliveOut <- mkConnection_Send("fromB");
  STAT statCount  <- mkStatCounter(`STATS_TESTC_COUNT);


  rule sayHello;
    aliveIn.deq();
    aliveOut.send(aliveIn.receive() + 7);
    $display("FPGA0: %d + 7 = %d",aliveIn.receive(),aliveIn.receive()+7);
    statCount.incr;
  endrule

endmodule

