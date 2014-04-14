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
import Vector::*;
import GetPut::*;
import Connectable::*;
import Clocks::*;
import LFSR::*;

`include "awb/provides/umf.bsh"
`include "awb/provides/physical_platform_utils.bsh"
`include "awb/provides/fpga_components.bsh"
`include "awb/provides/clocks_device.bsh"
`include "awb/provides/librl_bsv_base.bsh"
`include "awb/provides/librl_bsv_storage.bsh"

`define PIPE_NULL       1
`define POLL_INTERVAL   2



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
    method Bit#(TMul#(`UNIX_COMM_NUM_WORDS,`UNIX_COMM_WORD_WIDTH)) first();
    method Action                           write(Bit#(TMul#(`UNIX_COMM_NUM_WORDS,`UNIX_COMM_WORD_WIDTH)) chunk);
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
 
   Clock rawClock <- mkAbsoluteClock(0, max(5,`MAGIC_SIMULATION_CLOCK_FACTOR/(`CRYSTAL_CLOCK_FREQ*`UNIX_COMM_NUM_WORDS*64*20)));
   Reset rawReset <- mkInitialReset(10, clocked_by rawClock);
   
   let comm <- mkUNIXCommDeviceShift(outgoing, incoming, clocked_by(rawClock), reset_by(rawReset));

   SyncFIFOIfc#(Bit#(TMul#(`UNIX_COMM_NUM_WORDS,`UNIX_COMM_WORD_WIDTH))) rxfifo <- mkSyncFIFOToCC( 16, rawClock, rawReset);
   SyncFIFOIfc#(Bit#(TMul#(`UNIX_COMM_NUM_WORDS,`UNIX_COMM_WORD_WIDTH))) txfifo <- mkSyncFIFOFromCC( 16, rawClock);

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

typedef enum {
  FLIP_ALL,
  FLIP_ONE
} ERROR_CASE deriving (Bits, Eq);

module mkUNIXCommDeviceShift#(String outgoing, String incoming)
    // interface
                  (UNIX_COMM_DEVICE);
    
    // error correction test harness
    LFSR#(Bit#(16)) lfsr <- mkLFSR_16();
    Reg#(ERROR_CASE) errorCase <- mkReg(FLIP_ONE);

    // state
    Reg#(Bit#(8))  handle      <- mkReg(0);
    Reg#(Bit#(32)) pollCounter <- mkReg(0);
    Reg#(STATE)    state       <- mkReg(STATE_init0);
    
    // buffers
    MARSHALLER#(Bit#(`UNIX_COMM_WORD_WIDTH), Vector#(`UNIX_COMM_NUM_WORDS, Bit#(`UNIX_COMM_WORD_WIDTH))) marshaller <- mkSimpleMarshaller();
    DEMARSHALLER#(Bit#(`UNIX_COMM_WORD_WIDTH), Vector#(`UNIX_COMM_NUM_WORDS, Bit#(`UNIX_COMM_WORD_WIDTH))) demarshaller <- mkSimpleDemarshaller();

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

            demarshaller.enq(truncate(chunk));
            pollCounter <= `POLL_INTERVAL;
       end
    endrule

    // write chunk from write buffer into C code
    rule write_bdpi (state == STATE_ready);
        let guard <- comm_can_write(handle);
        if(unpack(guard))
          begin 
            Bit#(64) chunk = zeroExtend(marshaller.first());
            marshaller.deq();

            if(`UNIX_COMM_DEBUG > 0)
            begin
                $display("UNIX Comm TX %h", chunk);
            end 

            comm_write(handle, chunk);
          end
    endrule

   Reg#(Bit#(`UNIX_COMM_ERRORS_FREQ)) count <- mkReg(0); 

    // ==============================================================
    //                          Methods
    // ==============================================================
    
    // driver interface
    interface UNIX_COMM_DRIVER driver;
               
        method Bit#(TMul#(`UNIX_COMM_NUM_WORDS,`UNIX_COMM_WORD_WIDTH)) first();
            return pack(demarshaller.first);
        endmethod

        method Action deq();
            demarshaller.deq();
        endmethod

        // write
        method Action write(Bit#(TMul#(`UNIX_COMM_NUM_WORDS,`UNIX_COMM_WORD_WIDTH)) chunk);

            if(`UNIX_COMM_ERRORS > 0)
            begin
                let flip = 0;
                // occasionally damage a message
                if(count + 1 == 0)
                begin 
                    Bit#(TLog#(TMul#(`UNIX_COMM_NUM_WORDS,`UNIX_COMM_WORD_WIDTH))) flipIdx = truncate(lfsr.value);
                    flip[flipIdx] = 1;
                    lfsr.next();
                end
  
                count <= count + 1;
 
                marshaller.enq(unpack(chunk^flip));
            end
            else
            begin
                marshaller.enq(unpack(chunk));
            end

        endmethod

        method Bool write_ready = marshaller.notFull;
        
    endinterface
    
    // wires interface
    interface UNIX_COMM_WIRES wires;
        
    endinterface

endmodule
