
import ply.yacc as yacc
import ply.lex as lex
from typelex import *
from typeparse import *

def flatten(iterable):
  it = iter(iterable)
  for e in it:
    if isinstance(e, (list, tuple)):
      for f in flatten(e):
        yield f
    else:
      yield e

class TypeParser():
    def __init__(self):
        lex.lex()
        yacc.yacc()

    def parseType(self, typeString):
        typeStruct = yacc.parse(typeString)
        return typeStruct        

