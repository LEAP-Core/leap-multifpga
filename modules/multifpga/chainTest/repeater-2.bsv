`include "awb/provides/soft_connections.bsh"
`include "awb/provides/throughput_repeater.bsh"


module [CONNECTED_MODULE] mk2 (Empty);

  let m <- mkThroughputRepeater(2);

endmodule

