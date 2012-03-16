import ply.yacc as yacc

tokens = [ 'RARROW', 'SEMICOLON',
           'NAME'
         ]

t_RARROW = r'->'
t_SEMICOLON = r';'

def t_NAME(t):
    r'[a-zA-Z_][]a-zA-Z0-9_[]*'
    t.type = 'NAME'
    return t

t_ignore = " \t\r" #white space requirements are evil

def t_newline(t):
    r'\n+'
    t.lexer.lineno += t.value.count("\n") 

def t_error(t):
    print 'Error? at ' + str(t.lexer.lineno) +  ': Illegal character ' + t.value[0]
    t.lexer.skip(1) 
