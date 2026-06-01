from tkinter import *
from tkinter import messagebox as mb

calc = Tk()
calc.title("Calculator_V2.11")
# calc.iconbitmap(r"python\codes\Calculators\Calcutaor.co")
calc.columnconfigure(0, weight=1)
calc.rowconfigure(0, weight=1)
sum = 0
total = ""
expression = ""
l = 2
w = 6
frame = Frame(calc)
frame.grid(column=0, row=0, sticky="nsew")
frame.columnconfigure(0, weight=1)
frame.columnconfigure(1, weight=1)
frame.columnconfigure(2, weight=1)
frame.columnconfigure(3, weight=1)
frame.columnconfigure(4, weight=1)
frame.columnconfigure(5, weight=1)
frame.columnconfigure(6, weight=1)
frame.rowconfigure(0, weight=1)
frame.rowconfigure(1, weight=1)
frame.rowconfigure(2, weight=1)
frame.rowconfigure(3, weight=1)
frame.rowconfigure(4, weight=1)
frame.rowconfigure(5, weight=1)


def num_changer(x):
    global expression
    expression = expression + str(x)
    e1.delete(0, END)
    e1.insert(0, expression)


def clear():
    global expression
    global sum
    sum = ""
    expression = ""
    e1.delete(0, END)


def backspace():
    global expression
    global sum
    expression = expression[:-1]
    e1.delete(0, END)
    e1.insert(0, expression)


def eq():
    global sum
    global expression
    global total
    expression = e1.get()
    try:
        sum = eval(expression)
    except:
        mb.showerror(title="Error", message="Error encountered", command=clear())
    e1.delete(0, END)
    e1.insert(0, "=" + str(sum))
    expression = str(sum)
    sum = ""


e1 = Entry(frame, text="0", font=100)
e1.grid(column=1, row=0, columnspan=5, sticky="nsew")
b1 = Button(frame, text="1", font=100, command=lambda: num_changer(1), width=w, height=l)
b1.grid(column=1, row=2, sticky="nsew")
b2 = Button(frame, text="2", font=100, command=lambda: num_changer(2), width=w, height=l)
b2.grid(column=2, row=2, sticky="nsew")
b3 = Button(frame, text="3", font=100, command=lambda: num_changer(3), width=w, height=l)
b3.grid(column=3, row=2, sticky="nsew")
b4 = Button(frame, text="4", font=100, command=lambda: num_changer(4), width=w, height=l)
b4.grid(column=1, row=3, sticky="nsew")
b5 = Button(frame, text="5", font=100, command=lambda: num_changer(5), width=w, height=l)
b5.grid(column=2, row=3, sticky="nsew")
b6 = Button(frame, text="6", font=100, command=lambda: num_changer(6), width=w, height=l)
b6.grid(column=3, row=3, sticky="nsew")
b7 = Button(frame, text="7", font=100, command=lambda: num_changer(7), width=w, height=l)
b7.grid(column=1, row=4, sticky="nsew")
b8 = Button(frame, text="8", font=100, command=lambda: num_changer(8), width=w, height=l)
b8.grid(column=2, row=4, sticky="nsew")
b9 = Button(frame, text="9", font=100, command=lambda: num_changer(9), width=w, height=l)
b9.grid(column=3, row=4, sticky="nsew")
b0 = Button(frame, text="0", font=100, command=lambda: num_changer(0), width=w, height=l)
b0.grid(column=2, row=5, sticky="nsew")
bac = Button(frame, text="←", font=100, width=w, height=l, command=lambda: backspace())
bac.grid(column=3, row=1, sticky="nsew")
badd = Button(frame, text="+", font=100, width=w, height=l, command=lambda: num_changer("+"))
badd.grid(column=4, row=4, sticky="nsew")
bmin = Button(frame, text="-", font=100, width=w, height=l, command=lambda: num_changer("-"))
bmin.grid(column=4, row=3, sticky="nsew")
bmul = Button(frame, text="x", font=100, width=w, height=l, command=lambda: num_changer("*"))
bmul.grid(column=4, row=2, sticky="nsew")
bdiv = Button(frame, text="/", font=100, width=w, height=l, command=lambda: num_changer("/"))
bdiv.grid(column=4, row=1, sticky="nsew")
bdec = Button(frame, text=".", font=100, width=w, height=l, command=lambda: num_changer("."))
bdec.grid(column=3, row=5, sticky="nsew")
bback = Button(frame, text="C", font=100, width=w, height=l, command=lambda: clear())
bback.grid(column=2, row=1, sticky="nsew")
b = Button(frame, text="%", font=100, width=w, height=l, command=lambda: num_changer("/100"))
b.grid(column=1, row=1, sticky="nsew")
bcbo = Button(frame, text="(", font=100, width=w, height=l, command=lambda: num_changer("("))
bcbo.grid(column=5, row=1, sticky="nsew")
bcbc = Button(frame, text=")", font=100, width=w, height=l, command=lambda: num_changer(")"))
bcbc.grid(column=5, row=2, sticky="nsew")
bcsq = Button(frame, text="x²", font=100, width=w, height=l, command=lambda: num_changer("**2"))
bcsq.grid(column=5, row=3, sticky="nsew")
bcrt = Button(frame, text="√x", font=100, width=w, height=l, command=lambda: num_changer("**0.5"))
bcrt.grid(column=5, row=4, sticky="nsew")
beq = Button(frame, text="=", font=100, width=w, height=l, command=lambda: eq())
beq.grid(column=4, row=5, sticky="nsew")
bcbc = Button(frame, text="", font=100, width=w, height=l, command=lambda: num_changer(""))
bcbc.grid(column=5, row=5, sticky="nsew")
beq = Button(frame, text="00", font=100, width=w, height=l, command=lambda: num_changer("00"))
beq.grid(column=1, row=5, sticky="nsew")
calc.mainloop()
