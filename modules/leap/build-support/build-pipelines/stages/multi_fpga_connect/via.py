import sys

class Via():
  
  def __init__(self, via_direction, via_header_type, via_body_type, via_type, via_width, via_links, via_io_links, via_flowcontrol_links, via_method, via_switch, via_outgoing_flowcontrol_link, via_outgoing_flowcontrol_via, via_load, via_filler_width):
      self.via_direction = via_direction       
      self.via_type = via_type
      self.via_header_type = via_header_type
      self.via_body_type = via_body_type
      self.via_width = via_width
      self.via_io_links = via_io_links
      self.via_links = via_links
      self.via_flowcontrol_links = via_flowcontrol_links
      self.via_outgoing_flowcontrol_link = via_outgoing_flowcontrol_link
      self.via_outgoing_flowcontrol_via = via_outgoing_flowcontrol_via 
      self.via_method = via_method # the thing we need to call to activate the via
      self.via_switch = via_switch
      self.via_load = via_load
      self.via_filler_width = via_filler_width
