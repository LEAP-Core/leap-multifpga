`include "asim/provides/soft_connections.bsh"
`include "asim/provides/basestation.bsh"
`include "asim/provides/repeater1.bsh"
`include "asim/provides/repeater2.bsh"

module [CONNECTED_MODULE] mkSystem (Empty);
  let b <- mkBasestation();
  let r1 <- mk1();
  let r2 <- mk2();
endmodule
