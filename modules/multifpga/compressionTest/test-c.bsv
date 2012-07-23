`include "awb/provides/soft_connections.bsh"
`include "awb/provides/soft_services.bsh"
`include "awb/dict/PARAMS_TEST_D.bsh"
`include "awb/provides/common_services.bsh"

`define NUM_CONNS 16
`define WIDTH 32

module [CONNECTED_MODULE] mkC (Empty);
    PARAMETER_NODE paramNode <- mkDynamicParameterNode();
    Param#(5) threshold <- mkDynamicParameter(`PARAMS_TEST_D_INVALID_THRESHOLD, paramNode);

    function Maybe#(Bit#(`WIDTH)) expected(Bit#(32) counter);
	let expectedResult = tagged Valid (truncate(counter));
	if(counter[4:0] < threshold)
	begin
	    expectedResult = tagged Invalid;
        end
	return expectedResult;
    endfunction

    for(Integer i=0; i < `NUM_CONNS; i = i + 1) 
    begin   
        Connection_Send#(Maybe#(Bit#(`WIDTH))) sendX <- mkConnection_Send("fromB" + integerToString(i+1));
        Connection_Receive#(Maybe#(Bit#(`WIDTH))) recvX <- mkConnection_Receive("fromD" + integerToString(i));

        Reg#(Bit#(32)) reflectCounter <- mkReg(0);
        rule reflect;
            sendX.send(recvX.receive);
            reflectCounter <= reflectCounter + 1;
            recvX.deq;
            $display("TESTC:  %d fired got %d", i, recvX.receive);
            if(recvX.receive != expected(reflectCounter))
            begin
                $display("Error (Module C) %d: got %d expected %d", i,  recvX.receive, reflectCounter);
                $finish;
            end
        endrule
    end
endmodule

