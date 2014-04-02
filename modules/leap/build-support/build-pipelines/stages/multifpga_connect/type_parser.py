import ply.yacc as yacc
import ply.lex as lex
from typelex import *
from typeparse import *
from environment import *

def parseType (typeString):
    # build the compiler
    lex.lex()
    typeStruct = yacc.parse(typeString)
    return typeStruct
