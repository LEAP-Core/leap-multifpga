# platform P;
#   Q -> qinconnect;
#   R -> rinconnect;
#   R <- routconnect;
# endplatform
        #TaggedUnion union::UnionTest1 {members {{void YesEmpty {width 0}} {Bool NotEmpty {width 1}} {Bit#(32) Value {width 32}}}} {width 34} {position {union.bsv 7 3}}
reserved = {
    'TaggedUnion': 'TAGGEDUNION',
    'Struct': 'STRUCT',
    'Alias': 'ALIAS',
    'Typeclass': 'TYPECLASS',
    'TMax': 'TMAX',
    'TSub': 'TSUB',
    'TAdd': 'TADD',
    'TLog': 'TLOG',
    'members': 'MEMBERS',
    'dependencies': 'DEPENDENCIES',
    'determines': 'DETERMINES',
    'instances': 'INSTANCES',
    'function': 'FUNCTION',
    'position': 'POSITION',
    'polymorphic': 'POLYMORPHIC',
    'type': 'TYPE',
    'numeric': 'NUMERIC',
    'width': 'WIDTH',
    'provisos': 'PROVISOS',
    }

tokens = [ 'RCURLY', 'LCURLY', 'RPAREN', 'LPAREN', 'DOUBLECOLON',
           'POUND', 'STRING', 'PERIOD',
           'INT', 'FSLASH', 'COMMA', 'NAME', 'DASH'
         ] + list(reserved.values())

t_PERIOD = r'\.'
t_RCURLY = r'}'
t_LCURLY = r'{'
t_RPAREN = r'\)'
t_LPAREN = r'\('
t_FSLASH = r'/'
t_DASH = r'-'
t_COMMA = r','
t_DOUBLECOLON = r'::'
t_POUND = r'\#'
t_TAGGEDUNION = r'TaggedUnion'
t_ALIAS = r'Alias'
t_DEPENDENCIES = r'dependencies'
t_INSTANCES = r'instances'
t_TYPECLASS = r'Typeclass'
t_STRUCT = r'Struct'
t_TMAX = r'TMax'
t_TADD = r'TAdd'
t_TSUB = r'TSub'
t_TLOG = r'TLog'
t_MEMBERS = r'members'
t_POSITION = r'position'
t_FUNCTION = r'function'
t_POLYMORPHIC = r'polymorphic'
t_PROVISOS = r'provisos'
t_NUMERIC = r'numeric'
t_TYPE = r'type'
t_WIDTH = r'width'


def t_INT(t):
    r'[0-9][0-9]*'
    t.type = reserved.get(t.value,'INT')
    return t

def t_NAME(t):
    r'[a-zA-Z$0-9_]+'
    t.type = reserved.get(t.value,'NAME')
    return t

t_ignore = " \t\r" #white space requirements are evil

def t_newline(t):
    r'\n+'
    t.lexer.lineno += t.value.count("\n") 

def t_error(t):
    print 'Error at ' + str(t.lexer.lineno) +  ': Illegal character ' + t.value[0]
    t.lexer.skip(1) 

