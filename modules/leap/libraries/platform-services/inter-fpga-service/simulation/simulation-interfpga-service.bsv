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
`include "asim/provides/unix_comm_device.bsh"
`include "asim/provides/soft_services.bsh"
`include "asim/provides/soft_connections.bsh"
`include "asim/provides/soft_clocks.bsh"
`include "asim/provides/clocks_device.bsh"
`include "asim/provides/fpga_components.bsh"
`include "asim/provides/librl_bsv_storage.bsh"
`include "asim/provides/librl_bsv_base.bsh"

module [CONNECTED_MODULE] mkInterFPGAService#(PHYSICAL_DRIVERS drivers) (); 

   UNIX_COMM_DRIVER   unixDriver = drivers.unixCommDriver;

   Connection_Send#(Tuple2#(Bit#(1), Bit#(15))) analogRX <- mkConnection_Send("InterFPGARX");

   Connection_Receive#(Tuple2#(Bit#(1), Bit#(15))) analogTX <- mkConnection_Receive("InterFPGATX");

   rule tx;
     analogTX.deq;
     unixDriver.write(zeroExtend(pack(analogTX.receive)));
   endrule

   rule rx;
     let data <- unixDriver.read;
     analogRX.send(unpack(truncate(data)));
   endrule

endmodule
