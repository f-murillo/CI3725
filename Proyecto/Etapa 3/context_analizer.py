import sys
from parse import parser          
from ast_nodes import ContextError

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
    # Parseamos
    ast = parser.parse(data)

    # Analisis de contexto
    try:
        # El análisis arranca sin entorno padre
        ast.analyze(None)
    except ContextError as e:
        # Si hay algun error de contexto
        print(e)
        sys.exit(1)

    # Si todo esta ok, se imprime el AST decorado
    ast.pretty()

if __name__ == "__main__":
    main()
