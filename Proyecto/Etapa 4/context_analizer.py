import sys
from parse import parser          # tu parser de PLY
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
    # 2) Parsear: si hay error léxico/sintáctico, tu parser ya lo habrá impreso y salido
    ast = parser.parse(data)

    # 3) Análisis de contexto: añade types y detecta usos/errores
    try:
        # El análisis arranca sin entorno padre
        ast.analyze(None)
    except ContextError as e:
        # 4) Si hay error de contexto, lo reportas y terminas
        print(e)
        sys.exit(1)

    # 5) Si todo ok, imprimes el AST decorado
    ast.pretty()


if __name__ == "__main__":
    main()
