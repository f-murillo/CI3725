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
    p[0] = TypeNode('int')

def p_type_bool(p):
    "type : TkBool"
    p[0] = TypeNode('bool')

def p_type_func(p):
    "type : TkFunction TkOBracket TkSoForth TkNum TkCBracket"
    p[0] = TypeNode('function', p[4])

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

# Secuenciación de instrucciones (izquierdo-asociativa)
def p_instructions(p):
    """instructions : instruction
                    | instructions TkSemicolon instruction"""
    if len(p) == 2:
        p[0] = p[1]
    else:
        p[0] = Sequencing(p[1], p[3])

# Una instruccion puede ser asignacion, print, if, while o un bloque
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
    p[0] = Asig(p[1], p[3])

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
    p[0] = BinOp("Or", p[1], p[3])

def p_expr_and(p):
    "expr : expr TkAnd expr"
    p[0] = BinOp("And", p[1], p[3])

# Operadores logicos
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
    p[0] = BinOp(op_map[p[2]], p[1], p[3])

# Operadores aritmeticos
def p_expr_arith(p):
    """
    expr : expr TkPlus expr
         | expr TkMinus expr
         | expr TkMult expr
    """
    op_map = {'+': 'Plus', '-': 'Minus', '*': 'Mult'}
    p[0] = BinOp(op_map[p[2]], p[1], p[3])

# Not
def p_expr_not(p):
    "expr : TkNot expr"
    p[0] = UnaryOp("Not", p[2])
    
# Menos unario (para casos de numeros negativos)
def p_expr_uminus(p):
    "expr : TkMinus expr %prec UMINUS"
    p[0] = UnaryOp("Minus", p[2])

# Parentesis
def p_paren(p):
    "expr : TkOpenPar expr TkClosePar"
    p[0] = p[2]

# Literales (numeros, booleanos y strings)
def p_expr_num(p):
    "expr : TkNum"
    p[0] = Literal(p[1])

def p_expr_true(p):
    "expr : TkTrue"
    p[0] = Literal('true')

def p_expr_false(p):
    "expr : TkFalse"
    p[0] = Literal('false')

def p_expr_string(p):
    "expr : TkString"
    p[0] = StringLit(p[1])
    
# Identificacion
def p_expr_ident(p):
    "expr : TkId"
    p[0] = Ident(p[1])

# Aplicacion
def p_expr_app(p):
    "expr : expr TkApp expr"
    p[0] = App(p[1], p[3])

# Modificar funcion
def p_expr_mod(p):
    "expr : expr TkOBracket expr TkTwoPoints expr TkCBracket"
    p[0] = FuncModify(p[1], p[3], p[5])

# Coma
def p_expr_comma(p):
    "expr : expr TkComma expr"
    p[0] = BinOp("Comma", p[1], p[3])
    
# Escrbibir funcion    
def p_expr_writefunc(p):
    """expr : expr TkOpenPar expr TkTwoPoints expr TkClosePar"""
    # p[1] es la función, p[3] es el índice, p[5] el nuevo valor
    p[0] = FuncInit(p[1], [(p[3], p[5])])

# ------------------ Manejo de errores sintacticos ---------------------------

def p_error(p):
    if p:
        # sacamos el input directamente del lexer que trajo el token
        col = find_column(p.lexer.lexdata, p)
        print(f"Sintax error in row {p.lineno}, column {col}: unexpected token '{p.value}'.")
    else:
        print("Sintax error: unexpected end of input.")
    sys.exit(1)


# Construimos el parser
parser = yacc.yacc()

def main():
    if len(sys.argv) < 2:
        print("Uso: python parse.py archivo.imperat")
        sys.exit(1)

    filename = sys.argv[1]
    if not filename.endswith(".imperat"):
        print("Error: la extensión debe ser .imperat")
        sys.exit(1)

    # Lectura y chequeo lexico
    with open(filename, "r", encoding="utf-8") as f:
        data = f.read()

    lexer.input(data)
    while lexer.token():
        pass

    if errors:
        sys.exit(1)

    # Parseamos y obtenemos el AST
    ast = parser.parse(data, lexer=lexer)

    # Imprimos el AST
    ast.pretty()

if __name__ == "__main__":
    main()
