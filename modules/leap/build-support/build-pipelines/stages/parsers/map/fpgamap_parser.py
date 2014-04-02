import ply.yacc as yacc
import ply.lex as lex
from fpgamaplex import *
from fpgamapparse import *

mapParserCompiled = False
mapParser = None 
mapLexer = None 

def parseFPGAMap(fpgamapfile):
    # build the compiler
    global mapParser
    global mapLexer
    global mapParserCompiled

    if(not mapParserCompiled):
        mapLexer = lex.lex()
        mapParser = yacc.yacc()
        mapParserCompiled = True

    mappingDescription = (open(fpgamapfile, 'r')).read()
    mapping = mapParser.parse(mappingDescription, lexer=mapLexer)
    return mapping
