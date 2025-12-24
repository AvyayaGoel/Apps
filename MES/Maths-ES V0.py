import re

# Operator precedence
value_order = {
    '+': 1,
    '-': 1,
    '*': 2,
    '/': 2,
    '**': 3,
    '^': 3
}

# ─────────────────────────────────────────────
# Tokenizer
# ─────────────────────────────────────────────
def tokenize(expr):
    return re.findall(r'\d+\.?\d*|\*\*|[+\-*/()^]', expr.replace(" ", ""))


# ─────────────────────────────────────────────
# AST Node
# ─────────────────────────────────────────────
class Node:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right

    def is_number(self):
        return self.left is None and self.right is None

    def to_string(self):
        if self.is_number():
            return self.value

        l = self.left.to_string()
        r = self.right.to_string()

        # Parentheses only when needed
        if (not self.left.is_number() and
            value_order[self.left.value] < value_order[self.value]):
            l = f"({l})"

        if (not self.right.is_number() and
            value_order[self.right.value] < value_order[self.value]):
            r = f"({r})"

        return f"{l}{self.value}{r}"


# ─────────────────────────────────────────────
# Shunting Yard: Infix → Postfix
# ─────────────────────────────────────────────
def infix_to_postfix(tokens):
    output = []
    ops = []

    for t in tokens:
        if t.replace('.', '', 1).isdigit():
            output.append(t)
        elif t in value_order:
            while (ops and ops[-1] in value_order and
                   ((value_order[ops[-1]] > value_order[t]) or
                    (value_order[ops[-1]] == value_order[t] and t not in ('**', '^')))):
                output.append(ops.pop())
            ops.append(t)
        elif t == '(':
            ops.append(t)
        elif t == ')':
            while ops and ops[-1] != '(':
                output.append(ops.pop())
            ops.pop()

    while ops:
        output.append(ops.pop())

    return output


# ─────────────────────────────────────────────
# Postfix → AST
# ─────────────────────────────────────────────
def postfix_to_ast(postfix):
    stack = []

    for t in postfix:
        if t.replace('.', '', 1).isdigit():
            stack.append(Node(t))
        else:
            b = stack.pop()
            a = stack.pop()
            stack.append(Node(t, a, b))

    return stack[0]


# ─────────────────────────────────────────────
# One-step reduction (bottom-up)
# ─────────────────────────────────────────────
def reduce_one_step(node):
    if node.is_number():
        return False

    # If both children are numbers, collapse this node
    if node.left.is_number() and node.right.is_number():
        a = float(node.left.value)
        b = float(node.right.value)

        if node.value == '+': res = a + b
        elif node.value == '-': res = a - b
        elif node.value == '*': res = a * b
        elif node.value == '/': res = a / b
        elif node.value in ('**','^'): res = a ** b

        node.value = f"{res:.3f}".rstrip('0').rstrip('.')
        node.left = None
        node.right = None
        return True

    # Otherwise, go deeper (left first = natural order)
    return reduce_one_step(node.left) or reduce_one_step(node.right)


# ─────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────
expr = input("Enter expression: ")

tokens = tokenize(expr)
postfix = infix_to_postfix(tokens)
ast_root = postfix_to_ast(postfix)

print("\n--- Step-by-step ---")
print(f"Step 0: {ast_root.to_string()}")

n=1
while ast_root.left or ast_root.right:
    reduce_one_step(ast_root)
    print(f"Step {n}: {ast_root.to_string()}")
    n+=1

print("\nFinal Answer:", ast_root.value)
