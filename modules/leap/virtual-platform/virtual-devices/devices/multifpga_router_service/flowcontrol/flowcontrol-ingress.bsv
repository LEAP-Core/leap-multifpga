//
// Copyright (C) 2011 Intel Corporation
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
 * This contains a parametric ingress switch.  The basic idea is that packets come in from 
 * another FPGA and then get stuffed into fifos according to information in the packet header.
 * This switch makes use of the VLevelFIFO, which multiplexes the incoming FIFOs onto a single, 
 * dense BRAM.
 *
 * This file is a loose derivative of a similar file in the RRR stack. 
 */


import Vector::*;
import FIFOF::*;import DReg::*;

`include "awb/provides/channelio.bsh"
`include "awb/provides/rrr.bsh"
`include "awb/provides/umf.bsh"

`include "awb/rrr/service_ids.bsh"

// request/response port interfaces
interface SWITCH_INGRESS_PORT#(type umf_packet);
    method ActionValue#(umf_packet) read();
    method Action read_ready();
endinterface

interface INGRESS_SWITCH#(numeric type n, type umf_packet, type umf_packet_header_w, type umf_body_w);
    interface Vector#(n, SWITCH_INGRESS_PORT#(umf_packet))  ingressPorts;
    interface EGRESS_PACKET_GENERATOR#(umf_packet_header_w, umf_body_w) flowcontrol_response;
endinterface

// The ingress switch takes two arguments - a read and a write.   The read function is a stream 
// of serialized incoming packets.  The write function is used to send flow control tokens back to 
// the corresponding egress switch on another FPGA.
module mkIngressSwitch#(function ActionValue#(umf_chunk) read())

    (INGRESS_SWITCH#(n, 
                     GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                             umf_channel_id, umf_service_id,
                                             umf_method_id,  umf_message_len,
                                             umf_phy_pvt,    filler_bits), umf_chunk),
                     GENERIC_UMF_PACKET_HEADER#(umf_channel_id_w, umf_service_id_w,
                                                umf_method_id_w,  umf_message_len_w,
                                                umf_phy_pvt_w,    filler_bits_w), 
                     umf_chunk_w)) // Module interface
    
    provisos(Add#(serviceExcess, TLog#(n), umf_service_id),
                 Bits#(umf_chunk, TAdd#(filler_bits, TAdd#(umf_phy_pvt,
                                  TAdd#(umf_channel_id, TAdd#(umf_service_id,
                                                        TAdd#(umf_method_id,
                                        umf_message_len)))))),

                 Bits#(umf_chunk_w, TAdd#(filler_bits_w, TAdd#(umf_phy_pvt_w,
                                    TAdd#(umf_channel_id_w, TAdd#(umf_service_id_w,
                                                        TAdd#(umf_method_id_w,
                                        umf_message_len_w)))))),

                  Add#(chunk_extra, TAdd#(umf_service_id,TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))), SizeOf#(umf_chunk_w)),
                  Add#(1, nExcess, n)
            );
 
  // If we have no incoming links, then we won't instantiate a switch
  INGRESS_SWITCH#(n,
                  GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                        umf_channel_id, umf_service_id,
                        umf_method_id,  umf_message_len,
                        umf_phy_pvt,    filler_bits), umf_chunk),
                  GENERIC_UMF_PACKET_HEADER#(umf_channel_id_w, umf_service_id_w,
                                                umf_method_id_w,  umf_message_len_w,
                                                umf_phy_pvt_w,    filler_bits_w),
                  umf_chunk_w) m = ?;
  if(valueof(n) > 0)
    begin
      m <- mkFlowControlSwitchIngressNonZero(read);
    end
  return m;
endmodule


// Here we are reading and sticking things into the BRAM buffer. 
// We write back the credits periodically
module mkFlowControlSwitchIngressNonZero#(function ActionValue#(umf_chunk) read())

    (INGRESS_SWITCH#(n, 
                     GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                        umf_channel_id, umf_service_id,
                        umf_method_id,  umf_message_len,
                        umf_phy_pvt,    filler_bits), umf_chunk),
                     GENERIC_UMF_PACKET_HEADER#(umf_channel_id_w, umf_service_id_w,
                                                umf_method_id_w,  umf_message_len_w,
                                                umf_phy_pvt_w,    filler_bits_w),
                     umf_chunk_w)) // Module interface

    provisos(
             Bits#(umf_chunk, TAdd#(filler_bits, TAdd#(umf_phy_pvt,
                                  TAdd#(umf_channel_id, TAdd#(umf_service_id,
                                                        TAdd#(umf_method_id,
                                        umf_message_len)))))),
             
             Bits#(umf_chunk_w, TAdd#(filler_bits_w, TAdd#(umf_phy_pvt_w,
                                  TAdd#(umf_channel_id_w, TAdd#(umf_service_id_w,
                                                        TAdd#(umf_method_id_w,
                                        umf_message_len_w)))))),

             Add#(chunk_extra, TAdd#(umf_service_id,TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))), SizeOf#(umf_chunk_w)),

             Add#(service_id_extra, TLog#(n), umf_service_id),
             Add#(1, nExcess, n));

    // ==============================================================
    //                        Ports and Queues
    // ==============================================================

    // We don't need to send tokens at first.  The egress switch assumes that we are empty.
    // However we do need to eat the free tokens so that the flow control will work right. 
    VLevelFIFO#(n,`MULTIFPGA_FIFO_SIZES, GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk)) requestQueues <- mkBRAMVLevelFIFO(True); // This true claims all free buffering in the VLevelFIFO.

    Vector#(n, SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk))) ingress_ports = newVector();

    FIFO#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk)) flowcontrolQ <- mkSizedFIFO(8); // might want more buffer here

    Vector#(n, Wire#(Bool)) readReady <- replicateM(mkDWire(False));
    RWire#(Bit#(TLog#(n))) idxExamined <-mkRWire;
    Reg#(Bit#(TLog#(n))) idxRR <- mkReg(0);
    FIFOF#(Tuple2#(Bit#(umf_service_id),Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))))) sendSize <- mkSizedFIFOF(1);
    FIFOF#(GENERIC_UMF_PACKET_HEADER#(umf_channel_id_w, umf_service_id_w,
                                     umf_method_id_w,  umf_message_len_w,
                                     umf_phy_pvt_w,    filler_bits_w)) headerFIFO <- mkFIFOF();
    FIFOF#(umf_chunk_w) bodyFIFO <- mkFIFOF();

    Reg#(Bit#(10)) count <- mkReg(0);

    rule debug (`SWITCH_DEBUG == 1);
        count <= count + 1;
        let used = requestQueues.used();
        let free = requestQueues.free();
        if(count == 0)
        begin
           for(Integer i = 0; i < fromInteger(valueof(n)); i = i + 1)
           begin
               $display("Ingress Queue %d free %d used %d ready %b", i, free[i], used[i], readReady[i]);
           end
        end
    endrule

    // Flowcontrol credit return 
    
    // Depending on packet header parameters, we can be clever and pack flow control tokens along with the header
    // saving a cycle.
    if(valueof(filler_bits) > valueof(SizeOf#(Tuple2#(Bit#(umf_service_id),Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES)))))))
    begin
 
        rule startSendEmpty;
            // We do a round robin to decide which link should have flow control tokens sent back
            if(idxRR == fromInteger(valueof(n)-1)) 
            begin
                idxRR <= 1;
            end 
            else
            begin
                idxRR <= idxRR + 1;
            end

            let use_idx = idxRR;
       
            if(idxExamined.wget() matches tagged Valid .enqIdx)
            begin
                use_idx = enqIdx;
            end

            // If we get too free, we need to send come cedits down the pipe.
            if((requestQueues.free[use_idx] > `MULTIFPGA_FIFO_SIZES/2) && (use_idx != 0))
            begin 

                if(`SWITCH_DEBUG == 1)
                begin
                    $display("Sending %d tokens to %d",requestQueues.free[use_idx],use_idx);
                end

                Tuple2#(Bit#(umf_service_id),Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES)))) control_packet = tuple2(zeroExtend(use_idx),zeroExtend(requestQueues.free[use_idx]));

                // This blob is the header for a flow control packet (with the token information packed in the filler)
                GENERIC_UMF_PACKET_HEADER#(
                    umf_channel_id_w, umf_service_id_w,
                    umf_method_id_w,  umf_message_len_w,
                    umf_phy_pvt_w,    filler_bits_w) header = GENERIC_UMF_PACKET_HEADER
                                       {
                                         filler: zeroExtendNP(pack(control_packet)),
                                         phyChannelPvt: ?,
                                         channelID: ?, // for now we must preserve this because the egress side expects it. 
                                         serviceID: 0, // We're moving in this direction - the feed back uses channel 0
                                         methodID : ?,
                                         numChunks: 0
                                        };

                // hand out the whole pack of tokens  
                requestQueues.decrFree(use_idx, requestQueues.free[use_idx]);
                // send the header packet to channelio
                headerFIFO.enq(header);
           end 
       endrule
    end
    else // In this case the credit bits do not fit in along with the header. 
    begin
        rule startSendEmpty(!sendSize.notEmpty);
            if(idxRR == fromInteger(valueof(n)-1)) 
            begin
                idxRR <= 1;
            end 
            else
            begin
                idxRR <= idxRR + 1;
            end

            let use_idx = idxRR;
       
            if(idxExamined.wget() matches tagged Valid .enqIdx)
            begin
                use_idx = enqIdx;
            end

            // If we get too free, we need to send come cedits down the pipe.
            if((requestQueues.free[use_idx] > `MULTIFPGA_FIFO_SIZES/2)  && (use_idx != 0))
            begin 
                if(`SWITCH_DEBUG == 1)
                begin
                    $display("Sending %d tokens to %d",requestQueues.free[use_idx],use_idx);
                end

                // This is the flow control packet header. 
                GENERIC_UMF_PACKET_HEADER#(
                    umf_channel_id_w, umf_service_id_w,
                    umf_method_id_w,  umf_message_len_w,
                    umf_phy_pvt_w,    filler_bits_w) header = GENERIC_UMF_PACKET_HEADER
                                       {
                                         filler: ?,
                                         phyChannelPvt: ?,
                                         channelID: ?, // for now we must preserve this because the egress side expects it. 
                                         serviceID: 0, // We're moving in this direction - the feed back uses channel 0
                                         methodID : ?,
                                         numChunks: 1
                                        };

                // hand out the whole pack of tokens  
                requestQueues.decrFree(use_idx, requestQueues.free[use_idx]);

                // send the header packet to channelio
                headerFIFO.enq(header);
                sendSize.enq(tuple2(zeroExtend(use_idx),zeroExtend(requestQueues.free[use_idx])));
            end 
        endrule

        rule finishSendEmpty;
            if(`SWITCH_DEBUG == 1)
            begin
                $display("Finished sending tokens");
            end
            umf_chunk_w body = unpack(zeroExtend(pack(sendSize.first)));
            sendSize.deq;
            bodyFIFO.enq(body);
        endrule
    end


    // === other state ===

    Reg#(Bit#(umf_message_len)) requestChunksRemaining  <- mkReg(0);

    Reg#(Bit#(TLog#(n))) requestActiveQueue  <- mkReg(0);

    // ==============================================================
    //                          Request Rules
    // ==============================================================

    // scan channel for incoming request headers
    // the VLevelFIFO is a massive unguarded dance filled with potential miscalculation
    rule scan_requests (requestChunksRemaining == 0);
        let bits <-read();
        GENERIC_UMF_PACKET_HEADER#(
           umf_channel_id, umf_service_id,
           umf_method_id,  umf_message_len,
           umf_phy_pvt,    filler_bits) packet = unpack(pack(bits));
        if(`SWITCH_DEBUG == 1)
          begin
            $display("ingress got a packet for service %d", packet.serviceID);
          end


        // set up remaining chunks
        requestChunksRemaining <= packet.numChunks;
        requestActiveQueue     <= truncate(packet.serviceID);


        // enqueue header in service's queue
        // enqueues are always safe 
        if(packet.serviceID != 0)
        begin
            requestQueues.enq(truncate(packet.serviceID), tagged UMF_PACKET_header packet);
        end
        else 
        begin 
            flowcontrolQ.enq(tagged UMF_PACKET_header packet); // We can probably optimize this a little bit.
        end
    endrule

    // scan channel for request message chunks
    rule scan_params (requestChunksRemaining != 0);

        // grab a chunk from channelio and place it into the active request queue
        umf_chunk packet <- read();
        if(requestActiveQueue != 0)
        begin
            requestQueues.enq(requestActiveQueue, tagged UMF_PACKET_dataChunk packet);
           end
        else 
        begin 
            flowcontrolQ.enq(tagged UMF_PACKET_dataChunk packet); // We can probably optimize this a little bit.
        end

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

    Reg#(Maybe#(Bit#(TLog#(n))))  reqIdx <- mkDReg(tagged Invalid); // We use DReg because we may fail to deq.

    Scheduler#(n,Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))),Bit#(1)) scheduler <- mkZeroCycleScheduler;

    PulseWire deqFired <- mkPulseWire;

    //
    // First half -- pick an incoming responseQueue
    //
    rule write_response_newmsg1;
        scheduler.putInfo(map(pack,readVReg(readReady)), requestQueues.used());
    endrule

    // Now that we have a scheduling decsion, we can setup the switch dequeue
    rule makeReq(scheduler.getNext() matches tagged Valid .idx);
        requestQueues.firstReq(idx);
        if(`SWITCH_DEBUG == 1)
        begin
            $display("%t read request for %d", $time, idx);
        end

        reqIdx <= tagged Valid idx;
    endrule


    // ingress port 0 is used to handle flow control. 
    ingress_ports[0] = interface SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                              umf_channel_id, umf_service_id,
                                                                              umf_method_id,  umf_message_len,
                                                                              umf_phy_pvt,    filler_bits), umf_chunk))

                           // We should probably latch the newMsgqIdx and check that we actually have data before dequeuing
                           method ActionValue#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                       umf_channel_id, umf_service_id,
                                                                       umf_method_id,  umf_message_len,
                                                                       umf_phy_pvt,    filler_bits), umf_chunk)) 
                               read();
                                
                               flowcontrolQ.deq;
                               return flowcontrolQ.first;

                           endmethod

                           method Action read_ready();
                               noAction;
                           endmethod
                       endinterface;


    // need to use the arbiter to choose who we dequeue from
    // the right selection policy probably involves choosing the eldest 
    for (Integer s = 1; s < fromInteger(valueof(n)); s = s + 1)
    begin
         // create a new request port and link it to the FIFO
        ingress_ports[s] = interface SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                                  umf_channel_id, umf_service_id,
                                                                                  umf_method_id,  umf_message_len,
                                                                                  umf_phy_pvt,    filler_bits), umf_chunk))

                           // We should probably latch the newMsgqIdx and check that we actually have data before dequeuing
                           method ActionValue#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                       umf_channel_id, umf_service_id,
                                                                       umf_method_id,  umf_message_len,
                                                                       umf_phy_pvt,    filler_bits), umf_chunk)) 
                               read() if(reqIdx matches tagged Valid .idx &&& fromInteger(s) == idx);
                                
                               // Pick the first data in the queue
                               GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                       umf_channel_id, umf_service_id,
                                                       umf_method_id,  umf_message_len,
                                                       umf_phy_pvt,    filler_bits), umf_chunk) 
                                   val <- requestQueues.firstResp();


                               if(`SWITCH_DEBUG == 1)
                                 begin
                                   $display("%t read dequeue for %d: %h", $time, idx, val); 
                                 end

                               requestQueues.deq(idx); // Will this deq be one cycle behind?  Probably....
                               deqFired.send;
                               return val;

                           endmethod

                           method Action read_ready();
                               readReady[s] <= True;
                           endmethod
                       endinterface;

    end

    rule warnOnNonDeq(reqIdx matches tagged Valid .idx  &&& !deqFired);
      if(`SWITCH_DEBUG == 1)
      begin
          $display("Warning: Queue %d was scheduled but did not deq value",idx);
      end
    endrule

    interface ingressPorts  = ingress_ports;

    interface EGRESS_PACKET_GENERATOR flowcontrol_response;
        method notEmptyHeader = headerFIFO.notEmpty;
        method deqHeader = headerFIFO.deq;
        method firstHeader = headerFIFO.first;
       
        method notEmptyBody = bodyFIFO.notEmpty;
        method deqBody = bodyFIFO.deq;
        method umf_chunk_w firstBody;
            return bodyFIFO.first;
        endmethod
    endinterface

endmodule
