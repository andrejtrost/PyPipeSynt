# coding=utf-8
# -------------------------------------------------------------------------------
# par.py
#
# Python (limited syntax) parser for pipeline synthesis tool
#
# Copyright (C) 2017, Andrej Trost
# License: MIT
# -------------------------------------------------------------------------------
from __future__ import print_function
from sys import exit
from pyprog import *

debug = False


class Stack:
    def __init__(self, a):
        self.a = a
        self.num = 1
        self.left = None
        self.right = None

    def pop(self):
        if self.num == 0:  # special for unary op
            if self.right is None:
                # print ("1")
                self.right = self.a.oplist.pop()
        elif self.num == 1:
            if self.right is None:
                # print ("1")
                self.right = self.a.oplist.pop()
            if self.left is None:
                # print ("2")
                self.left = self.a.oplist.pop()
        else:
            # print ("3")
            if self.right is None:
                # print ("4")
                self.right = self.a.oplist.pop()
            self.left = self.a.oplist.pop()


class Par:
    name = ""
    level = 0

    src = " "
    slen = 1  # used by scan
    send = False
    si = 0
    sline = 1   # line for error report

    ident = 0
    Token = ''
    TokenStr = ""
    Look = 'n'
    LookStr = ""

    def __init__(self):
        print ("Parse ", end="")

    def error(self, s):
        print("Line " + str(self.sline) + " Error: " + s)
        exit()

    def match(self, s):
        self.scan()
        if s == 'v':
            if self.Token == 'a' or self.Token == '1':
                return True
        elif self.TokenStr == s:
            return True
        else:
            self.error("Expected " + s + " Got " + self.TokenStr)

    def scan(self):  # skeniraj token in konzumiraj presledke
        """

        :return:
        splošen izhod: 'n', 'a', '1',
        rezervirane besede: def: 'd', return: 'r'
        """
        s = ""
        self.Token = self.Look
        self.TokenStr = self.LookStr
        if not self.si < self.slen - 1:
            self.send = True
            return

        c = self.src[self.si]  # c vsebuje trenutni znak

        if self.Token == 'n':  # skeniraj novo vrstico
            self.ident = 0  # resetiraj ident

            if self.src[self.si] == ' ':  # spusti presledke
                while self.src[self.si] == ' ' and self.si < self.slen - 1:
                    self.si += 1
                    self.ident += 1

            if debug:
                print("Newline " + str(self.ident))

            if not self.si < self.slen - 1:
                self.send = True
                return

            c = self.src[self.si]

        if c == '\n':  # beri \n
            self.Look = 'n'
            self.LookStr = 'n'
            self.si += 1  # pojdi na naslednji znak in ne spusti presledkov
            self.sline += 1
            return

        elif c.isdigit():  # beri število
            while self.src[self.si].isdigit() and self.si < self.slen:
                s += self.src[self.si]
                self.si += 1
            self.Look = '1'
            self.LookStr = s

        elif c.isalpha():  # beri znake
            while (self.src[self.si].isalpha() or self.src[self.si].isdigit()) and self.si < self.slen:
                s += self.src[self.si]
                self.si += 1
            self.Look = 'a'
            self.LookStr = s

            if s == "def":
                self.Look = 'd'
            elif s == "if":
                self.Look = 'i'
            elif s == "else":
                self.Look = 'l'
            elif s == "return":
                self.Look = 'r'
            elif s in ["True", "False"]:
                self.Look = 'b'
            elif s in ["and", "or", "not"]:
                self.Look = 'o'  # Boolean op

        else:
            op = c  # testiraj operatorje
            opn = ""
            if self.si+1 < self.slen - 1:
                opn = self.src[self.si+1]
                if self.src[self.si+1] == "=":  # kombiniran operator ==, !=, >=, <=
                    op += "="

            if op in [">", "<"]:
                if opn == ">":    # operator >>
                    self.Look = "#"
                    self.si += 2
                    self.LookStr = ">>"
                else:
                    self.Look = "c"   # comparison op
                    self.LookStr = op
                    self.si += 1
            elif op in ["==", "!=", ">=", "<="]:
                self.Look = "c"
                self.LookStr = op
                self.si += 2
            else:
                self.Look = c
                self.si += 1
                self.LookStr = self.Look

        if not self.si < self.slen - 1:  # konec?
            self.send = True
            return

        c = self.src[self.si]  # spusti presledke
        if c == ' ':
            while self.src[self.si] == ' ' and self.si < self.slen - 1:  # isspace
                self.si += 1
        if debug:
            print("Scan : " + self.Token + " Look: " + self.Look)

    def comparison(self, block, c):
        s = Stack(c)
        s.left = self.expression(block, c)
        while self.Look == 'c':
            op = self.LookStr
            self.match(op)
            s.right = self.expression(block, c)
            s.pop()

            c.addop(Op(s.left, op, s.right))
            s.num += 1
        if s.num == 1:
            return s.left

        return None

    def boolnot(self, block, c):
        if self.LookStr == "not":
            s = Stack(c)
            s.num = 0  # unary !
            self.match("not")
            s.right = self.comparison(block, c)
            s.pop()
            c.addop(Op(None, 'not', s.right))
            return None
        else:
            return self.comparison(block, c)   # test

    def booland(self, block, c):
        s = Stack(c)
        s.left = self.boolnot(block, c)  # bl = term

        while self.LookStr == 'and':
            self.match('and')
            s.right = self.boolnot(block, c)
            s.pop()

            c.addop(Op(s.left, 'and', s.right))
            s.num += 1

            # if nterm == 1:
            #     c.addop(Op(bl, 'and', br))
            # else:
            #     o1 = c.oplist.pop()
            #     c.addop(Op(o1, 'and', br))
            # nterm += 1

        if s.num == 1:
            return s.left

        return None

    def boolor(self, block, c):
        s = Stack(c)
        s.left = self.booland(block, c)  # operacija & (None) ali term

        while self.LookStr == 'or':
            self.match('or')
            s.right = self.booland(block, c)
            s.pop()

            c.addop(Op(s.left, 'or', s.right))
            s.num += 1

        if s.num == 1 and not (s.left is None):
            c.addop(Op(s.left, '&', None))  # operacija Load
            return s.left
        else:
            return None

    def condition(self, block):  # boolor
        c = Condition()
        self.boolor(block, c)

        return c

    def assignment(self, block):
        v = block.get_var(self.TokenStr)
        a = Assign(v)
        # print ("AS1: "+self.TokenStr)
        self.match('=')
        l = self.expression(block, a)
        if not (l is None):
            a.addop(Op(l, '', None))

        # v.setsize(self.exprsize)  # izraz določa velikost ciljne spremenljvke

        if self.Look == ';':  # ?? kako je s podpičjem
            self.match(';')

        if self.Look == 'n':
            # print ("AS1a: "+self.TokenStr)
            self.match('n')
        else:
            self.error("(A) Expected new line")
        self.scan()
        # print ("AS2: "+self.TokenStr)
        return a

    def factor(self, block, a):
        if self.Look == '(':   # izraz z oklepaji
            # print ("OKL")
            self.match('(')
            self.expression(block, a)
            # print ("ZAK"+self.LookStr)
            self.match(')')
        elif self.Look == 'a':
            self.match('v')
            return block.get_var(self.TokenStr)
        elif self.Look == '1':
            self.match('v')
            return Num(self.TokenStr)
        elif self.Look == 'b':
            self.match('v')
            return Bool(self.TokenStr)

    def term(self, block, a):
        s = Stack(a)
        s.left = self.factor(block, a)

        while self.Look == '*' or self.Look == '#':
            op = self.LookStr

            self.match(op)
            # self.match('*')
            s.right = self.factor(block, a)
            s.pop()

            a.addop(Op(s.left, op, s.right))
            s.num += 1

        if s.num == 1 and not (s.left is None):
            return s.left
        return None

    def expression(self, block, a):  # potrebuje Block (Var) in Assign (operacije)
        s = Stack(a)
        s.left = self.term(block, a)

        while self.Look == '+' or self.Look == '-':
            if self.Look == '+':
                op = '+'
            else:
                op = '-'

            self.match(op)
            s.right = self.term(block, a)
            s.pop()

            a.addop(Op(s.left, op, s.right))
            s.num += 1

        if s.num == 1 and not (s.left is None):
            return s.left
            # a.addop(Op(s.left, '', None))
        return None

    def doif(self, block):  # referenca na block zaradi spremenljivk
        c = self.condition(block)

        # v = self.term(block)  # pogoj = VAR
        st = IfElse(block)  # superblock
        st.cond = c
        outident = self.ident  # shrani ident

        self.match(':')
        # print ("IF '"+self.Look+"'")
        self.match('n')
        self.scan()

        # print ("#Comp IF Block"+str(outident)+c.code())
        self.compblock(st, outident)

        # print("##Token "+self.TokenStr+" "+str(self.ident)+ " "+str(outident))
        if self.Token == 'l' and outident == self.ident:
            # print ("#Comp ELSE Block"+str(self.ident))
            outident = self.ident
            self.match(':')
            self.match('n')
            self.scan()
            # print("ELSEIF '" + self.TokenStr + "'")
            st.elsebody(block)
            self.compblock(st, outident)

        return st

    def list(self, block):  # parse and return list of variables
        varlist = []
        while self.Look == 'a':
            self.scan()
            name = self.TokenStr
            if block is None:  # no block, variable is new literal (eg. def fn)
                v = Var(name)
            else:
                v = block.get_var(name)
            varlist.append(v)

            if self.Look == ',':
                self.match(',')
            else:
                break

        return varlist

    def function(self, block):
        if self.Look == 'a':  # beri ime funkcije
            self.scan()
        else:
            self.error("Expected Function name")

        ident = self.ident  # shrani ident
        fn = Function(self.TokenStr, block)  # ime in superblock
        # print ("Funkcija: "+self.TokenStr)

        self.match('(')
        varlist = self.list(None)
        for v in varlist:
            v.settype(Signal.inport)  # definiraj tip in level?
            v.set_tree_level(0)     # mark initial data flow level = 0
            fn.add_var(v)           # in dodaj v blok
        self.match(')')
        self.match(':')
        self.match('n')

        self.scan()
        return self.compblock(fn, ident)

    def statement(self, block):
        if self.Token == 'n':  # prqazna vrstica ?
            while self.Look == 'n' and not self.send:  # spusti vse prazne vrstice
                self.scan()
        elif self.Token == 'a':
            # print ("A "+str(self.ident))
            a = self.assignment(block)
            block.add_to_body(a)
        elif self.Token == 'i':
            st = self.doif(block)
            block.add_to_body(st)
        elif self.Token == 'r':
            if self.Look == 'a':  # beri seznam izh. spremenljivk (tuple)
                varlist = self.list(block)
                for v in varlist:
                    v.settype(Signal.outport)  # definiraj tip
                block.add_to_body(Return(varlist))
                self.match('n')
                self.scan()
            else:
                self.error("Expected return variable")
        elif self.Token == 'd':  # def novo funkcijo
            fn = self.function(block)
            block.body.add(fn)
        else:
            self.error("Unexpected statement: "+self.Token)

    def compblock(self, block, outident=-1):  # prevedi blok kode
        while not self.send:
            while self.Token == 'n' and not self.send:  # spusti prazne vrstice
                self.scan()

            if not self.send:
                if not self.ident > outident:
                    # print ("Block exit")
                    return block

            self.statement(block)
            if self.send:
                break
        return block

    def compile(self, fname):
        if fname == "":
            return
        else:
            self.name = fname
            if fname.endswith(".py"):
                self.name = fname[:-3]
            f = open(fname, 'r')
            self.src = f.read() + " \n"
            print (fname)
            #print(self.src + "---------------------------------")
            self.slen = len(self.src)

        prog = PyProg(self.name)

        self.scan()
        self.scan()
        self.compblock(prog)  # compile block of code, outident=-1

        return prog
