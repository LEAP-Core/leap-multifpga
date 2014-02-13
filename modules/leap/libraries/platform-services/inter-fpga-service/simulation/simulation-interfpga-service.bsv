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
