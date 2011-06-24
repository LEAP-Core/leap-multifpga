`include "awb/provides/soft_connections.bsh"
`include "awb/rrr/remote_server_stub_TESTDRRR.bsh"
`include "asim/dict/STATS_TESTD.bsh"
`include "asim/provides/stats_service.bsh"
`include "awb/provides/librl_bsv_base.bsh"


module [CONNECTED_MODULE] mkD (Empty);

  ServerStub_TESTDRRR serverStub <- mkServerStub_TESTDRRR();

  Connection_Send#(Bit#(32)) aliveOut <- mkConnection_Send("fromD");
  Connection_Receive#(Bit#(32)) aliveIn <- mkConnection_Receive("fromB");
  STAT statCount  <- mkStatCounter(`STATS_TESTD_COUNT);

  rule getFromSW;
    let data <- serverStub.acceptRequest_TakeOneInput();
    aliveOut.send(data);
    $display("FPGA1 Takes request: %d", data);
    statCount.incr;
  endrule
  
  rule sendToSW;
    aliveIn.deq();
    serverStub.sendResponse_TakeOneInput(aliveIn.receive);    
    $display("FPGA1 Gets Response: %d", aliveIn.receive);
    statCount.incr;
  endrule

endmodule

