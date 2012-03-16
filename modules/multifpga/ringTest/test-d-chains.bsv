import FIFO::*;

`include "awb/provides/soft_connections.bsh"
`include "awb/rrr/remote_server_stub_TESTDRRR.bsh"
`include "asim/dict/STATS_TESTD.bsh"
`include "asim/provides/stats_service.bsh"
`include "awb/provides/librl_bsv_base.bsh"


module [CONNECTED_MODULE] mkD (Empty);

  ServerStub_TESTDRRR serverStub <- mkServerStub_TESTDRRR();

  STAT statCount  <- mkStatCounter(`STATS_TESTD_COUNT);
  CONNECTION_ADDR_RING#(Bit#(1), Bit#(32)) node <- mkConnectionAddrRingNode("TestRing",0);
  CONNECTION_ADDR_RING#(Bit#(1), Bit#(320)) nodeWide <- mkConnectionAddrRingNode("TestRingWide",0);
  FIFO#(Bit#(32)) dataFIFO <- mkFIFO;

  rule getFromSW(node.notFull);
    let data <- serverStub.acceptRequest_TakeOneInput();
    node.enq(1,data);
    nodeWide.enq(1,zeroExtend(data));
    statCount.incr;
    dataFIFO.enq(data);
    $display("FPGA1 send: %d", data);
  endrule
  
  rule sendToSW(node.notEmpty());
    node.deq();
    nodeWide.deq();
    dataFIFO.deq; 
    if((node.first != truncate(nodeWide.first())) || 
       (node.first != dataFIFO.first + 7)) 
    begin
      $display("Data mismatch %d %d %d", node.first, nodeWide.first, dataFIFO.first);
      $finish;
    end
    $display("Data %d %d %d", node.first, nodeWide.first, dataFIFO.first);
    $display("FPGA1 Gets Response: %d", node.first);
    serverStub.sendResponse_TakeOneInput(node.first);
    statCount.incr;
  endrule

endmodule

