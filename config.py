# -------------------------------------------------------------------------------
# config.py
#
# Python configuration parser for pipeline synthesis tool
#
# Copyright (C) 2017, Andrej Trost
# License: MIT
# -------------------------------------------------------------------------------
import ConfigParser


class Conf:
    def __init__(self, name):
        self.config = ConfigParser.ConfigParser()
        self.config.read(name)

        self.inputs = []
        self.insize = []
        self.in_inteface = []  # input interface string (name or reg)
        try:
            section = "inputs"
            opt = self.config.options(section)
            for p in opt:
                self.inputs.append(p)

                val = self.config.get(section, p)
                val = val.split(",")
                if len(val)>1:
                    self.in_inteface.append(val[0])
                    self.insize.append(int(val[1]))
                else:
                    self.insize.append(14)    # default size
        except ConfigParser.Error:
            print ("No section Inputs in configuration!")

        self.outputs = []
        self.outsize = []
        self.out_inteface = []
        try:
            section = "outputs"
            opt = self.config.options(section)
            for p in opt:
                self.outputs.append(p)

                val = self.config.get(section, p)
                val = val.split(",")
                if len(val)>1:
                    self.out_inteface.append(val[0])
                    self.outsize.append(int(val[1]))
                else:
                    self.outsize.append(14)    # default size
        except ConfigParser.Error:
            print ("No section Outputs in configuration!")

