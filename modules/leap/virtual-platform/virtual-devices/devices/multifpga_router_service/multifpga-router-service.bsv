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


/******** 
 * This file instantiates the per FPGA routing logic synthesized by the multi-FPGA compiler.
 * The routing module is named mkCommunicationModule (which is why you won't find it by grepping)
 */

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


module [CONNECTED_MODULE] mkMultifpgaRouterServices#(PHYSICAL_DRIVERS physicalDrivers) (Empty);
    let m <- mkCommunicationModule(physicalDrivers);
endmodule 
