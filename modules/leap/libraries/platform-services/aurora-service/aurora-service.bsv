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

   AURORA_COMPLEX_DRIVER auroraDriver = drivers.auroraDriver[0];

   STDIO#(Bit#(64)) stdio <- mkStdIO();  
   let serdes_infifo <- mkSizedBRAMFIFOF(64);
   // make soft connections to PHY
   Connection_Send#(Bit#(16)) analogRX <- mkConnectionSendOptional("AuroraRX");
   Reg#(Bit#(40)) rxCount <- mkReg(0);
   Reg#(Bit#(40)) sampleDropped <- mkReg(0);
   Reg#(Bit#(40)) sampleSent <- mkReg(0);
   
    if(`DEBUG_ONLY == 0)
    begin
        rule sendToSW (serdes_infifo.notFull);
            auroraDriver.deq;
            rxCount <= rxCount + 1;           
            sampleSent <= sampleSent + 1;
            serdes_infifo.enq(auroraDriver.first);
   
        endrule
    end

    rule toAnalog;
        serdes_infifo.deq;
        analogRX.send(truncate(serdes_infifo.first()));       
    endrule

    Connection_Receive#(Bit#(16)) analogTX  <- mkConnectionRecvOptional("AuroraTX");

    FIFOF#(Bit#(63)) serdes_send <- mkSizedFIFOF(32);  

    Reg#(Bit#(40)) txCountIn <- mkReg(0);  
    Reg#(Bit#(40)) txCount <- mkReg(0);  

    rule forwardToLL; 
        analogTX.deq();
        txCountIn <= txCountIn + 1;
        serdes_send.enq(zeroExtend(analogTX.receive));
    endrule

    if(`DEBUG_ONLY == 0)
    begin
        rule sendToSERDESData;
            auroraDriver.write(resizeNP(serdes_send.first()));  // Byte endian issue?
            txCount <= txCount + 1;
            serdes_send.deq();
        endrule
    end

    // periodic debug printout
    let aurSndMsg <- getGlobalStringUID("Aurora %d channel_up %x, lane_up %x, error_count %x rx_count %x tx_count %x rx_fifo_count %x tx_fifo_count %x\n");
    let aurFCMsg <- getGlobalStringUID("Flowcontrol tokens RX'ed: %x, Flowcontrol tokens TX'ed %x\n");
    let aurCreditMsg <- getGlobalStringUID("Debug Mode: %x, Aurora credit_underflow %x, rx_credit %x, tx_credit %x, data_drops %x\n");
    let txDebugMsg <- getGlobalStringUID("TXBuffer %x\n");
    let rxDebugMsg <- getGlobalStringUID("RXBuffer %x\n");

    Reg#(Bit#(26)) counter <- mkReg(0);
    Reg#(Bit#(TAdd#(1,TLog#(`NUM_AURORA_IFCS)))) ifc <- mkReg(0);
    AURORA_COMPLEX_DRIVER targetDriver = drivers.auroraDriver[ifc];

    rule printf;
        counter <= counter + 1;
        
        if(counter + 1 == 0) 
        begin
            stdio.printf(aurSndMsg, list8(zeroExtend(ifc),zeroExtend(pack(targetDriver.channel_up)), zeroExtend(pack(targetDriver.lane_up)), zeroExtend(targetDriver.error_count), zeroExtend(targetDriver.rx_count), zeroExtend(targetDriver.tx_count), zeroExtend(pack(targetDriver.rx_fifo_count)), zeroExtend(pack(targetDriver.tx_fifo_count))));
        end
        else if (counter + 1 == 1)
        begin
            stdio.printf(aurCreditMsg, list5(`DEBUG_ONLY, zeroExtend(pack(targetDriver.credit_underflow)), zeroExtend(pack(targetDriver.rx_credit)), zeroExtend(targetDriver.tx_credit), zeroExtend(pack(targetDriver.data_drops))));
        end
        else if (counter + 1 == 2)
        begin
            stdio.printf(aurFCMsg, list2(zeroExtend(pack(targetDriver.rx_fc)), zeroExtend(pack(targetDriver.tx_fc))));
	    if(ifc + 1 == `NUM_AURORA_IFCS)
            begin
	        ifc <= 0;
            end
            else
            begin
	        ifc <= ifc + 1;
            end
        end
    endrule
       

endmodule
