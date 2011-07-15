`include "asim/provides/soft_connections.bsh"
`include "awb/rrr/remote_server_stub_TESTDRRR.bsh"

module [CONNECTED_MODULE] mkD (Empty);

  ServerStub_TESTDRRR serverStub <- mkServerStub_TESTDRRR();

  Connection_Send#(Bit#(32)) aliveOut <- mkConnection_Send("fromD");
  Connection_Receive#(Bit#(32)) aliveIn <- mkConnection_Receive("fromB");

  Reg#(Bit#(32)) ticks <- mkReg(0);

  rule tickUp;
    ticks <= ticks +1;
  endrule
  

  rule sendBiscuit;
    let data <- serverStub.acceptRequest_TakeOneInput();
    aliveOut.send(ticks);
    $display("FPGA1 sends the biscuit");
  endrule
  
  rule sayHello;
    aliveIn.deq();
    serverStub.sendResponse_TakeOneInput(ticks - aliveIn.receive);    
  endrule

endmodule

