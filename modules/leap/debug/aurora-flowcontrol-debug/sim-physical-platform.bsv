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