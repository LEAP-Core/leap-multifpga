`include "asim/provides/soft_connections.bsh"
`include "asim/provides/stats_service.bsh"
`include "awb/provides/librl_bsv_base.bsh"

module [CONNECTED_MODULE] mkC (Empty);

  CONNECTION_ADDR_RING#(Bit#(1), Bit#(32)) node <- mkConnectionAddrRingNode("TestRing",1);
  CONNECTION_ADDR_RING#(Bit#(1), Bit#(320)) nodeWide <- mkConnectionAddrRingNode("TestRingWide",1);
  STAT statCount <- mkStatCounter(statName("TESTC_COUNT", "Number of values processed by test c"));

  rule sayHello;
    node.deq;
    nodeWide.deq;
    node.enq(0,node.first + 7);
    nodeWide.enq(0,nodeWide.first + 7);
    statCount.incr;
  endrule

endmodule

