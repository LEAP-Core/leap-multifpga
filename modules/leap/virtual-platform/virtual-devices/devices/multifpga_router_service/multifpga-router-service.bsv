//
// Copyright (C) 2011 Massachusetts Institute of Technology
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


/******** 
 * This file instantiates the per FPGA routing logic synthesized by the multi-FPGA compiler.
 * The routing module is named mkCommunicationModule (which is why you won't find it by grepping)
 */

`include "asim/provides/virtual_platform.bsh"
`include "asim/provides/virtual_devices.bsh"
`include "asim/provides/low_level_platform_interface.bsh"
`include "asim/provides/rrr.bsh"
`include "asim/provides/umf.bsh"
`include "asim/provides/channelio.bsh"
`include "asim/provides/physical_platform.bsh"
`include "asim/provides/soft_connections.bsh"
`include "asim/provides/multifpga_switch.bsh"

`include "asim/provides/multifpga_router_service.bsh"

import FIFOF::*;
import SpecialFIFOs::*;

`include "multifpga_routing.bsh"


module [CONNECTED_MODULE] mkMultifpgaRouterServices#(VIRTUAL_PLATFORM vplat) (Empty);
    let m <- mkCommunicationModule(vplat);
endmodule 