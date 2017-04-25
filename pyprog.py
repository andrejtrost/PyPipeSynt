# -------------------------------------------------------------------------------
# pyprog.py
#
# Classes for Python parser for pipeline synthesis tool
#
# Copyright (C) 2017, Andrej Trost
# License: MIT
# -------------------------------------------------------------------------------
from __future__ import print_function
from math import log


def tab(x): return " "*4*x  # define tab for ident


class Signal:
    no, inport, outport, int = range(4)


class Lit:  # literal superclass
    name = ""
    init = 0
    # mode = 0
    size = 0
    value = 0

    def __init__(self, s):
        self.name = s
        self.tree_level = -1  # data flow tree level, -1 = undefined

    def set_tree_level(self, l):
        self.tree_level = l

    def code(self):
        return str(self.name)

    def emit(self):
        return "Literal"
    

class Var(Lit):
    def __init__(self, s):
        Lit.__init__(self, s)
        self.mode = 0
        self.mode = 0  # set initial value
        self.register = False
        self.reglevel = 0  # or -1 ?

    def settype(self, n):
        self.mode = n

    def setsize(self, n):
        self.size = n

    def code(self):
        return self.name

    def emit(self):
        s = self.name + "("
        if self.mode == Signal.no:
            s += "no, "
        elif self.mode == Signal.inport:
            s += "in, "
        elif self.mode == Signal.outport:
            s += "out,"
        elif self.mode == Signal.int:
            s += "int,"
        else:
            s += "--, "
        s += str(self.size)
        if self.register:
            s += ", R)"
        else:
            s += ")"
        return s


class Num(Lit):
    def __init__(self, s):
        Lit.__init__(self, s)
        self.value = int(s)
        self.size = int(log(abs(self.value), 2)) + 2  # no. of signed bits

    def code(self):
        return str(self.value)

    def emit(self):
        return "(num: "+str(self.value)+","+str(self.size)+" bit)"


class Bool(Lit):
    def __init__(self, s):
        Lit.__init__(self, s)
        if s == "True":
            self.value = 1
        elif s == "False":
            self.value = 0
        else:
            print ("Bool: unknown: "+s)

    def emit(self):
        return "(bool: "+str(self.name)+")"


class Return:
    def __init__(self, v):
        self.varlist = v
        self.instances = False

    def emit(self):
        s = "return "
        first = True
        for v in self.varlist:
            if first:
                s += v.emit()
                first = False
            else:
                s += ", "+v.emit()
        s += "\n"
        return s

    def code(self, level):
        s = tab(level)+"return "
        if self.instances:
            s += "instances()"
        else:
            first = True
            for v in self.varlist:
                if first:
                    s += v.code()
                    first = False
                else:
                    s += ", "+v.code()
        s += "\n"
        return s


class Op:
    def __init__(self, l, o1, r):  # binary operation: left, operator, right
        self.left = l
        self.op = o1
        self.right = r

    def eval(self):
        if isinstance(self.left, Op):
            lv = self.left.eval()
        else:
            lv = self.left.value
        if isinstance(self.right, Op):
            rv = self.right.eval()
        else:
            rv = self.right.value

        return eval(lv + self.op + rv)  # instead of: if self.op == "+": return lv+rv ...
        # if self.op == "+":
        #     return lv + rv
        # elif self.op == "-":
        #     return lv - rv
        # elif self.op == "*":
        #     return lv * rv
        # elif self.op == "==":
        #     return lv == rv
        # elif self.op == "!=":
        #     return lv != rv
        # elif self.op == ">=":
        #     return lv >= rv
        # elif self.op == "<=":
        #     return lv <= rv
        # elif self.op == ">":
        #     return lv > rv
        # elif self.op == "<":
        #     return lv < rv
        # else:
        #     return -1  # unexpected

    def code(self):
        if self.left is None:
            if self.right is None:
                s = " '" + self.op + "' "
            else:
                s = " " + self.op + " "
                if isinstance(self.right, Op):
                    s += "("+self.right.code()+")"
                else:
                    s += self.right.code()
        elif self.right is None:
            if isinstance(self.left, Op):
                s = "("+self.left.code()+") "
            else:
                s = self.left.code()+" "
        else:
            if isinstance(self.left, Op):
                s = "("+self.left.code()+") "
            else:
                s = self.left.code()+" "
            s += self.op + " "
            if isinstance(self.right, Op):
                s += "("+self.right.code()+")"
            else:
                s += self.right.code()

        return s

    def emit(self):
        if self.left is None:
            if self.right is None:
                return "OP (load " + self.op + " load) "
            else:
                return "OP (load2 " + self.op + " right: " + self.right.emit() + ") "
        elif self.right is None:
            return "OP (load: " + self.left.emit() + ") "
        else:
            s = "OP (L "
            if isinstance(self.left, Var):
                s += "<V> "
            s += self.left.emit()+" "+self.op+" "
            if isinstance(self.right, Var):
                s += "<V> "
            s += self.right.emit()+") "
            return s


class Assign:
    def __init__(self, t):
        self.target = t
        self.oplist = []        # list of operators in expression (oplist[0] = expression tree root)
        self.cond = 0           # 1 = condition, 2 = else condition
        self.condition = None
        self.clist = []         # condition list, contain tuples (cond, True|False)

        self.nxt = False
        # self.tmp = False  # tmp assignment (comb logic or variable)

    def addop(self, op):
        self.oplist.append(op)

    def eval(self):
        if len(self.oplist) == 1:
            return self.oplist[0].eval()
        else:
            print ("Can't evaluate this.")
            return -1

    def code(self, level):
        s = tab(level) + self.target.code()
        if self.nxt:
            s += ".next = "
        else:
            s += " = "
        if self.oplist[0].op == "signal":
            s += "Signal"
            v = self.target
            if v.size <= 1:
                s += "(bool(" + str(v.init) + "))"
            else:
                s += "(intbv(" + str(v.init) + ", min=-2**" + str(v.size-1)
                s += ", max=2**" + str(v.size-1) + "))"
        else:
            for op in self.oplist:
                s += op.code()
        s += "\n"
        return s

    def emit(self):
        s = "A (target: "+self.target.emit()+"["
        for op in self.oplist:
            s += op.emit()
        s += "] "
        if self.clist:
            for (cond, b) in self.clist:
            #     (cond, b) = self.clist[0]
                s += "?"
                if not b:
                    s += "not "
            # (cond, b) = self.clist[0]
            # if b:
            #     s += "IF "
            # else:
            #     s += "ELSE "
                s += cond.emit()
        # if self.cond > 0:
        #     if self.cond == 1:
        #         s += "IF "
        #     else:
        #         s += "ELSE "
        #     s += self.condition.emit()
        s += ")\n"
        return s


class Condition:
    oplist = []  # operator list

    def __init__(self):
        self.oplist = []

    def addop(self, op):
        self.oplist.append(op)

    def eval(self):
        if len(self.oplist) == 1:
            return self.oplist[0].eval()
        else:
            print ("Can't evaluate this.")
            return -1

    def code(self):
        s = ""
        for op in self.oplist:
            s += op.code()
        return s

    def emit(self):
        s = "COND ["
        for op in self.oplist:
            s += op.emit()
        s += "]"
        return s


class Block:  # block of code, super class
    name = ""

    def __init__(self, name, level=0):
        self.name = name    # name string
        self.body = Body(level)  # body (statements)
        self.vardict = {}   # dictionary of block variables {name : Var}

    def add_to_body(self, st):  # add statement to block body
        self.body.add(st)

    def add_var(self, v):  # add block variable, create dictionary entry
        self.vardict.update({v.name: v})

    def get_var(self, name):  # get existing or create new variable
        if name in self.vardict:  # print ("Var: "+name+" obstaja")
            return self.vardict[name]
        else:
            v = Var(name)  # print ("Var: "+name+" ne obstaja")
            self.vardict.update({name: v})
            return v

    def code(self, level=0):
        return "Code"

    def emit(self):
        s = "Block: "+self.name+"\n"
        for key in self.vardict:
            s += " "+self.vardict[key].emit()
        s += "\n"
        s += self.body.emit()
        s += "\n"
        # s += "Return: "+self.returnvar.emit()+"\n"
        return s
        # return "Block!"


class Body:
    stlist = []
    level = 0

    def __init__(self, level):
        self.stlist = []
        self.level = level

    def add(self, st):
        self.stlist.append(st)

    # def geti(self, i):
    #     return self.stlist[i]
    # def getstatement(self):
    #     i = 0
    #     if i < len(self.stlist)-1:
    #         yield self.stlist[i]
    #         i += 1
    #     else:
    #         yield None

    def insert(self, i, st):
        self.stlist.insert(i, st)

    def code(self):
        s = ""
        for st in self.stlist:
            s += st.code(self.level)
        return s

    def emit(self):
        s = "Body <"+str(self.level)+">: "
        if len(self.stlist) > 0:
            s += "\n"
            for st in self.stlist:
                s += " " + st.emit()
        else:
            s += "()\n"
        return s


class IfElse(Block):
    truebody = True
    cond = Condition()

    def __init__(self, sb):
        Block.__init__(self, "if", sb.body.level+1)
        self.elsbody = None   #
        self.scopeblock = sb  # access upper block to get variable scope
        self.truebody = True

    def elsebody(self, sb):  # add elsbody (level <- sb)
        self.elsbody = Body(sb.body.level+1)
        self.truebody = False

    def add_to_body(self, st):  # add content
        if self.truebody:
            self.body.add(st)
        else:
            self.elsbody.add(st)

    def add_var(self, name, v):  # add block variables to scopeblock
        self.scopeblock.vardict.update({name: v})

    def get_var(self, name):  # check if exists and return

        if name in self.scopeblock.vardict:  #
            return self.scopeblock.vardict[name]
        else:
            v = Var(name)
            self.scopeblock.vardict.update({name: v})
            return v

    def eval(self):
        return self.cond.eval()

    def code(self, level=0):
        s = tab(level) + "if "+self.cond.code()+":\n"
        s += self.body.code()
        if not (self.elsbody is None):
            s += tab(level) + "else:\n"
            s += self.elsbody.code()
        return s

    def emit(self):
        s = "IF " + self.cond.emit()+"\n"
        s += self.body.emit()
        if not (self.elsbody is None):
            s += "ELSE \n"
            s += self.elsbody.emit()
        s += "ENDIF\n"
        return s


class Function(Block):
    def __init__(self, name, sb):
        Block.__init__(self, name, sb.body.level+1)
        self.decorator = ""

    def code(self, level=0):
        s = "\n"
        if self.decorator != "":
            s += tab(level)+self.decorator+"\n"
        s += tab(level) + "def "+self.name+"("
        first = True
        for key in self.vardict:
            if self.vardict[key].mode == Signal.inport:  # inport
                if first:
                    s += self.vardict[key].name
                    first = False
                else:
                    s += ", "+self.vardict[key].name
        for key in self.vardict:
            if self.vardict[key].mode == Signal.outport:  # outport
                if first:
                    s += self.vardict[key].name
                    first = False
                else:
                    s += ", "+self.vardict[key].name
        s += "):\n"
        s += self.body.code()
        s += "\n"
        return s

    def emit(self):
        s = "Def: "+self.name+"\n"
        for key in self.vardict:
            s += " "+self.vardict[key].emit()
        s += "\n"
        s += self.body.emit()
        s += "\n"
        # s += "Return: "+self.returnvar.emit()+"\n"
        return s


class PyProg(Block):

    def code(self, level=0):
        s = self.body.code()
        return s

    def emit(self):
        s = "Program: "+self.name+"\n"
        for key in self.vardict:
            s += " "+self.vardict[key].emit()
        s += "\n"
        s += self.body.emit()
        s += "End"
        return s
