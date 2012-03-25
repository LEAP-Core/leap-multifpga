`include "awb/provides/soft_connections.bsh"
`include "awb/rrr/remote_server_stub_TESTDRRR.bsh"
`include "asim/provides/stats_service.bsh"
`include "awb/provides/librl_bsv_base.bsh"


module [CONNECTED_MODULE] mkD (Empty);

  ServerStub_TESTDRRR serverStub <- mkServerStub_TESTDRRR();

  Connection_Send#(Bit#(32)) aliveOut <- mkConnection_Send("fromD");
  Connection_Receive#(Bit#(32)) aliveIn <- mkConnection_Receive("fromB");
  Connection_Send#(Bit#(320)) aliveOutWide <- mkConnection_Send("fromD_Wide");
  Connection_Receive#(Bit#(320)) aliveInWide <- mkConnection_Receive("fromB_Wide");
  STAT statCount <- mkStatCounter(statName("TESTD_COUNT", "Number of values processed by test d"));

  rule getFromSW;
    let data <- serverStub.acceptRequest_TakeOneInput();
    aliveOut.send(data);
    aliveOutWide.send(zeroExtend(data));
    $display("FPGA1 Takes request: %d", data);
    statCount.incr;
  endrule
  
  rule sendToSW;
    aliveIn.deq();
    aliveInWide.deq();
    serverStub.sendResponse_TakeOneInput(aliveIn.receive & truncate(aliveInWide.receive));    
    $display("FPGA1 Gets Response: %d", aliveIn.receive);

    if(aliveIn.receive != truncate(aliveInWide.receive))
      begin
        $display("Error %d != %d", aliveIn.receive, aliveInWide.receive);
        $finish;
      end
    statCount.incr;
  endrule

endmodule

