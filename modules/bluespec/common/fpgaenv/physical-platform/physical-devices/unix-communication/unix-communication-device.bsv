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
import GetPut::*;
import Connectable::*;
import Clocks::*;

`include "awb/provides/umf.bsh"
`include "awb/provides/physical_platform_utils.bsh"
`include "awb/provides/fpga_components.bsh"
`include "awb/provides/clocks_device.bsh"
`include "awb/provides/librl_bsv_base.bsh"
`include "awb/provides/librl_bsv_storage.bsh"

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

    method Action                           deq();
    method Bit#(TMul#(`UNIX_COMM_WIDTH,64)) first();
    method Action                           write(Bit#(TMul#(`UNIX_COMM_WIDTH,64)) chunk);
    method Bool                             write_ready();
        
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
// We need to provide the illusion that this module is faster inorder to accomodate shifting data out.
module mkUNIXCommDevice#(String outgoing, String incoming) (UNIX_COMM_DEVICE);
 
   Clock rawClock <- mkAbsoluteClock(0, max(1,`MAGIC_SIMULATION_CLOCK_FACTOR/(`CRYSTAL_CLOCK_FREQ*`UNIX_COMM_WIDTH*64)));
   Reset rawReset <- mkInitialReset(10, clocked_by rawClock);
   
   let comm <- mkUNIXCommDeviceShift(outgoing, incoming, clocked_by(rawClock), reset_by(rawReset));

   SyncFIFOIfc#(Bit#(TMul#(`UNIX_COMM_WIDTH,64))) rxfifo <- mkSyncFIFOToCC( 16, rawClock, rawReset);
   SyncFIFOIfc#(Bit#(TMul#(`UNIX_COMM_WIDTH,64))) txfifo <- mkSyncFIFOFromCC( 16, rawClock);

   rule connectRX;
     rxfifo.enq(comm.driver.first);
     comm.driver.deq;
   endrule 

   mkConnection(toGet(txfifo),toPut(comm.driver.write)); 

    // driver interface
    interface UNIX_COMM_DRIVER driver;
        
        method first            = rxfifo.first;
        method deq              = rxfifo.deq;
        method write            = toPut(txfifo).put;
        method Bool write_ready = txfifo.notFull;
        
    endinterface
    
    // wires interface
    interface UNIX_COMM_WIRES wires;
        
    endinterface   

endmodule

module mkUNIXCommDeviceShift#(String outgoing, String incoming)
    // interface
                  (UNIX_COMM_DEVICE);
    
    

    // state
    Reg#(Bit#(8))  handle      <- mkReg(0);
    Reg#(Bit#(32)) pollCounter <- mkReg(0);
    Reg#(STATE)    state       <- mkReg(STATE_init0);
    
    // buffers
    MARSHALLER#(Bit#(64), Vector#(`UNIX_COMM_WIDTH, Bit#(64))) marshaller <- mkSimpleMarshaller();
    DEMARSHALLER#(Bit#(64), Vector#(`UNIX_COMM_WIDTH, Bit#(64))) demarshaller <- mkSimpleDemarshaller();

    // ==============================================================
    //                            Rules
    // ==============================================================

    // poll cycle
    rule cycle_poll_counter(state == STATE_ready && pollCounter != 0);
        pollCounter <= pollCounter - 1;
    endrule

    // initialize C code
    rule initialize(state == STATE_init0);
        if(`UNIX_COMM_DEBUG > 0)
        begin
            $display("init" + outgoing + incoming);
	end
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

            if(`UNIX_COMM_DEBUG > 0)
            begin
                $display("UNIX Comm RX %h", chunk);
            end

            demarshaller.enq(chunk);
            pollCounter <= `POLL_INTERVAL;
       end
    endrule

    // write chunk from write buffer into C code
    rule write_bdpi (state == STATE_ready);
        let guard <- comm_can_write(handle);
        if(unpack(guard))
          begin 
            Bit#(64) chunk = marshaller.first();
            marshaller.deq();

            if(`UNIX_COMM_DEBUG > 0)
            begin
                $display("UNIX Comm TX %h", chunk);
            end 

            comm_write(handle, chunk);
          end
    endrule


    // ==============================================================
    //                          Methods
    // ==============================================================
    
    // driver interface
    interface UNIX_COMM_DRIVER driver;
               
        method Bit#(TMul#(`UNIX_COMM_WIDTH,64)) first();
            return pack(demarshaller.first);
        endmethod

        method Action deq();
            demarshaller.deq();
        endmethod

        // write
        method Action write(Bit#(TMul#(`UNIX_COMM_WIDTH,64)) chunk);
            marshaller.enq(unpack(chunk));
        endmethod

        method Bool write_ready = marshaller.notFull;
        
    endinterface
    
    // wires interface
    interface UNIX_COMM_WIRES wires;
        
    endinterface

endmodule
