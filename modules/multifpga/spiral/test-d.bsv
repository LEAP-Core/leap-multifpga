`include "awb/provides/soft_connections.bsh"
`include "awb/provides/soft_services.bsh"
`include "awb/provides/librl_bsv_base.bsh"
`include "awb/provides/test_common.bsh"
`include "awb/provides/dynamic_parameters_service.bsh"
`include "awb/rrr/remote_server_stub_TESTDRRR.bsh"


`define NUM_CONNS 2
`define WIDTH 32


module [CONNECTED_MODULE] mkD (Empty);

    ServerStub_TESTDRRR serverStub <- mkServerStub_TESTDRRR();

    Connection_Send#(Bit#(`WIDTH)) send0 <- mkConnection_Send("spiralOutDC0");
    Connection_Receive#(Bit#(`WIDTH)) recvLast <- mkConnection_Receive("spiralInCD" + integerToString(`NUM_CONNS - 1));

    Reg#(Bit#(32)) testLength <- mkReg(0);
    Reg#(Bit#(32)) counter    <- mkReg(0);
    Reg#(Bit#(32)) rxCounter  <- mkReg(0);
    Reg#(Bit#(32)) errors     <- mkReg(0);
    COUNTER#(32) cycles <- mkLCounter(0);

    rule count;
      cycles.up();
    endrule

    rule startTest(testLength == 0);
        let length <- serverStub.acceptRequest_RunTest();    
        testLength <= length;
        counter <= 0;
        errors <= 0;
        cycles.setC(0);
        rxCounter <= 0;
        //$display("TESTD: Got length %d", length);
    endrule

    rule tokenSts(counter < testLength);
        counter <= counter + 1;
        send0.send(truncate(counter));       
        //$display("TESTD: sends %d", counter);
    endrule

    rule sinkLast;
        rxCounter <= rxCounter + 1;
        recvLast.deq;
        if(truncate(recvLast.receive) != rxCounter)
        begin
            $display("Error last: got %d expected %d", recvLast.receive, rxCounter);
            errors <= errors + 1;
        end

        
        if(rxCounter + 1 == testLength)
        begin
            $display("TESTD: PASSED");
            serverStub.sendResponse_RunTest(errors,cycles.value); 
        end 
  endrule


  //Handle the base case
  for(Integer i=0; i < `NUM_CONNS-1; i = i + 1) 
    begin   
      Connection_Send#(Bit#(`WIDTH)) sendX <- mkConnection_Send("spiralOutDC" + integerToString(i+1));
      Connection_Receive#(Bit#(`WIDTH)) recvX <- mkConnection_Receive("spiralInCD" + integerToString(i));
      Reg#(Bit#(32)) reflectCounter <- mkReg(0);
      rule reflect;
         sendX.send(recvX.receive);
         reflectCounter <= reflectCounter + 1;
         recvX.deq;
         $display("TESTD:  %d fired got %d", i, recvX.receive);
         if(truncate(recvX.receive) != reflectCounter)
           begin
             $display("Error (Module D) %d: got %d expected %d", i,  recvX.receive, reflectCounter);
             $finish;
           end
      endrule
    end

  for(Integer i=0; i < `NUM_CONNS; i = i + 1) 
    begin   
      mkForward("spiralInDA" + integerToString(i),"spiralOutAD" + integerToString(i));
    end

endmodule


