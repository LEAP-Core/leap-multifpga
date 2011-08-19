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
import "BDPI" function ActionValue#(Bit#(1))  comm_can_write(Bit#(8) handle);
import "BDPI" function ActionValue#(Bit#(1))  comm_can_read(Bit#(8) handle);
import "BDPI" function Action                 comm_write(Bit#(8) handle, Bit#(64) data);
                  

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

    method ActionValue#(Bit#(64)) read();
    method Action                  write(Bit#(64) chunk);
        
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
    FIFOF#(Bit#(64)) readBuffer  <- mkFIFOF();
    FIFOF#(Bit#(64)) writeBuffer <- mkFIFOF();

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
        comm_init();
        state <= STATE_init1;
    endrule

    // another rule needed to initialize C code
    rule open_C_channel(state == STATE_init1);
        Bit#(8) wire_out <- comm_open(outgoing, incoming);
        handle <= wire_out;
        state  <= STATE_ready;
    endrule

    // probe C code for incoming chunk
    rule read_bdpi (state == STATE_ready && pollCounter == 0);
        let guard <- comm_can_read(handle);
        if(unpack(guard))
          begin 
            Bit#(64) chunk <- comm_read(handle);
            
            //$display("UNIX Comm RX %h", chunk);
            readBuffer.enq(chunk);
            pollCounter <= `POLL_INTERVAL;
         end
    endrule

    // write chunk from write buffer into C code
    rule write_bdpi (state == STATE_ready);
        let guard <- comm_can_write(handle);
        if(unpack(guard))
          begin 
            Bit#(64) chunk = writeBuffer.first();
            writeBuffer.deq();
            //$display("UNIX Comm TX %h", chunk);
            comm_write(handle, chunk);
          end
    endrule


    // ==============================================================
    //                          Methods
    // ==============================================================
    
    // driver interface
    interface UNIX_COMM_DRIVER driver;
        
        // read
        method ActionValue#(Bit#(64)) read();
            Bit#(64) chunk = readBuffer.first();
            readBuffer.deq();
            return chunk;
        endmethod

        // write
        method Action write(Bit#(64) chunk);
            writeBuffer.enq(chunk);
        endmethod
        
    endinterface
    
    // wires interface
    interface UNIX_COMM_WIRES wires;
        
    endinterface

endmodule
