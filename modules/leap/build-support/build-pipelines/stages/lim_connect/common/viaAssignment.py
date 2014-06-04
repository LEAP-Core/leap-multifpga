class ViaAssignment():
  
    def __init__(self, width, load, links):
        self.width = width
        self.load = load
        self.links = links
        
    def __repr__(self):
      return "Via Assignment width: " + str(self.width) + " load: " + str(self.load) + " links: " + str(self.links) + " "
    
