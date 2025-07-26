import sys
import os
import ply.lex as lex

# Lista de tokens basicos
tokens = [
    # Categorias de tokens que poseen atributos (identificadores, numeros y cadenas)
    'TkId', 'TkNum', 'TkString',
    # Separadores
    'TkOBlock', 'TkCBlock', 'TkSoForth', 'TkComma',
    'TkOpenPar', 'TkClosePar', 'TkAsig', 'TkSemicolon', 'TkArrow', 'TkGuard',
    # Operadores
    'TkPlus', 'TkMinus', 'TkMult', 'TkNot',
    'TkLess', 'TkLeq', 'TkGeq', 'TkGreater', 'TkEqual', 'TkNEqual',
    'TkOBracket', 'TkCBracket', 'TkTwoPoints', 'TkApp'
]

# Diccionario para las palabras reservadas
reserved = {
    'if': 'TkIf',
    'fi': 'TkFi',
    'while': 'TkWhile',
    'end': 'TkEnd',
    'and': 'TkAnd',
    'or': 'TkOr',
    'print': 'TkPrint',
    'int': 'TkInt',
    'bool': 'TkBool',
    'function': 'TkFunction',
    'true': 'TkTrue',
    'false': 'TkFalse',
    'skip': 'TkSkip'
}

# Se agregan las palabras reservadas a la lista de tokens
tokens = tokens + list(reserved.values())

#--------- Definición de reglas de tokens (para PLY) ----------------

# Tokens de dos o mas caracteres. Se definen primero para tener prioridad
t_TkAsig    = r':='
t_TkArrow   = r'-->'
t_TkSoForth = r'\.\.'
t_TkGuard   = r'\[\]'
t_TkLeq     = r'<='
t_TkGeq     = r'>='
t_TkEqual   = r'=='
t_TkNEqual  = r'<>'

# Tokens de un solo caracter u otros símbolos
t_TkPlus      = r'\+'
t_TkMinus     = r'-'
t_TkMult      = r'\*'
t_TkNot       = r'!'
t_TkLess      = r'<'
t_TkGreater   = r'>'
t_TkOBlock    = r'\{'
t_TkCBlock    = r'\}'
t_TkComma     = r','
t_TkOpenPar   = r'\('
t_TkClosePar  = r'\)'
t_TkSemicolon = r';'
t_TkOBracket  = r'\['
t_TkCBracket  = r'\]'
t_TkTwoPoints = r':'
t_TkApp       = r'\.'  # Este se define después de TkSoForth para evitar conflictos de solapamiento del simbolo \ por parte de PLY

#--------- Funciones para el manejo de los tokens ----------------

# Funcion que maneja los identificadores y las palabras reservadas
def t_TkId(t):
    # Se reconoce una secuencia que inicia con una letra (mayus. o minus.), guion bajo, seguida de digitos, mas letras o guiones bajos
    r'[A-Za-z_][A-Za-z0-9_]*' 
    # Se verifica si el valor reconocido esta en el diccionario de palabras reservadas
    # Si lo esta, se asigna el token correspondiente; de lo contrario, se utiliza TkId
    t.type = reserved.get(t.value, 'TkId')
    return t

# Funcion que maneja los números enteros
def t_TkNum(t):
    r'\d+' # Se reconoce una o mas cifras decimales
    t.value = int(t.value) # Se convierte a tipo entero
    return t

# Funcion que maneja las cadenas de caracteres encerradas en comillas.
def t_TkString(t):
    # La expresion regular reconoce lo siguiente:
    # - Comienza y termina con comillas dobles ("")
    # - Dentro de la cadena se permite:
    #   - [^"\\\n]: cualquier caracter que no sea ", \ o \n
    #   - \\(?:[n"\\]): una secuencia de escape válida
    r'"(?:[^"\\\n]|\\(?:[n"\\]))*"'
    # Se quitan las comillas de apertura y cierre para obtener el contenido
    s = t.value[1:-1]
    t.value = s
    return t

# Caracteres a ignorar (espacios, tabuladores y retornos de carro). Estos caracteres no seran convertidos en tokens
t_ignore = " \t\r"

# Funcion que maneja los saltos de linea
def t_newline(t):
    r'\n+' # Se reconoce uno o mas saltos de línea
    t.lexer.lineno += len(t.value) # Se actualiza el contador de líneas

# Funcion que maneja los comentarios
def t_comment(t):
    # Se reconoce los comentarios de una linea, es decir, desde // hasta el final de la linea, y se ignoran 
    r'//.*' 
    pass

# Lista para almacenar los errores lexicos que se vayan encontrando
errors = []

# Funcion auxiliar para calcular la columna de un token
def find_column(input, data):
    # Se utiliza la posicion inicial del token y se busca la posicion de la última
    # nueva linea ('\n') anterior a ese token en la entrada completa
    if hasattr(data, 'lexpos'):
        lexpos = data.lexpos
    else:
        lexpos = data
    last_cr = input.rfind('\n', 0, lexpos)
    if last_cr < 0:
        last_cr = -1  # Si no se encuentra, significa que el token esta en la primera linea
    # La diferencia entre token.lexpos y la posicion de ese salto de linea, sera la columna
    return lexpos - last_cr

# Funcion para reportar errores lexicos
def t_error(t):
    # Se obtiene la columna donde aparece el error
    col = find_column(t.lexer.lexdata, t)
    msg = f'Error: Unexpected character "{t.value[0]}" in row {t.lineno}, column {col}'
    # Se imprime el mensaje de error, y se agrega el error a la lista de errores
    print(msg)
    errors.append((t.lineno, col, t.value[0]))
    # Se omite el caracter actual y se continúa con el analisis
    t.lexer.skip(1)

# Construimos el lexer a partir de las definiciones anteriores
lexer = lex.lex()

#---------------------------------------------------------------
def main():
    """Metodo principal"""
    # Si el numero de argumentos ingresados es incorrecto
    if len(sys.argv) != 2:
        print("Error: número de argumentos incorrecto\nUso: python lexer.py archivo.imperat")
        sys.exit(1)

    filename = sys.argv[1] # Archivo
    
    # Si la extension del archivo no corresponde a imperat
    if not filename.endswith(".imperat"):
        print("Error: La extensión del archivo debe ser .imperat")
        sys.exit(1)

    # Si no se encuentra el archivo con el nombre daddo
    if not os.path.isfile(filename):
        print(f"Error: El archivo {filename} no existe.")
        sys.exit(1)

    # Leemos el contenido completo del archivo
    with open(filename, "r", encoding="utf-8") as f:
        data = f.read()

    # Se carga el input en el lexer
    lexer.input(data)

    token_list = [] # Lista de tokens
    while True:
        tok = lexer.token()
        if not tok: # Si ya no hay tokens
            break
        col = find_column(data, tok) # Ubicamos la columna de cada token 
        # Agregamos el token a la lista
        if tok.type in ['TkId', 'TkNum', 'TkString']: # Los tokens que llevan atributo se almacenan con su valor
            token_list.append((tok.type, tok.lineno, col, tok.value))
        else:
            token_list.append((tok.type, tok.lineno, col))

    # Si se detectaron errores lexicos, se finaliza la ejecucion del programa
    if errors:
        sys.exit(1)

    # Mostramos la secuencia de tokens
    for token in token_list:
        if len(token) == 4:
            typ, line, col, val = token
            print(f'{typ}({val if typ == "TkNum" else ("\"" + val + "\"")}) {line} {col}')
        else:
            typ, line, col = token
            print(f"{typ} {line} {col}")

if __name__ == '__main__':
    main()