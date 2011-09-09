import os
import sys
import re
import SCons.Script
from model import  *

def host_defs():
    hostos = one_line_cmd('uname -s')
    hostmachine = one_line_cmd('uname -m')

    if (hostos == 'FreeBSD'):
        hflags = '-DHOST_FREEBSD'
    else:
        hflags = '-DHOST_LINUX'
        if (hostmachine == 'ia64'):
            hflags += ' -DHOST_LINUX_IA64'
        else:
            hflags += ' -DHOST_LINUX_X86'

    return hflags


class Software():

  def __init__(self, moduleList):
      moduleList.swExe = []
      if (getBuildPipelineDebug(moduleList) != 0):
          print 'NULL Software'
