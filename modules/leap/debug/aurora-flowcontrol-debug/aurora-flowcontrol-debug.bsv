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
