"""
Calculator Engine - Core calculation logic separated from UI.
Handles expression parsing, evaluation, and mathematical operations.
"""

import math
import re
from decimal import Decimal, getcontext
from typing import Union, Optional
import sympy as sp

# Set precision for Decimal operations
getcontext().prec = 50


class CalculationError(Exception):
    """Custom exception for calculation errors."""
    pass


class CalculatorEngine:
    """Core calculator engine with expression parsing and evaluation."""

    # Operator precedence
    PRECEDENCE = {'+': 1, '-': 1, '*': 2, '/': 2, '^': 3, '**': 3}

    def __init__(self):
        self.last_result: Optional[str] = None
        self.history: list[tuple[str, str]] = []
        self.max_history = 100

    @staticmethod
    def normalize_expression(expr: str) -> str:
        """Convert UI symbols to Python-readable math notation."""
        # Remove whitespace
        expr = expr.replace(' ', '')

        # Handle factorials: 5! → factorial(5), 5.5! → gamma(5.5+1), (2+3)! → factorial(2+3)
        # Match integers: \d+
        # Match decimals: \d+\.\d+
        # Match parentheses groups: \([^()]+\)
        expr = re.sub(r'(\d+\.\d+|\d+|\([^()]+\))!', r'factorial(\1)', expr)

        # Replace UI symbols
        replacements = {
            '×': '*',
            'x': '*',
            'X': '*',
            '÷': '/',
            '^': '**',
            '²': '**2',
            'π': str(math.pi),
            'pi': str(math.pi),
            'e': str(math.e),
            '√': 'sqrt',
        }

        for old, new in replacements.items():
            expr = expr.replace(old, new)

        return expr

    @staticmethod
    def _find_operator_position(expr: str, pct_pos: int) -> int | None:
        """Find the owning + or - operator before a % (depth-aware)."""
        depth = 0
        for i in range(pct_pos - 1, -1, -1):
            if expr[i] == ')':
                depth += 1
            elif expr[i] == '(':
                depth -= 1
            elif depth == 0 and expr[i] in '+-':
                return i
        return None

    @staticmethod
    def _extract_percent_bounds(expr: str, pct_pos: int) -> tuple[int, int]:
        """Extract the start and end indices of the percent expression."""
        # Find start of percent number
        start = pct_pos - 1
        while start >= 0 and (expr[start].isdigit() or expr[start] == '.'):
            start -= 1

        # Find end (absorb multiplier/divider after %)
        end = pct_pos + 1
        while end < len(expr) and expr[end] in '*/0123456789().':
            end += 1

        return start, end

    @staticmethod
    def handle_percentage(expr: str) -> str:
        """
        Handle percentage logic in expressions.
        A ± B% → A ± (A * B / 100)
        """
        # Standalone percent in multiplicative contexts: 50% * 2 → (50/100) * 2
        expr = re.sub(r'(\d+(?:\.\d+)?)%(?=[*/])', r'(\1/100)', expr)

        # Consumer percentage resolution (left to right)
        while '%' in expr:
            pct_pos = expr.find('%')
            op_pos = CalculatorEngine._find_operator_position(expr, pct_pos)

            # Standalone percent fallback
            if op_pos is None:
                expr = expr[:pct_pos] + '/100' + expr[pct_pos + 1:]
                continue

            base = expr[:op_pos]
            op = expr[op_pos]

            start, end = CalculatorEngine._extract_percent_bounds(expr, pct_pos)
            pct_expr = expr[start + 1:end].replace('%', '')
            remainder = expr[end:]

            # Rewrite safely
            expr = f'({base}{op}({base}*({pct_expr})/100))' + remainder

        return expr

    def _precompute_factorials(self, expr: str) -> str:
        """Pre-compute factorial expressions and replace with their values."""
        import re

        # Pattern to match factorial(integer) or factorial(decimal)
        pattern = r'factorial\((\d+\.\d+|\d+)\)'

        def replace_factorial(match):
            try:
                n = float(match.group(1))
                result = self.factorial(n)
                return str(result)
            except Exception:
                return match.group(0)  # Keep original if failed

        # Replace all factorial calls with their computed values
        return re.sub(pattern, replace_factorial, expr)

    @staticmethod
    def _evaluate_with_numexpr(normalized: str) -> Union[int, float]:
        """Evaluate expression using numexpr and convert result."""
        import numexpr as ne
        result = ne.evaluate(normalized)

        # Convert numpy types to Python native types
        if hasattr(result, 'item'):
            result = result.item()
        elif hasattr(result, 'tolist'):
            result = result.tolist()

        # Ensure result is a scalar numeric type
        if isinstance(result, (list, tuple)) or (hasattr(result, '__len__') and not isinstance(result, (str, bytes))):
            raise CalculationError("Expression must evaluate to a single number")

        # Convert to int if it's a whole number
        if isinstance(result, float) and result == int(result):
            return int(result)
        if isinstance(result, (int, float)):
            return float(result)
        raise CalculationError(f"Cannot convert result to number: {type(result).__name__}")

    def safe_evaluate(self, expr: str) -> Union[int, float, Decimal]:
        """
        Safely evaluate a mathematical expression.
        Uses multiple strategies for different expression types.
        """
        if not expr:
            raise CalculationError("Empty expression")

        # Normalize the expression
        normalized = self.normalize_expression(expr)
        normalized = self.handle_percentage(normalized)

        # Pre-compute factorials before evaluation
        normalized = self._precompute_factorials(normalized)

        # Check for SCINUM marker (from scientific conversion)
        if 'SCINUM' in normalized:
            return self._parse_scinum(normalized)

        # Check for scientific notation that's standalone
        if self._is_standalone_scientific(normalized):
            return self._parse_scientific(normalized)

        # Try sympy simplification first for algebraic expressions
        try:
            sym_expr = sp.sympify(normalized)
            simplified = sp.simplify(sym_expr)
            if simplified.is_number and isinstance(simplified, sp.Expr):
                result = float(simplified.evalf())
                # Convert to int if it's a whole number
                if result == int(result):
                    return int(result)
                return result
        except Exception:
            pass

        # Use numexpr for arithmetic evaluation
        try:
            return self._evaluate_with_numexpr(normalized)
        except Exception as e:
            raise CalculationError(f"Evaluation error: {str(e)}")

    @staticmethod
    def _is_standalone_scientific(expr: str) -> bool:
        """Check if expression is just a scientific notation number."""
        if 'e' not in expr:
            return False
        # Check if it has arithmetic operators other than the 'e' in scientific notation
        operators = ['+', '-', '*', '/']
        for op in operators:
            if op in expr:
                # Check if the operator is part of the exponent
                parts = expr.split('e')
                if len(parts) == 2:
                    exponent = parts[1]
                    # Allow e+123 or e-123 or e123
                    if op in exponent and (exponent[0] == op or op in exponent[1:]):
                        continue
                return False
        return True

    @staticmethod
    def _parse_scientific(expr: str) -> float:
        """Parse a scientific notation string."""
        try:
            return float(expr)
        except ValueError:
            raise CalculationError(f"Invalid scientific notation: {expr}")

    @staticmethod
    def _parse_scinum(expr: str) -> Decimal:
        """Parse SCINUM marker format."""
        # SCINUM(mantissa, exponent) → Decimal
        match = re.search(r'SCINUM\(([^,]+),\s*([^)]+)\)', expr)
        if match:
            mantissa = match.group(1)
            exponent = match.group(2)
            return Decimal(f"{mantissa}e{exponent}")
        raise CalculationError("Invalid SCINUM format")

    @staticmethod
    def factorial(n: Union[int, float]) -> Union[int, float]:
        """Calculate factorial of n using SymPy. For non-integers, uses gamma(n+1)."""
        if n < 0:
            raise CalculationError("Factorial of negative number")

        # For integers, use factorial
        if n == int(n):
            return int(sp.factorial(int(n)))

        # For nonintegers, use gamma function: n! = gamma(n+1)
        return float(sp.gamma(n + 1))

    @staticmethod
    def sqrt(value: Union[int, float]) -> float:
        """Calculate square root using SymPy for precision."""
        if value < 0:
            raise CalculationError("Cannot calculate square root of negative number")
        return float(sp.sqrt(value))

    @staticmethod
    def ln(value: Union[int, float]) -> float:
        """Calculate natural logarithm using SymPy."""
        if value <= 0:
            raise CalculationError("Cannot calculate logarithm of non-positive number")
        return float(sp.log(value))

    @staticmethod
    def log10(value: Union[int, float]) -> float:
        """Calculate base-10 logarithm using SymPy."""
        if value <= 0:
            raise CalculationError("Cannot calculate logarithm of non-positive number")
        return float(sp.log(value, 10))

    @staticmethod
    def sin(value: Union[int, float]) -> float:
        """Calculate sine of value (in radians) using SymPy."""
        return float(sp.sin(value))

    @staticmethod
    def cos(value: Union[int, float]) -> float:
        """Calculate cosine of value (in radians) using SymPy."""
        return float(sp.cos(value))

    @staticmethod
    def tan(value: Union[int, float]) -> float:
        """Calculate tangent of value (in radians) using SymPy."""
        # Check for undefined points where cos(x) = 0
        cos_val = float(sp.cos(value))
        if abs(cos_val) < 1e-15:
            raise CalculationError("Tangent undefined at this value")
        return float(sp.tan(value))

    @staticmethod
    def power(base: Union[int, float], exp: Union[int, float]) -> float:
        """Calculate power using SymPy for precision."""
        try:
            return float(sp.Pow(base, exp))
        except (ValueError, TypeError) as e:
            raise CalculationError(f"Invalid power operation: {str(e)}")

    @staticmethod
    def to_scientific(value: Union[int, float], precision: int = 2) -> str:
        """Convert value to scientific notation."""
        try:
            return f"{value:.{precision}e}"
        except (ValueError, OverflowError) as e:
            raise CalculationError(f"Cannot convert to scientific notation: {str(e)}")

    @staticmethod
    def format_result(result: Union[int, float, Decimal]) -> str:
        """Format calculation result for display."""
        if isinstance(result, Decimal):
            result = float(result)

        if isinstance(result, float):
            # Check for scientific notation need
            if abs(result) >= 1e10 or (abs(result) < 1e-10 and result != 0):
                return f"{result:.6e}"

            # Format with appropriate precision
            if result == int(result):
                return str(int(result))

            # Remove trailing zeros
            formatted = f"{result:.10f}".rstrip('0').rstrip('.')
            return formatted

        return str(result)

    def calculate(self, expression: str) -> str:
        """
        Main calculation method.
        Evaluates expression and returns formatted result.
        """
        try:
            result = self.safe_evaluate(expression)
            formatted = self.format_result(result)
            self.last_result = formatted
            self._add_to_history(expression, formatted)
            return formatted
        except CalculationError:
            raise
        except Exception as e:
            raise CalculationError(f"Calculation failed: {str(e)}")

    def _add_to_history(self, expr: str, result: str) -> None:
        """Add entry to history."""
        self.history.insert(0, (expr, result))
        if len(self.history) > self.max_history:
            self.history.pop()

    def get_history(self) -> list[tuple[str, str]]:
        """Get calculation history."""
        return self.history.copy()

    def clear_history(self) -> None:
        """Clear calculation history."""
        self.history.clear()
        self.last_result = None

    @staticmethod
    def validate_input(text: str) -> bool:
        """Validate if input character is allowed."""
        allowed = set('0123456789.+-*/^()πe!%×÷√²x ')
        return all(c in allowed for c in text)

    @staticmethod
    def suggest_completion(partial: str) -> Optional[str]:
        """Suggest expression completion for partial input."""
        # Count open parentheses
        open_parens = partial.count('(')
        close_parens = partial.count(')')

        if open_parens > close_parens:
            return ')' * (open_parens - close_parens)
        return None


# Global engine instance
_engine: Optional[CalculatorEngine] = None


def get_engine() -> CalculatorEngine|None:
    """Get or create the global calculator engine instance."""
    global _engine
    if _engine is None:
        _engine = CalculatorEngine()
    return _engine
