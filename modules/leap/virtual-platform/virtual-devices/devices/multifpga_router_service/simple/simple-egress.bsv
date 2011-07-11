`include "awb/provides/rrr.bsh"
`include "awb/provides/umf.bsh"

import Vector::*;

interface SWITCH_EGRESS_PORT;
    method Action write(UMF_PACKET packet);
endinterface

interface EGRESS_SWITCH#(numeric type n);
    interface Vector#(n, SWITCH_EGRESS_PORT)  egressPorts;
endinterface

module mkEgressSwitch#(function ActionValue#(UMF_PACKET) read(), function Action write(UMF_PACKET data)) (EGRESS_SWITCH#(n));
  Vector#(n, SWITCH_EGRESS_PORT) egress_ports = newVector();
  if(valueof(n) > 0)
    begin
      ARBITED_CLIENT#(n) client <- mkArbitedClientNonZero(read, write);

      for (Integer s = 0; s < fromInteger(valueof(n)); s = s + 1)
        begin
          // create a new request port and link it to the FIFO
          egress_ports[s] = interface SWITCH_EGRESS_PORT
                           method write = client.requestPorts[s].write;
                       endinterface;
        end
    end
  interface egressPorts = egress_ports;
endmodule
