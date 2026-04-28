"""
Maths_Engine_Gemini_V3.py – V10.0
REAL Gemini+Sympy Hybrid Engine using NEW google.genai library
Uses actual Gemini API for AI explanations with config file for API key
"""
import re

import google.genai as genai
import sympy as sp
import sympy.parsing.latex as sympy_latex
from google.genai import types
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
from sympy.printing.latex import latex

from gemini_config import GEMINI_API_KEY


class GeminiMathsEngineV3:
    def __init__(self):

        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.transformations = standard_transformations + (implicit_multiplication_application,)

    def get_gemini_explanation(self, original_expr, result_expr, operation_type="simplification"):
        config = types.GenerateContentConfig(
            temperature=0.5,
            max_output_tokens=300,
            top_p=0.95
        )
        prompt = f"""
        Identify the mathematical identity or rule used in this {operation_type}.
        
        Original: {original_expr}
        Result: {result_expr}
        
        Instructions:
        1. Explain the logic in 1-2 full, sophisticated sentences.
        2. Focus strictly on the mathematical 'trick' or 'rule'.
        3. Maintain a dry, slightly arrogant academic tone.
        4. Use Pure Unicode for math symbols (no LaTeX).
        5. No enthusiastic fluff or 'congratulations'.
        6. Trust the result: The current step result is mathematically perfect and simplified.
        7. Do not mention 'errors' or 'mistakes' or 'result' in the engine's output.
        8. Focus on explaining how we got to the simplified form.
        9. MANDATORY TEMPLATE:
           Identity/Rule: [Name of the rule]\n
           Explanation: [Your sophisticated explanation]
        10. STRICT BAN: Do NOT use HTML tags like <sup>, <sub>, or <b>. Use ONLY plain text and Unicode.
        
        Example:
        Identity/Rule: Difference of Squares\n
        Explanation: The expression was factored by recognizing the subtraction of two perfect square terms, allowing for a swift reduction to its conjugate product form as any competent student should observe.
        """

        try:
            response = self.client.models.generate_content(
                model="gemma-3-27b-it",
                contents=prompt,
                config=config
            )
            return response.text
        except (ConnectionError, TimeoutError):
            return f"Applied {operation_type} from {original_expr} to {result_expr}"

    def _parse_expression(self, expr):
        """Parse expression using LaTeX parser first, then fallback to regular parser"""
        constants_dict = {"e": sp.E, "i": sp.I}
        try:
            # Try LaTeX parser first
            sympy_expr = sympy_latex.parse_latex(expr)
            if sympy_expr.has(sp.Symbol('e')):
                sympy_expr = sympy_expr.subs(sp.Symbol('e'), sp.E)
            if sympy_expr.has(sp.Symbol('i')):
                sympy_expr = sympy_expr.subs(sp.Symbol('i'), sp.I)
            return sympy_expr
        except (ValueError, SyntaxError, TypeError, sp.SympifyError):
            try:
                # Fallback to regular parser with ^ operator handling
                processed_expr = expr.replace('^', '**')
                if '**' in processed_expr and '=' in processed_expr:
                    # This is an equation with exponents - handle each side separately
                    left, right = processed_expr.split('=', 1)
                    left_expr = parse_expr(left.strip(), transformations=self.transformations,
                                           local_dict=constants_dict)
                    right_expr = parse_expr(right.strip(), transformations=self.transformations,
                                            local_dict=constants_dict)
                    return sp.Eq(left_expr, right_expr)
                else:
                    # Single expression
                    sympy_expr = parse_expr(processed_expr, transformations=self.transformations,
                                            local_dict=constants_dict)
                    return sympy_expr
            except (ValueError, SyntaxError, TypeError, sp.SympifyError):
                # Final fallback - try direct evaluation
                try:
                    return sp.sympify(expr.replace('^', '**'))
                except (ValueError, SyntaxError, TypeError, sp.SympifyError):
                    return None

    def simplify_with_gemini(self, expr):
        try:
            # Parse expression using LaTeX parser
            sympy_expr = self._parse_expression(expr)
            if sympy_expr is None:
                return {'error': f'Could not parse expression: {expr}', 'original': expr}

            simplified = sp.simplify(sympy_expr)

            original_readable = str(sympy_expr).replace('**', '^')
            simplified_readable = str(simplified).replace('**', '^')

            explanation = self.get_gemini_explanation(
                original_readable,
                simplified_readable,
                "simplification"
            )

            return {
                'original': str(sympy_expr),
                'simplified': str(simplified),
                'latex_original': latex(sympy_expr),
                'latex_simplified': latex(simplified),
                'explanation': explanation
            }
        except Exception as e:
            return {'error': str(e), 'original': expr}

    def differentiate_with_gemini(self, expr):
        try:
            # Parse expression using LaTeX parser
            sympy_expr = self._parse_expression(expr)
            if sympy_expr is None:
                return {'error': f'Could not parse expression: {expr}', 'original': expr}

            x = sp.symbols('x')
            derivative = sp.diff(sympy_expr, x)

            original_readable = str(sympy_expr).replace('**', '^')
            derivative_readable = str(derivative).replace('**', '^')

            explanation = self.get_gemini_explanation(
                original_readable,
                derivative_readable,
                "differentiation"
            )

            return {
                'original': str(sympy_expr),
                'derivative': str(derivative),
                'latex_original': latex(sympy_expr),
                'latex_derivative': latex(derivative),
                'explanation': explanation
            }
        except Exception as e:
            return {'error': str(e), 'original': expr}

    def integrate_with_gemini(self, expr):
        try:
            # Parse expression using LaTeX parser
            sympy_expr = self._parse_expression(expr)
            if sympy_expr is None:
                return {'error': f'Could not parse expression: {expr}', 'original': expr}

            x = sp.symbols('x')
            if isinstance(sympy_expr, sp.Integral):
                integral = sympy_expr.doit()
            else:
                integral = sp.integrate(sympy_expr, x)

            original_readable = str(sympy_expr).replace('**', '^')
            integral_readable = str(integral).replace('**', '^')

            explanation = self.get_gemini_explanation(
                original_readable,
                integral_readable,
                "integration"
            )

            return {
                'original': str(sympy_expr),
                'integral': str(integral),
                'latex_original': latex(sympy_expr),
                'latex_integral': latex(integral),
                'explanation': explanation
            }
        except Exception as e:
            return {'error': str(e), 'original': expr}

    def _parse_equation(self, equation):
        """Parse equation and return SymPy Eq object"""
        if '=' not in equation:
            return None, 'Not an equation'

        # Try parsing the entire equation first
        parsed_eq = self._parse_expression(equation.strip())

        # If parsing returned an Eq object directly, use it
        if isinstance(parsed_eq, sp.Eq):
            return parsed_eq, None

        # Otherwise, parse left and right sides separately
        left, right = equation.split('=', 1)
        left_expr = self._parse_expression(left.strip())
        right_expr = self._parse_expression(right.strip())

        if left_expr is None or right_expr is None:
            return None, f'Could not parse equation: {equation}'

        # Move everything to one side
        return sp.Eq(left_expr, right_expr), None

    @staticmethod
    def _format_solution_value(val, var_name=None):
        """Format a single solution value with numerical approximation if needed"""
        if hasattr(val, 'evalf'):
            try:
                # Try to get numerical approximation
                approx_val = val.evalf(6)  # 6 decimal places
                if var_name:
                    return f"{var_name} ≈ {approx_val}", latex(approx_val)
                else:
                    return f"x ≈ {approx_val}", latex(approx_val)
            except (ValueError, TypeError, sp.SympifyError):
                if var_name:
                    return f"{var_name} = {val}", latex(val)
                else:
                    return str(val), latex(val)
        else:
            if var_name:
                return f"{var_name} = {val}", latex(val)
            else:
                return str(val), latex(val)

    def _format_solutions(self, solutions):
        """Format solutions list for better display"""
        formatted_solutions = []
        latex_solutions = []

        for sol in solutions:
            if isinstance(sol, dict):
                for var, val in sol.items():
                    formatted, latex_sol = self._format_solution_value(val, str(var))
                    formatted_solutions.append(formatted)
                    latex_solutions.append(latex_sol)
            else:
                formatted, latex_sol = self._format_solution_value(sol)
                formatted_solutions.append(formatted)
                latex_solutions.append(latex_sol)

        return formatted_solutions, latex_solutions

    @staticmethod
    def _create_readable_solutions_string(formatted_solutions):
        """Create readable solutions string for Gemini explanation"""
        readable_solutions = ", ".join(formatted_solutions[:3])
        if len(formatted_solutions) > 3:
            readable_solutions += f" and {len(formatted_solutions) - 3} more solutions"
        return readable_solutions

    def solve_with_gemini(self, equation):
        try:
            full_eq, error = self._parse_equation(equation)
            if error:
                return {'error': error, 'original': equation}

            solutions = sp.solve(full_eq, dict=True, complex=True)

            # Format solutions for better display
            formatted_solutions, latex_solutions = self._format_solutions(solutions)

            # Create LaTeX version of the original equation
            latex_equation = latex(full_eq)

            # Create readable solutions string for Gemini
            readable_solutions = self._create_readable_solutions_string(formatted_solutions)

            explanation = self.get_gemini_explanation(
                equation,
                readable_solutions,
                "equation solving"
            )

            return {
                'original': equation,
                'latex_original': latex_equation,
                'solutions': formatted_solutions,
                'latex_solutions': latex_solutions,
                'explanation': explanation
            }
        except Exception as e:
            return {'error': str(e), 'original': equation}

    def _evaluate_limit_expression(self, expr):
        """Evaluate LaTeX limit expression"""
        # Pattern to match \lim_{x->a} f(x)
        match = re.search(r'\\lim_\{([^}]+)\\to([^}]+)}\s*(.+)$', expr)
        if not match:
            return None, 'Could not extract limit expression'

        var = match.group(1).strip()
        limit_val = match.group(2).strip()
        func = match.group(3).strip()

        try:
            # Parse the function
            sympy_func = self._parse_expression(func)
            if sympy_func is None:
                return None, f'Could not parse limit function: {func}'

            # Parse the limit value
            limit_val_parsed = self._parse_expression(limit_val)
            if limit_val_parsed is None:
                return None, f'Could not parse limit value: {limit_val}'

            # Calculate limit
            limit_result = sp.limit(sympy_func, sp.Symbol(var), limit_val_parsed)

            original_readable = f"lim_{{{var}\to{limit_val}}} {func}"
            result_readable = str(limit_result).replace('**', '^')

            explanation = self.get_gemini_explanation(
                original_readable,
                result_readable,
                "limit evaluation"
            )

            return {
                'original': str(sympy_func),
                'limit': str(limit_result),
                'latex_original': f"\\lim_{{{var}\\to{limit_val}}} {latex(sympy_func)}",
                'latex_limit': latex(limit_result),
                'explanation': explanation
            }, None
        except Exception as e:
            return None, f'Limit evaluation failed: {str(e)}'

    def _evaluate_derivative_expression(self, expr):
        """Evaluate LaTeX derivative expression"""
        # Pattern to match \frac{d}{dx} followed by the function
        match = re.search(r'\\frac\{d}\{dx}\s*(.+)$', expr)
        if not match:
            return None, 'Could not extract function from derivative notation'

        func_to_diff = match.group(1).strip()
        return self.differentiate_with_gemini(func_to_diff), None

    def _evaluate_simple_calculus_expression(self, expr):
        """Evaluate simple calculus expressions (diff/integrate keywords)"""
        if 'diff' in expr:
            func_part = expr.replace('diff', '').strip().strip('()')
            if func_part:
                return self.differentiate_with_gemini(func_part), None
        elif 'integrate' in expr:
            func_part = expr.replace('integrate', '').strip().strip('()')
            if func_part:
                return self.integrate_with_gemini(func_part), None

        return None, 'Unrecognized calculus expression'

    def evaluate_calculus_expression(self, expr):
        """Handle calculus expressions like derivatives, integrals, and limits using LaTeX parser"""
        # Check for LaTeX limit notation
        if r'\lim' in expr:
            result, error = self._evaluate_limit_expression(expr)
            if error:
                return {'error': error, 'original': expr}
            return result

        # Check for LaTeX calculus notation
        if r'\frac{d}{dx}' in expr:
            result, error = self._evaluate_derivative_expression(expr)
            if error:
                return {'error': error, 'original': expr}
            return result

        # Check for LaTeX integral notation
        if r'\int' in expr:
            return self.integrate_with_gemini(expr)

        # Fallback to simple notation
        result, error = self._evaluate_simple_calculus_expression(expr)
        if error:
            return {'error': error, 'original': expr}
        return result

    def step_by_step_simplify(self, expr, max_steps=5):
        # First check if it's a calculus expression (handle spaces)
        if r'\frac{d}{dx}' in expr or r'\int' in expr or r'\lim' in expr or 'diff' in expr or 'integrate' in expr:
            calculus_result = self.evaluate_calculus_expression(expr)
            if 'error' not in calculus_result:
                # Convert calculus result to step format
                step = {
                    'step': 1,
                    'original': calculus_result['original'],
                    'simplified': calculus_result.get('derivative', calculus_result.get('integral',
                                                                                        calculus_result.get('limit',
                                                                                                            calculus_result.get(
                                                                                                                'simplified',
                                                                                                                '')))),
                    'latex_original': calculus_result.get('latex_original', ''),
                    'latex_simplified': calculus_result.get('latex_derivative', calculus_result.get('latex_integral',
                                                                                                    calculus_result.get(
                                                                                                        'latex_limit',
                                                                                                        calculus_result.get(
                                                                                                            'latex_simplified',
                                                                                                            '')))),
                    'explanation': calculus_result['explanation']
                }
                return [step]
            else:
                # If calculus evaluation failed, try regular simplification
                pass

        # Regular algebraic simplification
        steps = []
        current = expr

        for i in range(max_steps):
            result = self.simplify_with_gemini(current)

            if 'error' in result:
                break

            steps.append({
                'step': i + 1,
                'original': result['original'],
                'simplified': result['simplified'],
                'latex_original': result['latex_original'],
                'latex_simplified': result['latex_simplified'],
                'explanation': result['explanation']
            })

            if result['original'] == result['simplified']:
                break

            current = result['simplified']

        return steps

    def smart_router(self, raw_latex):
        """Smart router that uses SymPy object types for proper classification"""
        # 1. Parse it once to see what it is
        obj = self._parse_expression(raw_latex)
        if obj is None:
            return {'error': f'Could not parse expression: {raw_latex}', 'original': raw_latex}

        # 2. Check the type directly
        if isinstance(obj, sp.Equality):
            return self.solve_with_gemini(raw_latex)

        elif isinstance(obj, sp.Sum):
            # Handle summations like the Basel Problem
            try:
                result = obj.doit()
                original_readable = str(obj).replace('**', '^')
                result_readable = str(result).replace('**', '^')

                explanation = self.get_gemini_explanation(
                    original_readable,
                    result_readable,
                    "summation evaluation"
                )

                return {
                    'original': str(obj),
                    'summation': str(result),
                    'latex_original': latex(obj),
                    'latex_summation': latex(result),
                    'explanation': explanation
                }
            except Exception as e:
                return {'error': f'Summation evaluation failed: {str(e)}', 'original': raw_latex}

        elif isinstance(obj, sp.Integral):
            # Handle integrals
            try:
                result = obj.doit()
                original_readable = str(obj).replace('**', '^')
                result_readable = str(result).replace('**', '^')

                explanation = self.get_gemini_explanation(
                    original_readable,
                    result_readable,
                    "integration"
                )

                return {
                    'original': str(obj),
                    'integral': str(result),
                    'latex_original': latex(obj),
                    'latex_integral': latex(result),
                    'explanation': explanation
                }
            except Exception as e:
                return {'error': f'Integration failed: {str(e)}', 'original': raw_latex}

        elif isinstance(obj, sp.Limit):
            # Handle limits
            try:
                result = obj.doit()
                original_readable = str(obj).replace('**', '^')
                result_readable = str(result).replace('**', '^')

                explanation = self.get_gemini_explanation(
                    original_readable,
                    result_readable,
                    "limit evaluation"
                )

                return {
                    'original': str(obj),
                    'limit': str(result),
                    'latex_original': latex(obj),
                    'latex_limit': latex(result),
                    'explanation': explanation
                }
            except Exception as e:
                return {'error': f'Limit evaluation failed: {str(e)}', 'original': raw_latex}

        elif isinstance(obj, sp.Derivative):
            # Handle derivatives
            try:
                result = obj.doit()
                original_readable = str(obj).replace('**', '^')
                result_readable = str(result).replace('**', '^')

                explanation = self.get_gemini_explanation(
                    original_readable,
                    result_readable,
                    "differentiation"
                )

                return {
                    'original': str(obj),
                    'derivative': str(result),
                    'latex_original': latex(obj),
                    'latex_derivative': latex(result),
                    'explanation': explanation
                }
            except Exception as e:
                return {'error': f'Differentiation failed: {str(e)}', 'original': raw_latex}

        else:
            # Standard expression - use step-by-step simplification
            return self.step_by_step_simplify(raw_latex)


# Convenience functions for easy use
def create_gemini_engine():
    """Create and return a Gemini engine instance"""
    return GeminiMathsEngineV3()


def simplify_with_explanation(expr):
    """Simplify expression with Gemini explanation"""
    engine = create_gemini_engine()
    return engine.simplify_with_gemini(expr)


def differentiate_with_explanation(expr):
    """Differentiate expression with Gemini explanation"""
    engine = create_gemini_engine()
    return engine.differentiate_with_gemini(expr)


def integrate_with_explanation(expr):
    """Integrate expression with Gemini explanation"""
    engine = create_gemini_engine()
    return engine.integrate_with_gemini(expr)


def solve_with_explanation(equation):
    """Solve equation with Gemini explanation"""
    engine = create_gemini_engine()
    return engine.solve_with_gemini(equation)
