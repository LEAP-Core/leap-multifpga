import Vector::*;
import Complex::*;
import FixedPoint::*;
import FIFO::*;
import FIFOF::*;

`include "awb/provides/low_level_platform_interface.bsh"
`include "awb/provides/soft_connections.bsh"
`include "awb/provides/common_services.bsh"
`include "awb/provides/librl_bsv_base.bsh"
`include "awb/provides/librl_bsv_storage.bsh"
`include "asim/rrr/remote_server_stub_INTER_FPGA_TEST.bsh"

module [CONNECTED_MODULE] mkConnectedApplication (); 

  Connection_Send#(Tuple2#(Bit#(1), Bit#(15))) analogTX <- mkConnection_Send("InterFPGATX");
  Connection_Receive#(Tuple2#(Bit#(1), Bit#(15))) analogRX <- mkConnection_Receive("InterFPGARX");
  ServerStub_INTER_FPGA_TEST serverStub <- mkServerStub_INTER_FPGA_TEST();

  // Make these stats...
  Reg#(Bit#(64)) countCorrect <- mkReg(0);
  Reg#(Bit#(64)) countError <- mkReg(0);
  Reg#(Bit#(64)) countSent <- mkReg(0);
  Reg#(Bit#(64)) countReturned <- mkReg(0);

  Reg#(Bit#(15)) rxData <- mkReg(0);
  Reg#(Bit#(15)) rxDataLast <- mkReg(0);
  Reg#(Bit#(15)) rxDataLastLast <- mkReg(0);
  Reg#(Bit#(15)) txData <- mkReg(0);

  // Yes, we have to prevent deadlocks.
  FIFO#(Tuple2#(Bit#(1), Bit#(15))) rxBuffer <- mkSizedBRAMFIFO(512);
  FIFO#(Bit#(1)) txAllocation <- mkSizedBRAMFIFO(16);
  FIFOF#(Tuple2#(Bit#(15),Bit#(15))) errorFIFO <- mkSizedBRAMFIFOF(512);
  RWire#(Tuple2#(Bit#(15),Bit#(15))) errorWire <- mkRWire;

  // Handle RRR
  rule getCorrect;
    let dummy <- serverStub.acceptRequest_GetCorrect();
    serverStub.sendResponse_GetCorrect(countCorrect);
  endrule

  rule getError;
    let dummy <- serverStub.acceptRequest_GetError();
    serverStub.sendResponse_GetError(countError);
  endrule

  rule getSent;
    let dummy <- serverStub.acceptRequest_GetSent();
    serverStub.sendResponse_GetSent(countSent);
  endrule

  rule getReturned;
    let dummy <- serverStub.acceptRequest_GetReturned();
    serverStub.sendResponse_GetReturned(countReturned);
  endrule

  rule getErrorPair;
    let dummy <- serverStub.acceptRequest_GetErrorPair();
    serverStub.sendResponse_GetErrorPair({1'b0,pack(tpl_1(errorFIFO.first)),1'b0,pack(tpl_2(errorFIFO.first))});
    errorFIFO.deq;
  endrule

  rule getErrorPairTail(!errorFIFO.notEmpty);
    let dummy <- serverStub.acceptRequest_GetErrorPair();
    serverStub.sendResponse_GetErrorPair(pack(0));
  endrule

  rule storeErrors (errorWire.wget matches tagged Valid .pair);
    errorFIFO.enq(pair);
  endrule

  rule rxLinkMe(tpl_1(analogRX.receive) == `ID);
    analogRX.deq;
    txAllocation.deq;
    let data = tpl_2(analogRX.receive);
    rxData <= data + 1;
    rxDataLast <= data;
    rxDataLastLast <= rxDataLast;

    if(data == rxData || data == rxDataLast + 1 || data == rxDataLastLast + 2)
      begin
        countCorrect <= countCorrect + 1;
      end
    else
      begin
        countError <= countError + 1;
        errorWire.wset(tuple2(data,rxData));
      end
  endrule

  rule rxLinkOther(tpl_1(analogRX.receive) != `ID);
    analogRX.deq;
    rxBuffer.enq(analogRX.receive);
  endrule

  rule txLinkMe;
    analogTX.send(tuple2(`ID,txData)); // reflect the data back to the other guy
    txData <= txData + 1;
    txAllocation.enq(0);
    countSent <= countSent + 1();
  endrule

  rule txLinkOther;
    analogTX.send(rxBuffer.first); // reflect the data back to the other guy
    rxBuffer.deq;
    countReturned <= countReturned + 1;
  endrule

endmodule