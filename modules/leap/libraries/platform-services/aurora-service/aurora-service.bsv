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

`include "awb/provides/low_level_platform_interface.bsh"
`include "awb/provides/physical_platform.bsh"
`include "awb/provides/aurora_device.bsh"
`include "awb/provides/aurora_flowcontrol_debugger.bsh"
`include "awb/provides/soft_services.bsh"
`include "awb/provides/soft_connections.bsh"
`include "awb/provides/soft_clocks.bsh"
`include "awb/provides/stdio_service.bsh"
`include "awb/provides/soft_strings.bsh"
`include "awb/provides/clocks_device.bsh"
`include "awb/provides/fpga_components.bsh"
`include "awb/provides/librl_bsv_storage.bsh"
`include "awb/provides/librl_bsv_base.bsh"
`include "awb/provides/dynamic_parameters_service.bsh"
`include "awb/dict/PARAMS_AURORA_SERVICE.bsh"

module [CONNECTED_MODULE] mkAuroraService#(PHYSICAL_DRIVERS drivers) (); 


    if(`DEBUG_DRIVER_MODE != 0)
    begin
        PARAMETER_NODE paramNode  <- mkDynamicParameterNode();
        Param#(8) targetAurora <- mkDynamicParameter(`PARAMS_AURORA_SERVICE_TARGET_AURORA,paramNode);
  
        AURORA_COMPLEX_DRIVER auroraDriver = drivers.auroraDriver[targetAurora];


        let serdes_infifo <- mkSizedBRAMFIFOF(64);
        // make soft connections to PHY
        Connection_Send#(Bit#(63)) analogRX <- mkConnectionSendOptional("AuroraRX");
        Reg#(Bit#(40)) rxCount <- mkReg(0);
        Reg#(Bit#(40)) sampleDropped <- mkReg(0);
        Reg#(Bit#(40)) sampleSent <- mkReg(0);
   

        rule sendToSW (serdes_infifo.notFull);
            auroraDriver.deq;
            rxCount <= rxCount + 1;           
            sampleSent <= sampleSent + 1;
            serdes_infifo.enq(auroraDriver.first);
   
        endrule

        rule toAnalog;
            serdes_infifo.deq;
            analogRX.send(truncate(serdes_infifo.first()));        
        endrule

        Connection_Receive#(Bit#(63)) analogTX  <- mkConnectionRecvOptional("AuroraTX");

        FIFOF#(Bit#(63)) serdes_send <- mkSizedFIFOF(32);  

        Reg#(Bit#(40)) txCountIn <- mkReg(0);  
        Reg#(Bit#(40)) txCount <- mkReg(0);  


        rule forwardToLL; 
            analogTX.deq();
            txCountIn <= txCountIn + 1;
            serdes_send.enq(zeroExtend(analogTX.receive));
        endrule

        rule sendToSERDESData;
            auroraDriver.write(resize(serdes_send.first()));  // Byte endian issue?
            txCount <= txCount + 1;
            serdes_send.deq();
        endrule
    end


    if(`MONITOR_DRIVER_MODE != 0)
    begin
        // instantiate an aurora debug module for each physical aurora interface.
        for(Integer i = 0; i < `NUM_AURORA_IFCS; i = i + 1)
        begin
            AURORA_COMPLEX_DRIVER auroraDriver = drivers.auroraDriver[i];
            let debugger <- mkAuroraDebugger(i,auroraDriver); 
        end  
    end
endmodule
