# -------------------------------------------------------------------------------
# PyPipeSynth.py
#
# Python pipeline synthesis tool: synthesize RTL code from a Python function
# in: python function and board ini file (see code at the bottom)
# out: MyHDL RTL code for function and interface (for Red Pitaya board)
#
# Copyright (C) 2017, Andrej Trost
# License: MIT
# -------------------------------------------------------------------------------
# coding=utf-8
from __future__ import print_function
from par import *
from config import *
from interface import *
from copy import deepcopy
import os

pipe_debug = False


def is_stream_var(name):    # return True if variable name defines pipeline stream
    if name == "a" or name == "b":
        return True
    else:
        return False


class Transf:

    def __init__(self, prg, conf):
        self.prg = prg
        self.conf = conf
        self.fn = Block("")

        self.assignments = []
        self.conditions = []

        self.targets = []   # list of assignment targets
        self.return_varlist = []
        self.varlist = []   # list of expression variables
        self.varlist_is_reg = False

        self.vardict = {}
        self.stlist = []    # list of statements (get_statement)
        self.stpos = []     # position of statements in body (get_statement)

        self.new_stlist = []
        self.new_vardict = {}  # last translation of source name to register var name

        self.vt = {}
        self.naddsub = 0
        self.nmul = 0

        self.reg_namelist = []  # list of register names (before renaming, a, b, x)
        self.reg_varlist = []   # list of register vars based on assignments

# Useful functions

    def var_tree(self, name, level):
        if level in self.vt:
            self.vt[level].append(name)
        else:
            self.vt[level] = [name]

    def report(self):
        # print ("Levels: "+str(self.nlevels))
        print ("Resources:")
        print ("ADD/SUB: "+str(self.naddsub))
        print ("MUL: "+str(self.nmul))
        print ("Dataflow levels:")
        for key in self.vt:
            print (" "+str(key)+": "+str(self.vt[key]))

    def get_function(self):  # return Function block of the program (or error exit)
        if len(self.prg.body.stlist) == 0:
            print ("Get function: empty program")
            exit(0)
        if not isinstance(self.prg.body.stlist[0], Function):
            print ("Get function: expecting function")
            exit(0)
        self.fn = self.prg.body.stlist[0]

        # check if Return statement is last
        self.get_statements(self.fn)
        if len(self.stlist) < 1:
            print ("Get function: Function body is empty!")
            exit(0)

        r = self.stlist[-1]
        if isinstance(r, Return):
            for v in r.varlist:
                if v.name in self.conf.outputs:
                    i = self.conf.outputs.index(v.name)
                    v.setsize(self.conf.outsize[i])
                else:
                    print ("Warning: output '"+v.name+"' is not in configuration! Set size: 16")
                    v.setsize(16)
            self.return_varlist = r.varlist
        else:
            print ("Get function: Expecting return!")
            exit(0)

        for v in self.fn.vardict.values():
            if v.mode == Signal.inport:
                if v.name in self.conf.inputs:
                    i = self.conf.inputs.index(v.name)
                    v.setsize(self.conf.insize[i])
                else:
                    print ("Warning: input '"+v.name+"' is not in configuration! Set size: 16")
                    v.setsize(16)

    def get_statements(self, block, stype=None):  # get list of statements of stype
        body = block.body
        if isinstance(block, IfElse):
            if not block.truebody:
                body = block.elsbody

        self.stlist = []
        n = len(body.stlist)
        for i in range(n):
            st = body.stlist[i]
        # for st in body.stlist:
            if stype is None:
                self.stlist.append(st)
                self.stpos.append(i)
            elif isinstance(st, stype):
                self.stlist.append(st)
                self.stpos.append(i)

# Pipeline utility functions

    def conditions_assign(self, b, in_condition):   # convert assignments to conditions
        imax = len(b.stlist)
        i = 0
        while i < imax:
        # for i in range(imax):
            st = b.stlist[i]
            i += 1
        # for st in b.stlist:             # loop through body code
            if isinstance(st, Assign):
                # if in_condition == 0:     # not in condition, just save assignment
                #     self.assignments.append(st)
                #     print ("Append "+st.target.name)
                # el
                if in_condition == 1:
                    st.clist.extend(self.conditions)  # extend the list with current conditions
                    self.assignments.append(st)       # save statement(s)

                    # print ("Search: "+st.target.name)
                    # for st0 in self.assignments:
                    #     if st.target.name == st0.target.name:    # add inverted condition to previous assignment
                    #         clist = self.conditions  # get conditions list and invert last
                    #         clist[-1] = (clist[-1][0], False)
                    #         st0.clist.extend(clist)
                    #         print("Found ****")
                elif in_condition == 2:
                    st.clist.extend(self.conditions)
                    self.assignments.append(st)

            elif isinstance(st, IfElse):
                # if in_condition == 0:
                #     print ("**First")  # mark st to be replaced

                self.conditions.append((st.cond, True))
                self.conditions_assign(st.body, 1)
                self.conditions.pop()
                if st.elsbody:
                    self.conditions.append((st.cond, False))
                    self.conditions_assign(st.elsbody, 2)
                    self.conditions.pop()

                if b == self.fn.body:   # check if we are in first level
                    # print ("Replace if statement")

                    amax = len(self.assignments)
                    for ai in reversed(range(amax)):
                        a = self.assignments[ai]
                        self.fn.body.insert(i, a)

                    del self.fn.body.stlist[i-1]
                    self.assignments = []

    def get_variables(self, op, start=True):   # get list of variables from expression
        if start:   # clear the var list the first time it is called
            self.varlist = []
            self.varlist_is_reg = False
        if isinstance(op.left, Var):
            if op.left not in self.varlist:
                self.varlist.append(op.left)
                if op.left.name in self.reg_namelist:
                    # print ("Found reg")
                    self.varlist_is_reg = True
        elif isinstance(op.left, Op):
            self.get_variables(op.left, False)
        if isinstance(op.right, Var):
            if op.right not in self.varlist:
                self.varlist.append(op.right)
                if op.right.name in self.reg_namelist:
                    # print ("Found reg")
                    self.varlist_is_reg = True
        elif isinstance(op.right, Op):
            self.get_variables(op.right, False)

    def set_variables(self, op, level, start=True):   # set variables to level
        if start:   # clear the var list the first time it is called
            pass
        if isinstance(op.left, Var):
            if op.left.name in self.reg_namelist:
                v = self.fn.get_var(op.left.name+"_z"+str(level))  # get or create new register
                v.register = True
                v.reglevel = level
                if v not in self.reg_varlist:
                    self.reg_varlist.append(v)
                op.left = v
                # print ("Replace reg "+v.name)

        elif isinstance(op.left, Op):
            self.set_variables(op.left, level, False)
        if isinstance(op.right, Var):
            if op.right.name in self.reg_namelist:
                v = self.fn.get_var(op.right.name+"_z"+str(level))
                v.register = True
                v.reglevel = level
                if v not in self.reg_varlist:
                    self.reg_varlist.append(v)
                op.right = v
                # print ("Replace reg "+v.name)
        elif isinstance(op.right, Op):
            self.set_variables(op.right, level, False)


################################################################################################
##### Analysis
################################################################################################

    def decompose(self, b):  # decompose assignment block into binary assignments
        change = False
        imax = len(b.body.stlist)
        for i in range(imax):     # loop through assignments
            st = b.body.stlist[i]
            if not isinstance(st, Assign):
                print ("Decompose: Expected assignment: "+st.code())
                exit(-1)

            target_name = st.target.name

            if len(st.oplist) != 1:  # make sure oplist is in binary tree form
                print ("Decompose: error in oplist, length = "+str(len(st.oplist)))
                exit(-1)

            op = st.oplist[0]

            if isinstance(op.left, Op):   # Expand left operand
                change = True
                nv = Var(target_name+"1")  # create new variable, left name suffix: 1
                b.add_var(nv)             # add to block and
                a = Assign(nv)            # to new assignment
                a.addop(op.left)
                op.left = nv              # replace op.left with variable
                b.body.insert(0, a)       # and insert to block

            if isinstance(op.right, Op):  # Expand right operand
                change = True
                nv = Var(target_name+"2")  # create new variable, right name suffix: 2
                b.add_var(nv)
                a = Assign(nv)
                a.addop(op.right)
                op.right = nv
                b.body.insert(0, a)
        return change

    def evaluate(self, b):  # evaluate  expressions in assignment block
        imax = len(b.body.stlist)
        for i in range(imax):
            st = b.body.stlist[i]
            if isinstance(st, Assign):  # evaluate all Assign statement
                if st.target.mode == Signal.no:  # mark undefined variable as Signal.int
                    st.target.mode = Signal.int

                jmax = len(st.oplist)
                for j in range(jmax):  # loop through operators
                    op = st.oplist[j]

                    if isinstance(op.left, Lit):
                        left = op.left
                        ls = left.size
                        ll = left.tree_level
                        if ll < 0 and not isinstance(op.left, Num):
                            print ("EvaluateBody: variable "+left.name+" undefined in")
                            print (st.code(0))
                            return False
                        if isinstance(op.right, Lit):
                            right = op.right
                            rs = right.size
                            rl = right.tree_level
                            if rl < 0 and not isinstance(op.right, Num):
                                print ("EvaluateBody: variable "+right.name+" undefined in")
                                print (st.code(0))
                                return False
                            if op.op == '>>':
                                rs = right.value
                                if isinstance(op.right, Num):
                                    print ("SHR: "+str(right.value))
                                else:
                                    print ("EvaluateBody: only support shift by constant!")
                                    print (st.code(0))
                                    return False
                        else:  # OPT: propagation!!
                            rs = 0
                            rl = 0
                    else:
                        print ("EvaluateBody: expecting left Literal!")

                    if rl > ll:  # define result level
                        yl = rl + 1
                    else:
                        yl = ll + 1

                    st.target.tree_level = yl
                    self.var_tree(st.target.name, yl)

                    if op.op == '+' or op.op == '-':
                        self.naddsub += 1
                        if ls > rs:
                            es = ls + 1
                        else:
                            es = rs + 1
                    elif op.op == '*':
                        self.nmul += 1
                        es = ls + rs
                    elif op.op == '>>':
                        es = ls - rs

                    elif op.op == 'load' or op.op == '':
                        if ls >= rs:
                            es = ls
                        else:
                            es = rs
                    else:
                        es = 0  # unknown op

                    if st.target.mode == Signal.outport:
                        if st.target.size != es:
                            print ("Warning: output '"+st.target.name+"' resized from "+str(es)+" to "+str(st.target.size))
                    else:
                        st.target.setsize(es)  # set size of target var
                    # print ("Size: "+str(es)+":"+op.left.name+"="+str(ls)+","+op.right.name+"="+str(rs))
        return True

    def analyze_body(self, cbody, cond):    # analyze body, cond=True for conditional (if, else) body
        for st in cbody.stlist:
            if isinstance(st, Assign):
                print ("ST: "+st.code(0), end="")
                if (not cond) and (st.target in self.targets):
                    print ("Analyse error: Multiple unconditional assignments not supported.")
                    exit(0)
                self.targets.append(st.target)

                b = Block("decomp")  # create tmp block
                cp_st = deepcopy(st)
                cp_st.target = st.target
                b.add_to_body(cp_st)  # add copy of st to body
                b.vardict = deepcopy(self.fn.vardict)

                i = 1
                while self.decompose(b):  # iteratively break expressions to binary in block b
                    i += 1
                # print ("Decompose "+str(i)+"-times.")

                self.evaluate(b)    # evaluate expression (data size)
                print ("  "+st.target.emit())

            elif isinstance(st, IfElse):  # za IfElse naredi rekurzivno za oba dela

                self.analyze_body(st.body, True)
                if not (st.elsbody is None):
                    self.analyze_body(st.elsbody, True)

    def analyze(self):
        print ("-------- Analyse input function: --------")
        self.get_function()     # get input function
        self.analyze_body(self.fn.body, False)  # recursively analyze function body

        # print (p.emit())
        # print (p.code())
        print ("-----------------------------------------")

################################################################################################

    def pipeline_variables(self):   # transform statements to pipeline, mark registers
        """
Do assignment statements transformation from sequential to pipeline.
- check if assignment expression contains pipeline variables (registers) and define reglevel
- rename assignment target and register variables to indicate level, mark variables as registers
- add missing registers from end level (pipe_levels) to level 0
- reorder assignments according to the level
        """
        for w in self.fn.vardict.values():  # browse block variables, fill reg_namelist for stream members (eg. a, b)
            if is_stream_var(w.name):
                self.reg_namelist.append(w.name)

        pipe_levels = 0
        self.get_statements(self.fn, Assign)   # Loop through Assignment statements
        for st in self.stlist:
            self.get_variables(st.oplist[0])  # set varlist[] from expression, mark varlist_is_reg

            level = max([v.reglevel for v in self.varlist]) + 1  # get max reglevel + 1
            pipe_levels = max(pipe_levels, level)

            if self.varlist_is_reg:
                self.reg_namelist.append(st.target.name)    # add target to reg_namelist
                st.target.reglevel = level                  # def target level

                self.set_variables(st.oplist[0], level-1)   # rename expr variables to level-1

                self.new_vardict[st.target.name] = st.target.name+"_z"+str(level)
                st.target = self.fn.get_var(st.target.name+"_z"+str(level))  # def new target
                st.target.register = True
                st.target.reglevel = level

                self.reg_varlist.append(st.target)          # finally add to reg_varlist

            if pipe_debug:
                    print ("Level "+str(level)+": "+st.code(0), end="")

        print ("Pipeline levels: "+str(pipe_levels))

        if pipe_debug:
            print ("reg_namelist: ", end="")
            for v1 in self.reg_namelist:
                print (str(v1)+",", end="")
            print ("")

            print ("reg_varlist: ", end="")
            for v1 in self.reg_varlist:
                print (v1.emit()+",", end="")
            print ("\n")

        # reverse order transformation: level = pipe_levels downto 0
        for level in reversed(range(pipe_levels)):

            for st in self.stlist:  # find (level+1) Assign statement
                if st.target.reglevel == level+1:

                    self.get_variables(st.oplist[0])    # get expression variables
                    varlist_n = len(self.varlist)
                    if pipe_debug:
                        print ("*** Check level "+str(level+1)+", "+str(varlist_n)+"-times")

                    for n in range(varlist_n):  # loop through expression variables
                        v = self.varlist[n]
                        if pipe_debug:
                            print (v.code(), end="")

                        found = False           # search for variable assignment statement
                        for st1 in self.stlist:
                            if v == st1.target:
                                found = True
                                if pipe_debug:
                                    print (" assignment found.")
                                break

                        if pipe_debug and not found:
                            print (" NOT found! ", end="")
                        if v.register and not found:    # if expression var = register and not found
                            base_name = v.name.split('_')[0]  # get original var name TODO

                            if pipe_debug and not found:
                                print (" Add base_name = "+base_name)

                            nv = self.fn.get_var(v.name)    # get new register variable
                            nv.register = True
                            nv.reglevel = level
                            self.varlist.append(nv)         # immediately add to varlist

                            if level == 0:                  # get (level-1) variable
                                nv2 = self.fn.get_var(base_name)
                            else:
                                nv2 = self.fn.get_var(base_name+"_z"+str(level-1))
                                nv2.register = True
                                nv2.reglevel = level-1

                            a = Assign(nv)                  # generate assignment
                            a.addop(Op(nv2, "load", None))
                            self.fn.body.add(a)
                            self.stlist.append(a)
                            # print (a.code(1))

        if pipe_debug:
            print ("*** Check return level ")
        for v in self.return_varlist:
            if pipe_debug:
                print("Return "+v.name)
            # if v.name in self.conf.outputs:
            #     v.setsize(14)
            # else:
            #     print ("Warning: output "+v.name+" is not in configuration! Set size: 16")
            #     v.setsize(16)

            a = Assign(v)                  # generate assignment
            if v.name in self.new_vardict:
                name2 = self.new_vardict[v.name]    # find original name
                v2 = self.fn.get_var(name2)
                a.addop(Op(v2, "load", None))  # TODO check level
                self.fn.body.add(a)
                self.stlist.append(a)
            else:
                print ("Can't find return variable " + v.name + " !")
                exit(-1)

        newstlist = []                          # order the statements into levels
        for level in range(pipe_levels+1):
            for st in self.stlist:
                if st.target.reglevel == level:
                    newstlist.append(st)

        self.fn.body.stlist = newstlist
        # print (self.fn.code(0))
        # exit()

    def decompbody(self, cbody):  # decompose body assignment statements to binary expressions
        change = False
        imax = len(cbody.stlist)
        for i in range(imax):     # loop program statements
            st = cbody.stlist[i]
            if isinstance(st, IfElse):  # for both bodies of IfElse
                change = change or self.decompbody(st.body)
                # if not (st.elsbody is None):
                #     change = change or decompbody(st.elsbody)  # TODO: error body?
            elif isinstance(st, Assign):  # check assignments
                targetname = st.target.name

                jmax = len(st.oplist)
                for j in range(jmax):  # loop through operators
                    op = st.oplist[j]

                    if isinstance(op.left, Op):  # Expand Left Op
                        change = True
                        nv = Var(targetname+"1")  # new variable
                        self.fn.add_var(nv)
                        a = Assign(nv)            # and assignment with op.left
                        a.addop(op.left)
                        op.left = nv       # replace op.left with variable
                        cbody.insert(i, a)  # and insert

                    if isinstance(op.right, Op):  # Expand Right Op
                        change = True
                        nv = Var(targetname+"2")
                        self.fn.add_var(nv)
                        a = Assign(nv)
                        a.addop(op.right)
                        op.right = nv
                        cbody.insert(i, a)
        return change

    def evaluatebody(self, cbody):  # evaluate assigments in body
        # global stat

        imax = len(cbody.stlist)
        for i in range(imax):     # Loop statements
            st = cbody.stlist[i]
            if isinstance(st, IfElse):  # for both bodies of IfElse
                self.evaluatebody(st.body)
            #     if not (st.elsbody is None):
            #         evaluatebody(st.elsbody)
            # el
            elif isinstance(st, Assign):  # check assignments
                if st.target.mode == Signal.no:
                    st.target.mode = Signal.int

                jmax = len(st.oplist)
                for j in range(jmax):
                    op = st.oplist[j]

                    if isinstance(op.left, Lit):
                        left = op.left
                        ls = left.size
                        ll = left.tree_level
                        if ll < 0 and not isinstance(op.left, Num):
                            print ("EvaluateBody: variable "+left.name+" undefined in")
                            print (st.code(0))
                            return False
                        if isinstance(op.right, Lit):
                            right = op.right
                            rs = right.size
                            rl = right.tree_level
                            if rl < 0 and not isinstance(op.right, Num):
                                print ("EvaluateBody: variable "+right.name+" undefined in")
                                print (st.code(0))
                                return False
                        else:  # OPT: propagation!!
                            rs = 0
                            rl = 0
                    else:
                        print ("EvaluateBody: expecting left Literal!")

                    if rl > ll:  # define result level
                        yl = rl + 1
                    else:
                        yl = ll + 1

                    st.target.tree_level = yl
                    self.var_tree(st.target.name, yl)

                    if op.op == '+' or op.op == '-':
                        self.naddsub += 1
                        if ls > rs:
                            es = ls + 1
                        else:
                            es = rs + 1
                    elif op.op == '*':
                        self.nmul += 1
                        es = ls + rs
                    elif op.op == '>>':
                        es = ls - (right.value)
                    elif op.op == 'load' or op.op == '':
                        if ls >= rs:
                            es = ls
                        else:
                            es = rs
                    else:
                        es = 0  # unknown op

                    if st.target.mode == Signal.outport:
                        if st.target.size != es:
                            print ("Warning: output '"+st.target.name+"' resized from "+str(es)+" to "+str(st.target.size))
                    else:
                        st.target.setsize(es)  # set size of target var
                    # print ("Size: "+str(es)+":"+op.left.name+"="+str(ls)+","+op.right.name+"="+str(rs))
        return True


    def pipe_transform(self):  # transformation and assignment evaluation
        print ("-------- Transform: -------------")  # p = deepcopy(prog)

        self.conditions_assign(self.fn.body, 0)  # convert if-else to conditional assignments

        self.pipeline_variables()  # transform dataflow assignments to pipeline

        # print ("FN: "+self.fn.code(0))
        i = 1
        while self.decompbody(self.fn.body):  # expand assignments to binary expressions
            i += 1
        print ("Decompose "+str(i)+"-times.")

        if self.evaluatebody(self.fn.body):
            self.report()
        else:
            exit(-1)

        if_list = []
        if_level = 0
        if_last_cond = []

        self.get_statements(self.fn)    # loop through statements
        # numst = len(self.stlist)
        #
        # for i in range(numst):
        #     st = self.stlist[i]
        #     print ("Test "+str(i)+": "+st.code(0))

        fnbody = Body(1)
        for st in self.stlist:
            if isinstance(st, Assign):
                if st.clist:            # conditional assignment
                    if if_list:         # check current list of if statements, if0 = last if
                        if0 = if_list[-1]
                        if st.clist[-1][0] == if0.cond:  # assign in existing if
                            if st.clist[-1][1]:          # select true body ?
                                if0.truebody = True     # maybe not necessary
                            else:                       # select else body
                                if not if0.elsbody:
                                    if0.elsbody = Body(if0.scopeblock.body.level+1)
                                    if0.truebody = False

                            if0.add_to_body(st)         # add statement to if
                        else:                           # different if, TODO levels
                            if_list.pop()
                            ist = IfElse(self.fn)  # new IF statement
                            ist.cond = st.clist[-1][0]  # set condition
                            ist.add_to_body(st)
                            fnbody.add(ist)
                            if_list.append(ist)
                    else:
                        ist = IfElse(self.fn)  # new IF statement
                        ist.cond = st.clist[0][0]  # set condition
                        ist.add_to_body(st)
                        fnbody.add(ist)
                        if_list.append(ist)
                else:
                    fnbody.add(st)

        self.fn.body = fnbody
        print ("-------- END Transform: ---------")

################################################################################################
######## MyHDL Code generation

    def raisebodylevel(self, fnbody):
        fnbody.level += 1

        stmax = len(fnbody.stlist)
        for i in range(stmax):
            st = fnbody.stlist[i]
            if isinstance(st, IfElse):  # for both bodies of IfElse
                self.raisebodylevel(st.body)
                if not (st.elsbody is None):
                    self.raisebodylevel(st.elsbody)
            if isinstance(st, Assign):  # MyHDL style output: .next
                st.nxt = True
            if isinstance(st, Return):  # remove return from statement list !
                del fnbody.stlist[i]

    def wrap(self):
        # self.get_function()
        # fname = fn.name
        self.fn.decorator = "@always(clk.posedge)"

        self.raisebodylevel(self.fn.body)  # increment function level with +1

        myp = PyProg("Proc")  # define new program (> MyHDL)
        myp_fn = Function("proc", myp)

        myp_fn.vardict = self.fn.vardict  # transfer parameters
        self.fn.vardict = {}
        clk = Var("clk")
        clk.mode = Signal.inport
        myp_fn.add_var(clk)

        intlevel = 0
        stmax = len(self.fn.body.stlist)  # search for assignment with target = int
        # print ("STMAX="+str(stmax))
        for i in range(stmax):
            st = self.fn.body.stlist[i]
            if isinstance(st, Assign):
                if (not st.target.register) and st.target.tree_level > intlevel:
                    intlevel = st.target.tree_level
                # print (str(intlevel) + " " + str(st.target.tree_level) + " " + st.code(0))

        for v in myp_fn.vardict.values():  # declare signals for all .int variables
            if v.mode == Signal.int:
                ast = Assign(v)
                ast.addop(Op(None, "signal", None))
                myp_fn.add_to_body(ast)

        for j in range(intlevel):  # combinational block for each intlevel
            comb = Function("comb"+str(j), myp_fn)
            comb.decorator = "@always_comb"

            # transfer assignments with int variables from fn to comb
            newlist = []
            stmax = len(self.fn.body.stlist)
            added = False
            for i in range(stmax):
                st = self.fn.body.stlist[i]
                if isinstance(st, Assign):  # search assignment with target = int
                    if (not st.target.register) and st.target.tree_level == j+1:
                        comb.add_to_body(st)  # add to comb or
                        added = True
                    else:                   # to new list
                        newlist.append(st)
                else:
                    newlist.append(st)

            self.fn.body.stlist = newlist

            if added:
                myp_fn.add_to_body(comb)

        myp_fn.add_to_body(self.fn)

        # r1 = Return([Var(fname), Var("comb")])
        r1 = Return([])
        r1.instances = True
        myp_fn.add_to_body(r1)

        myp.add_to_body(myp_fn)

        # print("***TEST"+myp.code())

        vlist = "proc"
        for v in myp_fn.vardict.values():  # loop fn variables
            if v.mode == Signal.inport:
                vlist += ", "+v.name
                ast = Assign(v)
                ast.addop(Op(None, "signal", None))
                myp.add_to_body(ast)

        for v in myp_fn.vardict.values():  # loop fn variables
            if v.mode == Signal.outport:
                vlist += ", "+v.name
                ast = Assign(v)
                ast.addop(Op(None, "signal", None))
                myp.add_to_body(ast)

        gen = "from myhdl import *\n"
        gen += myp.code()
        gen += "\ntoVerilog("+vlist+")\n"
        # gen += "toVHDL("+vlist+")\n"

        return gen
################################################################################################
#
# Test transformations
# first set source path and filename
dir = "work"
os.chdir(dir)
filename = "test.py"
# Parse Python function
p = Par().compile(filename)
print(p.code())
# Read configuration file
c = Conf("rp.ini")
# Call dataflow transformation with parser and configuration object
t = Transf(p, c)
# analysis: get function, analyze dataflow, convert
t.analyze()
# transform to pipeline, generate wrapper and save to output file (MyHDL)
t.pipe_transform()
# print (p.emit())
my = t.wrap()
fo = open("proc.py", 'w')
fo.write(my)
fo.close()
print (my)
# run MyHDL to generate Verilog output and generate interface for Red Pitaya board
# os.system('python proc.py')
oif = Interface(c)
outif = oif.compile()
fif = open("red_pitaya_proc.v", 'w')
fif.write(outif)
fif.close()
#
# print (outif)
