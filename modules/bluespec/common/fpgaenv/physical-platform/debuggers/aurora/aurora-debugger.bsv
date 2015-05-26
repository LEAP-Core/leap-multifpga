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
`include "awb/dict/PARAMS_PHYSICAL_PLATFORM_DEBUGGER.bsh"

module [CONNECTED_MODULE] mkPhysicalPlatformDebugger#(PHYSICAL_DRIVERS drivers) (PHYSICAL_DRIVERS); 

    if(`DEBUG_DRIVER_MODE != 0)
    begin
        PARAMETER_NODE paramNode  <- mkDynamicParameterNode();
        Param#(8) targetAurora <- mkDynamicParameter(`PARAMS_PHYSICAL_PLATFORM_DEBUGGER_TARGET_AURORA,paramNode);
  
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

    return drivers;
endmodule
