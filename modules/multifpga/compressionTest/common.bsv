
typedef union tagged {
  Bit#(1) LegA;
  Bit#(10) LegB;
  Bit#(40) LegC;	
  Bit#(50) LegD;	
} UnionTest deriving (Bits,Eq);