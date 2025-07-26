#!/usr/bin/env python3
# translator.py

import sys
from lexer import lexer
from parse import parser
from ast_nodes import ASTNode, Block, Sequencing, If, TypeNode, BinOp, Asig, Literal, Ident, UnaryOp, App
from context_analizer import ContextError

# Preamble: definiciones de combinadores en lambda‐cálculo
PREAMBLE = """\
Z    = lambda g:(lambda x:g(lambda v:x(x)(v)))(lambda x:g(lambda v:x(x)(v)))
true = lambda x:lambda y:x
false= lambda x:lambda y:y
nil  = lambda x:true
cons = lambda x:lambda y:lambda f:f(x)(y)
head = lambda p:p(true)
tail = lambda p:p(false)
apply= Z(lambda g:lambda f:lambda s:f if s==nil else (g(f(head(s)))(tail(s))))
lift_do=lambda exp:lambda f:lambda g: lambda x: g(f(x)) if (exp(x)) else x
do=lambda exp:lambda f:Z(lift_do(exp)(f))
"""

class LambdaGenerator:
    """
    Clase que representa el generador de codigo Python “curried” desde el AST
    """
    def __init__(self, ast: Block):
        self.ast         = ast
        self.vars        = []   # todas las celdas 
        self.global_vars = []   # variables globales (solo las variables int/bool del bloque raiz)
        self.arrays      = {}   # mapa nombre_arreglo (límite superior)
        self._collect_decls(ast, top_level=True)

    def _collect_decls(self, node, top_level=False):
        """
        Funcion que rellena self.vars con variables simples y celdas
        de cada function[..N], y self.global_vars con las
        variables int/bool del bloque principal.
        """
        if isinstance(node, Block):
            for names, type_node in node.decls.items:
                if type_node.typename == "function":
                    # se expande name0..nameN
                    for name in names:
                        self.arrays[name] = type_node.arg
                        for i in range(type_node.arg + 1):
                            self.vars.append(f"{name}{i}")
                else:
                    # int o bool
                    for name in names:
                        self.vars.append(name)
                        if top_level:
                            self.global_vars.append(name)
            self._collect_decls(node.instrs, top_level=False)
            return

        if isinstance(node, Sequencing):
            self._collect_decls(node.left,  top_level=False)
            self._collect_decls(node.right, top_level=False)
            return

        if isinstance(node, If):
            for _, instr in node.guards:
                self._collect_decls(instr, top_level=False)
            return

    def _flatten_comma(self, expr):
        """
        Funcion en la que, dada una expresión BinOp(op='Comma'), la aplana recursivamente en una lista de subexpresiones
        """
        if isinstance(expr, BinOp) and expr.op == "Comma":
            return self._flatten_comma(expr.left) + \
                   self._flatten_comma(expr.right)
        else:
            return [expr]

    def _collect_nodes(self, instr):
        """
        Funcion que aplana Secuencias, Bloques, Asig e If en una lista de nodos [Asig|If, …], 
        desdoblando asignaciones a arrays.
        """
        if isinstance(instr, Sequencing):
            return (self._collect_nodes(instr.left) +
                    self._collect_nodes(instr.right))

        if isinstance(instr, Block):
            return self._collect_nodes(instr.instrs)

        # se desdobla A := v1 , v2 , … , vN
        if isinstance(instr, Asig) and instr.name in self.arrays:
            vals     = self._flatten_comma(instr.expr)
            expected = self.arrays[instr.name] + 1
            if len(vals) != expected:
                raise RuntimeError(
                    f"Asignación a {instr.name} espera {expected} valores, "
                    f"pero encontró {len(vals)}"
                )
            out = []
            for i, val in enumerate(vals):
                new_asig = Asig(f"{instr.name}{i}", val,
                                instr.lineno, instr.column)
                out.append(new_asig)
            return out

        if isinstance(instr, Asig) or isinstance(instr, If):
            return [instr]

        return []

    def _expr_to_curried(self, expr, rev_vars, rev_params):
        """
        Funcion que traduce Literal, Ident, UnaryOp, BinOp y App(func,index) a fragmentos Python en infijo
        """
        if isinstance(expr, Literal):
            return str(expr.value)

        if isinstance(expr, Ident):
            idx = rev_vars.index(expr.name)
            return rev_params[idx]

        if isinstance(expr, UnaryOp):
            inner = self._expr_to_curried(expr.expr, rev_vars, rev_params)
            if expr.op == "Minus":
                return f"(-{inner})"
            if expr.op == "Not":
                return f"(not {inner})"
            raise RuntimeError(f"Unary op not supported: {expr.op}")

        if isinstance(expr, BinOp):
            opmap = {
                "Plus":"+","Minus":"-","Mult":"*",
                "Less":"<","Leq":"<=", "Greater":">","Geq":">=",
                "And":" and ","Or":" or ",
                "Equal":"==","NotEqual":"!=",
                "Comma":","  # usado internamente solo para flatten
            }
            l  = self._expr_to_curried(expr.left,  rev_vars, rev_params)
            r  = self._expr_to_curried(expr.right, rev_vars, rev_params)
            op = opmap.get(expr.op, expr.op)
            return f"({l}{op}{r})"

        if isinstance(expr, App):
            # acceso a arreglo: expr.func.name + expr.index.value
            var = f"{expr.func.name}{expr.index.value}"
            idx = rev_vars.index(var)
            return rev_params[idx]

        raise RuntimeError(f"Expr no soportado en curried: {expr}")

    def _gen_assign_curried(self, node):
        """
        Funcion que genera lambda que actualiza node.name en un estado desplegado por rev_params.
        """
        rev_vars   = list(reversed(self.vars))
        params     = [f"x{i+1}" for i in range(len(self.vars))]
        rev_params = list(reversed(params))

        idx     = rev_vars.index(node.name)
        new_val = self._expr_to_curried(node.expr, rev_vars, rev_params)

        suffix = "nil"
        for j in reversed(range(len(rev_params))):
            if j == idx:
                suffix = f"cons({new_val})({suffix})"
            else:
                suffix = f"cons({rev_params[j]})({suffix})"

        return "lambda " + ":lambda ".join(rev_params) + ": " + suffix

    def _gen_if_curried(self, node):
        """
        Funcion que traduce un If
        """
        rev_vars   = list(reversed(self.vars))
        params     = [f"x{i+1}" for i in range(len(self.vars))]
        rev_params = list(reversed(params))

        # estado identidad completo
        ident = "nil"
        for p in reversed(rev_params):
            ident = f"cons({p})({ident})"

        def collect_nodes(instr):
            """
            Funcion auxiliar para aplanar la rama
            """
            if isinstance(instr, Sequencing):
                return collect_nodes(instr.left) + collect_nodes(instr.right)
            if isinstance(instr, Block):
                return collect_nodes(instr.instrs)
            if isinstance(instr, Asig) or isinstance(instr, If):
                return [instr]
            return []

        branches = []
        for cond, instr in node.guards:
            cond_py    = self._expr_to_curried(cond, rev_vars, rev_params)
            then_nodes = collect_nodes(instr)

            then_state = ident
            for nd in then_nodes:
                if isinstance(nd, Asig):
                    lam = self._gen_assign_curried(nd)
                else:
                    lam = self._gen_if_curried(nd)
                then_state = f"(apply({lam}))({then_state})"

            branches.append((cond_py, then_state))

        body = ident
        for cond_py, then_state in reversed(branches):
            body = f"{then_state} if ({cond_py}) else {body}"

        return "lambda " + ":lambda ".join(rev_params) + ": " + body

    def generate(self) -> str:
        """
        Funcion que genera el archivo con el programa traducido
        """
        out = [PREAMBLE, ""]

        # Aplanamos los nodos de la raíz (Asig e If)
        nodes = self._collect_nodes(self.ast.instrs)

        # Se genera las lambdas inline
        curried = []
        for n in nodes:
            if isinstance(n, Asig):
                curried.append(self._gen_assign_curried(n))
            else:
                curried.append(self._gen_if_curried(n))

        # Se monta el program
        state = "x1"
        inner = state
        for lam in curried:
            inner = f"(apply({lam}))({inner})"
        out.append(f"program = (lambda {state}:{inner})")
        out.append("")

        # Valores por defecto para todo el estado
        defaults = "nil"
        for _ in self.vars:
            defaults = f"cons(0)({defaults})"
        out.append(f"result = program({defaults})")

        # print final
        names_rev_all = list(reversed(self.vars))
        binds_all     = "".join(f"lambda {v}:" for v in names_rev_all)
        dict_body     = "{" + ", ".join(
            f"'{v}':{v}" for v in self.global_vars
        ) + "}"
        out.append(f"print(apply({binds_all}{dict_body})(result))")

        return "\n".join(out)

def main(infile: str, outfile: str):
    """
    Metodo principal
    """
    src = open(infile, encoding="utf-8").read()
    ast = parser.parse(src, lexer=lexer)

    try:
        ast.analyze(None)
    except ContextError as err:
        print(err)
        sys.exit(1)

    code = LambdaGenerator(ast).generate()
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"Archivo {outfile} creado")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Error: Número de argumentos inválido. \nUso: translator.py programa.imperat programa_traducido.py")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])