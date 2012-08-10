import copy
import sys
import ply.yacc as yacc
from typelex import *
from taggedUnion import *
from struct import *
from type import *
from member import *
from typeclass import *

#TaggedUnion union::UnionTest1 {members {{void YesEmpty {width 0}} {Bool NotEmpty {width 1}} {Bit#(32) Value {width 32}}}} {width 34} {position {union.bsv 7 3}}

debugParser = True

def dumpToks(p):
    toks = ""
    for idx in range(1,len(p)):
        toks += str(p[idx])
    return toks

def p_type_decl(p):
    """
    type_decl : tagged_union 
    type_decl : alias 
    type_decl : struct 
    type_decl : typeclass
    type_decl : poly_tagged_union 
    type_decl : poly_struct 
    type_decl : type
    """
    if(debugParser):
        print "type_decl " + str(p) + "\n"
    p[0] = p[1]

def p_typeclass(p):
    """
    typeclass : TYPECLASS type dependence_decl member_decl instances position
    """
    if(debugParser):
        print "parse typeclass " + str(p) + "\n"
    p[0] = Typeclass(p[2],p[5])


def p_tagged_union(p):
    """
    tagged_union : TAGGEDUNION type member_decl width position
    """
    if(debugParser):
        print "parse tagged_union " + str(p) + "\n"
    p[0] = TaggedUnion(p[2],p[3],p[4])

def p_alias(p):
    """
    alias : ALIAS type type position
    """
    if(debugParser):
        print "parse alias " + str(p) + "\n"
    p[0] = TypeAlias(p[2],p[3])

def p_struct(p):
    """
    struct : STRUCT type member_decl width position
    """
    if(debugParser):
        print "struct " + str(p) + "\n"
    p[0] = Struct(p[2],p[3],p[4])

def p_type(p):
    """
    type : NAME DOUBLECOLON type
    type : NAME POUND param_list 
    type : NAME
    type : type PROVISOS LPAREN proviso_list RPAREN 
    type : LCURLY type RCURLY
    type : FUNCTION type NAME LPAREN argument_list RPAREN
    type : poly_type
    """
    if(debugParser):
        print "parse type: " + dumpToks(p) + "\n"
    if(len(p) == 2):
        if(isinstance(p[1],PolyType)):
            p[0] = p[1]       
        else: 
            # we may have a polymorphic type, if the name begins with a lowercase.
            if(p[1][0].isupper()):
                p[0] = Type(p[1],[])
            else:
                p[0] = PolyType(p[1])
    elif(len(p) == 4):
        if(isinstance(p[2],Type)):
            p[0] = p[2]
        elif(p[2] == "::"):
            p[0] = TypeRef(p[1],p[3].name,p[3].params)
        else:
            p[0] = Type(p[1],p[3])
    elif(len(p) == 7):
        #function type
        p[0] = Function(p[3],p[2],p[5])
    elif(len(p) == 6):
        #Something with provisos type
        p[0] = p[1]
    else:
        print "Type parsing error, expected type"
        exit(0)
def p_param_list(p):
    """
    param_list : LPAREN INT comma_list RPAREN
    param_list : LPAREN type comma_list RPAREN
    param_list : LPAREN type_function comma_list RPAREN
    """
    if(debugParser):
        print "parse param_list: " + dumpToks(p)  + "\n"
    if(isinstance(p[2],str)):
        p[0] = [NumericType(int(p[2]))] + p[3]
    else:
        p[0] =  [p[2]] + p[3]



def p_comma_list(p):
    """
    comma_list : 
    comma_list : param comma_list
    """
    if(debugParser):
        print "parse comma: " + dumpToks(p)  + "\n"
    if(len(p) == 1):
        p[0] = []
    else:
        p[0] = [p[1]] + p[2]

def p_param(p):
    """
    param : COMMA INT
    param : COMMA type
    param : COMMA type_function
    """
    if(debugParser):
        print "parse param: " + dumpToks(p)  + "\n"
    if(isinstance(p[2],str)):
        p[0] = NumericType(int(p[2]))
    else:
        p[0] = p[2]



def p_poly_tagged_union(p):
    """
    poly_tagged_union : TAGGEDUNION poly_decl member_decl position
    """
    if(debugParser):
        print "parse poly tagged_union " + dumpToks(p) + "\n"
    p[0] =  PolyTaggedUnion(p[2],p[3])

def p_poly_struct(p):
    """
    poly_struct : STRUCT poly_decl member_decl position
    """
    if(debugParser):
        print "poly struct " + dumpToks(p) + "\n"
    p[0] = PolyStruct(p[2],p[3])



def p_poly_decl(p):
    """
    poly_decl : LCURLY type RCURLY POLYMORPHIC    
    """
    if(debugParser):
        print "parse poly decl: " + dumpToks(p) + "\n"
    p[0] = p[2]

def p_poly_type(p):
    """
    poly_type : TYPE NAME
    poly_type : NUMERIC TYPE NAME
    """
    if(debugParser):
        print "parse poly type: " + dumpToks(p) + "\n"

    if(len(p) == 4):
        p[0] =  PolyNumericType(p[3])
    else:
        p[0] = PolyType(p[2])

def p_member_decl(p):
    """
    member_decl : LCURLY MEMBERS LCURLY member_list RCURLY RCURLY
    """
    if(debugParser):
        print "parse member_decl: " + str(p) + "\n"
 
    p[0] = p[4]
        
#def p_member_list(p):
#    """
#    member_list : member_list LCURLY type NAME width RCURLY 
#    member_list : member_list LCURLY poly_type NAME RCURLY 
#    member_list : member_list LCURLY type NAME RCURLY 
#    member_list : LCURLY type NAME width RCURLY 
#    member_list : LCURLY poly_type NAME RCURLY
#    member_list : LCURLY member_list RCURLY
#    """     
#    if(debugParser):
#        print "parse memberlist: " + dumpToks(p) + "\n"
#    if len(p) == 7:
#        p[0] = p[1] + [Member(p[3],p[4],p[5],len(p[1]))]
#    elif len(p) == 5:
#        p[0] = [PolyMember(p[2],p[3],0)]
#    elif len(p) == 4:
#        p[0] = p[2]
#    elif isinstance(p[2],Type):
#        p[0] = [Member(p[2],p[3],p[4],0)]
#    else:
#        p[0] = p[1] + [PolyMember(p[3],p[4],len(p[1]))]


def p_member_list(p):
    """
    member_list : member_list member 
    member_list : member_list poly_member
    member_list : member 
    member_list : poly_member
    """     
    if(debugParser):
        print "parse memberlist: " + dumpToks(p) + "\n"
    if len(p) == 2:
        p[1].index = 0
        p[0] = [p[1]]
    else:
        p[2].index = len(p[1])
        p[0] = p[1] + [p[2]]

def p_member(p):
    """
    member : LCURLY type NAME width RCURLY 
    """     
    if(debugParser):
        print "parse member: " + dumpToks(p) + "\n"
    p[0] =  Member(p[2],p[3],p[4],-1)

def p_poly_member(p):
    """
    poly_member : LCURLY type NAME RCURLY 
    """     
    if(debugParser):
        print "parse poly_member: " + dumpToks(p) + "\n"
    p[0] = PolyMember(p[2],p[3],-1)
    
def p_dependence_decl(p):
    """                                                                                                                      
    dependence_decl : LCURLY DEPENDENCIES LCURLY dependence_list RCURLY RCURLY          
    """
    if(debugParser):
        print "parse dependence_decl: " + dumpToks(p) + "\n"
    p[0] = []

def p_dependence_list(p):
    """
    dependence_list : dependence dependence_list 
    dependence_list : dependence 
    """     
    if(debugParser):
        print "parse dependence_list: " + dumpToks(p) + "\n"
    p[0] = []

def p_dependence(p):
    """
    dependence : LCURLY type DETERMINES type RCURLY
    dependence : LCURLY type DETERMINES param_list RCURLY
    """     
    # I'm reusing param list here, even though that probably isn't correct.
    if(debugParser):
        print "parse dependence: " + dumpToks(p) + "\n"
    p[0] = []

def p_width(p):
    """
    width : LCURLY WIDTH INT RCURLY
    """     
    if(debugParser):
        print "parse width: " + str(p[3]) + "\n"
    p[0] = int(p[3])

def p_position(p):
    """
    position : LCURLY POSITION LCURLY file INT INT RCURLY RCURLY
    """     
    if(debugParser):
        print "parse position: " + str(p) + "\n"
    p[0] = [] # we don't use this

def p_path(p):
    """
    path : NAME
    path : NAME PERIOD path
    path : NAME DASH path
    """     
    if(debugParser):
        print "parse path: " + str(p) + "\n"
    if len(p) == 2:
        p[0] = p[1]
    else:
        p[0] = p[1] + p[2] + p[3]

def p_file(p):
    """
    file : path
    file : NAME FSLASH file
    """     
    if(debugParser):
        print "parse filename: " + str(p) + "\n"
    if len(p) == 2:
        p[0] = p[1]
    else:
        p[0] = p[1] + '/' + p[3]

def p_error(p):
    if(p is None):
        raise TypeError("Error: No Tokens")
    else:
        raise TypeError("Error at token: " + p.value)

    
def p_argument_list(p):
    """
    argument_list : LPAREN  RPAREN
    argument_list : LPAREN argument argument_comma_list RPAREN
    """
    if(debugParser):
        print "parse argument_list: " + dumpToks(p)  + "\n"
    if(len(p) ==2):
        p[0] =  []
    else:
        p[0] = [p[2]] + p[3]

def p_argument_comma_list(p):
    """
    argument_comma_list : COMMA argument
    argument_comma_list : COMMA argument argument_comma_list
    """
    if(debugParser):
        print "parse argument_comma_list: " + dumpToks(p)  + "\n"
    if(len(p) == 2):
        p[0] = [p[2]]
    else:
        p[0] = [p[2]] + p[3]


def p_argument(p):
    """
    argument : type NAME
    """
    if(debugParser):
        print "parse argument: " + dumpToks(p)  + "\n"    
    p[0] = p[1]

def p_instances(p):
    """
    instances : LCURLY INSTANCES LCURLY instance_list RCURLY RCURLY
    """
    if(debugParser):
        print "parse instances: " + dumpToks(p)  + "\n"
    p[0] = p[4]

def p_instance_list(p):
    """
    instance_list : LCURLY type RCURLY instance_list
    instance_list : LCURLY type RCURLY
    """
    if(debugParser):
        print "parse instances_list: " + dumpToks(p)  + "\n"
    if(len(p) == 4):
        p[0] = [p[2]]
    else:
        p[0] = [p[2]] + p[4]


def p_proviso_list(p):
    """
    proviso_list : proviso COMMA proviso_list
    proviso_list : proviso
    """
    if(debugParser):
        print "parse proviso_list: " + dumpToks(p)  + "\n"
    if(len(p) == 2):
        p[0] = [p[1]]
    else:
        p[0] = [p[1]] + p[3]

def p_proviso(p):
    """
    proviso : NAME POUND LPAREN term_list RPAREN
    """
    if(debugParser):
        print "parse proviso: " + dumpToks(p)  + "\n"
    p[0] = Proviso(p[1],p[4])


def p_term_list(p):
    """
    term_list : INT COMMA term_list
    term_list : NAME COMMA term_list
    term_list : type_function COMMA term_list
    term_list : INT
    term_list : NAME    
    term_list : type_function
    """
    if(debugParser):
        print "parse term_list: " + dumpToks(p)  + "\n"
    if(len(p) == 4):
        p[0] = [p[1]] + p[3]
    else:
        p[0] = [p[1]]

def p_type_function(p):
    """
    type_function : TADD POUND LPAREN term_list RPAREN
    type_function : TSUB POUND LPAREN term_list RPAREN
    type_function : TMAX POUND LPAREN term_list RPAREN
    type_function : TLOG POUND LPAREN term_list RPAREN
    """
    if(debugParser):
        print "parse type_function: " + dumpToks(p)  + "\n"
    p[0] = TypeFunction(p[1],p[4])
