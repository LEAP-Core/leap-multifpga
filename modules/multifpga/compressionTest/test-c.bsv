`include "awb/provides/soft_connections.bsh"
`include "awb/provides/librl_bsv_base.bsh"
`include "awb/provides/soft_services.bsh"
`include "awb/dict/PARAMS_TEST_D.bsh"
`include "awb/provides/common_services.bsh"

`include "awb/provides/compress_common.bsh"
import LFSR::*;
import FIFO::*;

`define NUM_CONNS 2
`define WIDTH 32



module [CONNECTED_MODULE] mkC (Empty);
    PARAMETER_NODE paramNode <- mkDynamicParameterNode();
    Param#(5) threshold <- mkDynamicParameter(`PARAMS_TEST_D_INVALID_THRESHOLD, paramNode);

    Connection_Send#(UnionTest) testSend <- mkConnection_Send("fromB");
    Connection_Receive#(UnionTest) testRecv <- mkConnection_Receive("fromD");
    LFSR#(Bit#(32)) compressVal1 <- mkLFSR_32();					
    LFSR#(Bit#(32)) compressVal2 <- mkLFSR_32();						
    FIFO#(UnionTest) compressFIFO <- mkSizedFIFO(8);  

    rule sendCompress;
    	UnionTest value = unpack(truncate({compressVal1.value, compressVal2.value}));
        testSend.send(value);
	compressFIFO.enq(value);
	compressVal1.next();
	compressVal2.next();
	$display("Compress Test Sending: %h", value);
    endrule

    rule recvCompress;
       let incoming = testRecv.receive();
       if(incoming != compressFIFO.first)
       begin
           $display("Compress Test: got %h expected %h", incoming, compressFIFO.first);
	   $finish;
       end
       $display("Compress Test: got %h expected %h", incoming, compressFIFO.first);
       testRecv.deq;
       compressFIFO.deq;
    endrule


    function UNBALANCED_MAYBE#(Bit#(`WIDTH)) expected(Bit#(32) counter);
	UNBALANCED_MAYBE#(Bit#(`WIDTH)) expectedResult = tagged UnbalancedValid (truncate(counter));
	if(counter[4:0] < threshold)
	begin
	    expectedResult = tagged UnbalancedInvalid;
        end
	return expectedResult;
    endfunction

    for(Integer i=0; i < `NUM_CONNS; i = i + 1) 
    begin   
        Connection_Send#(UNBALANCED_MAYBE#(Bit#(`WIDTH))) sendX <- mkConnection_Send("fromB" + integerToString(i+1));
        Connection_Receive#(UNBALANCED_MAYBE#(Bit#(`WIDTH))) recvX <- mkConnection_Receive("fromD" + integerToString(i));

        LFSR#(Bit#(32)) reflectCounter <- mkLFSR_32();
        rule reflect;
            sendX.send(recvX.receive);
            reflectCounter.next;
            recvX.deq;
            $display("TESTC:  %d fired got %d", i, recvX.receive);
            if(recvX.receive != expected(reflectCounter.value))
            begin
                $display("Error (Module C) %d: got %h expected %h", i,  recvX.receive, expected(reflectCounter.value));
                $finish;
            end
        endrule
    end
endmodule

