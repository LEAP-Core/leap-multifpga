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

import Vector::*;
import List::*;

`include "awb/provides/virtual_platform.bsh"
`include "awb/provides/virtual_devices.bsh"
`include "awb/provides/common_services.bsh"
`include "awb/provides/librl_bsv.bsh"

`include "awb/provides/soft_connections.bsh"
`include "awb/provides/soft_services.bsh"
`include "awb/provides/soft_services_lib.bsh"
`include "awb/provides/soft_services_deps.bsh"
`include "awb/provides/dynamic_parameters_service.bsh"
`include "awb/dict/PARAMS_CONNECTED_APPLICATION.bsh"

typedef enum 
{
    STATE_start,
    STATE_say_hello,
    STATE_finish
} 
STATE deriving (Bits, Eq);


module [CONNECTED_MODULE] mkConnectedApplication ();

    Connection_Receive#(Bool) linkStarterStartRun <- mkConnectionRecv("vdev_starter_start_run");
    Connection_Send#(Bit#(8)) linkStarterFinishRun <- mkConnectionSend("vdev_starter_finish_run");
    STDIO#(Bit#(64)) stdio <- mkStdIO();

    Reg#(STATE) state <- mkReg(STATE_start);

    rule start (state == STATE_start);
        linkStarterStartRun.deq();
        state <= STATE_say_hello;
    endrule

    let msg <- getGlobalStringUID("Hello, World! This is hardware speaking.\n");

    rule hello (state == STATE_say_hello);
        stdio.printf(msg, List::nil);
        state <= STATE_finish;
        //linkStarterFinishRun.send(0);
    endrule

    rule finish (state == STATE_finish);
        noAction;
    endrule

    
   PARAMETER_NODE paramNode  <- mkDynamicParameterNode();
   Param#(8) sleepTime <- mkDynamicParameter(`PARAMS_CONNECTED_APPLICATION_SLEEP_TIME,paramNode);
   Param#(1) verbose   <- mkDynamicParameter(`PARAMS_CONNECTED_APPLICATION_VERBOSE,paramNode);
            


		Connection_Receive#(Bit#(63)) auroraRecv <- mkConnectionRecv("AuroraRX");
    Connection_Send#(Bit#(63)) auroraSend <- mkConnectionSend("AuroraTX");
		let aurMsg <- getGlobalStringUID("Aurora recv'd %x \n");
		let aurSndMsg <- getGlobalStringUID("Aurora sent %x \n");
		let aurErrorMsg <- getGlobalStringUID("Aurora recv'd %x expected %x total errors %x\n");
		Reg#(Bit#(63)) auroraTestVal <- mkReg(0);
		Reg#(Bit#(63)) recvExpected <- mkReg(0);
		Reg#(Bit#(8)) sleep  <- mkReg(0);
                Reg#(Bit#(32)) errors <- mkReg(0); 

                rule sleepUp(sleep != 0);
                   sleep <= sleep + 1;
                endrule


		rule sendToAurora(sleep == 0);
                        if(sleep + 1 < sleepTime)
                        begin
                            sleep <= sleep + 1;
                        end
                        else 
                        begin
                            sleep <= 0;
                        end 

                        if(sleep == 0)
                        begin
  			    auroraTestVal <= auroraTestVal + 1;
			    auroraSend.send(auroraTestVal);
                            if(unpack(verbose))
                            begin          
                                stdio.printf(aurSndMsg, list1(zeroExtend(auroraTestVal)));
                            end
                        end
		endrule

               

		rule recvFromAurora;
                    auroraRecv.deq();
                    recvExpected <= recvExpected + 1;

                    if(auroraRecv.receive() != recvExpected)
                    begin 
                         errors <= errors + 1;
                         stdio.printf(aurErrorMsg, list3(zeroExtend(auroraRecv.receive), zeroExtend(recvExpected), zeroExtend(errors)));
                    end 
                    else if(unpack(verbose))
                    begin    
                        stdio.printf(aurMsg, list1(zeroExtend(auroraRecv.receive)));
                    end


		endrule
endmodule
