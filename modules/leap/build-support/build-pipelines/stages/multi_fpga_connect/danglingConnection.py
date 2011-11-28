import sys

def inverseSCType(sc_type):
  if(sc_type == 'Send'):
    return 'Recv'
  if(sc_type == 'Recv'):
    return 'Send'
  if(sc_type == 'ChainSink'):
    return 'ChainSrc'
  if(sc_type == 'ChainSrc'):
    return 'ChainSink'

  # not matching is a bad idea
  raise Error

class DanglingConnection():
  
  def __init__(self, sc_type, raw_type, idx, name, platform, optional, bitwidth):
      self.sc_type = sc_type
      self.raw_type = raw_type
      self.name = name
      self.idx = -1 # we don't care about the physical indexes yet. They get assigned during the match operation
      self.platform = platform
      self.optional = optional
      self.bitwidth = int(bitwidth)
      self.matched = False
      self.chainPartner = -1
      self.via_idx = -1
      self.via_link = -1
      self.activity = 0 # this is used in lane allocation

  # can probably extend matches to support chains
  def matches(self, other):
      if(other.name == self.name):
          #do the types match?
          if(other.raw_type != self.raw_type):
              print "SoftConnection type mismatch for " + self.name + ": " + other.raw_type + " and " + self.raw_type
              sys.exit(-1)

          if(other.sc_type == 'Recv' and self.sc_type == 'Send' and not other.matched and not self.matched):
              return True
          if(self.sc_type == 'Recv' and other.sc_type == 'Send' and not other.matched and not self.matched):
              return True
          #Chains also match eachother
          if(other.sc_type == 'ChainSrc' and self.sc_type == 'ChainSink' and not other.matched and not self.matched):
              return True
          if(self.sc_type == 'ChainSink' and other.sc_type == 'ChainSrc' and not other.matched and not self.matched):
              return True

      return False

  def isSource(self):
      return self.sc_type == 'Send' or (self.sc_type == 'ChainSrc')

  def isSink(self):
      return self.sc_type == 'Recv' or (self.sc_type == 'ChainSink')

  def isChain(self):
      return (self.sc_type == 'ChainSrc') or (self.sc_type == 'ChainSink')
