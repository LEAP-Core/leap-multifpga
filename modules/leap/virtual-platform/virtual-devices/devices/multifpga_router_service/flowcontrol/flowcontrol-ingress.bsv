//
// Copyright (C) 2009 Intel Corporation
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
import FIFOF::*;

`include "awb/provides/channelio.bsh"
`include "awb/provides/rrr.bsh"
`include "awb/provides/umf.bsh"

`include "awb/rrr/service_ids.bsh"

// RRR Server: my job is to scan channelio for incoming requests and queue
// them in service-private internal buffers. Services will periodically probe
// me to inquire if there are any outstanding requests for them

// request/response port interfaces
interface SWITCH_INGRESS_PORT;
    method ActionValue#(UMF_PACKET) read();
    method Action read_ready();
endinterface

interface INGRESS_SWITCH#(numeric type n);
    interface Vector#(n, SWITCH_INGRESS_PORT)  egressPorts;
endinterface

// Here we are reading and sticking things into the BRAM buffer. 
// We write back the credits periodically
module mkFlowControlSwitchIngressNonZero#(function ActionValue#(UMF_PACKET) read(), function Action write(UMF_PACKET data)) (INGRESS_SWITCH#(n));

    // ==============================================================
    //                        Ports and Queues
    // ==============================================================

    // We don't need to send tokens at first.  The other side assumes that we are empty.
    // However we do need to eat the free tokens so that the flow control will work right. 
    VLevelFIFO#(n,`MULTIFPGA_FIFO_SIZES,UMF_PACKET) requestQueues <- mkBRAMVLevelFIFO(True); // This true causes the 
    Vector#(n, SWITCH_INGRESS_PORT) ingress_ports = newVector();
    Vector#(n, Reg#(Bool)) readReady <- replicateM(mkReg(True));
    RWire#(Bit#(TLog#(n))) idxExamined <-mkRWire;
    FIFO#(Bit#(TLog#(`MULTIFPGA_FIFO_SIZES))) sendSize <- mkSizedFIFO(1);

    rule startSendEmpty;
       if(idx + 1 == fromInteger(valueof(n))) 
         begin
           idx <= 0;
         end 
       else
         begin
           idx <= idx + 1;
         end
       let use_idx = idx;
       
       if(idxExamined matches tagged Valid .enqIdx)
         begin
           use_idx = enqIdx;
         end

       // If we get too free, we need to send come cedits down the pipe.
       if(requestQueues.free[use_idx] > `MULTIFPGA_FIFO_SIZES - `MAX_TRANSACTION_SIZE)
         begin 
           UMF_PACKET newpacket = tagged UMF_PACKET_header UMF_PACKET_HEADER
                                       {
                                         filler: ?,
                                         phyChannelPvt: ?,
                                         channelID: 1,
                                         serviceID: idx,
                                         methodID : ?,
                                         numChunks: 1
                                        };

          // hand out the whole pack of tokens  
          requestQueues.decrFree(idx, requestQueues.free[use_idx]);
          // send the header packet to channelio
          write(newpacket);
          sendSize.enq(requestQueues.free[use_idx]);
         end 
    endrule

    rule finishSendEmpty;
      sendSize.deq;
      write(zeroExtend(sendSize.first));
    endrule

    // === arbiters ===

    ARBITER#(n) arbiter <- mkRoundRobinArbiter();

    // === other state ===

    Reg#(UMF_MSG_LENGTH) requestChunksRemaining  <- mkReg(0);

    Reg#(UMF_SERVICE_ID) requestActiveQueue  <- mkReg(0);

    // ==============================================================
    //                          Request Rules
    // ==============================================================

    // scan channel for incoming request headers
    // the VLevelFIFO is a massive unguarded dance filled with potential miscalculation
    rule scan_requests (requestChunksRemaining == 0);

        UMF_PACKET packet <- read();

        // enqueue header in service's queue
        // enqueues are always safe 
        requestQueues.enq(packet.UMF_PACKET_header.serviceID,packet);

        // set up remaining chunks
        requestChunksRemaining <= packet.UMF_PACKET_header.numChunks;
        requestActiveQueue     <= packet.UMF_PACKET_header.serviceID;

    endrule

    // scan channel for request message chunks
    rule scan_params (requestChunksRemaining != 0);

        // grab a chunk from channelio and place it into the active request queue
        UMF_PACKET packet <- read();
        requestQueues.enq(requestActiveQueue,packet);
        // one chunk processed
        requestChunksRemaining <= requestChunksRemaining - 1;

    endrule

    // ==============================================================
    //                          Request Deq Rules
    // ==============================================================

    //
    // Start writing new message.  The write_response_newmsg rule is broken
    // into two parts in order to help Bluespec generate a significantly simpler
    // schedule than if the rules are combined.  Separating the rules breaks
    // the connection between arbiter input vector state and the test for
    // whether a responseQueue has data.
    //

    Wire#(Maybe#(UInt#(TLog#(n)))) newMsgQIdx <- mkDWire(tagged Invalid);

    // call first req in one rule
    // then call resp+deq in the next


    //
    // First half -- pick an incoming responseQueue
    //
    rule write_response_newmsg1 (responseChunksRemaining == 0);

        // arbitrate
        Bit#(n) request = pack(zipWith( \&&, map( \< (1), responseQueues.used(), readReady)));
        let idx = arbiter.arbitrate(request);
        newMsgQIdx <= idx;
        requestQueues.firstReq(idx);
    endrule



    // need to use the arbiter to choose who we dequeue from
    // the right selection policy probably involves choosing the eldest 
    for (Integer s = 0; s < fromInteger(valueof(n)); s = s + 1)
    begin
         // create a new request port and link it to the FIFO
        req_ports[s] = interface SWITCH_INGRESS_PORT
                           method ActionValue#(UMF_PACKET) read() if(newMsgQIdx matches tagged Valid .idx &&&
                                                                     fromInteger(s) == idx);

                               UMF_PACKET val = requestQueues.firstResp();
                               requestQueues.deq(idx);
                               return val;

                           endmethod

                           method Action read_ready();
                              readReady[s] <= True;
                           endmethod
                       endinterface;

    end


    interface ingressPorts  = ingress_ports;

endmodule
