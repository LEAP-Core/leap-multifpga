`include "asim/provides/soft_connections.bsh"
`include "asim/provides/test_d.bsh"
`include "asim/provides/test_b.bsh"
`include "asim/provides/test_a.bsh"
`include "asim/provides/test_c.bsh"

module [CONNECTED_MODULE] mkSystem (Empty);
  let a <- mkA();
  let b <- mkB();
  let c <- mkC();
  let d <- mkD();
endmodule
