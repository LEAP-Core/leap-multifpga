/*****************************************************************************
 * basic-rrr-client.bsv
 *
 * Copyright (C) 2008 Intel Corporation
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 */

import Vector::*;
import FIFOF::*;

`include "awb/provides/channelio.bsh"
`include "awb/provides/rrr.bsh"
`include "awb/provides/umf.bsh"

`include "awb/rrr/service_ids.bsh"

// RRR Client

// request/response port interfaces
interface SWITCH_EGRESS_PORT;
    method Action write(UMF_PACKET data);
endinterface

interface EGRESS_SWITCH#(numeric type n);
    interface Vector#(n, SWITCH_EGRESS_PORT)  egressPorts;
endinterface

module mkEgressSwitch#(function ActionValue#(UMF_PACKET) read(), function Action write(UMF_PACKET data)) (EGRESS_SWITCH#(n))
    provisos(Add#(serviceExcess, TLog#(n), SizeOf#(UMF_SERVICE_ID)));
  EGRESS_SWITCH#(n) m = ?;
  if(valueof(n) > 0)
    begin
      m <- mkFlowControlSwitchEgressNonZero(read, write);
    end
  return m;
endmodule

// Doesn't work if n == 0
// Read port gives us tokens
// General idea here is that we can only send for non-zero values
// One issue is simplifying the arbitration logic.  On one hand, we would like to just and buffer_available and fifo_ready. That's simple.  
// But that invovlves dealing with a max sized message, which is probably easy enough.   
module mkFlowControlSwitchEgressNonZero#(function ActionValue#(UMF_PACKET) read(), function Action write(UMF_PACKET data)) (EGRESS_SWITCH#(n))
   provisos(Add#(extraServices, TLog#(n), SizeOf#(UMF_SERVICE_ID)));

    // ==============================================================
    //                        Ports and Queues
    // ==============================================================

    // Lutram to store the pointer values
    // For now we do a 'full-knowledge' protocol, where each return token signifying a return of credits
    LUTRAM#(Bit#(TLog#(n)), Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES)))) portCredits <- mkLUTRAM(`MULTIFPGA_FIFO_SIZES);
    Vector#(n,Reg#(Bool)) bufferAvailable <- replicateM(mkReg(True));

    // create request/response buffers and link them to ports
    FIFOF#(UMF_PACKET)                     requestQueues[valueof(n)];
    Vector#(n,SWITCH_EGRESS_PORT) egress_ports = newVector();


    for (Integer s = 0; s < valueof(n); s = s + 1)
    begin
        requestQueues[s]  <- mkFIFOF();
        // create a new request port and link it to the FIFO
        egress_ports[s] = interface SWITCH_EGRESS_PORT
                             method Action write(UMF_PACKET data);
                               $display("enqueue to egress Q %d",s);
                               requestQueues[s].enq(data);
                             endmethod
                          endinterface;

    end

    // === arbiters ===

    ARBITER#(n) arbiter <- mkRoundRobinArbiter();

    // === other state ===

    Reg#(UMF_MSG_LENGTH) requestChunksRemaining  <- mkReg(0);
    Reg#(UMF_MSG_LENGTH) requestChunks <- mkReg(0);
    Reg#(UMF_MSG_LENGTH) responseChunksRemaining <- mkReg(0);

    Reg#(Bit#(TLog#(n))) requestActiveQueue  <- mkReg(0);
    Reg#(Bit#(TLog#(n))) responseActiveQueue <- mkReg(0);

    // ==============================================================
    //                          Response Rules
    // ==============================================================

    // scan channel for incoming flowcontrol headers
    rule scan_responses;
        UMF_PACKET packet <- read();

        // enqueue header in service's queue
        // set up remaining chunks
        case (packet) matches
          tagged UMF_PACKET_header .header: 
            begin
              responseActiveQueue     <= truncate(packet.UMF_PACKET_header.serviceID);
            end
          tagged UMF_PACKET_dataChunk .chunk:
            begin
              let creditsNext = truncate(chunk) + portCredits.sub(responseActiveQueue);
              bufferAvailable[responseActiveQueue] <= creditsNext >= `MAX_TRANSACTION_SIZE;
              portCredits.upd(responseActiveQueue, creditsNext);
            end
        endcase
    endrule

    // ==============================================================
    //                          Request Rules
    // ==============================================================

    //
    // Start writing new message.  The write_request_newmsg rule is broken
    // into two parts in order to help Bluespec generate a significantly simpler
    // schedule than if the rules are combined.  Separating the rules breaks
    // the connection between arbiter input vector state and the test for
    // whether a requestQueue has data.
    //

    Wire#(Maybe#(UInt#(TLog#(n)))) newMsgQIdx <- mkDWire(tagged Invalid);
    Reg#(Bool) countersAdjusted <- mkReg(True);

    //
    // First half -- pick an incoming requestQueue
    // we could make this 
    //
    rule write_request_newmsg1 (requestChunksRemaining == 0);

        // arbitrate
        Bit#(n) request = '0;
        for (Integer s = 0; s < valueof(n); s = s + 1)
        begin
            request[s] = pack(requestQueues[s].notEmpty() && bufferAvailable[s] );
        end

        newMsgQIdx <= arbiter.arbitrate(request);
        $display("Egress BufferAvailible %b Reqs %b", pack(readVReg(bufferAvailable)), request);
    endrule

    //
    // Second half -- consume a value from the chosen responseQueue.  If the
    // rule fails to fire because the channel write port is full it will fire
    // again later after being reselected by the first half.
    //
    for (Integer s = 0; s < valueof(n); s = s + 1)
    begin	
        rule write_request_newmsg2 (newMsgQIdx matches tagged Valid .idx &&&
                                    fromInteger(s) == idx &&&
                                    requestChunksRemaining == 0);
            $display("scheduled %d", idx);
            // get header packet
            UMF_PACKET packet = requestQueues[s].first();
            requestQueues[s].deq();

            // add my virtual channelID to header
            UMF_PACKET newpacket = tagged UMF_PACKET_header UMF_PACKET_HEADER
                                       {
                                        filler: ?,
                                        phyChannelPvt: ?,
                                        channelID: 0,
                                        serviceID: packet.UMF_PACKET_header.serviceID,
                                        methodID : packet.UMF_PACKET_header.methodID,
                                        numChunks: packet.UMF_PACKET_header.numChunks
                                       };

            // send the header packet to channelio
            write(newpacket);

            // setup remaining chunks
            requestChunksRemaining <= newpacket.UMF_PACKET_header.numChunks;
            requestChunks <= newpacket.UMF_PACKET_header.numChunks + 1; // also sending header
            requestActiveQueue <= fromInteger(s);
        endrule

    end

    // This happens post-arbitration, but before another arbitration can happen
    // It allows us to be using the channel while updating counters and possibly receiving credit 
    // messages 
    rule adjustCounters(!countersAdjusted);
      countersAdjusted <= True;
      let newCount =  portCredits.sub(requestActiveQueue) - truncate(requestChunks);
      portCredits.upd(requestActiveQueue,newCount);
      bufferAvailable[requestActiveQueue] <= newCount >= `MAX_TRANSACTION_SIZE;
      $display("Setting port credits for %d to %d", requestActiveQueue, newCount);
    endrule

    // continue writing message
    rule write_request_continue (requestChunksRemaining != 0);
        $display("sending packet on  %d", requestActiveQueue);

        // get the next packet from the active request queue
        UMF_PACKET packet = requestQueues[requestActiveQueue].first();
        requestQueues[requestActiveQueue].deq();

        // send the packet to channelio
        write(packet);

        // one more chunk processed
        requestChunksRemaining <= requestChunksRemaining - 1;

    endrule

    // ==============================================================
    //                        Set Interfaces
    // ==============================================================

    interface egressPorts  = egress_ports;
endmodule


