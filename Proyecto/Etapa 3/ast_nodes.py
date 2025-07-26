import re

# Excepcion para errores de contexto
class ContextError(Exception):
    pass

class SymbolTable:
    """
    Tabla de simbolos
    """
    def __init__(self, parent=None):
        self.parent = parent
        self.table  = {}

    def declare(self, name: str, type_str: str, lineno: int = None):
        if name in self.table:
            # recuperamos la linea donde se hizo la primera declaracion
            _, orig_lineno = self.table[name]
            raise ContextError(
                f"Variable {name} is already declared in the block at line {orig_lineno}"
            )
        # guardamos el tipo y la linea
        self.table[name] = (type_str, lineno)

    def lookup(self, name: str) -> str:
        if name in self.table:
            return self.table[name][0]
        if self.parent:
            return self.parent.lookup(name)
        raise ContextError(f"Variable no declarada: '{name}'")


# -------------------------------------------------------------------
class ASTNode:
    """
    Clase base para todos los nodos del AST
    Define las funciones pretty(indent) y analyze(env)
    """
    def pretty(self, indent=0):
        raise NotImplementedError("pretty() no implementado")

    def analyze(self, env):
        raise NotImplementedError("analyze() no implementado")

    def _print(self, label, indent):
        print(f"{'-' * indent}{label}")

# -------------------------------------------------------------------
class TypeNode(ASTNode):
    """
    Nodo que eepresenta un tipo: int, bool o function[..N]
    """
    def __init__(self, typename, arg=None, lineno=None, column=None):
        self.typename = typename   # int, bool o function
        self.arg       = arg       # N en 'function[..N]'
        self.lineno   = lineno     # linea donde aparecio el token relevante
        self.column   = column     # columna donde aparecio el token relevante

    def label(self):
        if self.typename == "function":
            return f"function[..{self.arg}]"
        return self.typename


# -------------------------------------------------------------------
class Block(ASTNode):
    """
    Nodo para un bloque { declarations instructions }
    """
    def __init__(self, decls, instrs):
        self.decls = decls
        self.instrs = instrs
        self.symbols = None  

    def analyze(self, parent_env):
        env = SymbolTable(parent_env)
        self.decls.analyze(env)      
        self.symbols = env
        self.instrs.analyze(env)    

    def pretty(self, indent=0):
        self._print("Block", indent)
        if self.symbols:
            self._print("Symbols Table", indent+1)
            for name, info in self.symbols.table.items():
                type_str = info if isinstance(info, str) else info[0]
                self._print(f"variable: {name} | type: {type_str}", indent+2)

        if self.instrs:
            self.instrs.pretty(indent+1)

# -------------------------------------------------------------------
class Decls(ASTNode):
    """
    Nodo para declaraciones multiples.
    """
    def __init__(self, items):
        self.items = items # lista de pares (lista_de_ids, TypeNode)

    def analyze(self, env):
        for names, typ_node in self.items:
            t_label = typ_node.label()
            for name in names:
                env.declare(name, t_label, lineno=typ_node.lineno)

    def pretty(self, indent=0):
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

# -------------------------------------------------------------------
class Sequencing(ASTNode):
    """
    Nodo para la sequenciacion de instrucciones
    """
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def analyze(self, env):
        self.left.analyze(env)
        self.right.analyze(env)

    def pretty(self, indent=0):
        self._print("Sequencing", indent)
        self.left.pretty(indent+1)
        self.right.pretty(indent+1)

# -------------------------------------------------------------------
class Skip(ASTNode):
    """
    Nodo para el skip
    """
    def analyze(self, env):
        pass

    def pretty(self, indent=0):
        self._print("skip", indent)

# -------------------------------------------------------------------
class Print(ASTNode):
    """
    Nodo para el print
    """
    def __init__(self, expr):
        self.expr = expr

    def analyze(self, env):
        try:
            # Analizamos la expresion a imprimir
            self.expr.analyze(env)
        except ContextError as e:
            msg = str(e)
            # Si es error de “not declared”, quitamos el nombre
            if "not declared" in msg:
                m = re.search(r"line (\d+) and column (\d+)", msg)
                if m:
                    ln, col = m.group(1), m.group(2)
                    raise ContextError(
                        f"Variable not declared at line {ln} and column {col}"
                    )
            # Los otros errores se propagan igual
            raise

    def pretty(self, indent=0):
        self._print("Print", indent)
        self.expr.pretty(indent+1)

# -------------------------------------------------------------------

def _types_equal(t1: str, t2: str) -> bool:
    """
    Funcion auxiliar para comparar tipos
    """
    if t1 == t2:
        return True

    # comparamos function[..N] vs function with length=L
    if t1.startswith("function[..") and t2.startswith("function with length="):
        N = int(t1[t1.find("[..")+3 : -1])
        L = int(t2.split("=",1)[1])
        return L == N + 1

    if t2.startswith("function[..") and t1.startswith("function with length="):
        N = int(t2[t2.find("[..")+3 : -1])
        L = int(t1.split("=",1)[1])
        return L == N + 1

    return False

class Asig(ASTNode):
    """
    Nodo para las asignaciones
    """
    def __init__(self, name, expr, lineno=None, column=None):
        self.name   = name
        self.expr   = expr
        self.lineno = lineno
        self.column = column
        self.type   = None

    def analyze(self, env):
        # 1) LHS (lado izquierdo de la asignacion)
        try:
            lhs_type = env.lookup(self.name)
        except ContextError:
            raise ContextError(
                f"Variable {self.name} not declared "
                f"at line {self.lineno} and column {self.column}"
            )

        # 2) RHS (lado derecho de la asignacion)
        try:
            rhs_type = self.expr.analyze(env)
        except ContextError as e:
            msg = str(e)
            if "not declared" in msg:
                m = re.search(r"line (\d+) and column (\d+)", msg)
                if m:
                    ln, col = m.group(1), m.group(2)
                    raise ContextError(
                        f"Variable not declared at line {ln} and column {col}"
                    )
            raise

        # 2.a) Caso especial: int ⇒ función de longitud 1 (function[..0])
        if lhs_type.startswith("function"):
            m = re.match(r"function\[\.\.(\d+)\]", lhs_type)
            if m:
                upper = int(m.group(1))
                if upper + 1 == 1 and rhs_type == "int":
                    # aceptamos la asignación sin más
                    self.type = lhs_type
                    return self.type

        # 3) comparación de tipos
        if not _types_equal(lhs_type, rhs_type):
            raise ContextError(
                f"Type error. Variable {self.name} has different type "
                f"than expression at line {self.lineno} "
                f"and column {self.column}"
            )

        self.type = lhs_type
        return self.type

    def pretty(self, indent=0):
        self._print("Asig", indent)
        # ahora imprimimos Ident con type
        self._print(f"Ident: {self.name} | type: {self.type}", indent+1)
        self.expr.pretty(indent+1)


# -------------------------------------------------------------------
class If(ASTNode):
    """
    Nodo para el if
    """
    def __init__(self, guards):
        # guards: lista de (condicion ASTNode, instrucciones ASTNode)
        self.guards = guards

    def analyze(self, env):
        for cond, instr in self.guards:
            t = cond.analyze(env)
            if t != "bool":
                raise ContextError("if guard must be bool")
            instr.analyze(env)

    def pretty(self, indent=0):
        N = len(self.guards)
        self._print("If", indent)
        # imprimimos las N-1 líneas "Guard"
        for depth in range(1, N):
            self._print("Guard", indent+depth)
        # e imprimimos luego los Then
        for i, (cond, instr) in enumerate(self.guards):
            level = indent + N - (0 if i < 2 else i-1)
            self._print("Then", level)
            cond.pretty(level+1)
            instr.pretty(level+1)

# -------------------------------------------------------------------
class While(ASTNode):
    """
    Nodo para el while
    """
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body

    def analyze(self, env):
        t = self.cond.analyze(env)
        if t != "bool":
            raise ContextError("while guard must be bool")
        self.body.analyze(env)

    def pretty(self, indent=0):
        self._print("While", indent)
        self._print("Then", indent+1)
        self.cond.pretty(indent+2)
        self.body.pretty(indent+2)

# -------------------------------------------------------------------
class FuncInit(ASTNode):
    """
    Nodo para la escritura en función: f(i:e)
    """
    def __init__(self, base, elems, lineno=None, column=None):
        self.base    = base
        self.elems   = elems       # lista de (idx ASTNode, val ASTNode)
        self.lineno  = lineno
        self.column  = column
        self.type    = None

    def analyze(self, env):
        base_t = self.base.analyze(env)

        # 1) Base no-funcion
        if not base_t.startswith("function"):
            ln  = getattr(self.base, "lineno", self.lineno)
            col = getattr(self.base, "column", self.column)
            raise ContextError(
                f"The function modification operator is use in not function "
                f"variable at line {ln} and column {col}"
            )

        # 2) Chequeo de cada par indice:valor
        for idx, val in self.elems:
            # 2a) el indice debe ser int
            it = idx.analyze(env)
            if it != "int":
                raise ContextError(
                    f"Expected expression of type int at "
                    f"line {idx.lineno} and column {idx.column}"
                )

            # 2b) el valor tambien debe ser int
            vt = val.analyze(env)
            if vt != "int":
                raise ContextError(
                    f"Expected expression of type int at "
                    f"line {val.lineno} and column {val.column}"
                )

        # 3) Si todo esta ok, el tipo resultante es el de la funcion base
        self.type = base_t
        return self.type

    def pretty(self, indent=0):
        self._print(f"WriteFunction | type: {self.type}", indent)
        self.base.pretty(indent+1)
        for idx, val in self.elems:
            self._print("TwoPoints", indent+1)
            idx.pretty(indent+2)
            val.pretty(indent+2)


# -------------------------------------------------------------------
#                       EXPRESIONES
# -------------------------------------------------------------------

class Ident(ASTNode):
    """
    Nodo para la identificacion
    """
    def __init__(self, name, lineno=None, column=None):
        self.name    = name
        self.lineno  = lineno
        self.column  = column
        self.type    = None

    def analyze(self, env):
        try:
            self.type = env.lookup(self.name)
            return self.type
        except ContextError:
            raise ContextError(
                f"Variable {self.name} not declared at line {self.lineno} and column {self.column}"
            )

    def pretty(self, indent=0):
        self._print(f"Ident: {self.name} | type: {self.type}", indent)


class Literal(ASTNode):
    """
    Nodo para los literales int y bool
    """
    def __init__(self, value, lineno=None, column=None):
        self.value  = value
        self.lineno = lineno
        self.column = column
        self.type   = None

    def analyze(self, env):
        # primero inferimos tipo
        if type(self.value) is bool:
            self.type = "bool"
        else:
            self.type = "int"
        return self.type

    def pretty(self, indent=0):
        self._print(f"Literal: {self.value} | type: {self.type}", indent)


class StringLit(ASTNode):
    """
    Nodo para el literal String
    """
    def __init__(self, text):
        self.text = text
        self.type = None

    def analyze(self, env):
        self.type = "String"
        return self.type

    def pretty(self, indent=0):
        self._print(f'String: "{self.text}"', indent)



class BinOp(ASTNode):
    """
    Nodo para las operaciones binarias
    """
    def __init__(self, op, left, right, lineno=None, column=None):
        self.op     = op
        self.left   = left
        self.right  = right
        self.lineno = lineno
        self.column = column
        self.type   = None

    def analyze(self, env):
        lt = self.left .analyze(env)
        rt = self.right.analyze(env)

        # Concat strings
        if self.op == "Plus" and (lt == "String" or rt == "String"):
            self.op, self.type = "Concat", "String"
            return self.type

        # Aritmetica: +, -, *
        if self.op in ("Plus","Minus","Mult"):
            if lt == "int" and rt == "int":
                self.type = "int"
                return self.type
            else:
                raise ContextError(
                    f"Type error at line {self.lineno} and column {self.column}"
                )

        # Comparaciones <, <=, >, >=
        if self.op in ("Less","Leq","Greater","Geq"):
            if lt == "int" and rt == "int":
                self.type = "bool"
                return self.type
            else:
                raise ContextError(
                    f"Type error at line {self.lineno} and column {self.column}"
                )

        # Igualdad / desigualdad
        if self.op in ("Equal","NotEqual"):
            if lt == rt:
                self.type = "bool"
                return self.type
            else:
                raise ContextError(
                    f"Type error at line {self.lineno} and column {self.column}"
                )

        # Logicos And / Or
        if self.op in ("And","Or"):
            if lt == "bool" and rt == "bool":
                self.type = "bool"
                return self.type
            else:
                raise ContextError(
                    f"Type error at line {self.lineno} and column {self.column}"
                )

        # 7) Comma 
        if self.op == "Comma":
            # 1) dos enteros → función literal de length=2
            if lt == "int" and rt == "int":
                length = 2

            # 2) int + funcion_literal → extiende en 1
            elif lt == "int" and rt.startswith("function with length="):
                prev = int(rt.split("=")[1])
                length = prev + 1

            # 3) funcion_literal + int → extiende en 1 tambien
            elif lt.startswith("function with length=") and rt == "int":
                prev = int(lt.split("=")[1])
                length = prev + 1

            else:
                raise ContextError(
                    f"There is no integer list at line {self.lineno} and column {self.column}"
                )

            self.type = f"function with length={length}"
            return self.type

        # operador desconocido
        raise ContextError(
            f"Type error at line {self.lineno} and column {self.column}"
        )


    def pretty(self, indent=0):
        self._print(f"{self.op} | type: {self.type}", indent)
        self.left.pretty(indent+1)
        self.right.pretty(indent+1)


class UnaryOp(ASTNode):
    """
    Nodo para las operaciones unarias
    """
    def __init__(self, op, expr, lineno=None, column=None):
        self.op     = op
        self.expr   = expr
        self.lineno = lineno
        self.column = column
        self.type   = None

    def analyze(self, env):
        t = self.expr.analyze(env)
        try:
            if self.op == "Not":
                if t != "bool":
                    raise ContextError("bad")
                self.type = "bool"
            elif self.op == "Minus":
                if t != "int":
                    raise ContextError("bad")
                self.type = "int"
            else:
                raise ContextError("bad")
        except ContextError:
            # relanzar solo posición genérica
            raise ContextError(
                f"Type error in line {self.lineno} and column {self.column}"
            )
        return self.type

    def pretty(self, indent=0):
        self._print(f"{self.op} | type: {self.type}", indent)
        self.expr.pretty(indent+1)


class App(ASTNode):
    """
    Nodo para las aplicaciones
    """
    def __init__(self, func, index, lineno=None, column=None):
        self.func    = func
        self.index   = index
        self.lineno  = lineno
        self.column  = column
        self.type    = None

    def analyze(self, env):
        # Analizamos la base y dejo que lance errores de lookup, etc.
        base_t = self.func.analyze(env)

        # 2) Si no es funcion
        if not base_t.startswith("function"):
            name = getattr(self.func, "name", "<expr>")
            ln   = getattr(self.func, "lineno", self.lineno)
            col  = getattr(self.func, "column", self.column)
            raise ContextError(
                f"Error. {name} is not indexable at line {ln} and column {col}"
            )

        # 3) Chequeo del indice
        idx_t = self.index.analyze(env)
        if idx_t != "int":
            raise ContextError(
                f"Error. Not integer index for function at "
                f"line {self.index.lineno} and column {self.index.column}"
            )

        self.type = "int"
        return self.type

    def pretty(self, indent=0):
        self._print(f"ReadFunction | type: {self.type}", indent)
        self.func .pretty(indent+1)
        self.index.pretty(indent+1)




class FuncModify(ASTNode):
    """
    Nodo para la modificación de una funcion: f[exp1:exp2]
    """
    def __init__(self, base, index, value):
        self.base = base # ASTNode que debe evaluar a un tipo function[..N]
        self.index = index # ASTNode que debe evaluar a int
        self.value = value # ASTNode cuyo tipo debe coincidir con el elemento devuelto por la función
        self.type = None

    def analyze(self, env):
        # 1) Verificamos que base sea funcion
        base_t = self.base.analyze(env)
        if not base_t.startswith("function"):
            raise ContextError("Se esperaba función/array para f[exp1:exp2]")
        # 2) El indice tiene que ser int
        idx_t = self.index.analyze(env)
        if idx_t != "int":
            raise ContextError("El índice de modificación debe ser int")
        # 3) El valor tambien lo limitamos a int (elementos de la funcion)
        val_t = self.value.analyze(env)
        if val_t != "int":
            raise ContextError("El valor de modificación debe ser int")
        # 4) El tipo resultante de toda la expresion sigue siendo la misma funcion
        self.type = base_t
        return self.type

    def pretty(self, indent=0):
        self._print("TwoPoints", indent)
        self.base.pretty(indent + 1)
        self.index.pretty(indent + 1)
        self.value.pretty(indent + 1)
