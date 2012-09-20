
typedef union tagged {
  Bit#(10) LegA;
  Bit#(10) LegB;
  Bit#(40) LegC;	
  Bit#(40) LegD;	
} UnionTest deriving (Bits,Eq);