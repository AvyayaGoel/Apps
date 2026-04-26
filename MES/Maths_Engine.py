"""
Maths_Engine.py – V6.0
Educational Step-by-Step Algebra Engine
Designed for UI-driven solvers
"""

# ─────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────
import re
from typing import Optional, List, Tuple

import sympy as sp
from sympy.parsing.latex import parse_latex
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
)
from sympy.printing.latex import latex

SYMPY_READY = True

TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)

# ─────────────────────────────────────────────
# MATHEMATICAL IDENTITIES DATABASE
# ─────────────────────────────────────────────
MATHEMATICAL_IDENTITIES = {
    # Trigonometric Identities
    "sin^2(x) + cos^2(x) = 1": "Pythagorean Identity",
    "1 + tan^2(x) = sec^2(x)": "Pythagorean Identity for Tangent",
    "1 + cot^2(x) = csc^2(x)": "Pythagorean Identity for Cotangent",
    "sin(2x) = 2sin(x)cos(x)": "Double Angle Identity",
    "cos(2x) = cos^2(x) - sin^2(x)": "Double Angle Identity",
    "cos(2x) = 2cos^2(x) - 1": "Double Angle Identity (Alternative)",
    "cos(2x) = 1 - 2sin^2(x)": "Double Angle Identity (Alternative)",
    "sin(a+b) = sin(a)cos(b) + cos(a)sin(b)": "Angle Addition Formula",
    "cos(a+b) = cos(a)cos(b) - sin(a)sin(b)": "Angle Addition Formula",

    # Logarithmic Properties
    "log(ab) = log(a) + log(b)": "Product Rule for Logarithms",
    "log(a/b) = log(a) - log(b)": "Quotient Rule for Logarithms",
    "log(a^b) = b*log(a)": "Power Rule for Logarithms",
    "ln(ab) = ln(a) + ln(b)": "Product Rule for Natural Logarithms",
    "ln(a/b) = ln(a) - ln(b)": "Quotient Rule for Natural Logarithms",
    "ln(a^b) = b*ln(a)": "Power Rule for Natural Logarithms",

    # Derivative Rules
    "d/dx(x^n) = n*x^(n-1)": "Power Rule",
    "d/dx(sin(x)) = cos(x)": "Derivative of Sine",
    "d/dx(cos(x)) = -sin(x)": "Derivative of Cosine",
    "d/dx(tan(x)) = sec^2(x)": "Derivative of Tangent",
    "d/dx(log(x)) = 1/(x*ln(10))": "Derivative of Logarithm",
    "d/dx(ln(x)) = 1/x": "Derivative of Natural Logarithm",
    "d/dx(e^x) = e^x": "Derivative of Exponential",

    # Integral Rules
    "∫x^n dx = x^(n+1)/(n+1) + C": "Power Rule for Integration",
    "∫sin(x) dx = -cos(x) + C": "Integral of Sine",
    "∫cos(x) dx = sin(x) + C": "Integral of Cosine",
    "∫sec^2(x) dx = tan(x) + C": "Integral of Secant Squared",
    "∫1/x dx = ln|x| + C": "Integral of Reciprocal",
    "∫e^x dx = e^x + C": "Integral of Exponential",
}

# ─────────────────────────────────────────────
# OPERATOR DEFINITIONS
# ─────────────────────────────────────────────
OPERATORS = {
    '+': (1, 'L'),
    '-': (1, 'L'),
    '*': (2, 'L'),
    '/': (2, 'L'),
    '^': (3, 'R'),
}

# ─────────────────────────────────────────────
# FUNCTION DEFINITIONS
# ─────────────────────────────────────────────
FUNCTIONS = {
    # Trigonometric
    'sin': {'arity': 1, 'type': 'trig'},
    'cos': {'arity': 1, 'type': 'trig'},
    'tan': {'arity': 1, 'type': 'trig'},
    'csc': {'arity': 1, 'type': 'trig'},
    'sec': {'arity': 1, 'type': 'trig'},
    'cot': {'arity': 1, 'type': 'trig'},
    'arcsin': {'arity': 1, 'type': 'trig'},
    'arccos': {'arity': 1, 'type': 'trig'},
    'arctan': {'arity': 1, 'type': 'trig'},

    # Logarithmic
    'log': {'arity': 1, 'type': 'log'},
    'ln': {'arity': 1, 'type': 'log'},

    # Calculus
    'sqrt': {'arity': 1, 'type': 'algebraic'},
    'abs': {'arity': 1, 'type': 'algebraic'},
    'exp': {'arity': 1, 'type': 'exponential'},

    # Matrix operations
    'det': {'arity': 1, 'type': 'matrix'},
    'inv': {'arity': 1, 'type': 'matrix'},
    'transpose': {'arity': 1, 'type': 'matrix'},

    # Calculus operations
    'diff': {'arity': 1, 'type': 'calculus'},
    'integrate': {'arity': 1, 'type': 'calculus'},
    'limit': {'arity': 2, 'type': 'calculus'},
    'sum': {'arity': 3, 'type': 'calculus'},
    'prod': {'arity': 3, 'type': 'calculus'},
}


# ─────────────────────────────────────────────
# AST NODE
# ─────────────────────────────────────────────
class Node:
    def __init__(self, value: str, left=None, right=None, args=None):
        self.value = value
        self.left = left
        self.right = right
        self.args = args or []  # For function calls with multiple arguments
        self.node_type = 'operator'  # Can be 'operator', 'function', 'matrix', 'number', 'variable'

        # Auto-detect node type
        if value in FUNCTIONS:
            self.node_type = 'function'
        elif re.fullmatch(r"-?\d+(\.\d+)?", value):
            self.node_type = 'number'
        elif value.isalpha():
            self.node_type = 'variable'
        elif value.startswith('[') and value.endswith(']'):
            self.node_type = 'matrix'

    def is_function(self):
        return self.node_type == 'function'

    def is_matrix(self):
        return self.node_type == 'matrix'

    def is_leaf(self):
        return not self.left and not self.right and not self.args

    def is_number(self):
        return re.fullmatch(r"-?\d+(\.\d+)?", self.value)

    def is_variable(self):
        return self.value.isalpha()

    def clone(self):
        return Node(
            self.value,
            self.left.clone() if self.left else None,
            self.right.clone() if self.right else None,
            [arg.clone() if hasattr(arg, 'clone') else arg for arg in self.args]
        )

    def precedence(self):
        return OPERATORS.get(self.value, (99,))[0]

    def to_string(self):
        if self.is_function():
            if self.args:
                args_str = ", ".join([arg.to_string() if hasattr(arg, 'to_string') else str(arg) for arg in self.args])
                return f"{self.value}({args_str})"
            else:
                return self.value
        elif self.is_matrix():
            return self.value
        elif self.is_leaf():
            return self.value

        l = self.left.to_string()
        r = self.right.to_string()

        if self.left and self.left.precedence() < self.precedence():
            l = f"({l})"
        if self.right and self.right.precedence() <= self.precedence():
            r = f"({r})"

        s = f"{l} {self.value} {r}"
        return s.replace("+ -", "- ").replace("- -", "+ ")


# ─────────────────────────────────────────────
# TOKENIZER (NEGATIVE SAFE)
# ─────────────────────────────────────────────
def parse_latex_expression(expr: str):
    try:
        return parse_latex(expr)
    except Exception as e:
        raise ValueError(f"LaTeX parsing error: {e}")


def tokenize(expr: str) -> List[str]:
    # Remove spaces but preserve backslashes for LaTeX commands
    expr = expr.replace(" ", "").replace("**", "^")

    # Enhanced token pattern for advanced mathematics
    # 1. Advanced functions (arcsin, arccos, arctan, etc.)
    # 2. Calculus operations (diff, integrate, limit, sum, prod)
    # 3. Matrix operations (det, inv, transpose)
    # 4. Constants (pi, theta, alpha, beta, gamma, delta, epsilon)
    # 5. Standard functions
    # 6. Operators and delimiters
    # 7. Numbers and variables
    token_pattern = r"(?:" \
                    r"arcsin|arccos|arctan|" \
                    r"diff|integrate|limit|sum|prod|" \
                    r"det|inv|transpose|" \
                    r"sqrt|sin|cos|tan|csc|sec|cot|" \
                    r"log|ln|abs|exp|" \
                    r"pi|theta|alpha|beta|gamma|delta|epsilon|" \
                    r"[()+\-*/^,\[\]{}]|" \
                    r"\d+\.\d+|\d+|" \
                    r"[a-zA-Z]" \
                    r")"

    raw = re.findall(token_pattern, expr)

    tokens = []
    i = 0
    while i < len(raw):
        t = raw[i]

        # Handle unary minus (negative numbers)
        if t == "-" and (i == 0 or raw[i - 1] in OPERATORS or raw[i - 1] in ["(", "[", "{", ","]):
            tokens.append("u-")
        # Handle matrix notation [a,b;c,d]
        elif t == "[":
            # Find matching closing bracket
            bracket_count = 1
            j = i + 1
            matrix_content = "["
            while j < len(raw) and bracket_count > 0:
                if raw[j] == "[":
                    bracket_count += 1
                elif raw[j] == "]":
                    bracket_count -= 1
                matrix_content += raw[j]
                j += 1
            tokens.append(matrix_content)
            i = j - 1  # Skip to the closing bracket
        else:
            tokens.append(t)
        i += 1

    return tokens


def insert_implicit_multiplication(tokens):
    result = []
    for i, t in enumerate(tokens):
        result.append(t)
        if i < len(tokens) - 1:
            a, b = t, tokens[i + 1]
            if (
                    (a.isdigit() or a.isalpha() or a == ')') and
                    (b.isalpha() or b.isdigit() or b == '(')
            ):
                result.append('*')
    return result


# ─────────────────────────────────────────────
# SHUNTING YARD
# ─────────────────────────────────────────────
def infix_to_postfix(tokens: List[str]) -> List[str]:
    out, stack = [], []

    for t in tokens:
        if t == "u-":
            stack.append(t)
        elif re.fullmatch(r"\d+(\.\d+)?", t) or t.isalpha() or (t.startswith('[') and t.endswith(']')):
            out.append(t)
        elif t in FUNCTIONS:
            # Functions have highest precedence
            stack.append(t)
        elif t == "(":
            stack.append(t)
        elif t == ")":
            while stack and stack[-1] != "(":
                out.append(stack.pop())
            stack.pop()
        else:
            while (
                    stack and stack[-1] not in ("(", "u-") and
                    OPERATORS.get(stack[-1], (0,))[0] >= OPERATORS.get(t, (0,))[0]
            ):
                out.append(stack.pop())
            stack.append(t)

    while stack:
        out.append(stack.pop())

    return out


# ─────────────────────────────────────────────
# POSTFIX → AST
# ─────────────────────────────────────────────
def postfix_to_ast(postfix: List[str]) -> Optional[Node]:
    stack = []

    for t in postfix:
        if t == "u-":
            n = stack.pop()
            stack.append(Node("-", Node("0"), n))
        elif t in OPERATORS:
            b, a = stack.pop(), stack.pop()
            stack.append(Node(t, a, b))
        elif t in FUNCTIONS:
            # Handle function calls - pop arguments based on arity
            func_info = FUNCTIONS[t]
            arity = func_info['arity']
            args = []
            for _ in range(arity):
                if stack:
                    args.insert(0, stack.pop())
            stack.append(Node(t, args=args))
        elif t.startswith('[') and t.endswith(']'):
            # Handle matrix notation
            stack.append(Node(t))
        else:
            stack.append(Node(t))

    return stack[0] if stack else None


# ─────────────────────────────────────────────
# STEP RULES (EXTEND THIS)
# ─────────────────────────────────────────────
def try_numeric(node: Node) -> Tuple[bool, str]:
    if not node or not node.left or not node.right:
        return False, ""

    if node.left.is_number() and node.right.is_number():
        a, b = float(node.left.value), float(node.right.value)
        op = node.value

        if op == '+':
            r = a + b
        elif op == '-':
            r = a - b
        elif op == '*':
            r = a * b
        elif op == '/':
            if b == 0:
                raise ZeroDivisionError
            r = a / b
        elif op == '^':
            r = a ** b
        else:
            return False, ""

        node.value = f"{r:g}"
        node.left = node.right = None
        return True, f"Computed {a:g} {op} {b:g}"

    return False, ""


def try_distribution(node: Node) -> Tuple[bool, str]:
    if node.value == "*" and node.right and node.right.value in ("+", "-"):
        a = node.left.clone()
        b = node.right.left.clone()
        c = node.right.right.clone()
        node.value = node.right.value
        node.left = Node("*", a, b)
        node.right = Node("*", a.clone(), c)
        return True, "Distributed multiplication"
    return False, ""


def try_trigonometric_simplification(node: Node) -> Tuple[bool, str]:
    """Apply trigonometric identities and simplifications"""
    if not node or not node.is_function():
        return False, ""

    func_name = node.value

    # Handle special cases
    if func_name == "sin" and node.args and node.args[0].is_number():
        angle = float(node.args[0].value)
        # Check for common angles
        if abs(angle % (2 * 3.14159)) < 0.001:  # sin(2π) = 0
            node.value = "0"
            node.args = []
            return True, "sin(2π) = 0 (Periodic property)"
        elif abs(angle % 3.14159) < 0.001:  # sin(π) = 0
            node.value = "0"
            node.args = []
            return True, "sin(π) = 0 (Periodic property)"

    elif func_name == "cos" and node.args and node.args[0].is_number():
        angle = float(node.args[0].value)
        if abs(angle % (2 * 3.14159)) < 0.001:  # cos(2π) = 1
            node.value = "1"
            node.args = []
            return True, "cos(2π) = 1 (Periodic property)"
        elif abs(angle % 3.14159) < 0.001:  # cos(π) = -1
            node.value = "-1"
            node.args = []
            return True, "cos(π) = -1 (Periodic property)"

    return False, ""


def try_logarithmic_simplification(node: Node) -> Tuple[bool, str]:
    """Apply logarithmic properties"""
    if not node or not node.is_function():
        return False, ""

    func_name = node.value

    if func_name in ["log", "ln"] and node.args:
        arg = node.args[0]

        # log(1) = 0 for any base
        if arg.is_number() and float(arg.value) == 1:
            node.value = "0"
            node.args = []
            return True, f"{func_name}(1) = 0 (Logarithm of 1)"

        # Handle log(a^b) = b*log(a)
        if arg.value == "^" and arg.left and arg.right:
            base = arg.left
            exponent = arg.right
            if exponent.is_number():
                node.value = "*"
                node.left = Node(exponent.value)
                node.right = Node(func_name, args=[base])
                node.args = []
                return True, f"Applied power rule: {func_name}(a^b) = b*{func_name}(a)"

    return False, ""


def try_calculus_operations(node: Node) -> Tuple[bool, str]:
    """Handle derivative and integral operations"""
    if not node or not node.is_function():
        return False, ""

    func_name = node.value

    # Power rule for derivatives: d/dx(x^n) = n*x^(n-1)
    if func_name == "diff" and node.args:
        expr = node.args[0]
        if expr.value == "^" and expr.left and expr.right:
            base = expr.left
            exponent = expr.right
            if base.is_variable() and exponent.is_number():
                n = float(exponent.value)
                node.value = "*"
                node.left = Node(f"{n}")
                node.right = Node("^", base.clone(), Node(f"{n - 1}"))
                node.args = []
                return True, f"Applied power rule: d/dx(x^{n}) = {n}*x^{n - 1}"

    # Basic integrals: ∫x^n dx = x^(n+1)/(n+1) + C
    elif func_name == "integrate" and node.args:
        expr = node.args[0]
        if expr.value == "^" and expr.left and expr.right:
            base = expr.left
            exponent = expr.right
            if base.is_variable() and exponent.is_number():
                n = float(exponent.value)
                if n != -1:  # Special case for 1/x
                    new_exp = n + 1
                    node.value = "/"
                    node.left = Node("^", base.clone(), Node(f"{new_exp}"))
                    node.right = Node(f"{new_exp}")
                    node.args = []
                    return True, f"Applied power rule for integration: ∫x^{n} dx = x^{new_exp}/{new_exp} + C"

    return False, ""


def try_matrix_operations(node: Node) -> Tuple[bool, str]:
    """Handle basic matrix operations"""
    if not node:
        return False, ""

    # Matrix determinant for 2x2: det([[a,b],[c,d]]) = ad - bc
    if node.is_function() and node.value == "det" and node.args:
        matrix = node.args[0]
        if matrix.is_matrix() and matrix.value.count(",") == 3:  # 2x2 matrix
            # Parse matrix content [a,b;c,d]
            content = matrix.value[1:-1]  # Remove brackets
            rows = content.split(";")
            if len(rows) == 2:
                elements = []
                for row in rows:
                    elements.extend(row.split(","))
                if len(elements) == 4:
                    a, b, c, d = elements
                    node.value = "-"
                    node.left = Node("*", Node(a), Node(d))
                    node.right = Node("*", Node(b), Node(c))
                    node.args = []
                    return True, "Calculated 2x2 determinant: det([[a,b],[c,d]]) = ad - bc"

    return False, ""


# ─────────────────────────────────────────────
# REDUCTION ENGINE
# ─────────────────────────────────────────────
def reduce_one_step(node: Node) -> Tuple[bool, str, str]:
    if not node or node.is_leaf():
        return False, "", ""

    # First, try function-specific rules
    if node.is_function():
        changed, reason = try_trigonometric_simplification(node)
        if changed:
            return True, reason, "trigonometric"

        changed, reason = try_logarithmic_simplification(node)
        if changed:
            return True, reason, "logarithmic"

        changed, reason = try_calculus_operations(node)
        if changed:
            return True, reason, "calculus"

        changed, reason = try_matrix_operations(node)
        if changed:
            return True, reason, "matrix"

    # Recursively try children
    for side in ("left", "right"):
        child = getattr(node, side)
        if child:
            changed, reason, kind = reduce_one_step(child)
            if changed:
                return True, reason, kind

    # Try function arguments
    if node.args:
        for i, arg in enumerate(node.args):
            if hasattr(arg, 'clone'):
                changed, reason, kind = reduce_one_step(arg)
                if changed:
                    return True, reason, kind

    # Standard algebraic rules
    changed, reason = try_numeric(node)
    if changed:
        return True, reason, "numeric"

    changed, reason = try_distribution(node)
    if changed:
        return True, reason, "expand"

    return False, "", ""


# ─────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────
def format_step_string(s: str) -> str:
    s = s.replace("**", "^")
    s = re.sub(r"\b1\*", "", s)
    s = re.sub(r"\*", "·", s)  # optional pretty dot
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def has_variables(expr: str) -> bool:
    return bool(re.search(r"[a-zA-Z]", expr))


def solve_symbolic(expr: str) -> dict:
    """Handle symbolic solving including equations"""
    try:
        # Check if it's an equation (contains =)
        if '=' in expr:
            return solve_equation(expr)
        else:
            # Regular symbolic expression
            x = sp.symbols("x")
            e = parse_latex(expr)
            sol = sp.solve(e, x)
            return {"roots": [str(r) for r in sol]}
    except Exception as e:
        return {"error": str(e)}


def solve_equation(expr: str) -> dict:
    """Handle equation solving with automatic variable detection"""
    try:
        # Split equation into left and right sides
        left, right = expr.split('=', 1)
        left = left.strip()
        right = right.strip()

        # Parse both sides
        left_expr = parse_latex(left)
        right_expr = parse_latex(right)

        # Move everything to left side: left - right = 0
        equation = left_expr - right_expr

        # Find all variables in the equation
        variables = list(equation.free_symbols)

        if not variables:
            return {"error": "No variables found in equation"}

        # Try to solve for each variable (usually only one variable)
        solutions = {}
        for var in variables:
            try:
                sol = sp.solve(equation, var)
                if sol:  # Only add if solutions exist
                    solutions[str(var)] = [str(s) for s in sol]
            except:
                continue

        if not solutions:
            return {"roots": []}

        # If only one variable, return in the expected format
        if len(solutions) == 1:
            var_name = list(solutions.keys())[0]
            return {
                "solutions": {
                    var_name: solutions[var_name]
                }
            }
        else:
            return {
                "solutions": solutions
            }

    except Exception as e:
        return {"error": str(e)}


def explain_error(expr: str, error_obj: Exception) -> str:
    """Detailed error explainer to help the user fix their input."""
    err_msg = str(error_obj)

    if "unmatched" in err_msg.lower() or expr.count('(') != expr.count(')'):
        return "Parentheses Mismatch: Ensure every '(' has a matching ')'."

    if "invalid syntax" in err_msg.lower():
        return "Syntax Error: Check for double operators (like '++' or '*/')."

    if "variable" in err_msg.lower():
        return "Unknown Symbol: This engine supports variables like x, a, b, c, etc."

    if "not a valid" in err_msg.lower() or "cannot" in err_msg.lower():
        return f"Expression Error: The expression '{expr}' cannot be processed. Check for valid mathematical operators and symbols."

    if "Symbol" in err_msg and "not found" in err_msg:
        return "Unknown Symbol: Please use standard variable names (x, y, z, a, b, c, etc.)"

    return f"Math Error: {err_msg}. Please check the expression format."


def to_latex(expr: str) -> str:
    """
    Convert a mathematical expression string to LaTeX format.
    Users can type regular math expressions and get LaTeX output.
    """
    try:
        # Parse the expression using sympy
        parsed_expr = parse_expr(expr.replace("^", "**"), transformations=TRANSFORMATIONS)

        # Convert to LaTeX
        latex_expr = latex(parsed_expr, mode='inline')

        # Clean up some common LaTeX formatting issues
        latex_expr = latex_expr.replace(r'\left(', '(').replace(r'\right)', ')')
        latex_expr = latex_expr.replace(r'\left[', '[').replace(r'\right]', ']')

        return latex_expr
    except Exception:
        # Fallback to original expression if LaTeX conversion fails
        return expr


def ast_to_latex(node: Node) -> str:
    """
    Convert AST node to LaTeX format.
    This provides LaTeX output for step-by-step solutions.
    """
    if not node:
        return ""

    if node.is_leaf():
        return node.value

    try:
        # Convert AST to string, then to LaTeX
        expr_str = node.to_string()
        return to_latex(expr_str)
    except Exception:
        # Fallback to regular string representation
        return node.to_string()


def normalize_ast(node):
    """
    Cleans up redundant spacing and enforces canonical structure.
    """
    if not node or node.is_leaf():
        return

    normalize_ast(node.left)
    normalize_ast(node.right)

    # Convert 1*x → x
    if node.value == '*' and node.left.value == '1':
        node.value = node.right.value
        node.left = node.right = None

    if node.value == '*' and node.right.value == '1':
        node.value = node.left.value
        node.left = node.right = None


def try_combine_like_terms(node):
    if node.value not in ('+', '-'):
        return False, ""

    if not node.left or not node.right:
        return False, ""

    # ax + bx → (a+b)x
    if (
            node.left.value == '*' and
            node.right.value == '*' and
            node.left.right.value == node.right.right.value
    ):
        a = float(node.left.left.value)
        b = float(node.right.left.value)
        x = node.left.right.clone()

        coeff = a + (b if node.value == '+' else -b)
        node.value = '*'
        node.left = Node(f"{coeff:g}")
        node.right = x
        return True, "Combined like terms"

    return False, ""
