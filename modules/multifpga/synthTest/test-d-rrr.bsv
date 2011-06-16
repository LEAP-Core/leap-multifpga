`include "awb/provides/soft_connections.bsh"
`include "awb/rrr/remote_server_stub_TESTDRRR.bsh"


module [CONNECTED_MODULE] mkD (Empty);

  ServerStub_TESTDRRR serverStub <- mkServerStub_TESTDRRR();

  Connection_Send#(Bit#(32)) aliveOut <- mkConnection_Send("fromD");
  Connection_Receive#(Bit#(32)) aliveIn <- mkConnection_Receive("fromB");

  rule getFromSW;
    let data <- serverStub.acceptRequest_TakeOneInput();
    aliveOut.send(data);
    $display("FPGA1 Takes request: %d", data);
  endrule
  
  rule sendToSW;
    aliveIn.deq();
    serverStub.sendResponse_TakeOneInput(aliveIn.receive);    
    $display("FPGA1 Gets Response: %d", aliveIn.receive);
  endrule

endmodule

