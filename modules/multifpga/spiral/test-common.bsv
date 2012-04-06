`include "awb/provides/soft_connections.bsh"
`include "awb/provides/soft_services.bsh" 
`include "awb/provides/librl_bsv_base.bsh"

import "BDPI" function ActionValue#(Bit#(32))  delay(Bit#(32) incoming);

module [CONNECTED_MODULE] mkForward#(String sendName, String recvName) (Empty);
    Connection_Send#(Bit#(32)) sendX <- mkConnection_Send(sendName);
    Connection_Receive#(Bit#(32)) recvX <- mkConnection_Receive(recvName);
    Reg#(Bit#(32)) reflectCounter <- mkReg(0);
    rule reflect;
        sendX.send(recvX.receive);
        recvX.deq;
        reflectCounter <= reflectCounter + 1;
        $display("%s -> %s:  %d fired",sendName, recvName);
	let val <- delay(recvX.receive);
        if(truncate(recvX.receive) != reflectCounter)
        begin
            $display("Error: got %d expected %d",  recvX.receive, reflectCounter);
            $finish;
        end
    endrule
endmodule
