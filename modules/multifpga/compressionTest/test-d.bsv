`include "awb/provides/soft_connections.bsh"
`include "awb/provides/soft_services.bsh"
`include "awb/provides/librl_bsv_base.bsh"
`include "awb/provides/dynamic_parameters_service.bsh"
`include "awb/rrr/remote_server_stub_TESTDRRR.bsh"
`include "awb/dict/PARAMS_TEST_D.bsh"
`include "awb/provides/common_services.bsh"
`include "awb/provides/compress_common.bsh"

import LFSR::*;
import FIFO::*;

`define NUM_CONNS 2
`define WIDTH 32



module [CONNECTED_MODULE] mkD (Empty);

    ServerStub_TESTDRRR serverStub <- mkServerStub_TESTDRRR();

    PARAMETER_NODE paramNode <- mkDynamicParameterNode();
    Param#(5) threshold <- mkDynamicParameter(`PARAMS_TEST_D_INVALID_THRESHOLD, paramNode);

    Connection_Receive#(UnionTest) testRecv <- mkConnection_Receive("fromB");
    Connection_Send#(UnionTest) testSend <- mkConnection_Send("fromD");
    LFSR#(Bit#(32)) compressVal1 <- mkLFSR_32();					
    LFSR#(Bit#(32)) compressVal2 <- mkLFSR_32();					
  

    rule reflectCompress;
       let incoming = testRecv.receive();
       UnionTest value = unpack(truncate({compressVal1.value,compressVal2.value}));
       if(incoming != value)
       begin
           $display("Compress Test Reflect: got %h expected %h", incoming, value);
	   $finish;
       end

       $display("Compress Test Reflect: got %h expected %h", incoming, value);	
       testRecv.deq;
       compressVal1.next;
       compressVal2.next;	
       testSend.send(incoming);
    endrule


    function UNBALANCED_MAYBE#(Bit#(`WIDTH)) expected(Bit#(32) counter);
	UNBALANCED_MAYBE#(Bit#(`WIDTH)) expectedResult = tagged UnbalancedValid (truncate(counter));
	if(counter[4:0] < threshold)
	begin
	    expectedResult = tagged UnbalancedInvalid;
        end
	return expectedResult;
    endfunction

    Connection_Send#(UNBALANCED_MAYBE#(Bit#(`WIDTH))) send0 <- mkConnection_Send("fromD0");
    Connection_Receive#(UNBALANCED_MAYBE#(Bit#(`WIDTH))) recvLast <- mkConnection_Receive("fromB" + integerToString(`NUM_CONNS));

    Reg#(Bit#(32)) testLength <- mkReg(0);
    Reg#(Bit#(32)) counter    <- mkReg(0);
    Reg#(Bit#(32)) rxCounter  <- mkReg(0);
    LFSR#(Bit#(32)) srcLFSR   <- mkLFSR_32();
    LFSR#(Bit#(32)) sinkLFSR  <- mkLFSR_32();
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
        $display("TESTD: Got length %d", length);
    endrule

    rule tokenSts(counter < testLength);
        counter <= counter + 1;
	srcLFSR.next();
	send0.send(expected(srcLFSR.value()));       
        $display("TESTD: sends %h", expected(srcLFSR.value()));
    endrule

    rule sinkLast;
        rxCounter <= rxCounter + 1;
        recvLast.deq;
	sinkLFSR.next();
        if(recvLast.receive != expected(sinkLFSR.value()))
        begin
            $display("Error last: got %h expected %h", recvLast.receive, expected(sinkLFSR.value()));
            errors <= errors + 1;
        end

        $display("TESTD: got %h expected %h", recvLast.receive, rxCounter);

        if(rxCounter + 1 == testLength)
        begin
            $display("TESTD: PASSED");
            serverStub.sendResponse_RunTest(errors,cycles.value); 
        end 
  endrule


  for(Integer i=1; i < `NUM_CONNS; i = i + 1) 
    begin   
      Connection_Send#(UNBALANCED_MAYBE#(Bit#(`WIDTH))) sendX <- mkConnection_Send("fromD" + integerToString(i));
      Connection_Receive#(UNBALANCED_MAYBE#(Bit#(`WIDTH))) recvX <- mkConnection_Receive("fromB" + integerToString(i));
      LFSR#(Bit#(32)) reflectCounter <- mkLFSR_32();
      rule reflect;
         sendX.send(recvX.receive);
         reflectCounter.next();
         recvX.deq;
         $display("TESTD:  %d fired got %d", i, recvX.receive);
         if(recvX.receive != expected(reflectCounter.value()))
           begin
             $display("Error (Module D) %d: got %d expected %d", i,  recvX.receive, expected(reflectCounter.value()));
             $finish;
           end
      endrule
    end

endmodule


