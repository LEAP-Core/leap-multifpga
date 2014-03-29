import List::*;


`include "awb/provides/soft_connections.bsh"
`include "awb/provides/fpga_components.bsh"
`include "awb/provides/librl_bsv_storage.bsh"
`include "awb/provides/throughput_repeater.bsh"
`include "awb/provides/common_services.bsh"
`include "awb/provides/soft_strings.bsh"
`include "awb/dict/PARAMS_BASESTATION.bsh"

module [CONNECTED_MODULE] mkBasestation (Empty);

    STDIO#(Bit#(32)) stdio <- mkStdIO();
    let startMsg <- getGlobalStringUID("Test Complete, basestation\n");
      
    // Dynamic parameters
    PARAMETER_NODE paramNode         <- mkDynamicParameterNode();
    Param#(1) initDone               <- mkDynamicParameter(`PARAMS_BASESTATION_BASESTATION_CHAIN_TEST, paramNode);

    Reg#(Bool) done <- mkReg(False);

    // We don't care about init so long as we are actually initialized. 
    rule sendBiscuit((initDone == 0 || initDone ==1) && !done);
        stdio.printf(startMsg, List::nil);
        done <= True;
    endrule
  
endmodule

