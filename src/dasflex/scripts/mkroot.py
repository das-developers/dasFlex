#!/usr/bin/env python3

import sys
import argparse
import platform
import inspect
import os
import os.path
import copy
import shutil

from os.path import dirname as dname
from os.path import join as pjoin

try:
	from importlib.resources import files as resfiles
except:
	from importlib_resources import files as resfiles

# ########################################################################### #

def perr(sMsg):
	sys.stderr.write("ERROR: %s\n"%sMsg)

def pinfo(sMsg):
	sys.stderr.write("INFO: %s\n"%sMsg)

# ########################################################################### #
def copyFile(path, sDest, dRep):
	# Open anything ending in ".in" in text mode and do replacement.
	# otherwise just copy over the bytes

	if str(path).endswith(".hide"):
		return None

	sDestDir = dname(sDest)
	if not os.path.exists(sDestDir):
		os.makedirs(sDestDir, 0o775, True)

	if str(path).endswith(".in"):
		# Strip off the .in
		# Add install directory
		dRep = copy.deepcopy(dRep)
		dRep["INST_DIR"] = sDestDir
		dRep["SUPER_DIR"] = dname(sDestDir)

		sDest = sDest[:-3]
		pinfo("%s -> %s"%(str(path), sDest))

		with path.open(mode='r') as fIn:
			sTplt = fIn.read()
			with open(sDest, "w") as fOut:
				fOut.write(sTplt%dRep)
	else:
		pinfo("%s -> %s"%(str(path), sDest))

		with path.open(mode='rb') as fIn:
			with open(sDest, 'wb') as fOut:
				fOut.write(fIn.read())

# ########################################################################### #
def copySub(path, sStripTo, sRep, dRep):
	"""Copy a sub items.
	Args:
		sStrip (str) - Find this 
	"""
	for subPath in path.iterdir():
		if str(subPath).find("__pycache__") > -1: continue

		if subPath.is_dir():
			copySub(subPath, sStripTo, sRep, dRep)
		else:
			print(str(subPath), sStripTo, sRep)
			
			sDest = str(subPath)
			i = sDest.find(sStripTo)
			n = len(sStripTo) + 1
			sDest = pjoin(sRep, sDest[i+n:])
			copyFile(subPath, sDest, dRep)


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
		#sDef = "$ROOT/bin:%s:/usr/bin"%sExeDir
		sDef = "$ROOT/bin:/usr/bin"
		sTight = "$ROOT/bin"
	else:
		sWinDir = os.getenv('systemroot')
		#sDef = "%%ROOT%%\\bin;%s\\;%s\\System32"%(sExeDir, sWinDir)
		sDef = "%%ROOT%%\\bin;%s\\System32"%sWinDir
		sTight = "%%ROOT%%\\bin"
	psr.add_argument(
		'-b','--bin-path', default=sDef, metavar="PATH", dest="sBinPath",
		help="Set the path for any reducers or other sub-programs launched by dasFlex."+\
		" Defaults to: '%s'."%sDef + " For tighter security you can restrict this to "+\
		"just %s"%sTight
	)
	# Walk up stack to SOMEPLACE from SOMPLACE/dasflex/scripts/mkroot.py
	sDef = dname(dname(dname(os.path.abspath(inspect.stack()[0][1]))))
	psr.add_argument(
		'-p','--py-path', default=sDef, help="Set the module path for dasFlex components."+\
		" Defaults to: '%s'.  There is rarely a reason to change this"%sDef, dest="sPyPath",
		metavar="PATH"
	)

	psr.add_argument(
		'-n','--no-examples', default=True, action="store_false", dest="bExamples",
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

	if not os.path.isdir(sRoot):
		try:
			os.makedirs(sDestDir, 0o775, True)
		except:
			perr("Can't create the top level directory, %s.  Do that manually and re-run"%sRoot)
			return 13

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

	# Assume dasflex bin is always first
	n = dRep['BIN_PATH'].find(os.pathsep)
	if n == -1:
		n = len(dRep['BIN_PATH'])
	dRep['DASFLEX_BIN'] = dRep['BIN_PATH'][:n]

	dRep['PY_PATH'] = opts.sPyPath

	dRep['SERVER_ID'] = opts.SERVER_ID

	# Save off the python executable used to run this command
	dRep['PY_INTERPRETER'] = sys.executable

	# Dictionary is setup, now read and output files

	# Start here:  
	#
	#  copy out items into each ['THING_DIR']
	#
	# make copies of things that don't end in ".in" and
	# use the substitution dictionary above for things that d.

	dDirs = {
		'etc'           : dRep['ETC_DIR'], 
		'static'        : dRep['STATIC_DIR'],
		'sdef.commands' : "%s/include"%sRoot
	}

	if opts.bExamples:
		dDirs['Examples'] = "%s/dsdf/Examples"%sRoot

	for sDir in dDirs.keys():
		for path in resfiles('dasflex.root.%s'%sDir).iterdir():
			sIn = str(path)
			sStrip = pjoin('dasflex/root', sDir.replace('.','/'))
			i = sIn.find(sStrip)
			if i < 0:
				raise EnvironmentError("Couldn't find %s in resource path %s"%(sStrip, sIn))
			i += len(sStrip) + 1 # Get dir posix sep
			sOut = pjoin(dDirs[sDir], sIn[i:])

			if sIn.find("__pycache__") > -1: continue

			# If the sub item is a directory, go recursive
			if path.is_dir():
				copySub(path, sStrip, dDirs[sDir], dRep)
			else:
				copyFile(path, sOut, dRep)

	# Top level special item.  If dasflex.conf.example exists but not dasflex.conf,
	# then copy over to dasflex.conf.  Same for mime.json.example.
	for sFile in ('dasflex.conf', 'mime.json'):
		sSrc = pjoin(dRep['ETC_DIR'], "%s.example"%sFile)
		sDest = pjoin(dRep['ETC_DIR'], sFile)
		if not os.path.isfile(sDest):
			pinfo("dasflex.conf missing, copying over example file")
			shutil.copy2(sSrc, sDest)


	if not os.path.isdir(dRep['CAT_DIR']):
		os.makedirs(dRep['CAT_DIR'], 0o775, True)

	sConfFile = pjoin(dRep['ETC_DIR'], 'dasflex.conf')
	print(
'''DasFlex root directory minimally initialized. Insure that:
   
    SetEnv DASFLEX_CONFIG %s

is set in your Apache <Directory> block for the CGI bin area.
'''%sConfFile)
	return 0

# ########################################################################### #
if __name__ == '__main__':
	sys.exit(main())
