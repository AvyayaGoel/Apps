import math
from tkinter import *
from tkinter import messagebox as mb


class Calculator:
    def __init__(self, root):
        self.root = root
        self.root.title("Calculator_V2.12")
        self.root.iconbitmap(r"python\codes\Calculators\Calculator icon.ico")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.expression = ""
        self.total = ""

        self.frame = Frame(self.root)
        self.frame.grid(column=0, row=0, sticky="nsew")
        self.w, self.l = 6, 2
        self.buttons = [
            ('C', 0, 1), ('←', 1, 1), ('%', 2, 1), ('/', 3, 1), ('(', 4, 1), (')', 5, 1),
            ('7', 0, 2), ('8', 1, 2), ('9', 2, 2), ('*', 3, 2), ('√', 4, 2), ('x²', 5, 2),
            ('4', 0, 3), ('5', 1, 3), ('6', 2, 3), ('-', 3, 3), ('π', 4, 3), ('e', 5, 3),
            ('1', 0, 4), ('2', 1, 4), ('3', 2, 4), ('+', 3, 4), ('ln', 4, 4), ('!', 5, 4),
            ('00', 0, 5), ('0', 1, 5), ('.', 2, 5), ('=', 3, 5), ('^', 4, 5), ('Sc', 5, 5)
        ]

        # Automatically configure columns and rows
        max_col = max(button[1] for button in self.buttons) + 1
        max_row = max(button[2] for button in self.buttons) + 1

        for i in range(max_col):
            self.frame.columnconfigure(i, weight=1)
        for i in range(max_row):
            self.frame.rowconfigure(i, weight=1)

        self.e1 = Entry(self.frame, text="0", font=100)
        self.e1.grid(column=0, row=0, columnspan=6, sticky="nsew")

        for (text, col, row) in self.buttons:
            if text == '=':
                Button(self.frame, text=text, font=100, command=self.eq, width=self.w, height=self.l).grid(column=col,
                                                                                                           row=row,
                                                                                                           sticky="nsew")
            elif text == 'C':
                Button(self.frame, text=text, font=100, command=self.clear, width=self.w, height=self.l).grid(
                    column=col, row=row, sticky="nsew")
            elif text == '←':
                Button(self.frame, text=text, font=100, command=self.backspace, width=self.w, height=self.l).grid(
                    column=col, row=row, sticky="nsew")
            elif text == 'x²':
                Button(self.frame, text=text, font=100, command=lambda: self.num_changer('²'), width=self.w,
                       height=self.l).grid(column=col, row=row, sticky="nsew")
            elif text == '!':
                Button(self.frame, text=text, font=100, command=self.factorial, width=self.w, height=self.l).grid(
                    column=col, row=row, sticky="nsew")
            elif text == 'π':
                Button(self.frame, text=text, font=100, command=self.insert_pi, width=self.w, height=self.l).grid(
                    column=col, row=row, sticky="nsew")
            elif text == 'e':
                Button(self.frame, text=text, font=100, command=self.insert_e, width=self.w, height=self.l).grid(
                    column=col, row=row, sticky="nsew")
            elif text == '√':
                Button(self.frame, text=text, font=100, command=self.square_root, width=self.w, height=self.l).grid(
                    column=col, row=row, sticky="nsew")
            elif text == 'ln':
                Button(self.frame, text=text, font=100, command=self.ln, width=self.w, height=self.l).grid(column=col,
                                                                                                           row=row,
                                                                                                           sticky="nsew")
            elif text == 'Sc':
                Button(self.frame, text=text, font=100, command=self.scientific, width=self.w, height=self.l).grid(
                    column=col, row=row, sticky="nsew")
            else:
                Button(self.frame, text=text, font=100, command=lambda t=text: self.num_changer(t), width=self.w,
                       height=self.l).grid(column=col, row=row, sticky="nsew")
        self.root.bind("<Return>", self.eq_event)
        self.root.bind("=", self.eq_event)
        self.root.bind("<Escape>", self.clear_event)

    def num_changer(self, x):
        self.expression = self.e1.get()
        self.expression = self.expression.replace('=', '')
        self.expression += str(x)
        self.e1.delete(0, END)
        self.e1.insert(0, self.expression)

    def replacer(self):
        self.expression = self.e1.get()
        self.expression = self.expression.replace('^', '**')
        self.expression = self.expression.replace('²', '**2')
        self.expression = self.expression.replace('%', '/100')
        self.expression = self.expression.replace('=', '')
        self.e1.delete(0, END)
        self.e1.insert(0, self.expression)

    def clear(self):
        self.expression = self.e1.get()
        self.expression = ""
        self.e1.delete(0, END)

    def clear_event(self, event):
        self.clear()

    def backspace(self):
        self.expression = self.e1.get()
        self.expression = self.expression.replace('=', '')
        self.expression = self.expression[:-1]
        self.e1.delete(0, END)
        self.e1.insert(0, self.expression)

    def scientific(self):
        try:
            self.expression = self.e1.get()
            self.expression = self.expression.replace('=', '')
            self.result = "{:.2e}".format(eval(self.expression))
            self.e1.delete(0, END)
            self.e1.insert(0, self.result)
            self.expression = str(self.result)
        except Exception as e:
            mb.showerror(title="Error", message=f"Error encountered: {e}")
            self.expression = ""
            self.e1.delete(0, END)

    def eq(self):
        try:
            self.replacer()
            self.result = eval(self.expression)
            self.e1.delete(0, END)
            self.e1.insert(0, "=" + str(self.result))
            self.expression = str(self.result)
        except Exception as e:
            mb.showerror(title="Error", message=f"Error encountered: {e}")
            self.clear()

    def eq_event(self, event):
        self.eq()

    def square_root(self):
        try:
            self.replacer()
            self.result = math.sqrt(eval(self.expression))
            self.e1.delete(0, END)
            self.e1.insert(0, "=" + str(self.result))
            self.expression = str(self.result)
        except Exception as e:
            mb.showerror(title="Error", message=f"Error encountered: {e}")
            self.clear()

    def factorial(self):
        try:
            self.replacer()
            self.result = math.factorial(int(eval(self.expression)))
            self.e1.delete(0, END)
            self.e1.insert(0, "=" + str(self.result))
            self.expression = str(self.result)
        except Exception as e:
            mb.showerror(title="Error", message=f"Error encountered: {e}")
            self.clear()

    def insert_pi(self):
        self.expression += str(math.pi)
        self.e1.delete(0, END)
        self.e1.insert(0, self.expression)

    def insert_e(self):
        self.expression += str(math.e)
        self.e1.delete(0, END)
        self.e1.insert(0, self.expression)

    def ln(self):
        try:
            self.replacer()
            self.result = math.log(eval(self.expression))
            self.e1.delete(0, END)
            self.e1.insert(0, "=" + str(self.result))
            self.expression = str(self.result)
        except Exception as e:
            mb.showerror(title="Error", message=f"Error encountered: {e}")
            self.clear()


if __name__ == "__main__":
    root = Tk()
    calc = Calculator(root)
    root.mainloop()
