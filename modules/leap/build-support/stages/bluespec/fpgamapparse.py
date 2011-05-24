import sys
import ply.yacc as yacc
from fpgamap import *

def p_mapping(p):
    """
    mapping : mapping_list
    """
    p[0] = FPGAMap(p[1])    

def p_mapping_list(p):
    """
    mapping_list :  
    mapping_list : NAME RARROW NAME SEMICOLON mapping_list 
    """
    if len(p) == 1:
        p[0] = []
    else:
        p[0] = [[p[1],p[3]]] + p[5]
