class LinkType():
  
  def __init__(self, type, compressable, dependencies):
      self.type = type
      self.compressable = compressable
      self.dependencies = dependencies
      
  def __repr__(self):
    return "LinkType: " + str(self.type) + " compressable: " + str(self.compressable) 
