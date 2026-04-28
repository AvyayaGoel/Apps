"""
Maths-ES V1.2.0 - PyQt6 Professional Version
Fixed all critical runtime errors and architectural issues
"""

import json
import os
import re
import sys

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QPalette, QColor
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton
)

from Maths_Engine_Gemini_V3 import GeminiMathsEngineV3
from latex_keypad_manager import LaTeXKeypadManager

# Dark theme colors
DARK_BG = "#2b2b2b"
DARKER_BG = "#1e1e1e"
LIGHT_TEXT = "#ffffff"
DARK_TEXT = "#cccccc"
ACCENT_COLOR = "#007acc"
SUCCESS_COLOR = "#28a745"
ERROR_COLOR = "#dc3545"
WARNING_COLOR = "#ffc107"
LATEX_COLOR = "#4ec9b0"
VARIABLE_COLOR = "#4ec9b0"
OPERATOR_COLOR = "#dcdcaa"
NUMBER_COLOR = "#b5cea8"
EXPLANATION = "Explanation:"
GEMINI_404_MSG = "Gemini engine not available"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

mq_js_path = QUrl.fromLocalFile(os.path.join(BASE_DIR, "mathquill.js")).toString()
mq_css_path = QUrl.fromLocalFile(os.path.join(BASE_DIR, "mathquill.css")).toString()

MATHQUILL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">

<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/mathquill@0.10.1/build/mathquill.css">
<script src="https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mathquill@0.10.1/build/mathquill.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<style>
html, body {
    background-color: #2b2b2b;
    color: white;
    margin: 3px;
    font-size: 22px;
}

#editor {
    border: 1px solid #007acc;
    padding: 10px;
    min-height: 30px;
    border-radius: 6px;
    background-color: #1e1e1e;
}
</style>
</head>

<body>
<div id="editor"></div>

<script>
new QWebChannel(qt.webChannelTransport, function(channel) {
    window.backend = channel.objects.backend;
});
(function() {

    if (typeof MathQuill === "undefined") {
        document.body.innerHTML = "<h2 style='color:red'>MathQuill failed to load</h2>";
        return;
    }

    var MQ = MathQuill.getInterface(2);
    var editor = document.getElementById('editor');
    
    window.mathField = MQ.MathField(editor, {
        spaceBehavesLikeTab: true,
        handlers: {
            edit: function() {
                if (window.backend) {
                    window.backend.expressionChanged(window.mathField.latex());
                }
            }
        }
    });
    editor.focus();
})();
</script>

</body>
</html>
"""
# KaTeX HTML template - REMOVED AUTO-RENDER
KATEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>LaTeX Renderer</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" integrity="sha384-n8MVd4RsNIU0KOVEMeaKrumfonJpasSUgnkYtGIYLpAkH5EVWNeDNJg8vVqYk7yM" crossorigin="anonymous">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js" integrity="sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1YQqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8" crossorigin="anonymous"></script>
    <style>
        body {{
            background-color: #1e1e1e;
            color: #ffffff;
            font-family: 'Times New Roman', serif;
            font-size: 16px;
            margin: 0;
            padding: 10px;
            overflow-x: auto;
        }}
               

        .katex-display {{
            margin: 0.5em 0;
        }}
        .step {{
            color: #4ec9b0; /* Nice cyan/teal for steps */
            font-family: 'Consolas', monospace;
            margin-top: 25px;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .explanation {{
            color: #cccccc;
            font-style: italic;
            margin: 10px 0;
            line-height: 1.5;
            font-size: 15px;
        }}
        .result {{
            color: #28a745;
            margin: 15px 0;
            padding-left: 10px;
            border-left: 3px solid #28a745;
        }}
        .katex {{
            color: inherit !important;
            font-size: 1.1em;
        }}
        .error {{
            color: #dc3545;
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <div id="math-content">{content}</div>
</body>
</html>
"""


class MathBridge(QObject):
    expressionChangedSignal = pyqtSignal(str)

    @pyqtSlot(str)
    def expressionChanged(self, latex):
        self.expressionChangedSignal.emit(latex)


class MathQuillInputWidget(QWebEngineView):
    expression_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.bridge = MathBridge()
        self.bridge.expressionChangedSignal.connect(self._store_expr)

        self.channel = QWebChannel()
        self.channel.registerObject("backend", self.bridge)
        self.page().setWebChannel(self.channel)

        self._last_expr = ""

        # IMPORTANT: wait for loadFinished
        self.loadFinished.connect(self._on_load_finished)

        self.setHtml(MATHQUILL_TEMPLATE, QUrl("https://localhost/"))

        self.setMinimumHeight(30)

    @staticmethod
    def _on_load_finished():
        print("MathQuill page loaded")

    def _store_expr(self, expr):
        self._last_expr = expr
        self.expression_changed.emit(expr)

    def get_expression(self):
        return self._last_expr

    def clear(self):
        self.page().runJavaScript("if (typeof mathField !== 'undefined') mathField.latex('');")


class KaTeXOutputWidget(QWebEngineView):
    """KaTeX-based LaTeX output widget for solutions - 2026 Standard"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QWebEngineView {{
                border: 1px solid {ACCENT_COLOR};
                background-color: {DARKER_BG};
            }}
        """)

        # Initialize with container
        self.setHtml(KATEX_TEMPLATE.format(content=''))

    def render_solution_steps(self, steps):
        steps_json = json.dumps(steps)
        js_code = f"""
        (function() {{
            console.log("JS EXECUTED");

            const steps = {steps_json};
            const container = document.getElementById('math-content');
            container.innerHTML = '';

            steps.forEach(step => {{
                const div = document.createElement('div');
                div.className = step.type;

                if (step.type === 'result') {{
                    const span = document.createElement("span");
                    katex.render(step.content, span, {{
                        throwOnError: true,
                        displayMode: false,
                        output: "mathml"
                    }});
                    div.appendChild(span);
                }} else {{
                    div.textContent = step.content;
                }}

                container.appendChild(div);
            }});
        }})();
        """
        self.page().runJavaScript(js_code)

    def clear(self):
        """Clear the widget"""
        self.page().runJavaScript("document.getElementById('math-content').innerHTML = '';")

    def render_latex(self, latex_content):
        """Render a single LaTeX expression"""
        steps = [{'type': 'result', 'content': latex_content}]
        self.render_solution_steps(steps)


class MesPyQt6Professional(QMainWindow):
    """Professional PyQt6 application with QScintilla + KaTeX"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Maths Ex Solver V2.0 - Gemini+Sympy Professional")
        self.setGeometry(100, 100, 1100, 640)

        # Initialize variables
        self.output_widget = None
        self.evaluate_btn = None
        self.clear_btn = None
        self.math_input = None
        self.keypad_manager = None
        self.keypad_btn = None

        # Initialize Gemini Engine V3
        try:
            self.gemini_engine = GeminiMathsEngineV3()
            print("✓ Gemini V3 engine initialized successfully!")
        except Exception as e:
            print(f"Error initializing Gemini V3 engine: {e}")
            print("Please edit gemini_config.py with your API key")
            self.gemini_engine = None

        self.setup_ui()
        self.setup_styles()

    def setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Mathematical Expression Solver - Professional Version")
        title.setFont(QFont("Courier New", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {LIGHT_TEXT}; padding: 10px;")
        main_layout.addWidget(title)

        # Input area
        input_label = QLabel("Input:")
        input_label.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        input_label.setStyleSheet(f"color: {LIGHT_TEXT}; margin-bottom: 5px;")
        main_layout.addWidget(input_label)

        self.math_input = MathQuillInputWidget()
        self.math_input.expression_changed.connect(self.on_expression_changed)
        main_layout.addWidget(self.math_input)

        # Buttons
        button_frame = QHBoxLayout()

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setFont(QFont("Consolas", 12))
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ERROR_COLOR};
                color: {LIGHT_TEXT};
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #c82333;
            }}
        """)
        self.clear_btn.clicked.connect(self.clear_fields)

        self.evaluate_btn = QPushButton("Evaluate")
        self.evaluate_btn.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        self.evaluate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SUCCESS_COLOR};
                color: {LIGHT_TEXT};
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #218838;
            }}
        """)
        self.evaluate_btn.clicked.connect(self.evaluate)

        # LaTeX Keypad Button
        self.keypad_btn = QPushButton("🧮 Symbols")
        self.keypad_btn.setFont(QFont("Consolas", 12))
        self.keypad_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_COLOR};
                color: {LIGHT_TEXT};
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #005a9e;
            }}
        """)
        self.keypad_btn.clicked.connect(self.toggle_keypad)

        button_frame.addWidget(self.clear_btn)
        button_frame.addWidget(self.keypad_btn)
        button_frame.addWidget(self.evaluate_btn)
        button_frame.addStretch()
        main_layout.addLayout(button_frame)

        # Output area with KaTeX
        output_label = QLabel("Output:")
        output_label.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        output_label.setStyleSheet(f"color: {LIGHT_TEXT}; margin: 20px 0 5px 0;")
        main_layout.addWidget(output_label)

        # Create KaTeX output widget
        self.output_widget = KaTeXOutputWidget()
        self.output_widget.setMinimumHeight(250)
        main_layout.addWidget(self.output_widget)

    def setup_styles(self):
        """Setup additional styles"""
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {DARK_BG};
            }}
            QWidget {{
                background-color: {DARK_BG};
                color: {LIGHT_TEXT};
            }}
        """)

    def on_expression_changed(self, expr):
        self.math_input._last_expr = expr

    def clear_fields(self):
        """Clear all fields"""
        self.math_input.clear()
        self.output_widget.clear()

    def toggle_keypad(self):
        """Toggle LaTeX keypad window"""
        if self.keypad_manager is None:
            # Initialize keypad manager on first use
            self.keypad_manager = LaTeXKeypadManager(self, self.math_input)

        self.keypad_manager.toggle_keypad(self.keypad_btn)

    def evaluate(self):
        """Evaluate the mathematical expression"""
        expr = self.math_input.get_expression().strip()
        if not expr:
            return

        # Input validation - allow LaTeX characters but require at least one number or constant
        # Allow letters, numbers, math symbols, LaTeX commands, and common constants
        print(expr)
        if not re.search(r'[0-9a-zA-Z]', expr) and not re.search(r'\\[a-zA-Z]+', expr):
            self._show_error("❌ Expression must contain at least one number, variable")
            return

        # Allow LaTeX commands, basic math operators, and common characters
        # This focuses on LaTeX syntax rather than Unicode symbols
        if not re.fullmatch(r"^[0-9a-zA-Z+\-*/^()=.,\s\\{}_\[\]<>!@#$%&|~?]+$", expr):
            self._show_error(f"❌ Invalid characters in expression: {expr}")
            return

        # Clear previous output
        self.output_widget.clear()

        try:
            # Use smart router that understands SymPy object types
            if not self.gemini_engine:
                self._show_error(GEMINI_404_MSG)
                return

            result = self.gemini_engine.smart_router(expr)
            self._handle_smart_router_result(result)

        except Exception as e:
            self._handle_evaluation_error(expr, e)

    def _evaluate_equation(self, expr):
        """Handle equation evaluation with Gemini V3"""
        if not self.gemini_engine:
            self._show_error(GEMINI_404_MSG)
            return

        try:
            result = self.gemini_engine.solve_with_gemini(expr)
            if 'error' in result:
                self._show_error(f"Error: {result['error']}")
                return
            print(result)
            # Build solution content with Gemini explanations
            solution_steps = [
                {'type': 'step', 'content': "Original equation:"},
                {'type': 'result', 'content': result['latex_original']},
                {'type': 'explanation', 'content': result['explanation']},
                {'type': 'step', 'content': "Solutions:"}
            ]

            # Add each solution as a separate step
            for i, (sol, latex_sol) in enumerate(zip(result['solutions'], result['latex_solutions'])):
                solution_steps.append({'type': 'result', 'content': latex_sol})

            self.output_widget.render_solution_steps(solution_steps)

        except Exception as e:
            self._show_error(f"Error solving equation: {e}")

    def _evaluate_expression(self, expr):
        """Handle regular expression evaluation with Gemini V3"""
        if not self.gemini_engine:
            self._show_error(GEMINI_404_MSG)
            return

        try:
            # Get step-by-step simplification with Gemini explanations
            steps = self.gemini_engine.step_by_step_simplify(expr, max_steps=5)
            print(steps)
            if not steps:
                self._show_error("No simplification steps found")
                return

            # Build solution content
            solution_steps = []
            for step in steps:
                solution_steps.append({'type': 'step', 'content': f"Step {step['step']}"})
                solution_steps.append({'type': 'result', 'content': step['latex_original']})
                solution_steps.append({'type': 'explanation', 'content': step['explanation']})
                solution_steps.append({'type': 'result', 'content': step['latex_simplified']})

            self.output_widget.render_solution_steps(solution_steps)

        except Exception as e:
            self._show_error(f"Error evaluating expression: {e}")

    def _handle_smart_router_result(self, result):
        """Handle results from smart router for all mathematical object types"""
        if 'error' in result:
            self._show_error(f"Error: {result['error']}")
            return

        print(result)

        # Check what type of result we have and format accordingly
        if 'solutions' in result:
            # Equation solving result
            self._format_equation_result(result)
        elif 'summation' in result:
            # Summation result
            self._format_summation_result(result)
        elif 'integral' in result:
            # Integral result
            self._format_integral_result(result)
        elif 'limit' in result:
            # Limit result
            self._format_limit_result(result)
        elif 'derivative' in result:
            # Derivative result
            self._format_derivative_result(result)
        elif isinstance(result, list) and len(result) > 0 and 'step' in result[0]:
            # Step-by-step simplification result
            self._format_steps_result(result)
        else:
            # Generic result
            self._format_generic_result(result)

    def _format_equation_result(self, result):
        """Format equation solving results"""
        solution_steps = [
            {'type': 'step', 'content': "Original equation:"},
            {'type': 'result', 'content': result['latex_original']},
            {'type': 'step', 'content': "Solutions:"}
        ]

        for i, sol in enumerate(result['solutions'], 1):
            solution_steps.append({
                'type': 'result',
                'content': result['latex_solutions'][i - 1]
            })

        solution_steps.append({'type': 'step', 'content': EXPLANATION})
        solution_steps.append({'type': 'explanation', 'content': result['explanation']})

        self.output_widget.render_solution_steps(solution_steps)

    def _format_summation_result(self, result):
        """Format summation results"""
        solution_steps = [
            {'type': 'step', 'content': "Original summation:"},
            {'type': 'result', 'content': result['latex_original']},
            {'type': 'step', 'content': "Evaluated sum:"},
            {'type': 'result', 'content': result['latex_summation']},
            {'type': 'step', 'content': EXPLANATION},
            {'type': 'explanation', 'content': result['explanation']}
        ]

        self.output_widget.render_solution_steps(solution_steps)

    def _format_integral_result(self, result):
        """Format integral results"""
        solution_steps = [
            {'type': 'step', 'content': "Original integral:"},
            {'type': 'result', 'content': result['latex_original']},
            {'type': 'step', 'content': "Integrated result:"},
            {'type': 'result', 'content': result['latex_integral']},
            {'type': 'step', 'content': EXPLANATION},
            {'type': 'explanation', 'content': result['explanation']}
        ]

        self.output_widget.render_solution_steps(solution_steps)

    def _format_limit_result(self, result):
        """Format limit results"""
        solution_steps = [
            {'type': 'step', 'content': "Original limit:"},
            {'type': 'result', 'content': result['latex_original']},
            {'type': 'step', 'content': "Limit value:"},
            {'type': 'result', 'content': result['latex_limit']},
            {'type': 'step', 'content': EXPLANATION},
            {'type': 'explanation', 'content': result['explanation']}
        ]

        self.output_widget.render_solution_steps(solution_steps)

    def _format_derivative_result(self, result):
        """Format derivative results"""
        solution_steps = [
            {'type': 'step', 'content': "Original derivative:"},
            {'type': 'result', 'content': result['latex_original']},
            {'type': 'step', 'content': "Differentiated result:"},
            {'type': 'result', 'content': result['latex_derivative']},
            {'type': 'step', 'content': EXPLANATION},
            {'type': 'explanation', 'content': result['explanation']}
        ]

        self.output_widget.render_solution_steps(solution_steps)

    def _format_steps_result(self, result):
        """Format step-by-step simplification results"""
        solution_steps = []
        for step in result:
            solution_steps.append({'type': 'step', 'content': f"Step {step['step']}:"})
            solution_steps.append({'type': 'result', 'content': step['latex_original']})
            solution_steps.append({'type': 'result', 'content': step['latex_simplified']})
            solution_steps.append({'type': 'explanation', 'content': step['explanation']})

        self.output_widget.render_solution_steps(solution_steps)

    def _format_generic_result(self, result):
        """Format generic results"""
        solution_steps = [
            {'type': 'step', 'content': "Result:"},
            {'type': 'result', 'content': str(result.get('result', result))}
        ]

        self.output_widget.render_solution_steps(solution_steps)

    def _show_error(self, message):
        """Show error message"""
        self.output_widget.render_solution_steps([{
            'type': 'error',
            'content': message
        }])

    def _handle_evaluation_error(self, expr, e):
        """Handle evaluation errors"""
        self._show_error(f"Error processing expression: {expr} - {str(e)}")


def main():
    app = QApplication(sys.argv)

    # Apply dark theme
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(DARK_BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(LIGHT_TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(DARKER_BG))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#3c3c3c"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(LIGHT_TEXT))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(DARK_BG))
    palette.setColor(QPalette.ColorRole.Text, QColor(LIGHT_TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor("#3c3c3c"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(LIGHT_TEXT))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(LIGHT_TEXT))
    palette.setColor(QPalette.ColorRole.Link, QColor(ACCENT_COLOR))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT_COLOR))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(LIGHT_TEXT))

    app.setPalette(palette)

    window = MesPyQt6Professional()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
