`include "awb/provides/rrr.bsh"
`include "awb/provides/umf.bsh"

import Vector::*;

// request/response port interfaces
interface SWITCH_INGRESS_PORT;
    method ActionValue#(UMF_PACKET) read();
    method Action read_ready();
endinterface

interface INGRESS_SWITCH#(numeric type n);
    interface Vector#(n, SWITCH_INGRESS_PORT)  ingressPorts;
endinterface

module mkIngressSwitch#(function ActionValue#(UMF_PACKET) read(), function Action write(UMF_PACKET data)) (INGRESS_SWITCH#(n));
  Vector#(n, SWITCH_INGRESS_PORT) ingress_ports = newVector();
  if(valueof(n) > 0)
    begin
      ARBITED_SERVER#(n) server <- mkArbitedServerNonZero(read,write);

      for (Integer s = 0; s < fromInteger(valueof(n)); s = s + 1)
        begin
          // create a new request port and link it to the FIFO
          ingress_ports[s] = interface SWITCH_INGRESS_PORT
                           method read = server.requestPorts[s].read;
                           method read_ready = ?;
                       endinterface;
        end
    end
 interface ingressPorts = ingress_ports;
endmodule


