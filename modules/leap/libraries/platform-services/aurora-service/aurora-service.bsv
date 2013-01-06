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
`include "asim/provides/ml605_aurora_device.bsh"
`include "asim/provides/soft_services.bsh"
`include "asim/provides/soft_connections.bsh"
`include "asim/provides/soft_clocks.bsh"
`include "asim/provides/stdio_service.bsh"
`include "asim/provides/soft_strings.bsh"
`include "asim/provides/clocks_device.bsh"
`include "asim/provides/fpga_components.bsh"
`include "asim/provides/librl_bsv_storage.bsh"
`include "asim/provides/librl_bsv_base.bsh"

module [CONNECTED_MODULE] mkAuroraService#(PHYSICAL_DRIVERS drivers) (); 

   AURORA_DRIVER       auroraDriver = drivers.auroraDriver;
   STDIO#(Bit#(64)) stdio <- mkStdIO();  
   let serdes_infifo <- mkSizedBRAMFIFOF(64);
   // make soft connections to PHY
   Connection_Send#(Bit#(16)) analogRX <- mkConnection_Send("AuroraRX");
   Reg#(Bit#(40)) rxCount <- mkReg(0);
   Reg#(Bit#(40)) sampleDropped <- mkReg(0);
   Reg#(Bit#(40)) sampleSent <- mkReg(0);
   
    rule sendToSW (serdes_infifo.notFull);
      auroraDriver.deq;
      rxCount <= rxCount + 1;
      // This may be a bug Alfred will know what to do. XXX
      sampleSent <= sampleSent + 1;
      serdes_infifo.enq(auroraDriver.first);
    endrule

/* ///// ???????????
    rule dropdata (!serdes_infifo.notFull);
       Bit#(16) dataIn <- auroraDriver.read();
       rxCount <= rxCount + 1;
       // This may be a bug Alfred will know what to do. XXX
       sampleDropped <= sampleDropped + 1;
    endrule
*/
    rule toAnalog;
       serdes_infifo.deq;
       analogRX.send(truncate(serdes_infifo.first()));       
    endrule

    Connection_Receive#(Bit#(16)) analogTX <- mkConnection_Receive("AuroraTX");

    let serdes_send <- mkSizedFIFOF(32);  

    Reg#(Bit#(40)) txCountIn <- mkReg(0);  
    Reg#(Bit#(40)) txCount <- mkReg(0);  

    rule forwardToLL; 
      analogTX.deq();
      txCountIn <= txCountIn + 1;
      serdes_send.enq(zeroExtend(analogTX.receive));
    endrule

    rule sendToSERDESData;
      auroraDriver.write(serdes_send.first());  // Byte endian issue?
      txCount <= txCount + 1;
      serdes_send.deq();
    endrule

    // periodic debug printout

   
    /*
        method channel_up = ug_device.channel_up;
        method lane_up = ug_device.lane_up;
        method hard_err = ug_device.hard_err;
        method soft_err = ug_device.soft_err;
 
        method status = ug_device.status;
        method rx_count = ug_device.rx_count;
        method tx_count = ug_device.tx_count;
        method error_count = ug_device.error_count;
        method rx_fifo_count = serdes_rxfifo.dCount;
        method tx_fifo_count = serdes_txfifo.sCount;
*/ 
        let aurSndMsg <- getGlobalStringUID("Aurora channel_up %x, lane_up %x, error_count %x rx_count %x tx_count %x rx_fifo_count %x tx_fifo_count %x\n");

        Reg#(Bit#(24)) counter <- mkReg(0);

        rule printf;
           counter <= counter + 1;
           if(counter + 1 == 0) 
           begin
               stdio.printf(aurSndMsg, list7(zeroExtend(pack(auroraDriver.channel_up)), zeroExtend(pack(auroraDriver.lane_up)), zeroExtend(auroraDriver.error_count), zeroExtend(auroraDriver.rx_count), zeroExtend(auroraDriver.tx_count), zeroExtend(pack(auroraDriver.rx_fifo_count)), zeroExtend(pack(auroraDriver.tx_fifo_count))));
           end
       endrule
        

endmodule
