`include "asim/provides/soft_connections.bsh"

module [CONNECTED_MODULE] mkC (Empty);

  Connection_Receive#(Bit#(16)) aliveIn16 <- mkConnection_Receive("fromD16");
  Connection_Send#(Bit#(16)) aliveOut16 <- mkConnection_Send("fromB16");
  Connection_Receive#(Bit#(32)) aliveIn32 <- mkConnection_Receive("fromD32");
  Connection_Send#(Bit#(32)) aliveOut32 <- mkConnection_Send("fromB32");
  Connection_Receive#(Bit#(64)) aliveIn64 <- mkConnection_Receive("fromD64");
  Connection_Send#(Bit#(64)) aliveOut64 <- mkConnection_Send("fromB64");
  Connection_Receive#(Bit#(128)) aliveIn128 <- mkConnection_Receive("fromD128");
  Connection_Send#(Bit#(128)) aliveOut128 <- mkConnection_Send("fromB128");
  Connection_Receive#(Bit#(256)) aliveIn256 <- mkConnection_Receive("fromD256");
  Connection_Send#(Bit#(256)) aliveOut256 <- mkConnection_Send("fromB256");

  rule sayHello16;
    $display("Alive 16 bounces %d", aliveIn16.receive());
    aliveIn16.deq();
    aliveOut16.send(aliveIn16.receive());
  endrule

  rule sayHello32;
    aliveIn32.deq();
    aliveOut32.send(aliveIn32.receive());
  endrule

  rule sayHello64;
    aliveIn64.deq();
    aliveOut64.send(aliveIn64.receive());
  endrule

  rule sayHello128;
    aliveIn128.deq();
    aliveOut128.send(aliveIn128.receive());
  endrule

  rule sayHello256;
    aliveIn256.deq();
    aliveOut256.send(aliveIn256.receive());
  endrule

endmodule

