#!/usr/bin/env python3
"""Expand source definitions into final form based on the server configuration"""

import sys
import os.path
from os.path import join as pjoin
from os.path import dirname as dname
from os.path import basename as bname
import optparse
import json
from io import StringIO

# WARNING:    
#   Insure these align with the versions dictionary: 
#
#       U.catalog.versions   (line 22)
#   
#   We can't use that source for help text as the arguments from optparse
#   determine the python module path!
_ver_copy = {'Catalog':'0.5', 'SourceSet':'0.1', 'HttpStreamSrc':'0.7'}

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
	#if isinstance(item, str):
	#	sys.stderr.buffer.write(item.encode('utf-8'))
	#	sys.stderr.buffer.write('\n'.encode('utf-8'))
	#else:
	#	sys.stderr.buffer.write(item)
	sys.stderr.write(item)
	sys.stderr.write('\n')

#
# class BufferLog(object):
#	def __init__(self, bTee=False):
#		self.bTee = bTee
#		self.fOut = StringIO()
#
#	def write(self, sThing):
#		if self.bTee: perr("%s"%sThing)
#		self.fOut.write("%s\n"%sThing)
#
#	def getvalue(self):
#		return self.fOut.getvalue()

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
# Writing files #

def _writeFile(fLog, sPath, sOutput):
	if bname(sPath) == 'flex.json':
		perr("Writing: %s"%sPath)
	sDir = dname(sPath)

	if not os.path.isdir(sDir):
		os.makedirs(sDir)

	fLog.write("Writing: %s"%sPath)
	with open(sPath, 'w') as f:
		f.write(sOutput)

def _writeJsonFile(fLog, sPath, dOutput):
	sOutput = json.dumps(dOutput, indent="  ");
	_writeFile(fLog, sPath, sOutput)


# ########################################################################### #

def importUtil(dConf):
	"""Setup the utility module using the global name 'U'
	"""
	global U;
	U = None
	# Load the dasflex.util module
	try:
		mTmp = __import__('dasflex', globals(), locals(), ['util'], 0)
	except ImportError as e:
		perr("importing module 'dasflex' using %s\r\n: %s\n"%(
			str(e), opts.sConfig))
		return False
	try:
		U = mTmp.util
	except AttributeError:
		perr("Server definition: %s"%opts.sConfig)
		perr('No module named dasflex.util under %s\n'%dConf['MODULE_PATH'])
		return False

	return True

# ########################################################################## #

def makeSrcSet(fLog, dConf, sCatRoot, sInRoot, sPath, bSocket, sLocalId = None):
	"""
	Write a source set at the local-id offset from the root output directory
	Args:
		fLog - An object with a .write() member

		dconf - The parsed server configuration file

		sCatRoot - The output area (may not be same as sroot in server config)

		sInRoot - The input path to ignore when generating local ID from paths

		sPath - The DSDF file to read, must be an actual source

		bSocket - Also write a socket data source for this one, ususally this
		   is false for das2 readers since they don't have a keep-alive option

		sLocalId - The local Id of this DSDF, may be null if LocalId is in the
		   DSDF file itself.  Not when call as part a recursive directory read
			it's best if the caller supples this value else DSDFs may be installed
			in the wrong place.

	Returns (int): 
		The number of output files generated
	"""

	#fLog.write("add: CatRoot: %s"%sCatRoot)
	#fLog.write("add: sPath:   %s"%sPath)
	#fLog.write("add: sInRoot: %s"%sInRoot)
	#fLog.write("add: LocalId: %s"%sLocalId)

	if (not os.path.isfile(sPath)) or (not sPath.lower().endswith('.dsdf')) or \
		( bname(sPath) == '_dirinfo_.dsdf'):
		raise ValueError("%s is not a regular dsdf file."%sPath)

	# Use local ID from:  A) cmd line, B) filename, C) relative directory
	if not sLocalId:

		# Check to see if we are getting local IDs from filesystem paths
		if sInRoot:
			n = sPath.find(sInRoot)
			if n < 0:
				perr("Local Root %s does not appear in source path %s"%(
					sInRoot, sPath
				))
			sLocalId = sPath[n+len(sInRoot):].replace(".dsdf",'').replace(".json",'')
			sLocalId = sLocalId.strip(os.sep)

		else:
			sLocalId = U.convdsdf.getLocalId(fLog, dConf, sPath)
			if not sLocalId:
				perr("Local ID not defined in %s nor provided via the command line"%sPath)
				return None
	else:
		sLocalId = sLocalId

	dPaths = U.catalog.sourceFiles(sCatRoot, sLocalId)

	
	# To add extra output filters (PSD, SPICE X-Form) include thier command 
	# definition dictionaries below.
	#lFilters = [dDasSpice, dDasPsd]
	lFilters = []

	#perr("Input:  %s"%sPath)
	lOutput = []
	try:
	#	if sInType == 'dsdf':
		lOutput.append(dPaths['flex'])
		sFormAction = '%s/data'
		dFlex = U.convdsdf.makeGetSrc(fLog, dConf, sPath, sLocalId, lFilters)
		_writeJsonFile(fLog, lOutput[-1], dFlex)
				
		if bSocket:
			lOutput.append(dPaths['flexRT'])
			_writeJsonFile(fLog, lOutput[-1], U.convdsdf.makeSockSrc(fLog, dConf, sPath, sLocalId))
				
		lOutput.append(dPaths['intern'])
		dIntern = U.convdsdf.makeInternal(fLog, dConf, sPath, sLocalId, lFilters)
		_writeJsonFile(fLog, lOutput[-1], dIntern)
				
		lOutput.append(dPaths['das2'])
		_writeFile(fLog, lOutput[-1], U.convdsdf.makeD2t(fLog, dConf, sPath))
				
		sDas1 = U.convdsdf.makeDas1(fLog, dConf, sPath)
		if sDas1: 
			lOutput.append(dPaths['das1'])
			_writeFile(fLog, lOutput[-1], sDas1)
					
		#	else:
		#		lOutput.append(dPaths['flex'])
		#		_writeJsonFile(lOutput[-1], U.convjson.makeFedCat(fLog, dConf, sPath))
		#
		#		lOutput.append(dPaths['intern'])
		#		_writeJsonFile(lOutput[-1], U.convjson.makeInternal(fLog, dConf, sPath))
		#
		#		lOutput.append(dPaths['das2'])
		#		_writeFile(lOutput[-1], U.convjson.makeD2t(fLog, dConf, sPath))
	
			# Read the sources you've written and update the collection
		lOutput.append(dPaths['set'])
		U.catalog.makeSrcSet(fLog, dConf, sLocalId, lOutput, lOutput[-1])
	
		perr("Source Def: %s"%("\n            ".join(lOutput)))

		#sys.exit(117)

	except Exception as e:
		import traceback
		perr('ERROR: %s'%str(e))
		perr(traceback.format_exc())
		return None

	return sLocalId

# ########################################################################## #

def makeSubSets(fLog, dConf, sCatRoot, sInRoot, sDir, bSocket):
	"""
	Make all sources sets at this level and maybe proceed down to a lower level
	"""
	lLocalSrcIds = []
	fLog.write("Reading: %s"%sDir)

	for sItem in os.listdir(sDir):
		if sItem in ('.','..'): continue
		if sItem == '_dirinfo_.dsdf': continue
		
		sSubPath = pjoin(sDir, sItem)
		
		if os.path.isdir(sSubPath):
			lMore = makeSubSets(fLog, dConf, sCatRoot, sInRoot, sSubPath, bSocket)
			if lMore == None:
				return None
			lLocalSrcIds += lMore
		else:
			if not sItem.endswith('.dsdf'): continue

			sLocalId = sDir.replace(sInRoot, '')
			if sLocalId[0] == '/':
				sLocalId = sLocalId[1:]

			# Add the root name of the DSDF into the ID
			sLocalId = sLocalId + "/" + sItem.replace(".dsdf","")

			sLocalId = makeSrcSet(fLog, dConf, sCatRoot, None, sSubPath, bSocket, sLocalId)
			if sLocalId == None:
				return None
			lLocalSrcIds.append(sLocalId)

	return lLocalSrcIds

# ########################################################################## #

def writeCatTitles(fLog, dConf, sCatRoot, sInRoot, sDir):
	"""
	Loop through directory entries adding descriptions to catalogs at
	each level
	"""
	lLocalIds = []

	#fLog.write("writeCatTitles for dir: %s and local root: %s"%(sDir, sInRoot))

	for sItem in os.listdir(sDir):
		sSubItem = pjoin(sDir, sItem)
		if os.path.isdir(sSubItem):
			writeCatTitles(fLog, dConf, sCatRoot, sInRoot, sSubItem)
		else:
			#fLog.write("%s is not a directory"%sItem)
			if sItem != '_dirinfo_.dsdf': continue

			sLocalId = dname(sSubItem).replace(sInRoot, '')
			if not sLocalId:
				fLog.write("Can't import _dirinfo_.dsdf files from the local root.")
				return None
			#fLog.write("sub item: %s, sLocalId: %s"%(sSubItem, sLocalId))
			if sLocalId[0] == '/':
				sLocalId = sLocalId[1:]

			sLocalId = writeACatTitle(fLog, dConf, sCatRoot, sInRoot, sSubItem, sLocalId)
			if sLocalId == None:
				return None

			lLocalIds.append(sLocalId)

	return lLocalIds

# ########################################################################## #

def writeACatTitle(fLog, dConf, sCatRoot, sInRoot, sPath, sLocalId):

	#fLog.write("writeACatTitle for : %s at %s"%(sPath, sLocalId))

	# If sLocalId defined, use it.  Otherwise get it from the source
	if not sLocalId:

		# Check to see if we are getting local IDs from filesystem paths
		if sInRoot:
			sDir = dname(sPath)
			n = sDir.find(sInRoot)
			if n < 0:
				perr("Local Root %s does not appear in source path %s"%(
					sInRoot, sPath
				))
			sLocalId = sDir[n+1:].replace(os.sep, '/')
			#fLog.write("Local ID 1: %s"%sLocalId)
		else:
			sLocalId = U.convdsdf.getLocalId(fLog, dConf, sPath)
			if not sLocalId:
				perr("Local ID not defined in %s nor provided via the command line"%sPath)
				return None
			#fLog.write("Local ID 2: %s"%sLocalId)


	#fLog.write("Local ID 3: %s"%sLocalId)
	sDesc = U.convdsdf.getDescription(fLog, dConf, sPath)
	if sDesc:
		U.catalog.addCatTitle(fLog, dConf, sCatRoot, sLocalId, sDesc)
		return sLocalId
	else:
		return None

# ########################################################################## #

def _maybeAddDirId(lGlobal, lNew):
	"""
	Merge in new lead IDs to walk. This is only needed when a _dirinfo_.dsdf
	is added without sub-nodes.  This is because the catalog will automatically
	be read if a sub item is added.

	For exmaple adding an local id:
	   Juno/WAV
	when:
	   Juno/WAV/Survey

	is also present just results in double reads and chances for catalog 
	corruption.
	"""

	if isinstance(lNew, str):
		lNew = [ lNew ]

	for sNew in lNew:
		bSkip = False
		sTest = sNew + '/'
		for sGlob in lGlobal:
			if sGlob.startswith(sTest):
				bSkip = True
				break
		if not bSkip:
			lGlobal.append(sNew)

# ########################################################################## #
# The program needs way better help than the default OptionParser can provide

class MyOptParse(optparse.OptionParser):
	def print_help(self, file=None):
		if file == None:
			file = sys.stdout

		# Help pops before the utility module is loaded, hand code these but be
		# on the lookout for changes.  
		dRep = {
			'das2':'das2.d2t', 'das3':'flex.json', 'das3ws':'flexRT.json', 
			'intern':'internal.json', 'http_src_ver':_ver_copy['HttpStreamSrc'],
			'src_set_ver':_ver_copy['SourceSet']
		}

		file.write("""
NAME:
   dasflex_sdef - Create sets of related data source definitions

SYNOPSIS:
   dasflex_sdef [options] [FILE_OR_DIR1 FILE_OR_DIR2 ...]

DESCRIPTION:
   dasflex_sdef adds a data source collection to a server catalog.  For each
   DSDF input file, multiple output catalog files are generated, typically:

      root/$LOCAL_ID.json          - A SourceSet %(src_set_ver)s catalog node
      root/$LOCAL_ID/%(das2)s      - A das v2.2 source description 
      root/$LOCAL_ID/%(das3)s     - An HttpStreamSrc %(http_src_ver)s catalog node 
      root/$LOCAL_ID/%(intern)s - Internal processing instructions

   The LOCAL_ID value is critical to properly organizing data sources. It is
   normally hieractical, for example:
   
       LOCAL_ID=Juno/Wav/Uncalibrated/HRS

   The LOCAL_ID can be provided inside source definition files and on the 
   command line:

      localId = Value      DSDF file

      -l ID                Command Line, single item
      -d ROOT_DIR          Command Line, relative to some root directory

   No matter the source, the LOCAL_ID must be usable as a legal relative
   directory name as it's lower-cases version defines the path to the data
   source files from the server root. The full elements are used to label
   catalog notes.  Typically LOCAL_IDs from a 3-level hierachy that organizes
   sources by mission name, then by instrument name and finally by specific
   data source, but this is merely a convention.

   If a "__dirinfo__.dsdf" file in encounted in a directory leading to a data
   source dsdf file, then the "description" element in that file will be used
   in the corresponding catalog node.

   The input FILE_OR_DIR values may be omitted with '-d'.  In that case 
   any sub-directory below the IN_ROOT is taken to be part of the LOCAL_ID.

OPTIONS:
   -h, --help  Print this help message and exit
	
   -c FILE, --config=FILE
               Use FILE as the dasflex.conf configuration instead of locating
               it via the environment variable DASFLEX_PREFIX

   -d IN_ROOT, --dir-to-id IN_ROOT
               Useful for importing DSDFs from an existing das2 server.  Do not
               look in DSDFs for a 'localId' property.  Instead assume that the
               ID is defined by the relative path from the directory ROOT. Also
               assume that the filename provides the last component of the
               local ID.

   -l ID, --local-id=ID
               Provide the local ID of the data source via the command line.
               This overrides any value provided by '-d' or in the source file
               itself. Not compatable with multiple inputs.

   -o DIR, --out-dir=DIR
               Unless source definitions are to be installed (-I), they are
               normally written to the current directory.  Use this option to
               select an alternate, non-install, output directory.

   -I, --install
               Install the source definition in the catalog directory for the
               the server defined by the configuration file.  Without this
               option, all runs are test runs.

   -f, --formats
               A comma separated list of additional formats to provide. Using
               'csv,cdf' will add UI definitions for CSV and CDF files, and
               will also install triggers for enabling CSV and CDF output 
               converters. (Not Yet Implimented)

ENVIRONMENT:
   If present, the environment variable DASFLEX_PREFIX is used to locate the
   server configuration file at $DASFLEX_PREFIX/etc/dasflex.conf.

EXAMPLES:
   1. Processing a das2 DSDF file that has localId keyword defined as 
      'Juno/WAV/Survey' within the file using the command:

         dasflex_add survey.dsdf

      will create at least the following files:

         ./root/juno/wav/survey.json 
         ./root/juno/wav/survey/%(das2)s    # If source is das v2.2 compatable
         ./root/juno/wav/survey/%(das3)s  

      Other source definitions files may be created for compatability with
      other APIs, depending on the server configuration.

   2. Import all DSDFs for a server in one command using relative file paths to
      define the Local ID.  First to a test directory, then to the live catalog.

         dasflex_add -o test -d /var/www/das2srv/datasets
         dasflex_add -I -d /var/www/das2srv/datasets

SEE ALSO:
   The DSDF format is defined by das2 ICD at DOI: 10.5281/zenodo.3588534
"""%dRep)

	# The following options were remove to generate a paired down version
	# just for DSDFS imports:

	#OPTIONS:
	# -W, --no-web-sock
   #             Even if the source supports realtime operations and $WEBSOCK_URI
   #             is defined in the server configuration, don't output or link a
   #             WebSockSrc catalog object.
   # 
   # -H, --no-hapi 
   #             Even if the source and the server support the HAPI protocol,
   #             don't output or link a HAPI v2.0 info object.
   # 
   # -V, --no-vo Even if the source and the server support the IVOA datalink 
   #             protocol, don't output or link an IVOA service definition.
   # 
   # --no-gen    When processing JSON source templates, only expand $include
   #             sections, don't expand automatically $generate'd definitions.
   #             This is incompatable with --install

	# EXAMPLES:
	#   1. Processing a das2 DSDF file that has localId keyword defined as 
	#      'Juno/WAV/Survey' within the file using the command:
	#
	#         dasflex_sdef survey.dsdf
	#
	#      will create at least the following files:
	#
	#         ./root/juno/wav/survey.json 
	#         ./root/juno/wav/survey/%(das2)s    # If source is das v2.2 compatable
	#         ./root/juno/wav/survey/%(das3)s  
	#         ./root/juno/wav/survey/%(das3ws)s # If real-time operations supported
	#
	#      Other source definitions files may be created for compatability with
	#      other APIs, depending on the server configuration.
	#	
	#    2. Process a JSON template for the dataset that does not define a local ID
	#       and install it for use by the server:
	# 
	#          dasflex_sdef -i -l Voyager/1/PWS/Waveform waveform.json
	# 
	#       The resulting data source set will be visible at:
	# 
	#          $SERVER_URL/source/voyager/1/pws/waveform.json
	# 
	#       and the %(das2)s file with be available at:
	# 
	#          $SERVER_URL?server=dsdf&dataset=Voyager/1/PWS/Waveform         
	# 
	#       In the paths above, $SERVER_URL is defined in dasflex.conf.
	# 
	# SEE ALSO:
	#    The DSDF format is defined by das2 ICD at DOI: 10.5281/zenodo.3588534
	# 
	#    The json template format is yet to be codified, see examples distributed
	#    with das2py-server.

# ########################################################################## #

def main():
	global das2, U

	sUsage = "dasflex_sdef [options] INPUT"
	psr = MyOptParse(prog="dasflex_sdef", usage="sUsage")

	sDef = None
	if os.getenv('DASFLEX_CONFIG'):
		sDef = os.getenv('DASFLEX_CONFIG')
	psr.add_option('-c', '--config', dest="sConfig", default=sDef)

	psr.add_option('-o', '--out-dir', dest="sOutRoot", default='.')
	psr.add_option('-l','--local-id', dest="sLocalId", default=None)
	psr.add_option('-d','--dir-to-id', dest="sInRoot", default=None)
	#psr.add_option(
	#	'-W', '--no-web-sock', action="store_false", dest='bSocSrc', default=True
	#)
	psr.add_option(
		'-I', '--install', action="store_true", dest="bInstall", default=False
	)

	(opts,lInPaths) = psr.parse_args()
	opts.bSocSrc = False
	opts.bIncOnly = False

	if len(lInPaths) < 1:
		if opts.sInRoot and (len(opts.sInRoot) > 0):
			if opts.sLocalId:
				perr("ERROR: Argument '-l' can not be used with directory processing");
				return 13
			if not os.path.isdir(opts.sInRoot):
				perr("ERROR: DSDF root directory '%d' is not a directory."%opts.sInRoot)
				return 13

			perr("INFO: Reading all dsdf files under %s"%opts.sInRoot)
			lInPaths = [opts.sInRoot]
		else:
			perr("ERROR: No inputs specified")
			return 13
	
	if (len(lInPaths) > 1) and opts.sLocalId:
		perr("Argument '-l' can only be used when processing files one at a time.")
	
	if opts.sConfig == None:
		perr("Server configuration file not specified")
		return 13
	if not os.path.isfile(opts.sConfig):
		perr("Configuration file %s doesn't exist"%opts.sConfig)
		return 13

	dConf = getConf(opts.sConfig)
	if dConf == None:            return 13
	if not setModulePath(dConf): return 13
	if not importUtil(dConf):    return 13
		
	#fLog = BufferLog(True) # True = Tee the output to stderr
	fLog = SimpleLog()
	
	sCatRoot = None
	if opts.bInstall: 
		if opts.sOutRoot != '.':
			fLog.write(
				"ERROR: The install option (-I) and output directory option (-o) "+\
				"conflict.  Use -h for help."
			)
			return 21
		sCatRoot = dConf['DATASRC_ROOT']
	else:
		sCatRoot = opts.sOutRoot


	# Pass 1: Generate/Update source sets from regular *.dsdf files
	lLocalSrcIds = []
	for sItem in lInPaths:
		if os.path.isdir(sItem):
			lMore = makeSubSets(fLog, dConf, sCatRoot, opts.sInRoot, sItem, opts.bSocSrc)
			if lMore == None:
				return 13
			lLocalSrcIds += lMore
		else:
			sLocalId = makeSrcSet(
				fLog, dConf, sCatRoot, opts.sInRoot, sItem, opts.bSocSrc, opts.sLocalId
			)
			if sLocalId == None:
				return 13
			lLocalSrcIds.append(sLocalId)
	

	# Pass 2: Write the _dirinfo_.dsdf we find to catalogs, making them if needed
	for sItem in lInPaths:
		if os.path.isdir(sItem):
			lMore = writeCatTitles(fLog, dConf, sCatRoot, opts.sInRoot, sItem)
			if lMore == None:
				return 13
			_maybeAddDirId(lLocalSrcIds, lMore)
		else:
			if bname(sItem) != '_dirinfo_.dsdf': continue	
			sLocalId = writeACatTitle(fLog, dConf, sCatRoot, opts.sInRoot, sItem, opts.sLocalId)
			if sLocalId == None:
				return 13
			_maybeAddDirId(lLocalSrcIds, sLocalId)


	# Part 3: Walk backwards up the tree updating catalogs as you go
	for sLocalId in lLocalSrcIds:
		lUpdates = U.catalog.updateFromSrc(fLog, dConf, sCatRoot, sLocalId)
		if not lUpdates:
			return 7
		perr("Node Update: %s"%("\n             ".join(lUpdates)))


	# Part 4: Generate new listings after the import
	if len(lLocalSrcIds) == 0:
		perr("No changes. Root data source lists not updated")
		return 0
	else:
		perr("Updating global lists")

	lWrote = U.catalog.updateLists(fLog, dConf, sCatRoot)
	if not lWrote:
		return 8
	perr("List Update: %s"%("\n             ".join(lWrote)))
		
	return 0

# ########################################################################## #
if __name__ == '__main__':
	main()
