#!/usr/bin/env python
__author__ = 'akeshavan'
import sys
from nipype.utils.filemanip import loadpkl

if __name__ == "__main__":
    if len(sys.argv) > 1:
        crashes = sys.argv[1:]
        for c in crashes:
            pk = loadpkl(c)["node"]
            print(pk, pk.inputs.mseID)
