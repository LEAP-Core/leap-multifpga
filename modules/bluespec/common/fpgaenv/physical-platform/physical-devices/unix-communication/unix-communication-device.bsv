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
import Vector::*;

`include "umf.bsh"
`include "physical_platform_utils.bsh"

`define PIPE_NULL       1
`define POLL_INTERVAL   0

// BDPI imports
import "BDPI" function Action                 comm_init();
import "BDPI" function ActionValue#(Bit#(8))  comm_open(String outgoing, String incoming);
import "BDPI" function ActionValue#(Bit#(64)) comm_read(Bit#(8) handle);
import "BDPI" function Bit#(1)  comm_can_write(Bit#(8) handle);
import "BDPI" function Bit#(1)  comm_can_read(Bit#(8) handle);
import "BDPI" function Action   comm_write(Bit#(8) handle, Bit#(64) data);
                  

// types
typedef enum
{
    STATE_init0,
    STATE_init1,
    STATE_ready 
}
STATE
    deriving (Bits, Eq);

// UNIX_COMM_DRIVER
interface UNIX_COMM_DRIVER;

    method ActionValue#(UMF_CHUNK) read();
    method Action                  write(UMF_CHUNK chunk);
        
endinterface

// UNIX_COMM_WIRES
interface UNIX_COMM_WIRES;

endinterface

// UNIX_COMM_DEVICE
// By convention a Device is a Driver and a Wires
interface UNIX_COMM_DEVICE;

  interface UNIX_COMM_DRIVER driver;
  interface UNIX_COMM_WIRES  wires;

endinterface
                  
// UNIX pipe module
module mkUNIXCommDevice#(String outgoing, String incoming)
    // interface
                  (UNIX_COMM_DEVICE);
    
    // state
    Reg#(Bit#(8))  handle      <- mkReg(0);
    Reg#(Bit#(32)) pollCounter <- mkReg(0);
    Reg#(STATE)    state       <- mkReg(STATE_init0);
    
    // buffers
    FIFOF#(UMF_CHUNK) readBuffer  <- mkFIFOF();
    FIFOF#(UMF_CHUNK) writeBuffer <- mkFIFOF();

    // ==============================================================
    //                            Rules
    // ==============================================================

    // poll cycle
    rule cycle_poll_counter(state == STATE_ready && pollCounter != 0);
        pollCounter <= pollCounter - 1;
    endrule

    // initialize C code
    rule initialize(state == STATE_init0);
        $display("init" + outgoing + incoming);
        comm_init(outgoing, incoming);
        state <= STATE_init1;
    endrule

    // another rule needed to initialize C code
    rule open_C_channel(state == STATE_init1);
        Bit#(8) wire_out <- comm_open(outgoing, incoming);
        handle <= wire_out;
        state  <= STATE_ready;
    endrule

    // probe C code for incoming chunk
    rule read_bdpi (state == STATE_ready && pollCounter == 0 && unpack(comm_can_read(handle)));
        Bit#(64) data <- comm_read(handle);
        UMF_CHUNK chunk = truncate(data);
        readBuffer.enq(chunk);
        pollCounter <= `POLL_INTERVAL;
    endrule

    // write chunk from write buffer into C code
    rule write_bdpi (state == STATE_ready && unpack(comm_can_write(handle)));
        UMF_CHUNK chunk = writeBuffer.first();
        writeBuffer.deq();
        comm_write(handle, zeroExtend(chunk));
    endrule


    // ==============================================================
    //                          Methods
    // ==============================================================
    
    // driver interface
    interface UNIX_COMM_DRIVER driver;
        
        // read
        method ActionValue#(UMF_CHUNK) read();
            UMF_CHUNK chunk = readBuffer.first();
            readBuffer.deq();
            return chunk;
        endmethod

        // write
        method Action write(UMF_CHUNK chunk);
            writeBuffer.enq(chunk);
        endmethod
        
    endinterface
    
    // wires interface
    interface UNIX_COMM_WIRES wires;
        
    endinterface

endmodule
