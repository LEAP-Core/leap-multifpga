# platform P;
#   Q -> qinconnect;
#   R -> rinconnect;
#   R <- routconnect;
# endplatform

reserved = {
    'platform': 'PLATFORM',
    'master': 'MASTER',
    'endmaster': 'ENDMASTER',
    'endplatform': 'ENDPLATFORM',
    }

tokens = [ 'RARROW', 'LARROW', 'SEMICOLON', 'EQUAL','COMMENT',
           'NAME', 'STRING', 'INT'
         ] + list(reserved.values())


t_EQUAL = r'='
t_RARROW = r'->'
t_LARROW = r'<-'
t_SEMICOLON = r';'
t_PLATFORM = r'platform'
t_ENDPLATFORM = r'endplatform'
t_MASTER = r'master'
t_ENDMASTER = r'endmaster'
#t_ENDPLATFORM = r'unknown'

def t_ignore_COMMENT(t):
    r'\#.*'
    pass

def t_NAME(t):
    r'[a-zA-Z_][]a-zA-Z0-9_[]*'
    t.type = reserved.get(t.value,'NAME')
    return t

def t_STRING(t):
    r'".*"'
    t.type = reserved.get(t.value,'STRING')
    return t

def t_INT(t):
    r'[0-9]+'
    t.type = reserved.get(t.value,'INT')
    return t

t_ignore = " \t\r" #white space requirements are evil

def t_newline(t):
    r'\n+'
    t.lexer.lineno += t.value.count("\n") 

def t_error(t):
    print 'Error at ' + str(t.lexer.lineno) +  ': Illegal character ' + t.value[0]
    t.lexer.skip(1) 

