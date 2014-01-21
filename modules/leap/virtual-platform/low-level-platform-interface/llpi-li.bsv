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

`include "awb/provides/local_mem.bsh"
`include "awb/provides/remote_memory.bsh"
`include "awb/provides/physical_platform.bsh"
`include "awb/provides/physical_channel.bsh"
`include "awb/provides/physical_platform_debugger.bsh"
`include "awb/provides/clocks_device.bsh"
`include "awb/provides/umf.bsh"

//
// LowLevelPlatformInterface.
//
// A convenient bundle of all ways to interact with the outside world.
//
interface LowLevelPlatformInterface;

    interface LOCAL_MEM                 localMem;
    interface REMOTE_MEMORY             remoteMemory;
    interface PHYSICAL_DRIVERS          physicalDrivers;
    interface TOP_LEVEL_WIRES           topLevelWires;
    interface PHYSICAL_CHANNEL          physicalChannel;

endinterface

//
// mkLowLevelPlatformInterface
//
// Instantiate the subcomponents in one module.
//
`ifdef N_TOP_LEVEL_CLOCKS
module mkLowLevelPlatformInterface#(Vector#(`N_TOP_LEVEL_CLOCKS, Clock) topClocks, Reset topReset)
`else
module mkLowLevelPlatformInterface
`endif
    // Interface:
    (LowLevelPlatformInterface);

    // instantiate physical platform
    
`ifdef N_TOP_LEVEL_CLOCKS
    PHYSICAL_PLATFORM phys_plat <- mkPhysicalPlatform(topClocks, topReset);
`else
    PHYSICAL_PLATFORM phys_plat <- mkPhysicalPlatform();
`endif 
    
    // LLPI is instantiated in a NULL clock domain, so first get some clocks
    // from the physical platform, which we'll pass down into the debugger
    // and virtual platform
    
    Clock clk = phys_plat.physicalDrivers.clocksDriver.clock;
    Reset rst = phys_plat.physicalDrivers.clocksDriver.reset;
    
    // instantiate physical platform debugger and obtain gated drivers from it
    PHYSICAL_DRIVERS  drivers   <- mkPhysicalPlatformDebugger(phys_plat.physicalDrivers, clocked_by clk, reset_by rst);
    
    // interfaces to the physical platform
    LOCAL_MEM     locMem <- mkLocalMem(drivers, clocked_by clk, reset_by rst);
    REMOTE_MEMORY remMem <- mkRemoteMemory(drivers, clocked_by clk, reset_by rst);
  
    PHYSICAL_CHANNEL physicalChannelInst <- mkPhysicalChannel(drivers, clocked_by clk, reset_by rst);

    // plumb interfaces

    interface localMem         = locMem;
    interface remoteMemory     = remMem;
    interface physicalDrivers  = drivers;
    interface topLevelWires    = phys_plat.topLevelWires;
    interface physicalChannel  = physicalChannelInst;
endmodule