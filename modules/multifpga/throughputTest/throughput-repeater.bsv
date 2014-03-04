`include "asim/provides/soft_connections.bsh"

module [CONNECTED_MODULE] mkThroughputRepeater#(Integer station) (Empty);

  Connection_Receive#(Bit#(16)) aliveIn16 <- mkConnection_Receive("16_" + integerToString(station - 1));
  Connection_Send#(Bit#(16)) aliveOut16 <- mkConnection_Send("16_" + integerToString(station));
  Connection_Receive#(Bit#(32)) aliveIn32 <- mkConnection_Receive("32_" + integerToString(station - 1));
  Connection_Send#(Bit#(32)) aliveOut32 <- mkConnection_Send("32_" + integerToString(station));
  Connection_Receive#(Bit#(64)) aliveIn64 <- mkConnection_Receive("64_" + integerToString(station - 1));
  Connection_Send#(Bit#(64)) aliveOut64 <- mkConnection_Send("64_" + integerToString(station));
  Connection_Receive#(Bit#(128)) aliveIn128 <- mkConnection_Receive("128_" + integerToString(station - 1));
  Connection_Send#(Bit#(128)) aliveOut128 <- mkConnection_Send("128_" + integerToString(station));
  Connection_Receive#(Bit#(256)) aliveIn256 <- mkConnection_Receive("256_" + integerToString(station - 1));
  Connection_Send#(Bit#(256)) aliveOut256 <- mkConnection_Send("256_" + integerToString(station));

  rule sayHello16;
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

