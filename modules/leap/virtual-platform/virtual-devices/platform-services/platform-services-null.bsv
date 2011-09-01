//
// Copyright (C) 2008 Massachusetts Institute of Technology
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

`include "awb/provides/virtual_platform.bsh"
`include "awb/provides/virtual_devices.bsh"
`include "awb/provides/low_level_platform_interface.bsh"
`include "awb/provides/soft_connections.bsh"
`include "awb/provides/multifpga_router_service.bsh"
`include "awb/provides/mem_services.bsh"
`include "mem-services-standard.bsh"

//
// mkPlatformInterface: Wrap the LLPI and virtual devices in soft connections.
//

module [CONNECTED_MODULE] mkPlatformServices#(VIRTUAL_PLATFORM virtualPlatform)
    // interface
        ();

    // auto-generated submodules for RRR connections
    let multifpgaRouterService  <- mkMultifpgaRouterServices(virtualPlatform);    
    let memoryServices <- mkMemServices(virtualPlatform.virtualDevices);

endmodule
