import ply.yacc as yacc
import ply.lex as lex
from fpgamaplex import *
from fpgamapparse import *


def parseFPGAMap(fpgamapfile):
    # build the compiler
    lex.lex()
    yacc.yacc()
    mappingDescription = (open(fpgamapfile, 'r')).read()
    mapping = yacc.parse(mappingDescription)
    return mapping
