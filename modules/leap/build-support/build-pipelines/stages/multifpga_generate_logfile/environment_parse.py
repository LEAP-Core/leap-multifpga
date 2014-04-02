import sys
import ply.yacc as yacc
from connection import *
from environment import *
from platform import *

def p_environment(p):
    """
    environment : platform_list
    """
    p[0] = FPGAEnvironment(p[1])    

def p_platform_list(p):
    """
    platform_list :
    platform_list : PLATFORM NAME NAME STRING SEMICOLON connection_list ENDPLATFORM platform_list
    platform_list : MASTER NAME NAME STRING SEMICOLON connection_list ENDMASTER platform_list
    """
    if len(p) == 1:
        p[0] = []  # end of list - may want to do stuff here.
    elif p[1] == "master":
        # the eval strips out the "" on the string
        p[0] = [Platform(p[2], p[3], True, eval(p[4]), p[6])] + p[8] 
    else:
        # the eval strips out the "" on the string
        p[0] = [Platform(p[2], p[3], False, eval(p[4]), p[6])] + p[8] 
        
def p_connection_list(p):
    """
    connection_list :
    connection_list : NAME RARROW STRING SEMICOLON connection_list
    connection_list : NAME LARROW STRING SEMICOLON connection_list
    """     
    if len(p) == 1:
        p[0] = []
    else:
        if(p[2] == '<-'):
            p[0] = [PhysicalVia(PhysicalVia.ingress,p[1],eval(p[3]))] + p[5]
        else:
            p[0] = [PhysicalVia(PhysicalVia.egress,p[1],eval(p[3]))] + p[5]

def p_error(p):
    print "LIM ENVIRONMENT: Syntax error at token", p.type
