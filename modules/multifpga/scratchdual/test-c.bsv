`include "asim/provides/librl_bsv_base.bsh"
`include "asim/provides/librl_bsv_storage.bsh"

`include "asim/provides/soft_connections.bsh"

`include "asim/provides/mem_services.bsh"
`include "asim/provides/common_services.bsh"

`include "asim/dict/VDEV_SCRATCH.bsh"

typedef Bit#(13) MEM_ADDRESS;

module [CONNECTED_MODULE] mkC (Empty);

  Connection_Receive#(Bool) sendDone <- mkConnection_Receive("Done");
  Connection_Send#(Bit#(8)) finishConn <- mkConnection_Send("vdev_starter_finish_run");   
  MEMORY_IFC#(MEM_ADDRESS, Bit#(32)) memoryLG <- mkScratchpad(`VDEV_SCRATCH_C, SCRATCHPAD_CACHED);  
 
  Reg#(MEM_ADDRESS) addr <- mkReg(0);
  Reg#(MEM_ADDRESS) addrResps <- mkReg(0);
  Reg#(Bool) writesComplete <- mkReg(False);  
  Reg#(Bool) readsComplete <- mkReg(False);  

  rule tryWrite(!writesComplete);
    addr <= addr + 1;
    if(addr+1 == 0)
      begin
       writesComplete <= True;
      end
    memoryLG.write(addr,zeroExtend(addr));    
  endrule

  rule tryRead(writesComplete);
    addr <= addr + 1;
    memoryLG.readReq(addr);    
  endrule

  rule tryReadRsp;
    addrResps <= addrResps + 1;
    if(addrResps + 1 == 0)
      begin
        readsComplete <= True;
      end

    let data <- memoryLG.readRsp();    
    if(data != zeroExtend(addrResps))
      begin
        finishConn.send(1);
        $display("Bogus Data @ D: %d %d", addrResps, data);
        $finish;
      end
  endrule

  rule fini(readsComplete);
    sendDone.deq;
    finishConn.send(0);
    $display("PASSED");
    $finish;    
  endrule

endmodule


