import List::*;

`include "awb/provides/soft_connections.bsh"
`include "awb/provides/fpga_components.bsh"
`include "awb/provides/librl_bsv_storage.bsh"
`include "awb/provides/common_services.bsh"
`include "awb/dict/PARAMS_THROUGHPUT_REPEATER.bsh"
`include "awb/provides/soft_strings.bsh"

module [CONNECTED_MODULE] mkThroughputRepeater#(Integer station) (Empty);

    STDIO#(Bit#(32)) stdio <- mkStdIO();
    let startMsg <- getGlobalStringUID("Test Complete, repeater " + integerToString(station) + "\n");
  
    // Dynamic parameters
    PARAMETER_NODE paramNode         <- mkDynamicParameterNode();
    Param#(1) initDone               <- mkDynamicParameter(`PARAMS_THROUGHPUT_REPEATER_CHAIN_TEST, paramNode);
    Reg#(Bool) done <- mkReg(False);

    // We don't care about init so long as we are actually initialized. 
    rule sendBiscuit((initDone == 0 || initDone ==1) && !done);
        stdio.printf(startMsg, List::nil);
        done <= True;
    endrule

endmodule

