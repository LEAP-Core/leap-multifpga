import sys

class Via():
  
  def __init__(self, via_direction, via_type, via_width, via_links, via_method, via_switch):
      self.via_direction = via_direction       
      self.via_type = via_type
      self.via_width = via_width
      self.via_links = via_links
      self.via_method = via_method # the thing we need to call to activate the via
      self.via_switch = via_switch
