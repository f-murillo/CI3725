import sys
import ply.yacc as yacc
from lexer import tokens, lexer, errors, find_column
from ast_nodes import *

start = 'program' # Simbolo inicial

#----------------- Precedencia de operadores (de menor a mayor prioridad)----------------
precedence = [
    ('left',   'TkComma'),
    ('left',   'TkOr'),
    ('left',   'TkAnd'),
    ('nonassoc',
        'TkLess','TkLeq','TkGreater','TkGeq','TkEqual','TkNEqual'
    ),
    ('left',   'TkPlus','TkMinus'),
    ('left',   'TkMult'),
    ('right',  'UMINUS'),
    ('left',   'TkApp'),
    ('left',   'TkOpenPar'),
    ('right',  'TkNot'),
]

#----------------- Reglas de la gramatica y construccion del AST ----------------------

# Un bloque 
def p_block(p):
    "block : TkOBlock declarations instructions TkCBlock"
    p[0] = Block(p[2], p[3])

# El programa completo es un unico bloque
def p_program(p):
    "program : block"
    p[0] = p[1]

# Declaraciones y tipos
def p_declarations(p):
    "declarations : declaration declarations"
    p[0] = Decls([p[1]] + p[2].items)

def p_declarations_empty(p):
    "declarations :"
    p[0] = Decls([])

def p_declaration(p):
    "declaration : type id_list TkSemicolon"
    p[0] = (p[2], p[1])

def p_type_int(p):
    "type : TkInt"
    ln     = p.lineno(1)
    col    = find_column(p.lexer.lexdata, p.lexpos(1))
    p[0]  = TypeNode('int',
                     arg=None,
                     lineno=ln,
                     column=col)

def p_type_bool(p):
    "type : TkBool"
    ln     = p.lineno(1)
    col    = find_column(p.lexer.lexdata, p.lexpos(1))
    p[0]  = TypeNode('bool',
                     arg=None,
                     lineno=ln,
                     column=col)

def p_type_func(p):
    "type : TkFunction TkOBracket TkSoForth TkNum TkCBracket"
    ln     = p.lineno(4)
    col    = find_column(p.lexer.lexdata, p.lexpos(4))
    val    = int(p[4]) # p[4] es el lexema numerico
    p[0]  = TypeNode('function',
                     arg=val,
                     lineno=ln,
                     column=col)

# Listas de identificadores
def p_id_list_single(p):
    "id_list : TkId"
    p[0] = [p[1]]

def p_id_list_multi(p):
    "id_list : TkId TkComma id_list"
    p[0] = [p[1]] + p[3]

# Skip    
def p_skip(p):
    "skip_stmt : TkSkip"
    p[0] = Skip()

# Secuenciacion de instrucciones (asociativa a la izquierda)
def p_instructions(p):
    """instructions : instruction
                    | instructions TkSemicolon instruction"""
    if len(p) == 2:
        p[0] = p[1]
    else:
        p[0] = Sequencing(p[1], p[3])

# Instrucciones. Una instruccion puede ser asignacion, print, if, while o un bloque
def p_instruction(p):
    """
    instruction : assignment
                | print_stmt
                | if_stmt
                | while_stmt
                | skip_stmt
                | block
    """
    p[0] = p[1]

# Asignacion
def p_assignment(p):
    "assignment : TkId TkAsig expr"
    lineno = p.lineno(1)
    lexpos = p.lexpos(1)
    column = find_column(p.lexer.lexdata, lexpos)
    # Se construye el nodo Asig con id, expr, y los datos de la posicion
    p[0] = Asig(p[1], p[3], lineno, column)

# Print
def p_print(p):
    "print_stmt : TkPrint expr"
    p[0] = Print(p[2])

# If con guardias
def p_if(p):
    "if_stmt : TkIf guard_list TkFi"
    p[0] = If(p[2])

def p_guard_list_single(p):
    "guard_list : expr TkArrow instructions"
    p[0] = [(p[1], p[3])]

def p_guard_list_multi(p):
    "guard_list : expr TkArrow instructions TkGuard guard_list"
    p[0] = [(p[1], p[3])] + p[5]

# While
def p_while(p):
    "while_stmt : TkWhile expr TkArrow instructions TkEnd"
    p[0] = While(p[2], p[4])

#------------------------ Reglas de expresiones -------------------------

# Or y And
def p_expr_or(p):
    "expr : expr TkOr expr"
    # Se captura la posicion del or
    lineno = p.lineno(2)
    lexpos = p.lexpos(2)
    column = find_column(p.lexer.lexdata, lexpos)

    p[0] = BinOp(
        "Or",       # nombre interno del operador
        p[1],       # operando izquierdo
        p[3],       # operando derecho
        lineno=lineno,
        column=column
    )

def p_expr_and(p):
    "expr : expr TkAnd expr"
    # Se captura la posición del and
    lineno = p.lineno(2)
    lexpos = p.lexpos(2)
    column = find_column(p.lexer.lexdata, lexpos)

    p[0] = BinOp(
        "And",
        p[1],
        p[3],
        lineno=lineno,
        column=column
    )

# Operadores logicos y relacionales
def p_expr_rel(p):
    """
    expr : expr TkLess expr
         | expr TkLeq expr
         | expr TkGreater expr
         | expr TkGeq expr
         | expr TkEqual expr
         | expr TkNEqual expr
    """
    op_map = {
        '<': 'Less', '<=': 'Leq',
        '>': 'Greater', '>=': 'Geq',
        '==': 'Equal', '<>': 'NotEqual'
    }
    # Capturamos la linea y columna del operador
    lineno = p.lineno(2)
    lexpos = p.lexpos(2)
    column = find_column(p.lexer.lexdata, lexpos)

    p[0] = BinOp(
        op_map[p[2]],  # nombre interno del operador
        p[1],          # operando izquierdo
        p[3],          # operando derecho
        lineno=lineno,
        column=column
    )

# Operadores aritmeticos
def p_expr_arith(p):
    """
    expr : expr TkPlus expr
         | expr TkMinus expr
         | expr TkMult expr
    """
    op_map = {'+': 'Plus', '-': 'Minus', '*': 'Mult'}
    # Capturamos la linea y columna del operador
    lineno = p.lineno(2)
    lexpos = p.lexpos(2)
    column = find_column(p.lexer.lexdata, lexpos)

    p[0] = BinOp(
        op_map[p[2]],
        p[1],
        p[3],
        lineno=lineno,
        column=column
    )

# Not
def p_expr_not(p):
    "expr : TkNot expr"
    lineno = p.lineno(1)
    lexpos = p.lexpos(1)
    column = find_column(p.lexer.lexdata, lexpos)
    p[0] = UnaryOp("Not", p[2], lineno, column)
    
# Menos unario (para casos de numeros negativos)
def p_expr_uminus(p):
    "expr : TkMinus expr %prec UMINUS"
    lineno = p.lineno(1)
    lexpos = p.lexpos(1)
    column = find_column(p.lexer.lexdata, lexpos)
    p[0] = UnaryOp("Minus", p[2], lineno=lineno, column=column)

# Parentesis
def p_paren(p):
    "expr : TkOpenPar expr TkClosePar"
    p[0] = p[2]

# -------- Literales (numeros, booleanos y strings) ---------
def p_expr_num(p):
    "expr : TkNum"
    lineno = p.lineno(1)
    lexpos = p.lexpos(1)
    column = find_column(p.lexer.lexdata, lexpos)
    p[0] = Literal(p[1], lineno=lineno, column=column)

def p_expr_true(p):
    "expr : TkTrue"
    lineno = p.lineno(1)
    lexpos = p.lexpos(1)
    column = find_column(p.lexer.lexdata, lexpos)
    p[0] = Literal(True, lineno=lineno, column=column)

def p_expr_false(p):
    "expr : TkFalse"
    lineno = p.lineno(1)
    lexpos = p.lexpos(1)
    column = find_column(p.lexer.lexdata, lexpos)
    p[0] = Literal(False, lineno=lineno, column=column)

def p_expr_string(p):
    "expr : TkString"
    p[0] = StringLit(p[1])

    
# Identificacion
def p_expr_ident(p):
    "expr : TkId"
    lineno = p.lineno(1)
    lexpos = p.lexpos(1)
    column = find_column(p.lexer.lexdata, lexpos)
    p[0] = Ident(p[1], lineno, column)

# Aplicacion
def p_expr_app(p):
    "expr : expr TkApp expr"
    lineno = p.lineno(2)
    lexpos = p.lexpos(2)
    column = find_column(p.lexer.lexdata, lexpos)
    p[0] = App(
        p[1],        # funcion o expresion de funcion
        p[3],        # expresion indice
        lineno=lineno,
        column=column
    )

# Modificacion de funcion
def p_expr_mod(p):
    "expr : expr TkOBracket expr TkTwoPoints expr TkCBracket"
    p[0] = FuncModify(p[1], p[3], p[5])

# Coma
def p_expr_comma(p):
    "expr : expr TkComma expr"
    lineno = p.lineno(2)
    lexpos = p.lexpos(2)
    column = find_column(p.lexer.lexdata, lexpos)

    # construimos la operacion binaria
    p[0] = BinOp("Comma", p[1], p[3], lineno=lineno, column=column)
    
# Escrbibir funcion    
def p_expr_writefunc(p):
    """expr : expr TkOpenPar expr TkTwoPoints expr TkClosePar"""
    # p[1] es la funcion, p[3] es el indice, y p[5] es el nuevo valor
    lineno = p.lineno(2)
    column = find_column(p.lexer.lexdata, p.lexpos(2))
    p[0] = FuncInit(
        base   = p[1],
        elems  = [(p[3], p[5])],
        lineno = lineno,
        column = column
    )

# ------------------ Manejo de errores sintacticos ---------------------------
def p_error(p):
    if p:
        # sacamos el input directamente del lexer del token
        col = find_column(p.lexer.lexdata, p)
        print(f"Sintax error in row {p.lineno}, column {col}: unexpected token '{p.value}'.")
    else:
        print("Sintax error: unexpected end of input.")
    sys.exit(1)

# Construimos el parser
parser = yacc.yacc()
