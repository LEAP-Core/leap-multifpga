import sys
import ply.yacc as yacc
from physical_via import *
from environment import *
from platform import *

def p_environment(p):
    """
    environment : platform_list
    """
    p[0] = FPGAEnvironment(p[1])    

def p_comment(p):
    """
    comment : COMMENT
    """
    #We aren't supposed to get here.
    p[0]  = None

def p_platform_list(p):
    """
    platform_list :
    platform_list : comment
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

# The third pattern match, the EQUAL is used to declare parameter values. 
# Probably it would be more clean to make this a seperate syntax element.         
def p_connection_list(p):
    """
    connection_list :
    
    connection_list : physical_via connection_list
    connection_list : int_param connection_list
    connection_list : string_param connection_list
    """     

    if len(p) == 1:
        p[0] = []
    else:
        p[0] = p[1] + p[2]
        

def p_physical_via(p):
    """
    physical_via : NAME RARROW STRING SEMICOLON
    physical_via : NAME LARROW STRING SEMICOLON
    """     

    if(p[2] == '<-'):
        p[0] = [PhysicalVia(PhysicalVia.ingress,p[1],eval(p[3]))]
    elif(p[2] == '->'):
        p[0] = [PhysicalVia(PhysicalVia.egress,p[1],eval(p[3]))] 

def p_int_param(p):
    """
    int_param : NAME EQUAL INT SEMICOLON
    """     
    p[0] = [Parameter(p[1],int(eval(p[3])), "INT")]

def p_string_param(p):
    """
    string_param : NAME EQUAL STRING SEMICOLON
    """     
    p[0] = [Parameter(p[1],eval(p[3]), "STR")]

def p_error(p):
    print "LIM ENVIRONMENT: Syntax error at token", p.type
