#!/usr/bin/env python3

import sys
import argparse
import logging

# ########################################################################### #

def perr(sMsg):
	sys.stderr.write("ERROR: %s\n"%sMsg)

def pinfo(sMsg):
	sys.stderr.write("INFO: %s\n"%sMsg)

# ########################################################################### #
def main():
	psr = argparse.ArgumentParser(
		description = "Produce a flex source from a data source description file (DSDF)."
	)

	psr.add_argument(
		'-t','--test', default=False, action="store_true", help="Parse the provided "+\
		"dsdf files, but don't actually write any catalog files."
	)

	psr.add_argument(
		'CONFIG', help="A dasFlex configuration file used to find the  This determines where "

	)
