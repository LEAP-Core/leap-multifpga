`include "asim/provides/soft_connections.bsh"
`include "asim/provides/basestation.bsh"
`include "asim/provides/repeater1.bsh"

module [CONNECTED_MODULE] mkSystem (Empty);
  let a <- mkBasestation();
  let b <- mk1();
endmodule
