#!/usr/bin/env python3

import sys
import argparse
import platform
import inspect
import os
import os.path

from os.path import dirname as dname
from os.path import join as pjoin

try:
	from importlib.resources import files as resfiles
except:
	from importlib_resources import files as resfiles

# ########################################################################### #

def perr(sMsg):
	sys.stderr.write("ERROR: %s\n"%sMsg)

# ########################################################################### #
def main():

	psr = argparse.ArgumentParser(
		description = "dasFlex server root initialization."
	)

	psr.add_argument(
		'-e','--etc-dir', default=None, help="Set the configuration data directory. "+\
		"By default it will be ROOT/etc. The setting directory need not reside "+\
		"under the server ROOT directory.", dest="sEtcDir", metavar="DIR"
	)
	psr.add_argument(
		'-l','--log-dir', default=None, help="Set the web-log directory. Defaults "+\
		"to ROOT/log.  This directory must be writable by the web-server user account",
		dest="sLogDir", metavar="DIR"
	)
	psr.add_argument(
		'-c','--catalog-dir', default=None, help="Set the data source catalog directory."+\
		" Defaults to ROOT/catalog. This is where dasflex_addsrc will write data"+\
		" source definition files.", dest="sCatDir", metavar="DIR"
	)
	psr.add_argument(
		'-s','--static-dir', default=None, help="Set static web resource directory. Defaults"+\
		" to ROOT/static. This is where stylesheets, logos and other static web content"+\
		" will reside.", dest="sResDir", metavar="DIR"
	)
	psr.add_argument(
		'-r','--response-cache', default=None, help="Set the reduced-resolution stream "+\
		"cache directory. This is where cached responces will be kept, and it can "+\
		"grow quite large! Defaults to $ROOT/cache", dest="sCacheDir", metavar="DIR"
	)
	if platform.system() != 'Windows':
		psr.add_argument(
			'-o','--shared-obj-path', default=None, help="Set the shared-object path for "+\
			"any sub programs that are run.  Equivalent to setting LD_LIBRARY_PATH. "+\
			"Defaults to $ROOT/lib", dest="sLibPath", metavar="PATH"
		)

	sExeDir = dname(sys.executable)
	if platform.system() != 'Windows':
		sDef = "$ROOT/bin:%s:/usr/bin"%sExeDir
	else:
		sWinDir = os.getenv('systemroot')
		sDef = "%%ROOT%%\\bin;%s\\;%s\\System32"%(sExeDir, sWinDir)
	psr.add_argument(
		'-b','--bin-path', default=sDef, help="Set the path for any readers or other "+\
		"sub-programs launched by dasFlex.  Defaults to: '%s'"%sDef, dest="sBinPath",
		metavar="PATH"
	)
	# Walk up stack to SOMEPLACE from SOMPLACE/dasflex/scripts/mkroot.py
	sDef = dname(dname(dname(os.path.abspath(inspect.stack()[0][1]))))
	psr.add_argument(
		'-p','--py-path', default=sDef, help="Set the module path for dasFlex components."+\
		"Defaults to: '%s'.  There is rarely a reason to change this"%sDef, dest="sPyPath",
		metavar="PATH"
	)

	psr.add_argument(
		'-n','--no-examples', default=True, action="store_false", dest="bNoExamples",
		help="Do not install example data sources in the catalog.  Note: You can "+\
		" remove examples simply by deleting them and re-running dasflex_cupdate"
	)
	psr.add_argument(
		'ROOT', help="The root directory for this dasFlex web-service end point.",
		metavar='ROOT'
	)
	psr.add_argument(
		'SERVER_ID', help="A token to identify this server in log files.",
		metavar='SERVER_ID'
	)

	opts = psr.parse_args()

	sRoot = opts.ROOT.strip()

	if platform.system() != 'Windows':
		if not sRoot.startswith('/'):
			perr("You must provide an absolute path for the server root directory, "+\
				"'%s' does not start with a '/'"%sRoot)
			return 7

		if len(sRoot.strip('/')) < 1:
			perr("Invalid root directory, '%s'."%sRoot)
			return 7
	else:
		if (len(sRoot) < 3) or (not sRoot[1:3] == "\\:"):
			perr("You must provide an absolute path for the server root directory, "+\
				"'%s' does not start with a drive letter, (ex: 'C:\\opt\\dasflex')."%sRoot)
			return 7

		if len(sRoot.strip('\\')) < 3:
			perr("Invalid root directory, '%s'."%sRoot)
			return 7

	dRep = {'ROOT_DIR': sRoot}

	if opts.sEtcDir: dRep['ETC_DIR'] = opts.sEtcDir
	else: dRep['ETC_DIR'] = pjoin(sRoot, 'etc')

	if opts.sLogDir: dRep['LOG_DIR'] = opts.sLogDir
	else: dRep['LOG_DIR'] = pjoin(sRoot, 'log')

	if opts.sCatDir: dRep['CAT_DIR'] = opts.sCatDir
	else: dRep['CAT_DIR'] = pjoin(sRoot, 'catalog')

	if opts.sResDir: dRep['STATIC_DIR'] = opts.sResDir
	else: dRep['STATIC_DIR'] = pjoin(sRoot, 'static')

	if opts.sCacheDir: dRep['CACHE_DIR'] = opts.sCacheDir
	else: dRep['CACHE_DIR'] = pjoin(sRoot, 'cache')

	if platform.system() != 'Windows':
		if opts.sLibPath: dRep['LIB_PATH'] = opts.sLibPath
		else: dRep['LIB_PATH'] = pjoin(sRoot, 'lib')

	# Some things are never null
	dRep['BIN_PATH'] = opts.sBinPath.replace('$ROOT', sRoot)

	dRep['PY_PATH'] = opts.sPyPath

	dRep['SERVER_ID'] = opts.SERVER_ID

	# Dictionary is setup, now read and output files

	# Start here:  
	#
	#  copy out items into each ['THING_DIR']
	#
	# make copies of things that don't end in ".in" and
	# use the substitution dictionary above for things that d.

	for thing in resfiles('dasflex.root').iterdir():
		print(thing)

	sConfFile = pjoin(dRep['ETC_DIR'], 'dasflex.conf')
	print(
'''DasFlex root directory initialized. Insure that:
   
    SetEnv DASFLEX_CONFIG %s

is set in your Apache <Directory> block for the CGI bin area.
''')
	return 0

# ########################################################################### #
if __name__ == '__main__':
	sys.exit(main())
