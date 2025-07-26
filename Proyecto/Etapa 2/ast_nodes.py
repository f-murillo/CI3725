class ASTNode:
    """
    Clase base para todos los nodos del AST
    Define la interfaz pretty(indent) y un helper _print
    """
    def pretty(self, indent=0):
        raise NotImplementedError("pretty() no implementado en nodo base")

    def _print(self, label, indent):
        print(f"{'-' * indent}{label}")

class TypeNode(ASTNode):
    """
    Clase que representa un tipo: int, bool o function[..N]
    label() devuelve la representacion para el AST
    """
    def __init__(self, typename, arg=None):
        self.typename = typename  # int, bool o function
        self.arg = arg            # N en function[..N] entero

    def label(self):
        if self.typename == "function":
            return f"function[..Literal: {self.arg}]"
        return self.typename

#--------------------- Nodos de instrucciones --------------------------------------

class Block(ASTNode):
    """
    Clase para el bloque
    Bloque completo: { declaraciones instrucciones }
    """
    def __init__(self, decls, instrs):
        self.decls = decls      # Declaraiones (Decls)
        self.instrs = instrs    # Instrucciones (ASTNode)

    def pretty(self, indent=0):
        self._print("Block", indent)
        if self.decls:
            self.decls.pretty(indent + 1)
        if self.instrs:
            self.instrs.pretty(indent + 1)


class Decls(ASTNode):
    """
    Clase para las declaraciones
    """
    def __init__(self, items):
        self.items = items

    def pretty(self, indent=0):
        # Si no hay declaraciones, no imprimimos nada
        if not self.items:
            return

        self._print("Declare", indent)
        n = len(self.items)

        if n == 1:
            names, typ = self.items[0]
            self._print(f"{', '.join(names)} : {typ.label()}", indent+1)

        elif n == 2:
            self._print("Sequencing", indent+1)
            for names, typ in self.items:
                self._print(f"{', '.join(names)} : {typ.label()}", indent+2)

        else:
            self._print("Sequencing", indent+1)
            self._print("Sequencing", indent+2)
            # dos primeras
            for names, typ in self.items[:2]:
                self._print(f"{', '.join(names)} : {typ.label()}", indent+3)
            # resto
            for names, typ in self.items[2:]:
                self._print(f"{', '.join(names)} : {typ.label()}", indent+2)


class FuncInit(ASTNode):
    """
    Clase del nodo para la instruccion f(i:e)
    elems es una lista de (index, value)
    """
    def __init__(self, base, elems):
        self.base = base    
        self.elems = elems  

    def pretty(self, indent=0):
        self._print("WriteFunction", indent)
        self.base.pretty(indent+1)
        for idx, val in self.elems:
            # imprimimos la parte TwoPoints
            self._print("TwoPoints", indent+1)
            idx.pretty(indent+2)
            val.pretty(indent+2)


class Sequencing(ASTNode):
    """
    Clase para la secuenciacion de dos instrucciones: instr1 ; instr2
    """
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def pretty(self, indent=0):
        self._print("Sequencing", indent)
        self.left.pretty(indent + 1)
        self.right.pretty(indent + 1)


class Asig(ASTNode):
    """
    Clase para la asignacion: x := expr
    """
    def __init__(self, name, expr):
        self.name = name   # nombre de variable, string
        self.expr = expr   # ASTNode expresion

    def pretty(self, indent=0):
        self._print("Asig", indent)
        self._print(f"Ident: {self.name}", indent + 1)
        self.expr.pretty(indent + 1)


class Print(ASTNode):
    """
    Clase para el print: print expr
    """
    def __init__(self, expr):
        self.expr = expr

    def pretty(self, indent=0):
        self._print("Print", indent)
        self.expr.pretty(indent + 1)


class If(ASTNode):
    """
    Clase para el if con multiples guardias
    Las guardias son una lista de tuplas (condición ASTNode, instruccion ASTNode)
    """
    def __init__(self, guards):
        self.guards = guards

    def pretty(self, indent=0):
        N = len(self.guards)

        # Nodo If
        self._print("If", indent)

        # N-1 guardias, en cascada
        for depth in range(1, N):
            self._print("Guard", indent + depth)

        # Ahora los N Then
        for i, (cond, instr) in enumerate(self.guards):
            # los dos primeros Then al pleno (indent + N)
            # a partir del tercero resto (i-1)
            indent_then = indent + N - (0 if i < 2 else (i - 1))
            self._print("Then", indent_then)
            cond.pretty(indent_then + 1)
            instr.pretty(indent_then + 1)


class While(ASTNode):
    """
    Clase para el while: while cond --> instr end
    """
    def __init__(self, cond, body):
        self.cond = cond    # ASTNode condicion
        self.body = body    # ASTNode cuerpo

    def pretty(self, indent=0):
        self._print("While", indent)
        self._print("Then", indent + 1)
        self.cond.pretty(indent + 2)
        self.body.pretty(indent + 2)
        
# ast_nodes.py

class Skip(ASTNode):
    """
    Clase para la instruccion skip: no hace nada
    """
    def pretty(self, indent=0):
        self._print("skip", indent)


#------------------------ Nodos de expresiones -----------------------------------------

class Literal(ASTNode):
    """
    Clase para los literales
    """
    def __init__(self, value):
        self.value = value

    def pretty(self, indent=0):
        self._print(f"Literal: {self.value}", indent)


class Ident(ASTNode):
    """
    Clase para el uso de variable
    """
    def __init__(self, name):
        self.name = name

    def pretty(self, indent=0):
        self._print(f"Ident: {self.name}", indent)


class StringLit(ASTNode):
    """
    Clase para el literal de cadena
    """
    def __init__(self, text):
        self.text = text

    def pretty(self, indent=0):
        self._print(f'String: "{self.text}"', indent)



class BinOp(ASTNode):
    """
    Clase para las operaciones binaria genericas 
    """
    def __init__(self, op, left, right):
        self.op = op          # op es cadena: Plus, Minus, And, Or, etc
        self.left = left      # ASTNode
        self.right = right    # ASTNode

    def pretty(self, indent=0):
        self._print(self.op, indent)
        self.left.pretty(indent + 1)
        self.right.pretty(indent + 1)


class UnaryOp(ASTNode):
    """
    Clase para las operaciones unarias genericas
    """
    def __init__(self, op, expr):
        self.op = op #  op es cadena: Not, Minus (para numeros negativos)
        self.expr = expr

    def pretty(self, indent=0):
        self._print(self.op, indent)
        self.expr.pretty(indent + 1)


class App(ASTNode):
    """
    Clase para la aplicacion de una funcion: f.exp
    """
    def __init__(self, base, arg):
        self.base = base  # ASTNode
        self.arg = arg    # ASTNode

    def pretty(self, indent=0):
        self._print("App", indent)
        self.base.pretty(indent + 1)
        self.arg.pretty(indent + 1)


class FuncModify(ASTNode):
    """
    Clase para la modificacion de una funcióo: f[exp1:exp2]
    """
    def __init__(self, base, index, value):
        self.base = base    # ASTNode funcion
        self.index = index  # ASTNode indice
        self.value = value  # ASTNode nuevo valor

    def pretty(self, indent=0):
        self._print("TwoPoints", indent)
        self.base.pretty(indent + 1)
        self.index.pretty(indent + 1)
        self.value.pretty(indent + 1)