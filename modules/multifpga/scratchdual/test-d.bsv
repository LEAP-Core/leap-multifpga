`include "asim/provides/librl_bsv_base.bsh"
`include "asim/provides/librl_bsv_storage.bsh"

`include "asim/provides/soft_connections.bsh"

`include "asim/provides/mem_services.bsh"
`include "asim/provides/common_services.bsh"

`include "asim/dict/VDEV_SCRATCH.bsh"

typedef Bit#(13) MEM_ADDRESS;

module [CONNECTED_MODULE] mkD (Empty);

  Connection_Send#(Bool) sendDone <- mkConnection_Send("Done");
     
  MEMORY_IFC#(MEM_ADDRESS, Bit#(32)) memoryLG <- mkScratchpad(`VDEV_SCRATCH_D, SCRATCHPAD_CACHED);  
 
  Reg#(MEM_ADDRESS) addr <- mkReg(0);
  Reg#(MEM_ADDRESS) addrResps <- mkReg(0);
  Reg#(Bool) writesComplete <- mkReg(False);    

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
        $display("Sending Done");
        sendDone.send(True);
      end

    let data <- memoryLG.readRsp();    
    if(data != zeroExtend(addrResps))
      begin
        $display("Bogus Data @ D: %d %d", addrResps, data);
      end
  endrule


endmodule


