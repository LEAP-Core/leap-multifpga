`include "asim/provides/soft_connections.bsh"
`include "asim/provides/test_d.bsh"
`include "asim/provides/test_c.bsh"

module [CONNECTED_MODULE] mkSystem (Empty);
  let a <- mkC();
  let b <- mkD();
endmodule
