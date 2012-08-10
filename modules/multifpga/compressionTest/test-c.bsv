`include "awb/provides/soft_connections.bsh"
`include "awb/provides/librl_bsv_base.bsh"
`include "awb/provides/soft_services.bsh"
`include "awb/dict/PARAMS_TEST_D.bsh"
`include "awb/provides/common_services.bsh"
import LFSR::*;

`define NUM_CONNS 2
`define WIDTH 32

module [CONNECTED_MODULE] mkC (Empty);
    PARAMETER_NODE paramNode <- mkDynamicParameterNode();
    Param#(5) threshold <- mkDynamicParameter(`PARAMS_TEST_D_INVALID_THRESHOLD, paramNode);

    function UnbalancedMaybe#(Bit#(`WIDTH)) expected(Bit#(32) counter);
	UnbalancedMaybe#(Bit#(`WIDTH)) expectedResult = tagged UnbalancedValid (truncate(counter));
	if(counter[4:0] < threshold)
	begin
	    expectedResult = tagged UnbalancedInvalid;
        end
	return expectedResult;
    endfunction

    for(Integer i=0; i < `NUM_CONNS; i = i + 1) 
    begin   
        Connection_Send#(UnbalancedMaybe#(Bit#(`WIDTH))) sendX <- mkConnection_Send("fromB" + integerToString(i+1));
        Connection_Receive#(UnbalancedMaybe#(Bit#(`WIDTH))) recvX <- mkConnection_Receive("fromD" + integerToString(i));

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

