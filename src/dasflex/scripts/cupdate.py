#!/usr/bin/env python3
"""Refresh SourceSets and Catalogs when new sources are defined"""

import sys
import json
import os.path
from os.path import join as pjoin
from os.path import dirname as dname
from os.path import basename as bname
import optparse
from io import StringIO

U = None  # Namespace anchor for dasflex.util module, loaded after sys.path 
          # is set via the config file

# ########################################################################## #
# Work around ubuntu apport bugs
if sys.excepthook != sys.__excepthook__:
	if sys.excepthook.__name__ == 'apport_excepthook':
		#sys.stderr.write("Info: disabling Ubuntu's Apport hook\n")
		sys.excepthook = sys.__excepthook__
	else:
		sys.stderr.write("Warning: 3rd party exception hook is active\n")

# ########################################################################## #
# handle output
			
def perr(item):
	"""If input item is bytes encode as utf-8 first"""	
	if not isinstance(item, str):
		item = item.encode('utf-8')
	sys.stderr.write(item)
	sys.stderr.write('\n')

class SimpleLog(object):
	def write(self, sThing):
		sys.stderr.write(sThing)
		sys.stderr.write('\n')

# ########################################################################## #
# Get my config file, boiler plate that has to be re-included in each script
# since the location of the server module is in the config file, not sys.path

def getConf(sConfPath):
	
	if not os.path.isfile(sConfPath):
		if os.path.isfile(sConfPath + ".example"):
			perr(u"Move\n   %s.example\nto\n   %s\nto enable your site\n"%(
				  sConfPath, sConfPath))
		else:
			perr(u"%s is missing\n"%sConfPath)
			
		return None

	fIn = open(sConfPath, 'r')
	
	dConf = {}
	nLine = 0
	for sLine in fIn:
		nLine += 1
		iComment = sLine.find('#')
		if iComment > -1:
			sLine = sLine[:iComment]
	
		sLine = sLine.strip()
		if len(sLine) == 0:
			continue
		
		iEquals = sLine.find('=')
		if iEquals < 1 or iEquals > len(sLine) - 2:
			preLoadError(u"Error in %s line %d"%(sConfPath, nLine))
			fIn.close()
			return None
		
		sKey = sLine[:iEquals].strip()
		sVal = sLine[iEquals + 1:].strip(' \t\v\r\n\'"')
		dConf[sKey] = sVal
	
	fIn.close()
	
	# As a final step, inclued a reference to the config file itself
	dConf['__file__'] = sConfPath
	
	return dConf

# ########################################################################## #
# Update sys.path since config file can change module path

def setModulePath(dConf):
	if 'MODULE_PATH' not in dConf:
		perr(u"Set MODULE_PATH = /dir/containing/dasflex_python_module")
		return False	
	
	lDirs = dConf['MODULE_PATH'].split(os.pathsep)
	for sDir in lDirs:
		if os.path.isdir(sDir):
				if sDir not in sys.path:
					sys.path.insert(0, sDir)
		
	return True

# ########################################################################## #

def getSrcSets(sRoot, dSrcSets, nMaxDepth=20, _n=0):
	"""Walk a directory tree, following symlinks.

	Args:
		sRoot (str): Top level directory to read

		lSources (list): The data structure that will be filled with
			the data source directory names.
	
	Returns (None)
	"""
	
	tSrcFiles = ('flex.json','flexRT.json','das2.d2t','das1.pro')

	_sRoot = sRoot
	if nMaxDepth < 1:
		raise ValueError("In find, nMaxDepth must be at least 1")
	
	nCurDepth = _n + 1
	if nCurDepth > nMaxDepth:
		raise RecursionError("In getSrcSets:", nMaxDepth)
	
	try:
		lItems = os.listdir(_sRoot)
	except OSError as e:
		perr("WARNING:  Couldn't list directory '%s'"%_sRoot)
		return
		
	lItems.sort()
	
	for sItem in os.listdir(_sRoot):
		sPath = os.path.join(_sRoot, sItem)
		
		if os.path.isfile(sPath) and (sItem in tSrcFiles):
			if _sRoot not in dSrcSets:
				dSrcSets[_sRoot] = [sPath]
			else:
				dSrcSets[_sRoot].append(sPath)
			
		elif os.path.isdir(sPath):
			getSrcSets(sPath, dSrcSets, nMaxDepth, nCurDepth)
	
# ########################################################################## #

def _writeFile(fLog, sPath, sOutput):
	#perr("Writing: %s"%sPath)
	sDir = dname(sPath)

	if not os.path.isdir(sDir):
		os.makedirs(sDir)

	fLog.write("Writing: %s"%bname(sPath))
	with open(sPath, 'w') as f:
		f.write(sOutput)

def _writeJsonFile(fLog, sPath, dOutput):
	sOutput = json.dumps(dOutput, indent="  ");
	_writeFile(fLog, sPath, sOutput)


# ########################################################################## #

class MyOptParse(optparse.OptionParser):
	def print_help(self, file=None):
		if file == None:
			file = sys.stdout


		# Help pops before the utility module is loaded, hand code these but be
		# on the lookout for changes.  
		dRep = {
			'das2':'das2.d2t', 'das3':'flex.json', 'das3ws':'flexRT.json', 
			'intern':'internal.json'
		}

		file.write("""
NAME:
   dasflex_cupdate - Update Catalog information after data source changes

SYNOPSIS:
   dasflex_cupdate [options] CONFIG_FILE

DESCRIPTION:
   dasflex_cupdate walks the server catalog area in a bottom up fashion 
   propogating changes to source definitions into higher level catalog 
   nodes.  Specifically this program updates catalog nodes of type:

      Catalog, SourceSet

   as well as the top level listings: catalog.json, das2list.txt, nodes.csv.

   This program is most useful when data source definitions are generated
   by custom mission specific sources and these changes need to be propogated
   to higher level nodes.

OPTIONS:
   -h, --help  Print this help message and exit
	
   -d DIR, --cat-dir=DIR
               Instead of updating the server's catalogs, update an alternate
               external catalog area.

FILES:
   Each dasFlex server is defined by a single top-level configuration file. The
   path to this file must be supplied as a command line parameter.  Any other
   files read are only found via the top-level configuration filel.

SEE ALSO:
   The companion program dasflex_dsdf handles defining catalog nodes using 
   das2-pyserver DSDF files.
"""%dRep)

# ########################################################################## #
def main():
	global U

	sUsage = "dasflex_cupdate [options]"
	psr = MyOptParse(prog="dasflex_sdef", usage="sUsage")

	psr.add_option('-d', '--cat-dir', dest="sCatDir", default=None)

	(opts,lPaths) = psr.parse_args()

	if len(lPaths) != 1:
		perr("The location of the server definition file, dasflex.conf' was not provided.")
		if os.getenv('DASFLEX_PREFIX'):
			perr("Since DASFLEX_PREFIX is set, there's a high probability the "+\
				  "file you're looking for is %s/etc/dasflex.conf ."%os.getenv('DASFLEX_PREFIX'))
		else:
			perr("Use -h for help.")
		return 16
	else:
		sConfPath = lPaths[0]

	dConf = getConf(sConfPath)
	if dConf == None:
		return 17

	if not setModulePath(dConf):   # Set the system path
		return 18

	if not opts.sCatDir:
		opts.sCatDir = dConf['DATASRC_ROOT']

	fLog = SimpleLog()

	sDir = pjoin(opts.sCatDir,'root')
	sRoot = pjoin(opts.sCatDir, 'root.json')
	if not os.path.isfile(sRoot):
		perr("Creating empty catalog root at %s"%sRoot)
		os.makedirs(sDir, 0o755, exist_ok=True)
		dRoot = {
			"version":"0.5","type":"Catalog","label":"Sources",
			"name":"sources",
			"catalog":{}, "title":"Local Root Catalog",
			"separator":":/"
		}
		_writeJsonFile(fLog, sRoot, dRoot)

		# Note, just because root.json was missing doesn't mean that
		# there is nothing else in the catalog.  Go ahead and try
		# to read the rest and thus re-write the root just generated. 
		#perr("Run dasflex_sdef, the examples/define.sh or equivalent to define sources")
		#return 0

	# Load the dasflex.util module
	try:
		mTmp = __import__('dasflex', globals(), locals(), ['util'], 0)
	except ImportError as e:
		perr("Error importing module 'dasflex' using %s\r\n: %s\n"%(
			str(e), opts.sConfig))
		return 19
	try:
		U = mTmp.util
	except AttributeError:
		perr("Server definition: %s"%opts.sConfig)
		perr('No module named dasflex.util under %s\n'%dConf['MODULE_PATH'])
		return 20

	# A source set is just a:
	#
	# (key) path to the containing directory for flex.json, das2.d2t, etc. 
	# (value) path to all the contents of the directory.
	#
	dSrcSets = {}
	getSrcSets(opts.sCatDir, dSrcSets, nMaxDepth=20, _n=0)

	lSrcSets = list(dSrcSets.keys())
	lSrcSets.sort(reverse=True)
	#for sSrcSet in lSrcSets:
	#	print("%s -> %s"%(sSrcSet, dSrcSets[sSrcSet]))

	# Depends on structure built in getSrcSets, not very maintainable
	lLocalSrcIds = []
	
	for sSrcSetDir in lSrcSets:
		sSrcSetFile = sSrcSetDir + '.json'
		sLocalId = sSrcSetDir.replace("%s/root/"%opts.sCatDir, '')
		#print(sLocalId)
		perr("Node Update: %s"%sSrcSetFile)
		U.catalog.makeSrcSet(fLog, dConf, sLocalId, dSrcSets[sSrcSetDir], sSrcSetFile)
		lLocalSrcIds.append(sLocalId)

	# Walk backwards up the tree updating catalogs as you go
	for sLocalId in lLocalSrcIds:
		lUpdates = U.catalog.updateFromSrc(fLog, dConf, opts.sCatDir, sLocalId)
		if not lUpdates:
			return 7
		perr("Node Update: %s"%("\n             ".join(lUpdates)))

	# Recreate the summary listings
	lWrote = U.catalog.updateLists(fLog, dConf, opts.sCatDir)
	if not lWrote:
		return 8
	perr("List Update: %s"%("\n             ".join(lWrote)))

	return 0

# ########################################################################## #
if __name__ == '__main__':
	main()
