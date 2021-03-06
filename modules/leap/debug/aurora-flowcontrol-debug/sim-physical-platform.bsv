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

// Simulation Physical Platform

import Clocks::*;
import Vector::*;

`include "clocks_device.bsh"
`include "unix_pipe_device.bsh"
`include "awb/provides/ddr_sdram_device.bsh"
`include "physical_platform_utils.bsh"

// PHYSICAL_DRIVERS

// This represents the collection of all platform capabilities which the
// rest of the FPGA uses to interact with the outside world.
// We use other modules to actually do the work.
interface AURORA_DRIVER;
       method Action send(Bit#(16) tx);
        method ActionValue#(Bit#(16)) receive();

                method Bit#(1) channel_up;
    method Bit#(1) lane_up;
    method Bit#(1) hard_err;
    method Bit#(1) soft_err;
    method Bool    cc;
                /*
    method Bit#(32) status;
    method Bit#(32) rx_count;
    method Bit#(32) tx_count;
    method Bit#(32) error_count;
                */
                interface Clock aurora_clk;
                interface Reset aurora_rst;
                interface Reset aurora_rst_n;

endinterface

interface PHYSICAL_DRIVERS;

    interface CLOCKS_DRIVER    clocksDriver;
    interface UNIX_PIPE_DRIVER unixPipeDriver;
    interface Vector#(FPGA_DDR_BANKS, DDR_DRIVER) ddrDriver;
    interface AURORA_DRIVER    auroraDriver;

endinterface

// TOP_LEVEL_WIRES

// The TOP_LEVEL_WIRES is the datatype which gets passed to the top level
// and output as input/output wires. These wires are then connected to
// physical pins on the FPGA as specified in the accompanying UCF file.
// These wires are defined in the individual devices.

interface TOP_LEVEL_WIRES;
    
    interface CLOCKS_WIRES    clocksWires;
    interface UNIX_PIPE_WIRES unixPipeWires;
    interface DDR_WIRES       ddrWires;
    
endinterface

// PHYSICAL_PLATFORM

// The platform is the aggregation of wires and drivers.

interface PHYSICAL_PLATFORM;
    
    interface PHYSICAL_DRIVERS physicalDrivers;
    interface TOP_LEVEL_WIRES  topLevelWires;

endinterface

// mkPhysicalPlatform

// This is a convenient way for the outside world to instantiate all the devices
// and an aggregation of all the wires.

module mkPhysicalPlatform
    // interface:
    (PHYSICAL_PLATFORM);
    
    // The Platform is instantiated inside a NULL clock domain. Our first course of
    // action should be to instantiate the Clocks Physical Device and obtain interfaces
    // to clock and reset the other devices with.
    
    CLOCKS_DEVICE clocks_device <- mkClocksDevice();
    
    Clock clk = clocks_device.driver.clock;
    Reset rst = clocks_device.driver.reset;

    // The simulation platform emulates DDR using BRAM.  Having a DRAM-like
    // interface makes it easier to test clients of memory in simulation
    // instead of debugging on hardware.
    DDR_DEVICE ram <- mkDDRDevice(clk, rst, clocked_by clk, reset_by rst);

    // Next, create the physical device that can trigger a soft reset. Pass along the
    // interface to the trigger module that the clocks device has given us.

    UNIX_PIPE_DEVICE unix_pipe_device  <- mkUNIXPipeDevice(clocks_device.softResetTrigger,
                                                           clocked_by clk,
                                                           reset_by rst);

    // Finally, instantiate all other physical devices

    // Aggregate the drivers
    
    interface PHYSICAL_DRIVERS physicalDrivers;
    
        interface clocksDriver   = clocks_device.driver;
        interface unixPipeDriver = unix_pipe_device.driver;
        interface ddrDriver      = ram.driver;

    endinterface
    
    // Aggregate the wires
    
    interface TOP_LEVEL_WIRES topLevelWires;
    
        interface clocksWires    = clocks_device.wires;
        interface unixPipeWires  = unix_pipe_device.wires;
        interface ddrWires       = ram.wires;

    endinterface
               
endmodule
