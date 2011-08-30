//----------------------------------------------------------------------//
// The MIT License 
// 
// Copyright (c) 2008 Alfred Man Cheuk Ng, mcn02@mit.edu 
// 
// Permission is hereby granted, free of charge, to any person 
// obtaining a copy of this software and associated documentation 
// files (the "Software"), to deal in the Software without 
// restriction, including without limitation the rights to use,
// copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be
// included in all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
// EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
// OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
// WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
// FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
// OTHER DEALINGS IN THE SOFTWARE.
//----------------------------------------------------------------------//

//////////////////////////////////////////////////////////////////////////
// Summary:
//
// This file describes the implementations of a level of a merge tree, there
// are two implementations: 1) mkTwoToOneMerger and 2) mkBRAMOneLevelMerger. 
// "mkTwoToOneMerger" is used to instantiate the top level 
// (i.e. the 1st level) of the sort tree. It is a straight forward implementation of 
// a two-to-one merger which merges two sorted streams into a single sorted stream.
// The implementation is parameterized for the width of the each data entry.       
// "mkBRAMOneLevelMerger" is used to instantiate other levels of the sort tree.
// The implementation merges 2n sorted streams into n sorted streams, whereas n is 
// a static parameter. It is obvious that an straight forward implementation 
// will simply have n two-to-one mergers. However, this makes the area of one level 
// roughly grows twice as big as the previous level. Since the performance of 
// is bottlenecked by the top level, we decide to time multiplex a single two-to-one
// merger between the 2n streams. This allows the area of the design grow with the level
// while maintaining roughtly the same performance throughput. One of the biggest challenges
// of the design is to determine which two stream to be merged next. 
// The problem gets tougher with lower level of the sort tree because more streams are available. 
// To solve this problem, we make the scheduler as a parameter to "mkBRAMOneLevelMerger". 
// The scheduler implements the algorithm for picking the next two stream to merge. 
// We have different implementations of the scheduler which have different complexity and 
// take different number of cycles to return the decision. By passing the appropriate scheduler 
// implementations to the same "mkBRAMOneLevelMerger" definition, we can instantiate 
// different levels of the sort tree with roughly the same critical path.                                
//////////////////////////////////////////////////////////////////////////

// import standard librarys
import Connectable::*;
import GetPut::*;
import FIFO::*;
import FIFOF::*;
import StmtFSM::*;
import Vector::*;

// import self-made library
import BRAMVLevelFIFO::*;
import EHRReg::*;
import VLevelFIFO::*;

`define SortDebug0 False
`define SortDebug1 False

//////////////////////////////////////////////////////////////////////////////////////////////
// interfaces definitions

// the scheduler interface, the scheduler try to collect credit tokens information
// from the next level and the current level of the sort and then decide which
// stream to process next  
interface Scheduler#(numeric type k, type tok_t, type next_tok_t);
   // give the scheduler usage information so that it can pick the next to process
   (* always_ready *) method Action putInfo(Vector#(k,next_tok_t) nextTok,
                                            Vector#(k,tok_t)      tok0);
                         
   // return the next stream to be processed, if return tagged Invalid = do nothing
   (* always_ready *) method Maybe#(Bit#(TLog#(k))) getNext();
endinterface 



//////////////////////////////////////////////////////////////////////////
// auxiliary functions

function Bool notValid(Maybe#(a) i);
   return !isValid(i);
endfunction

function Bool largerThan(Bit#(sz) a, Bit#(sz) val);
   return val > a;
endfunction

function Bool and3(Bool a, Bool b, Bool c);
   return a && b && c;
endfunction

function Tuple2#(Bool,a) chooseFirstIfPossible(Tuple2#(Bool,a) fst,
                                               Tuple2#(Bool,a) snd);
   return tpl_1(fst) ? fst : snd;
endfunction

function Bool isSmaller(d_t a, d_t b)
   provisos (Bits#(d_t,d_sz),
             Mul#(8,q_sz,d_sz),
             Add#(1,xxA,d_sz));
   
   Vector#(8,Bit#(q_sz)) aVec = reverse(unpack(pack(a)));
   Vector#(8,Bit#(q_sz)) bVec = reverse(unpack(pack(b)));
   
   function Tuple2#(Bool,Bool) getLargerAndEqual(Tuple2#(Bool,Bool) aTup, Tuple2#(Bool,Bool) bTup);
      return tuple2((tpl_1(aTup) || (tpl_2(aTup) && tpl_1(bTup))), 
                    (tpl_2(aTup) && tpl_2(bTup)));
   endfunction
   
   let res = tpl_1(fold(getLargerAndEqual, 
                        zip(zipWith(\< ,aVec,bVec),
                            zipWith(\== ,aVec,bVec))));
   
   return res;
   
endfunction

//////////////////////////////////////////////////////////////////////////
// Module definitions

// a scheduler which the scheduling decision is return in the same cycle
module mkZeroCycleScheduler (Scheduler#(k_next,Bit#(sz),Bit#(sz_next)))
   provisos (Add#(1,xxA,k_next));
   
   Reg#(Maybe#(Bit#(TLog#(k_next))))  last     <- mkReg(tagged Invalid);

   Wire#(Maybe#(Bit#(TLog#(k_next)))) getNextW <- mkDWire(tagged Invalid); 
   
   method Action putInfo(Vector#(k_next,Bit#(sz_next)) nextTok,
                         Vector#(k_next,Bit#(sz))      tok0);

      let idx    = fromMaybe(?,last);
      let okNext = map(largerThan(0),nextTok);
      let ok0    = map(largerThan(0),tok0);
      ok0[idx]   = isValid(last) ? False : ok0[idx];
      let okVec0 = zipWith( \&& ,okNext,ok0);
      Vector#(k_next,Integer) intVec = genVector();
      let vec0   = zip(okVec0,intVec);
      let res0   = fold(chooseFirstIfPossible,vec0);
      let dec    = tpl_1(res0) ? tagged Valid fromInteger(tpl_2(res0)) : 
                                 tagged Invalid;  
      last <= dec;
      getNextW <= dec;

      if(isValid(dec))
        if(`SortDebug0) $display("%m scheduler choose ok %d idx %d",isValid(dec),fromMaybe(?,dec));
   endmethod
      
   method Maybe#(Bit#(TLog#(k_next))) getNext();
      return getNextW;
   endmethod

endmodule

// a scheduler which the scheduling decision is returned one cycle later
module mkOneCycleScheduler (Scheduler#(k_next,Bit#(sz),Bit#(sz_next)))
   provisos (Add#(1,xxA,k_next));
   
   Reg#(Maybe#(Bit#(TLog#(k_next))))  last     <- mkReg(tagged Invalid);
   Reg#(Maybe#(Bit#(TLog#(k_next))))  sndLast  <- mkReg(tagged Invalid);
   Reg#(Maybe#(Bit#(TLog#(k_next))))  sRes0    <- mkReg(tagged Invalid);
   Reg#(Maybe#(Bit#(TLog#(k_next))))  sRes1    <- mkReg(tagged Invalid);

   Wire#(Maybe#(Bit#(TLog#(k_next)))) getNextW <- mkDWire(tagged Invalid); 
   
   rule choose(True);
      let chk1 = (sRes1 != last) && (sRes1 != sndLast);
      let next = chk1 ? sRes1 : sRes0;
      sndLast <= last;
      last <= next;
      getNextW <= next;
      if(`SortDebug0) $display("%m scheduler choose ok %d idx %d",isValid(next),fromMaybe(?,next));
   endrule   
   
   method Action putInfo(Vector#(k_next,Bit#(sz_next)) nextTok,
                         Vector#(k_next,Bit#(sz))      tok0);

      let okNext = map(largerThan(2),nextTok);
      let ok0    = map(largerThan(2),tok0);
      let okVec0 = zipWith( \&& ,okNext,ok0);
      Vector#(k_next,Integer) intVec = genVector();
      let vec0   = zip(okVec0,intVec);
      let res0   = fold(chooseFirstIfPossible,vec0);
      let dec0   = tpl_1(res0) ? tagged Valid fromInteger(tpl_2(res0)) : 
                                 tagged Invalid;  

      let okNext1 = map(largerThan(0),nextTok);
      let ok2     = map(largerThan(0),tok0);
      let okVec1  = zipWith( \&& ,okNext1,ok2);
      let vec1    = zip(okVec1,intVec);
      let res1    = fold(chooseFirstIfPossible,vec1);
      let dec1    = tpl_1(res1) ? tagged Valid fromInteger(tpl_2(res1)) : 
                                  tagged Invalid;  
   
      sRes0 <= dec0;
      sRes1 <= dec1;
   endmethod
      
   method Maybe#(Bit#(TLog#(k_next))) getNext();
      return getNextW;
   endmethod

endmodule

// a scheduler which the scheduling decision is returned one cycle later
module mkOneCycleScheduler2 (Scheduler#(k_next,Bit#(sz),Bit#(sz_next)))
   provisos (Add#(1,xxA,k_half),
             Div#(k_next,2,k_half),
             Add#(k_half,k_half,k_next));
   
   Reg#(Maybe#(Bit#(TLog#(k_next))))  last     <- mkReg(tagged Invalid);
   Reg#(Maybe#(Bit#(TLog#(k_next))))  sndLast  <- mkReg(tagged Invalid);
   Reg#(Maybe#(Bit#(TLog#(k_next))))  sRes0    <- mkReg(tagged Invalid);
   Reg#(Maybe#(Bit#(TLog#(k_next))))  sRes1    <- mkReg(tagged Invalid);
   Reg#(Maybe#(Bit#(TLog#(k_next))))  sRes2    <- mkReg(tagged Invalid);
   Reg#(Maybe#(Bit#(TLog#(k_next))))  sRes3    <- mkReg(tagged Invalid);
   Reg#(Bool)                         round    <- mkReg(False);
   
   Wire#(Maybe#(Bit#(TLog#(k_next)))) getNextW <- mkDWire(tagged Invalid); 
   
   rule choose(True);
//       let chk2 = (sRes2 != last) && (sRes2 != sndLast);
//       let chk3 = (sRes3 != last) && (sRes3 != sndLast);
//       let next0 = chk2 ? sRes2 : sRes0;
//       let next1 = chk3 ? sRes3 : sRes1;
//       let next3 = isValid(next0) ? next0 : next1;
//       let next4 = isValid(next1) ? next1 : next0;
//       let next = round ? next3 : next4;

      let chk2 = (sRes2 != last) && (sRes2 != sndLast);
      let chk3 = (sRes3 != last) && (sRes3 != sndLast);
      let next0 = chk2 ? sRes2 : sRes0;
      let next1 = chk3 ? sRes3 : sRes1;
      let next  = round ? next0 : next1;

      sndLast <= last;
      last <= next;
      getNextW <= next;
      round <= !round;
      
      if(`SortDebug0) $display("%m scheduler choose ok %d idx %d",isValid(next),fromMaybe(?,next));
   endrule   
   
   method Action putInfo(Vector#(k_next,Bit#(sz_next)) nextTok,
                         Vector#(k_next,Bit#(sz))      tok0);
//       let okNext = map(largerThan(2),nextTok);
//       let ok0    = map(largerThan(2),tok0);
//       let ok1    = map(largerThan(2),tok1);   
//       let okVec = zipWith3(and3,okNext,ok0,ok1);
      Vector#(k_next,Integer) intVec = genVector();
//       let vec   = zip(okVec,intVec);
//       Vector#(k_half,Tuple2#(Bool,Integer)) vec0 = take(vec);
//       Vector#(k_half,Tuple2#(Bool,Integer)) vec1 = takeTail(vec);
//       let res0   = fold(chooseFirstIfPossible,vec0);
//       let res1   = fold(chooseFirstIfPossible,vec1);
//       let dec0   = tpl_1(res0) ? tagged Valid fromInteger(tpl_2(res0)) : 
//                                  tagged Invalid;  
//       let dec1   = tpl_1(res1) ? tagged Valid fromInteger(tpl_2(res1)) : 
//                                  tagged Invalid;  

      let okNext1 = map(largerThan(0),nextTok);
      let ok2     = map(largerThan(0),tok0);
      let okVec1  = zipWith( \&& ,okNext1,ok2);
      let vecc    = zip(okVec1,intVec);
      Vector#(k_half,Tuple2#(Bool,Integer)) vec2 = take(vecc);
      Vector#(k_half,Tuple2#(Bool,Integer)) vec3 = takeTail(vecc);
      let res2   = fold(chooseFirstIfPossible,vec2);
      let res3   = fold(chooseFirstIfPossible,vec3);
      let dec2   = tpl_1(res2) ? tagged Valid fromInteger(tpl_2(res2)) : 
                                 tagged Invalid;  
      let dec3   = tpl_1(res3) ? tagged Valid fromInteger(tpl_2(res3)) : 
                                 tagged Invalid;  
   
//      sRes0 <= dec0;
//      sRes1 <= dec1;
      sRes2 <= dec2;
      sRes3 <= dec3;
   endmethod
      
   method Maybe#(Bit#(TLog#(k_next))) getNext();
      return getNextW;
   endmethod

endmodule

