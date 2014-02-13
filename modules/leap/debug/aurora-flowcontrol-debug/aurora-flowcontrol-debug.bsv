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

import Vector::*;
import List::*;
import GetPut::*;
import FIFO::*;

`include "awb/provides/virtual_platform.bsh"
`include "awb/provides/virtual_devices.bsh"
`include "awb/provides/common_services.bsh"
`include "awb/provides/librl_bsv.bsh"

`include "awb/provides/soft_connections.bsh"
`include "awb/provides/soft_services.bsh"
`include "awb/provides/soft_services_lib.bsh"
`include "awb/provides/soft_services_deps.bsh"
`include "awb/provides/inter_fpga_device.bsh"
`include "awb/provides/low_level_platform_interface.bsh"
`include "awb/provides/physical_platform.bsh"

module [CONNECTED_MODULE] mkConnectedApplication ();
   
    Reg#(Bit#(63)) sendToBValue <- mkReg(0);
    Reg#(Bit#(63)) sendToAValue <- mkReg(0);
    Reg#(Bit#(63)) recvFromBValue <- mkReg(0);
    Reg#(Bit#(63)) recvFromAValue <- mkReg(0);

    FIFO#(Bit#(16)) aToB <- mkSizedFIFO(64);
    FIFO#(Bit#(16)) bToA <- mkSizedFIFO(64);

    let clk <- exposeCurrentClock;
    let rst <- exposeCurrentReset;

    Reg#(Bit#(8)) ccOn <- mkReg(0);

    LowLevelPlatformInterface llpiA = interface LowLevelPlatformInterface;
                                          interface PHYSICAL_DRIVERS physicalDrivers;
                                              interface AURORA_DRIVER auroraDriver;
                                                  method send = toPut(aToB).put;
                                                  method receive = toGet(bToA).get;
                                                  method aurora_clk = clk;
                                                  method aurora_rst = rst;
                                                  method cc = ccOn < 16;
                                              endinterface
                                          endinterface
                                      endinterface;

    LowLevelPlatformInterface llpiB = interface LowLevelPlatformInterface;
                                          interface PHYSICAL_DRIVERS physicalDrivers;
                                              interface AURORA_DRIVER auroraDriver;
                                                  method send = toPut(bToA).put;
                                                  method receive = toGet(aToB).get;
                                                  method aurora_clk = clk;
                                                  method aurora_rst = rst;
                                                  method cc = ccOn < 16;
                                              endinterface
                                          endinterface
                                      endinterface;

    let deviceA <- mkInterFPGADevice(llpiA);
    let deviceB <- mkInterFPGADevice(llpiB);

    Reg#(Bool) finishA <- mkReg(False);
    Reg#(Bool) finishB <- mkReg(False);

    rule tickCC;
        ccOn <= ccOn + 1;
    endrule

    rule sendToB;
        sendToBValue <= sendToBValue + 1;
        deviceA.write(sendToBValue);
    endrule

    rule sendToA;
        sendToAValue <= sendToAValue + 1;
        deviceB.write(sendToAValue);
    endrule
  
    rule recvFromB;
        recvFromBValue <= recvFromBValue + 1;
        deviceA.deq;
        if(recvFromBValue != deviceA.first)
        begin
            $display("Recv From B %x != %x", recvFromBValue, deviceA.first);
            $finish;
        end
        
        if(recvFromBValue == 2000)
        begin
            finishA <= True;
        end
    endrule

    rule recvFromA;
        recvFromAValue <= recvFromAValue + 1;
        deviceB.deq;
        if(recvFromAValue != deviceB.first)
        begin
            $display("Recv From A %x != %x", recvFromAValue, deviceB.first);
            $finish;
        end
        
        if(recvFromAValue == 2000)
        begin
            finishB <= True;
        end
    endrule

    rule done(finishA && finishB);
        $display("PASSED");
        $finish;
    endrule

endmodule
