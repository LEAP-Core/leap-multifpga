`include "asim/provides/soft_connections.bsh"
`include "asim/provides/test_b.bsh"
`include "asim/provides/test_a.bsh"

module [CONNECTED_MODULE] mkSystem (Empty);
  let a <- mkA();
  let b <- mkB();
endmodule
