#!/usr/bin/env python3

import sys
import os

sIn = sys.argv[1]
fIn = open(sIn, 'rb')

sOut = sys.argv[1] + ".tmp"
fOut = open(sOut, 'wb')

xBuf = fIn.read(4)
while xBuf != b'\r\n\r\n':
	x = fIn.read(1)
	xBuf = xBuf[1:] + x

fOut.write(fIn.read())

fOut.close()
fIn.close()

os.rename(sOut, sIn)
