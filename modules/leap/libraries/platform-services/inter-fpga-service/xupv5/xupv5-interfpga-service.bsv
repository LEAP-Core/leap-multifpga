//
// Copyright (c) 2014, Intel Corporation
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
// Redistributions of source code must retain the above copyright notice, this
// list of conditions and the following disclaimer.
//
// Redistributions in binary form must reproduce the above copyright notice,
// this list of conditions and the following disclaimer in the documentation
// and/or other materials provided with the distribution.
//
// Neither the name of the Intel Corporation nor the names of its contributors
// may be used to endorse or promote products derived from this software
// without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
// ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
// LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
// CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
// SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
// INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
// CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
// POSSIBILITY OF SUCH DAMAGE.
//

import FIFOF::*;
import GetPut::*;
import Connectable::*;
import CBus::*;
import Clocks::*;
import FIFO::*;
import FixedPoint::*;
import Complex::*;

`include "asim/provides/low_level_platform_interface.bsh"
`include "asim/provides/physical_platform.bsh"
//`include "asim/provides/sata_device.bsh"
`include "asim/provides/soft_services.bsh"
`include "asim/provides/soft_connections.bsh"
`include "asim/provides/soft_clocks.bsh"
`include "asim/provides/clocks_device.bsh"
`include "asim/provides/fpga_components.bsh"
`include "asim/provides/librl_bsv_storage.bsh"
`include "asim/provides/librl_bsv_base.bsh"
`include "asim/rrr/remote_server_stub_INTER_FPGA.bsh"


module [CONNECTED_MODULE] mkInterFPGAService#(PHYSICAL_DRIVERS drivers) (); 

   AURORA_DRIVER       auroraDriver = drivers.auroraDriver;
   ServerStub_INTER_FPGA serverStub <- mkServerStub_INTER_FPGA();

   FIFOF#(Bit#(16)) serdes_infifo <- mkSizedBRAMFIFOF(64);

   // make soft connections to PHY
   Connection_Send#(Tuple2#(Bit#(1), Bit#(15))) analogRX <- mkConnection_Send("InterFPGARX");
   Reg#(Bit#(40)) rxCount <- mkReg(0);
   Reg#(Bit#(40)) sampleDropped <- mkReg(0);
   Reg#(Bit#(32)) realign <- mkReg(0);
   Reg#(Bit#(40)) sampleSent <- mkReg(0);
   
   rule getSampleRX;
     let dummy <- serverStub.acceptRequest_GetRXCount();
     serverStub.sendResponse_GetRXCount(zeroExtend(rxCount));
   endrule

   rule getPHYStatus;
     let dummy <- serverStub.acceptRequest_GetPHYStatus();
     Bit#(8) rx_fifo_count = zeroExtend(pack(auroraDriver.rx_fifo_count));
     Bit#(8) tx_fifo_count = zeroExtend(pack(auroraDriver.tx_fifo_count));
     serverStub.sendResponse_GetPHYStatus(zeroExtend({rx_fifo_count,
                                                      tx_fifo_count,
                                                      auroraDriver.channel_up,
                                                      auroraDriver.lane_up,
                                                      auroraDriver.hard_err,
                                                      auroraDriver.soft_err,
                                                      auroraDriver.status}));
   endrule

   rule getPHYTX;
     let dummy <- serverStub.acceptRequest_GetPHYTXCount();
     serverStub.sendResponse_GetPHYTXCount(auroraDriver.tx_count);
   endrule

   rule getPHYRX;
     let dummy <- serverStub.acceptRequest_GetPHYRXCount();
     serverStub.sendResponse_GetPHYRXCount(auroraDriver.rx_count);
   endrule

   rule getSampleDropped;
     let dummy <- serverStub.acceptRequest_GetSampleDropped();
     serverStub.sendResponse_GetSampleDropped(zeroExtend(sampleDropped));
   endrule

   rule getSampleSent;
     let dummy <- serverStub.acceptRequest_GetSampleSent();
     serverStub.sendResponse_GetSampleSent(zeroExtend(sampleSent));
   endrule

   rule getRXError;
     let dummy <- serverStub.acceptRequest_GetRXErrors();
     serverStub.sendResponse_GetRXErrors(0);
   endrule

   rule getRealign;
     let dummy <- serverStub.acceptRequest_GetRealign();
     serverStub.sendResponse_GetRealign(0);
   endrule

    rule sendToSW (serdes_infifo.notFull);
      Bit#(16) dataIn <- auroraDriver.read();
      rxCount <= rxCount + 1;
      // This may be a bug Alfred will know what to do. XXX
      sampleSent <= sampleSent + 1;
      serdes_infifo.enq(dataIn);
    endrule

    rule dropdata (!serdes_infifo.notFull);
       Bit#(16) dataIn <- auroraDriver.read();
       rxCount <= rxCount + 1;
       // This may be a bug Alfred will know what to do. XXX
       sampleDropped <= sampleDropped + 1;
    endrule

    rule toAnalog;
       serdes_infifo.deq;
       analogRX.send(unpack(truncate(serdes_infifo.first())));       
    endrule

    Connection_Receive#(Tuple2#(Bit#(1), Bit#(15))) analogTX <- mkConnection_Receive("InterFPGATX");

    FIFOF#(Bit#(16)) serdes_send <- mkSizedFIFOF(32);  

    Reg#(Bit#(40)) txCountIn <- mkReg(0);  
    Reg#(Bit#(40)) txCount <- mkReg(0);  

   rule getSampleTX;
     let dummy <- serverStub.acceptRequest_GetTXCount();
     serverStub.sendResponse_GetTXCount(zeroExtend(txCount));
   endrule

   rule getSampleTXIn;
     let dummy <- serverStub.acceptRequest_GetTXCountIn();
     serverStub.sendResponse_GetTXCountIn(zeroExtend(txCountIn));
   endrule

    rule forwardToLL; 
      analogTX.deq();
      txCountIn <= txCountIn + 1;
      serdes_send.enq(pack(analogTX.receive));
    endrule

    rule sendToSERDESData;
      auroraDriver.write(serdes_send.first());  // Byte endian issue?
      txCount <= txCount + 1;
      serdes_send.deq();
    endrule
endmodule
