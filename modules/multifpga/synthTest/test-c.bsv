`include "asim/provides/soft_connections.bsh"

module [CONNECTED_MODULE] mkC (Empty);
  Connection_Receive#(Bool) alive <- mkConnection_Receive("fromD");
endmodule

