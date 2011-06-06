import sys

class DanglingConnection():
  
  def __init__(self, sc_type, raw_type, idx, name, platform, optional):
      self.sc_type = sc_type
      self.raw_type = raw_type
      self.name = name
      self.idx = -1 # we don't care about the physical indexes yet. They get assigned during the match operation
      self.platform = platform
      self.optional = optional
      self.matched = False

  def matches(self, other):
      if(other.name == self.name):
          #do the types match?
          if(other.raw_type != self.raw_type):
              print "SoftConnection type mismatch: " 
              sys.exit(-1)

          if(other.sc_type == 'Recv' and self.sc_type == 'Send' and not other.matched and not self.matched):
              return True
          if(self.sc_type == 'Recv' and other.sc_type == 'Send' and not other.matched and not self.matched):
              return True

          print "Warning, unknown connection types " + other.sc_type + " " + self.sc_type 
          sys.exit(-1)
      return False

  def isSource(self):
      return self.sc_type == 'Send'

  def isSink(self):
      return self.sc_type == 'Recv'
