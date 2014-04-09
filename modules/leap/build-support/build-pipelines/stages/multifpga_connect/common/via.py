import sys

class Via():
  
    def __init__(self, via_source, via_sink, via_direction, umfType, via_width, via_links, via_io_links, via_flowcontrol_links, via_method, via_switch, via_outgoing_flowcontrol_link, via_outgoing_flowcontrol_via, via_load, via_filler_width):
        self.via_source = via_source
        self.via_sink = via_sink
        self.via_direction = via_direction
        self.umfType = umfType       
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


    def __repr__(self):
        return "Via direction:" + self.via_direction +  "width: " + str(self.via_width) + " load: " + str(self.via_load) + " links: " + str(self.via_links) + " type: " + str(self.umfType) + " flowcontrol_link: " + str(self.via_outgoing_flowcontrol_link) +  " flowcontrol_via: " + str(self.via_outgoing_flowcontrol_via) 
    
