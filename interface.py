# -------------------------------------------------------------------------------
# interface.py
#
# Python interface generator for pipeline synthesis tool
# Generates specific interface for Red Pitaya board
# Copyright (C) 2017, Andrej Trost
# License: MIT
# -------------------------------------------------------------------------------
from string import Template


class Interface:

    def __init__(self, c):
        self.c = c  # configuration

    def compile(self):
        filein = open('sigproc.tmp')

        d = {'name': "red_pitaya_sigproc"}

        num = len(self.c.inputs)
        reg_decl = ""
        reg_reset = ""
        reg_write = ""
        reg_read = ""
        reg_adr = 0
        module = "proc iProc (\n"
        module += "   .clk ( clk_i )"
        stat = ""
        s = ""
        for i in range(num):
            if self.c.in_inteface[i] == "reg":
                reg_decl += "reg "
                reg_reset += "      " + self.c.inputs[i] + " <= " + str(self.c.insize[i]) + "'"
                reg_write += "         if (sys_addr[19:0]==16'h" + format(reg_adr, 'x') + ")   "
                reg_read += "      20'h" + format(reg_adr, '02x') + " : begin sys_ack <= sys_en;   sys_rdata <= "
                reg_read += "{{32-" + str(32-self.c.insize[i]) + "{1'b0}}, " + self.c.inputs[i] + "}; end\n"

                stat += self.c.inputs[i] + "  " + format(reg_adr, '02x') + " (" + str(self.c.insize[i]) + ")\n"
                reg_adr += 4

                if self.c.insize[i] > 1:
                    reg_decl += "[ " + str(self.c.insize[i]) + "-1: 0] "
                    reg_reset += "d0;\n"
                    reg_write += self.c.inputs[i] + " <= sys_wdata[ " + str(self.c.insize[i]) + "-1: 0] ;\n"
                else:
                    reg_reset += "b1;\n"
                    reg_write += self.c.inputs[i] + " <= sys_wdata[0] ;\n"

                reg_decl += self.c.inputs[i] + ";\n"
                module += ",\n"
                module += "   ." + self.c.inputs[i] + " ("
                module += self.c.inputs[i] + ")"

            else:
                s += "   input      [ " + str(self.c.insize[i]) + "-1: 0] " + self.c.in_inteface[i] + ",\n"
                module += ",\n"
                module += "   ." + self.c.inputs[i] + " ("
                module += self.c.in_inteface[i] + ")"


        d['inputs'] = s
        d['reg_decl'] = reg_decl
        d['reg_reset'] = reg_reset
        d['reg_write'] = reg_write
        d['reg_read'] = reg_read


        num = len(self.c.outputs)
        s=""
        for i in range(num):
            if self.c.out_inteface[i] != "reg":
                s += "   output     [ " + str(self.c.outsize[i]) + "-1: 0] " + self.c.out_inteface[i] + ",\n"
                module += ",\n"
                module += "   ." + self.c.outputs[i] + " ("
                module += self.c.out_inteface[i] + ")"
        d['outputs'] = s
        module += "\n);\n"
        d['module'] = module

        src = Template(filein.read())
        out = src.substitute(d)
        print("Interface:\nname adr (size)\n"+stat)
        return out

