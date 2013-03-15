import FIFO::*;

`include "awb/provides/soft_connections.bsh"
`include "awb/rrr/remote_server_stub_BASESTATIONRRR.bsh"
`include "awb/provides/fpga_components.bsh"
`include "awb/provides/librl_bsv_storage.bsh"
`include "awb/provides/throughput_repeater.bsh"

module [CONNECTED_MODULE] mkBasestation (Empty);

    ServerStub_BASESTATIONRRR serverStub <- mkServerStub_BASESTATIONRRR();

    // Grumble.  I wish I could write these in a for loop.
    Connection_Send#(Bit#(16)) aliveOut16 <- mkConnection_Send("16_0");
    Connection_Receive#(Bit#(16)) aliveIn16 <- mkConnection_Receive("16_" + integerToString(`NUM_REPEATERS));
    Connection_Send#(Bit#(32)) aliveOut32 <- mkConnection_Send("32_0");
    Connection_Receive#(Bit#(32)) aliveIn32 <- mkConnection_Receive("32_" + integerToString(`NUM_REPEATERS));
    Connection_Send#(Bit#(64)) aliveOut64 <- mkConnection_Send("64_0");
    Connection_Receive#(Bit#(64)) aliveIn64 <- mkConnection_Receive("64_" + integerToString(`NUM_REPEATERS));
    Connection_Send#(Bit#(128)) aliveOut128 <- mkConnection_Send("128_0");
    Connection_Receive#(Bit#(128)) aliveIn128 <- mkConnection_Receive("128_" + integerToString(`NUM_REPEATERS));
    Connection_Send#(Bit#(256)) aliveOut256 <- mkConnection_Send("256_0");
    Connection_Receive#(Bit#(256)) aliveIn256 <- mkConnection_Receive("256_" + integerToString(`NUM_REPEATERS));

    Reg#(Bit#(48)) ticks       <- mkReg(0);
    Reg#(Bit#(32)) errors      <- mkReg(0);
    Reg#(Bit#(48)) testStart   <- mkReg(0);
    Reg#(Bit#(48)) testLatency <- mkReg(0);
    Reg#(Bit#(32)) testWidth   <- mkReg(0);
    Reg#(Bit#(32)) testTX      <- mkReg(0);
    Reg#(Bit#(32)) testRX      <- mkReg(0);

    FIFO#(Bit#(48)) latencyFIFO <- mkSizedBRAMFIFO(16384); //Make this big in case we have a lot of inter-fpga latency. Each K covers ~1us of latency

    rule tickUp;
      ticks <= ticks + 1;
    endrule
  

    rule sendBiscuit (testTX == 0 && testRX == 0);
        $display("Starting the test");
        let data <- serverStub.acceptRequest_RunTest();
        testWidth <= data.width;
        testTX <= data.count;
        testRX <= data.count;
	testStart <= ticks;
	errors <= 0;
        testLatency <= 0;
    endrule
  
    rule tx16(testWidth == 16 && testTX > 0);
        aliveOut16.send(truncate(testTX));
   	testTX <= testTX - 1;
        $display("Sending test 16 %d",testTX);
        latencyFIFO.enq(ticks);
    endrule

    rule rx16(testWidth == 16 && testRX > 0);
    	aliveIn16.deq();
        if(aliveIn16.receive() != (truncate(testRX)))
	begin
	    errors <= errors + 1;
        end

        latencyFIFO.deq;

        testLatency <= testLatency + (ticks - latencyFIFO.first());

	if(testRX - 1 == 0)  
	begin
            serverStub.sendResponse_RunTest(zeroExtend(ticks - testStart),zeroExtend(testLatency + (ticks - latencyFIFO.first())),errors);
        end

        $display("Receiving test 16 %d",testTX);

   	testRX <= testRX - 1;
    endrule



    rule tx32(testWidth == 32 && testTX > 0);
        aliveOut32.send(truncate(testTX));
   	testTX <= testTX - 1;
        latencyFIFO.enq(ticks);
    endrule

    rule rx32(testWidth == 32 && testRX > 0);
    	aliveIn32.deq();
        if(aliveIn32.receive() != (truncate(testRX)))
	begin
	    errors <= errors + 1;
        end

        latencyFIFO.deq;

        testLatency <= testLatency + (ticks - latencyFIFO.first());

	if(testRX - 1 == 0)  
	begin
            serverStub.sendResponse_RunTest(zeroExtend(ticks - testStart),zeroExtend(testLatency + (ticks - latencyFIFO.first())),errors);
        end

   	testRX <= testRX - 1;
    endrule



    rule tx64(testWidth == 64 && testTX > 0);
        aliveOut64.send(zeroExtend(testTX));
   	testTX <= testTX - 1;
        latencyFIFO.enq(ticks);
    endrule

    rule rx64(testWidth == 64 && testRX > 0);
    	aliveIn64.deq();
        if(aliveIn64.receive() != (zeroExtend(testRX)))
	begin
	    errors <= errors + 1;
        end

        latencyFIFO.deq;

        testLatency <= testLatency + (ticks - latencyFIFO.first());

	if(testRX - 1 == 0)  
	begin
            serverStub.sendResponse_RunTest(zeroExtend(ticks - testStart),zeroExtend(testLatency + (ticks - latencyFIFO.first())),errors);
        end

   	testRX <= testRX - 1;
    endrule



    rule tx128(testWidth == 128 && testTX > 0);
        aliveOut128.send(zeroExtend(testTX));
   	testTX <= testTX - 1;
        latencyFIFO.enq(ticks);
    endrule

    rule rx128(testWidth == 128 && testRX > 0);
    	aliveIn128.deq();
        if(aliveIn128.receive() != (zeroExtend(testRX)))
	begin
	    errors <= errors + 1;
        end

        latencyFIFO.deq;

        testLatency <= testLatency + (ticks - latencyFIFO.first());

	if(testRX - 1 == 0)  
	begin
            serverStub.sendResponse_RunTest(zeroExtend(ticks - testStart),zeroExtend(testLatency + (ticks - latencyFIFO.first())),errors);
        end

   	testRX <= testRX - 1;
    endrule


    rule tx256(testWidth == 256 && testTX > 0);
        aliveOut256.send(zeroExtend(testTX));
   	testTX <= testTX - 1;
        latencyFIFO.enq(ticks);
    endrule

    rule rx256(testWidth == 256 && testRX > 0);
    	aliveIn256.deq();
        if(aliveIn256.receive() != (zeroExtend(testRX)))
	begin
	    errors <= errors + 1;
        end

        latencyFIFO.deq;

        testLatency <= testLatency + (ticks - latencyFIFO.first());

	if(testRX - 1 == 0)  
	begin
            serverStub.sendResponse_RunTest(zeroExtend(ticks - testStart),zeroExtend(testLatency + (ticks - latencyFIFO.first())),errors);
        end

   	testRX <= testRX - 1;
    endrule

endmodule

