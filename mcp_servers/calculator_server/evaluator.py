"""
安全的数学表达式求值器
基于 AST 白名单，杜绝 eval 注入风险
"""
import ast
import math

_SAFE_FUNCS = {
    "abs": abs, "round": round, "int": int, "float": float,
    "min": min, "max": max, "sum": sum,
    "sqrt": math.sqrt, "pow": math.pow, "exp": math.exp,
    "log": math.log, "log10": math.log10, "log2": math.log2,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "degrees": math.degrees, "radians": math.radians,
    "ceil": math.ceil, "floor": math.floor, "trunc": math.trunc,
    "factorial": math.factorial,
}
_SAFE_CONSTS = {"pi": math.pi, "e": math.e, "inf": math.inf, "nan": math.nan}


class _SafeEvaluator(ast.NodeVisitor):
    """用 AST 实现安全的数学表达式求值"""

    def visit_Expression(self, node):
        return self.visit(node.body)

    def visit_Constant(self, node):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("不支持的常量类型")

    def visit_NamedConstant(self, node):
        if node.value in (True, False):
            return float(node.value)
        raise ValueError(f"不允许的常量: {node.value}")

    def visit_UnaryOp(self, node):
        val = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +val
        if isinstance(node.op, ast.USub):
            return -val
        raise ValueError("不支持的一元运算符")

    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            return left ** right
        raise ValueError("不支持的二元运算符")

    def visit_Call(self, node):
        func_name = node.func.id if isinstance(node.func, ast.Name) else None
        if func_name not in _SAFE_FUNCS:
            raise ValueError(f"不允许的函数: {func_name}")
        args = [self.visit(a) for a in node.args]
        return _SAFE_FUNCS[func_name](*args)

    def visit_Name(self, node):
        if node.id in _SAFE_CONSTS:
            return _SAFE_CONSTS[node.id]
        raise ValueError(f"不允许的变量: {node.id}")

    def generic_visit(self, node):
        raise ValueError(f"不允许的语法: {type(node).__name__}")


def safe_eval(expr: str) -> float:
    """安全计算数学表达式"""
    tree = ast.parse(expr.strip(), mode="eval")
    return _SafeEvaluator().visit(tree)
