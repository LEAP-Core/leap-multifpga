//
// Copyright (C) 2008 Intel Corporation
//
// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// as published by the Free Software Foundation; either version 2
// of the License, or (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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
`include "asim/provides/sata_device.bsh"
`include "asim/provides/soft_services.bsh"
`include "asim/provides/soft_connections.bsh"
`include "asim/provides/soft_clocks.bsh"
`include "asim/provides/clocks_device.bsh"
`include "asim/provides/fpga_components.bsh"
`include "asim/provides/librl_bsv_storage.bsh"
`include "asim/provides/librl_bsv_base.bsh"
`include "asim/rrr/remote_server_stub_INTER_FPGA.bsh"


module [CONNECTED_MODULE] mkInterFPGAService#(PHYSICAL_DRIVERS drivers) (); 

   XUPV5_SERDES_DRIVER       sataDriver = drivers.sataDriver;
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
     Bit#(8) rx_fifo_count = zeroExtend(pack(sataDriver.rx_fifo_count));
     Bit#(8) tx_fifo_count = zeroExtend(pack(sataDriver.tx_fifo_count));
     serverStub.sendResponse_GetPHYStatus(zeroExtend({rx_fifo_count,
                                                      tx_fifo_count,
                                                      sataDriver.channel_up,
                                                      sataDriver.lane_up,
                                                      sataDriver.hard_err,
                                                      sataDriver.soft_err,
                                                      sataDriver.status}));
   endrule

   rule getPHYTX;
     let dummy <- serverStub.acceptRequest_GetPHYTXCount();
     serverStub.sendResponse_GetPHYTXCount(sataDriver.tx_count);
   endrule

   rule getPHYRX;
     let dummy <- serverStub.acceptRequest_GetPHYRXCount();
     serverStub.sendResponse_GetPHYRXCount(sataDriver.rx_count);
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
      Bit#(16) dataIn <- sataDriver.read();
      rxCount <= rxCount + 1;
      // This may be a bug Alfred will know what to do. XXX
      sampleSent <= sampleSent + 1;
      serdes_infifo.enq(dataIn);
    endrule

    rule dropdata (!serdes_infifo.notFull);
       Bit#(16) dataIn <- sataDriver.read();
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
      sataDriver.write(serdes_send.first());  // Byte endian issue?
      txCount <= txCount + 1;
      serdes_send.deq();
    endrule
endmodule
