class LinkType():
  
  def __init__(self, type, compressable):
      self.type = type
      self.compressable = compressable
  
      
  def __repr__(self):
    return "LinkType: " + str(self.type) + " compressable: " + str(self.compressable) 
