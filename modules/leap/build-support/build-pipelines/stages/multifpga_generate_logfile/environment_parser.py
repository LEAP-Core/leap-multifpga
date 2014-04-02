import ply.yacc as yacc
import ply.lex as lex
from environment_lex import *
from environment_parse import *
from environment import *

envParserCompiled = False
envParser = None 
envLexer = None

def parseFPGAEnvironment (environmentFile):
    # build the compiler
    global envParser
    global envParserCompiled
    global envLexer

    if(not envParserCompiled):
        envLexer = lex.lex()
        envParser = yacc.yacc()
        envParserCompiled = True

    environmentDescription = (open(environmentFile, 'r')).read()
    environment = envParser.parse(environmentDescription, lexer=envLexer)
    return environment
