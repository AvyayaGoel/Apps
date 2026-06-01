"""
Calculator Engine - Core calculation logic separated from UI.
Handles expression parsing, evaluation, and mathematical operations.
"""

import math
import re
from decimal import Decimal, getcontext, InvalidOperation, Overflow
from typing import Union, Optional

import numexpr as ne
import sympy as sp
from sympy import Expr

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

        # Protect scientific notation by temporarily replacing it with SCINUM markers
        # Pattern: number followed by e/E and optional sign and digits (e.g., 1e10, 1.5e-5, 2E+308)
        scientific_pattern = r'(\d+\.?\d*)[eE]([+-]?\d+)'

        def protect_scientific(match):
            mantissa = match.group(1)
            exponent = match.group(2)
            return f"SCINUM({mantissa},{exponent})"

        expr = re.sub(scientific_pattern, protect_scientific, expr)

        # Replace UI symbols (now safe to replace 'e' since scientific notation is protected)
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

        # Restore scientific notation numbers from SCINUM markers
        def restore_scientific(match):
            mantissa = match.group(1)
            exponent = match.group(2)
            return f"{mantissa}e{exponent}"

        expr = re.sub(r'SCINUM\(([^,]+),([^)]+)\)', restore_scientific, expr)

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

    @staticmethod
    def _estimate_number_digits(num_str: str) -> int:
        """Estimate the number of digits in a number string (handles scientific notation)."""
        num_str = num_str.strip()

        # Handle scientific notation
        if 'e' in num_str.lower():
            parts = num_str.lower().split('e')
            if len(parts) == 2:
                try:
                    exponent = int(parts[1])
                    # digits ≈ exponent + 1 (for positive exponents)
                    if exponent >= 0:
                        return exponent + 1
                    else:
                        # For negative exponents, it's a small number
                        return 1
                except ValueError:
                    pass

        # Regular number - count digits
        digits = re.sub(r'\D', '', num_str)
        return len(digits) if digits else 1

    @staticmethod
    def _is_valid_number(s: str) -> bool:
        """Check if string is a valid number (handles scientific notation without overflow)."""
        if not s or s == '.' or s.lower() in ('e', 'e+', 'e-'):
            return False
        s = s.strip().lower()
        if 'e' in s:
            parts = s.split('e')
            if len(parts) == 2:
                mantissa, exp = parts[0], parts[1]
                if mantissa and not all(c in '0123456789.' for c in mantissa):
                    return False
                if exp and not (exp[0] in '+-' and exp[1:].isdigit() or exp.isdigit()):
                    return False
                return True
            return False
        try:
            float(s)
            return True
        except (ValueError, OverflowError):
            return False

    @staticmethod
    def _get_number_digits(num_str: str) -> int:
        """Get digit count from number string (handles scientific notation)."""
        num_str = num_str.strip().lower()
        if 'e' in num_str:
            parts = num_str.split('e')
            if len(parts) == 2:
                try:
                    exp = int(parts[1])
                    return exp + 1 if exp >= 0 else 1
                except ValueError:
                    pass
        digits = re.sub(r'\D', '', num_str)
        return len(digits) if digits else 1

    @staticmethod
    def _parse_sci_notation(s: str) -> tuple[float, int]:
        """Parse scientific notation, return (mantissa, exponent) tuple."""
        s = s.strip().lower()
        if 'e' in s:
            parts = s.split('e')
            if len(parts) == 2:
                try:
                    mantissa = float(parts[0]) if parts[0] else 1.0
                    exp = int(parts[1])
                    return mantissa, exp
                except ValueError:
                    pass
        return float(s), 0

    @staticmethod
    def _calculate_log10_magnitude(n: str) -> float:
        """Calculate log10 magnitude of a number string."""
        n_lower = n.lower()
        if 'e' in n_lower:
            parts = n_lower.split('e')
            if len(parts) == 2:
                try:
                    mantissa = float(parts[0]) if parts[0] else 1.0
                    exp = int(parts[1])
                    return math.log10(abs(mantissa)) + exp if mantissa != 0 else float('-inf')
                except (ValueError, OverflowError):
                    pass
        try:
            val = float(n)
            return math.log10(abs(val)) if val != 0 else float('-inf')
        except (ValueError, OverflowError):
            return 0

    @staticmethod
    def _check_power_operation(base_str: str, exp_str: str, max_digits: int) -> tuple[bool, str]:
        """Check if power operation would exceed digit limit."""
        if not CalculatorEngine._is_valid_number(base_str) or not CalculatorEngine._is_valid_number(exp_str):
            return True, ""

        base_mantissa, base_exp = CalculatorEngine._parse_sci_notation(base_str)
        exp_mantissa, exp_exp = CalculatorEngine._parse_sci_notation(exp_str)

        if base_mantissa in (0, 1) or exp_mantissa == 0:
            return True, ""

        log_base = math.log10(abs(base_mantissa)) + base_exp if base_mantissa != 0 else 0

        if 'e' in exp_str.lower():
            exp_value = 10 ** (math.log10(abs(exp_mantissa)) + exp_exp)
        else:
            exp_value = abs(exp_mantissa)

        estimated_digits = exp_value * log_base + 1

        if estimated_digits > max_digits:
            return False, f"Result would have ~{int(estimated_digits)} digits"
        if exp_value > 10000:
            return False, "Exponent too large - would take too long"

        return True, ""

    @staticmethod
    def _check_factorial(n_str: str, max_digits: int) -> tuple[bool, str]:
        """Check if factorial would exceed digit limit."""
        n = int(n_str)
        if n <= 10000:
            return True, ""
        log10_factorial = n * math.log10(n) - n / math.log(10) + math.log10(2 * math.pi * n) / 2
        estimated_digits = int(log10_factorial) + 1
        if estimated_digits > max_digits:
            return False, f"Result would have ~{estimated_digits} digits"
        return True, ""

    @staticmethod
    def _check_computation_feasibility(expr: str) -> tuple[bool, str]:
        """
        Pre-check if calculation is feasible before attempting it.
        Estimates result digit count to prevent excessive computation.
        Works on original user input (handles scientific notation like 1e+100).
        Returns (is_feasible, reason) tuple.
        """
        MAX_DIGITS = 15000
        number_pattern = r'\d+\.?\d*(?:[eE][+-]?\d+)?'

        # Check power operations
        power_patterns = [
            rf'({number_pattern})\s*\*\*\s*({number_pattern})',
            rf'({number_pattern})\s*\^\s*({number_pattern})',
        ]

        for pattern in power_patterns:
            for match in re.finditer(pattern, expr):
                try:
                    is_feasible, reason = CalculatorEngine._check_power_operation(
                        match.group(1), match.group(2), MAX_DIGITS
                    )
                    if not is_feasible:
                        return False, reason
                except (ValueError, OverflowError):
                    continue

        # Check multiplication chains
        mul_div_pattern = rf'(?:{number_pattern}\s*[*×/÷]\s*)+{number_pattern}'
        for match in re.finditer(mul_div_pattern, expr):
            numbers = re.findall(number_pattern, match.group(0))
            numbers = [n for n in numbers if CalculatorEngine._is_valid_number(n)]
            if len(numbers) >= 2:
                total_log10 = sum(CalculatorEngine._calculate_log10_magnitude(n) for n in numbers)
                if total_log10 > 0:
                    estimated_digits = int(total_log10) + 1
                    if estimated_digits > MAX_DIGITS:
                        return False, f"Result would have ~{estimated_digits} digits"

        # Check addition/subtraction
        add_sub_pattern = rf'(?:{number_pattern}\s*[+-]\s*)+{number_pattern}'
        for match in re.finditer(add_sub_pattern, expr):
            numbers = re.findall(number_pattern, match.group(0))
            numbers = [n for n in numbers if CalculatorEngine._is_valid_number(n)]
            if len(numbers) >= 2:
                max_digits = max(CalculatorEngine._get_number_digits(n) for n in numbers)
                if max_digits > MAX_DIGITS:
                    return False, f"Cannot handle numbers with {max_digits} digits"

        # Check factorial
        factorial_pattern = r'factorial\((\d+)\)|(\d+)!'
        for match in re.finditer(factorial_pattern, expr):
            try:
                n_str = match.group(1) if match.group(1) else match.group(2)
                is_feasible, reason = CalculatorEngine._check_factorial(n_str, MAX_DIGITS)
                if not is_feasible:
                    return False, reason
            except (ValueError, OverflowError):
                continue

        return True, ""

    def safe_evaluate(self, expr: str) -> Union[int, float, Decimal]:
        """
        Safely evaluate a mathematical expression.
        Uses multiple strategies for different expression types.
        """
        if not expr:
            raise CalculationError("Empty expression")

        # Pre-check computation feasibility
        is_feasible, reason = CalculatorEngine._check_computation_feasibility(expr)
        if not is_feasible:
            raise CalculationError(reason)

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
                # Check if result is a large integer (avoid float overflow)
                if simplified.is_Integer:
                    int_result = int(simplified)
                    # If it's too large for float, return as Decimal
                    if abs(int_result) > 2 ** 1024:  # Approx float max
                        return Decimal(str(simplified))
                    return int_result
                # Evaluate with high precision for nonintegers
                result = simplified.evalf(100)
                # Check if result is a finite number
                if result.is_finite:
                    result_float = float(result)
                    # Check for infinity (overflow during float conversion)
                    if math.isinf(result_float):
                        # Return as Decimal to preserve precision
                        return Decimal(str(result))
                    # Convert to int if it's a whole number
                    if result_float == int(result_float):
                        return int(result_float)
                    return result_float
                else:
                    # Result is infinity, use high precision evaluation
                    return self._evaluate_with_decimal(normalized)
        except Exception:
            pass

        # Use numexpr for arithmetic evaluation
        try:
            result = self._evaluate_with_numexpr(normalized)
            # Check if result overflowed to infinity
            if isinstance(result, float) and math.isinf(result):
                # Fall back to high-precision Decimal evaluation
                return self._evaluate_with_decimal(normalized)
            return result
        except Exception as e:
            raise CalculationError(f"Evaluation error: {str(e)}")

    @staticmethod
    def _evaluate_with_decimal(expr: str) -> Decimal:
        """Evaluate expression using high-precision Decimal arithmetic."""
        # Set high precision for large numbers
        getcontext().prec = 200

        # Replace ** back to proper Python power operator for eval
        expr = expr.replace('^', '**')

        try:
            # Use sympy with high precision for the evaluation
            sym_expr = sp.sympify(expr)
            # Simplify the expression (computes the power)
            simplified = sp.simplify(sym_expr)
            # Evaluate with high precision (check isinstance for type safety)
            if isinstance(simplified, Expr):
                # For integers, convert directly to Decimal (avoid float overflow)
                if simplified.is_Integer:
                    return Decimal(str(simplified))
                # For other numbers, use evalf with high precision
                result = simplified.evalf(200)
                if result.is_number and result.is_finite:
                    return Decimal(str(result))
        except Exception:
            pass

        # Fallback: Create a safe evaluation context with Decimal
        try:
            # Helper function for Decimal power (exponent must be int for large powers)
            def _dec_pow(base, exp):
                if isinstance(exp, Decimal):
                    # Convert to int if it's a whole number
                    if exp == exp.to_integral_value():
                        exp = int(exp)
                return base ** exp

            # Create a locals dict with Decimal constructor and power helper
            decimal_locals = {
                'Decimal': Decimal,
                'dec': lambda x: Decimal(str(x)),  # Helper to convert to Decimal
                '_pow': _dec_pow
            }

            # First convert all numbers to Decimal
            safe_expr = re.sub(r'(\d+\.?\d*)', r'Decimal(\'\1\')', expr)

            # Then replace ** operations with _pow function calls
            # Pattern matches: something ** something
            # We need to handle nested operations, so we process from right to left
            # Simple approach: replace ** with , and wrap in _pow()
            # But this is tricky with regex, so we use a different strategy:
            # Split by ** and rebuild with _pow()
            if '**' in safe_expr:
                parts = safe_expr.split('**')
                if len(parts) == 2:
                    safe_expr = f"_pow({parts[0]}, {parts[1]})"
                else:
                    # Multiple ** - handle right-associative: a**b**c = a**(b**c)
                    # Build nested _pow calls from right to left
                    result = parts[-1]
                    for part in reversed(parts[:-1]):
                        result = f"_pow({part}, {result})"
                    safe_expr = result

            return eval(safe_expr, {"__builtins__": {}}, decimal_locals)
        except Overflow:
            # Number is too large even for Decimal - return infinity
            return Decimal('inf')
        except InvalidOperation as e:
            raise CalculationError(f"High-precision evaluation failed: {str(e)}")

    @staticmethod
    def _is_standalone_scientific(expr: str) -> bool:
        """Check if expression is just a scientific notation number."""
        if 'e' not in expr and 'E' not in expr:
            return False
        # Check for any operators that would indicate this is an expression, not just a number
        # Only + and - are allowed (as part of exponent), * and / are never allowed in standalone notation
        operators_never_allowed = ['*', '/', '×', '÷']
        for op in operators_never_allowed:
            if op in expr:
                return False
        # For + and -, check if they appear AFTER the 'e' (as part of exponent) or BEFORE (as operators)
        expr_lower = expr.lower()
        if 'e' in expr_lower:
            e_index = expr_lower.index('e')
            # Check for + or - before the 'e' - these would be operators
            before_e = expr[:e_index]
            if '+' in before_e or '-' in before_e:
                return False
            # Check for + or - after the 'e' - only one sign allowed as part of exponent
            after_e = expr[e_index + 1:]
            # After e, we should only have digits and optionally one sign at the start
            if not after_e:
                return False
            # Check that after the optional sign, there are only digits
            if after_e[0] in '+-':
                after_e = after_e[1:]
            if not after_e.isdigit():
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
    def _add_thousands_separator(num_str: str) -> str:
        """Add thousands separators to a number string."""
        # Handle negative numbers
        if num_str.startswith('-'):
            prefix = '-'
            num_str = num_str[1:]
        else:
            prefix = ''

        # Split into integer and decimal parts
        if '.' in num_str:
            integer_part, decimal_part = num_str.split('.')
        else:
            integer_part, decimal_part = num_str, ''

        # Add commas to integer part
        integer_part = f"{int(integer_part):,}"

        # Recombine
        if decimal_part:
            return f"{prefix}{integer_part}.{decimal_part}"
        return f"{prefix}{integer_part}"

    @staticmethod
    def format_result(result: Union[int, float, Decimal]) -> str:
        """Format calculation result for display with thousands separators."""
        if isinstance(result, Decimal):
            # Check magnitude using Decimal comparison (not float conversion)
            abs_result = abs(result)
            if abs_result >= Decimal('1e10') or (abs_result < Decimal('1e-10') and abs_result != 0):
                # Format large decimals in scientific notation
                # Use to_eng_string() or custom formatting for very large numbers
                _, digits, exponent = result.as_tuple()
                # Convert to scientific notation manually
                if len(digits) > 0:
                    mantissa = f"{digits[0]}.{''.join(map(str, digits[1:7])).rstrip('0') or '0'}"
                    exp = len(digits) - 1 + exponent
                    return f"{mantissa}e+{exp}" if result > 0 else f"-{mantissa}e+{exp}"
                return str(result)
            # Remove trailing zeros for cleaner display
            result_str = str(result)
            if '.' in result_str:
                result_str = result_str.rstrip('0').rstrip('.')
            return CalculatorEngine._add_thousands_separator(result_str) if result_str else "0"

        if isinstance(result, float):
            # Check for infinity
            if math.isinf(result):
                return "∞ (overflow)"
            # Check for scientific notation need
            if abs(result) >= 1e10 or (abs(result) < 1e-10 and result != 0):
                return f"{result:.6e}"

            # Format with appropriate precision
            if result == int(result):
                return CalculatorEngine._add_thousands_separator(str(int(result)))

            # Remove trailing zeros and add separators
            formatted = f"{result:.10f}".rstrip('0').rstrip('.')
            return CalculatorEngine._add_thousands_separator(formatted)

        # For int
        return CalculatorEngine._add_thousands_separator(str(result))

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


def get_engine() -> CalculatorEngine | None:
    """Get or create the global calculator engine instance."""
    global _engine
    if _engine is None:
        _engine = CalculatorEngine()
    return _engine
