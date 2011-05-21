`include "asim/provides/soft_connections.bsh"

module [CONNECTED_MODULE] mkD (Empty);
  Connection_Send#(Bool) alive <- mkConnection_Send("fromD");
endmodule

