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
	if isinstance(item, str):
		sys.stderr.buffer.write(item.encode('utf-8'))
		sys.stderr.buffer.write('\n'.encode('utf-8'))
	else:
		sys.stderr.buffer.write(item)

class BufferLog(object):
	def __init__(self, bTee=False):
		self.bTee = bTee
		self.fOut = StringIO()

	def write(self, sThing):
		if self.bTee: perr("%s\n"%sThing)
		self.fOut.write("%s\n"%sThing)

	def getvalue(self):
		return self.fOut.getvalue()

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

def _writeFile(sPath, sOutput):
	#perr("Writing: %s"%sPath)
	sDir = dname(sPath)

	if not os.path.isdir(sDir):
		os.makedirs(sDir)

	with open(sPath, 'w') as f:
		f.write(sOutput)

def _writeJsonFile(sPath, dOutput):
	sOutput = json.dumps(dOutput, indent="  ");
	_writeFile(sPath, sOutput)


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
   dasflex_sdef [options] FILE1 [FILE2 FILE3 ...]

DESCRIPTION:
   dasflex_sdef adds a data source collection to a server catalog.  Multiple
   input FILEs *.dsdf is parsed to produced the output.  The output consists
   of at least four files:

      root/$LOCAL_ID.json          - A SourceSet %(src_set_ver)s catalog node
      root/$LOCAL_ID/%(das2)s      - A das v2.2 source description 
      root/$LOCAL_ID/%(das3)s     - An HttpStreamSrc %(http_src_ver)s catalog node 
      root/$LOCAL_ID/%(intern)s - Internal processing instructions

   Other outputs may be added to the basic forms above for real-time support
   and external system compatability.

   The LOCAL_ID value is critical to properly organizing data sources. It can
   be provided inside source definition files and on the command line:

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

OPTIONS:
   -h, --help  Print this help message and exit
	
   -c FILE, --config=FILE
               Use FILE as the dasflex.conf configuration instead of locating
               it via the environment variable DASFLEX_PREFIX

   -o DIR, --out-dir=DIR
               Unless source definitions are to be installed (-I), they are
               normally written to the current directory.  Use this option to
               select an alternate, non-install, output directory.

   -d ROOT, --dir-to-id ROOT
               Useful for importing DSDFs from an existing das2 server.  Do not
               look in DSDFs for a 'localId' property.  Instead assume that the
               ID is defined by the relative path from the directory ROOT. Also
               assume that the filename provides the last component of the
               local ID.

   -l ID, --local-id=ID
               Provide the local ID of the data source via the command line.
               This overrides any value provided by '-d' or in the source file
               itself. Not compatable with multiple inputs.

   -n, --no-catalog
               Don't try to create or update any catalog nodes that would lead
               to the SourceSet node.

   -I, --install
               Install the source definition in the catalog directory for the
               the server defined by the configuration file.  Without this
               option, all runs are test runs.

   -f, --formats
               A comma separated list of additional formats to provide. Using
               'csv,cdf' will add UI definitions for CSV and CDF files, and
               will also install triggers for enabling CSV and CDF output 
               converters.

ENVIRONMENT:
   If present, the environment variable DASFLEX_PREFIX is used to locate the
   server configuration file at $DASFLEX_PREFIX/etc/dasflex.conf.

EXAMPLES:
   1. Processing a das2 DSDF file that has localId keyword defined as 
      'Juno/WAV/Survey' within the file using the command:

         dasflex_sdef survey.dsdf

      will create at least the following files:

         ./root/juno/wav/survey.json 
         ./root/juno/wav/survey/%(das2)s    # If source is das v2.2 compatable
         ./root/juno/wav/survey/%(das3)s  

      Other source definitions files may be created for compatability with
      other APIs, depending on the server configuration.

   2. Import all DSDFs for a server in one command using relative file paths to
      define the Local ID:

         ROOT=/var/www/das2srv/datasets
         dasflex_sdef -d $ROOT $(find $ROOT -name "*.dsdf")

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
def main():
	global das2, U

	sUsage = "dasflex_sdef [options] INPUT"
	psr = MyOptParse(prog="dasflex_sdef", usage="sUsage")

	sDef = None
	if os.getenv('DASFLEX_PREFIX'):
		sDef = pjoin(os.getenv('DASFLEX_PREFIX'), 'etc', 'dasflex.conf')

	psr.add_option('-c', '--config', dest="sConfig", default=sDef)
	psr.add_option('-o', '--out-dir', dest="sOutRoot", default='.')
	psr.add_option('-l','--local-id', dest="sLocalId", default=None)
	psr.add_option('-d','--dir-to-id', dest="sLocalRoot", default=None)
	psr.add_option(
		'', '--no-cat', action="store_false", dest="bNewCat", default=True
	)
	#psr.add_option(
	#	'-W', '--no-web-sock', action="store_false", dest='bSocSrc', default=True
	#)
	#psr.add_option(
	#	'', '--no-gen', action="store_true", dest="bIncOnly", default=False
	#)
	psr.add_option(
		'-I', '--install', action="store_true", dest="bInstall", default=False
	)

	(opts,lInPaths) = psr.parse_args()
	opts.bSocSrc = False
	opts.bIncOnly = False

	if len(lInPaths) < 1:
		perr("No data source file specified, use -h for help.")
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
		
	fLog = BufferLog(True) # True = Tee the output to stderr
	
	lLocalSrcIds = [] # Save list of source IDs for second pass work

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

	# Run processing in multiple passes:
	#
	# Pass 1) Generate/Update sources sets from *.dsdf files
	# Pass 2) Generate/Update catalog files 
	# Pass 3) Fill in any missing catalog points up to the root with minimal stubs

	# Pass 1:

	for sPath in lInPaths:

		if (not os.path.isfile(sPath)) or (not sPath.lower().endswith('.dsdf')):
			continue

		if bname(sPath) == '_dirinfo_.dsdf': continue  # Handle in pass 2
		
		# Use local ID from:  A) cmd line, B) filename, C) relative directory
		if not opts.sLocalId:

			# Check to see if we are getting local IDs from filesystem paths
			if opts.sLocalRoot:
				n = sPath.find(sLocalRoot)
				if n < 0:
					perr("Local Root %s does not appear in source path %s"%(
						opts.sLocalRoot, sPath
					))
				sLocalId = sPath[n+1:].replace(".dsdf",'').replace(".json",'')
				sLocalId = sLocalId.strip(os.sep)

			else:
				sLocalId = U.convdsdf.getLocalId(fLog, dConf, sPath)
				if not sLocalId:
					perr("Local ID not defined in %s nor provided via the command line"%sPath)
					return 22
		else:
			sLocalId = opts.sLocalId

		dPaths = U.catalog.sourceFiles(sCatRoot, sLocalId)
	
		# To add extra output filters (PSD, SPICE X-Form) include thier command 
		# definition dictionaries below.
		#lFilters = [dDasSpice, dDasPsd]
		lFilters = []

		perr("Input:  %s %s"%(opts.sConfig, sPath))
		lOutput = []
		try:
		#	if sInType == 'dsdf':
			lOutput.append(dPaths['flex'])
			sFormAction = '%s/data'
			dFlex = U.convdsdf.makeGetSrc(fLog, dConf, sPath, sLocalId, lFilters)
			_writeJsonFile(lOutput[-1], dFlex)
				
			if opts.bSocSrc:
				lOutput.append(dPaths['flexRT'])
				_writeJsonFile(lOutput[-1], U.convdsdf.makeSockSrc(fLog, dConf, sPath, sLocalId))
				
			lOutput.append(dPaths['intern'])
			dIntern = U.convdsdf.makeInternal(fLog, dConf, sPath, sLocalId, lFilters)
			_writeJsonFile(lOutput[-1], dIntern)
				
			lOutput.append(dPaths['das2'])
			_writeFile(lOutput[-1], U.convdsdf.makeD2t(fLog, dConf, sPath))
				
			sDas1 = U.convdsdf.makeDas1(fLog, dConf, sPath)
			if sDas1: 
				lOutput.append(dPaths['das1'])
				_writeFile(lOutput[-1], sDas1)
					
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
			U.catalog.makeSrcSet(dConf, sLocalId, lOutput, lOutput[-1])
	
			perr("Source Def: %s"%("\n            ".join(lOutput)))
	
		except Exception as e:
			import traceback
			perr('%s'%fLog.getvalue())
			perr('ERROR: %s'%str(e))
			perr(traceback.format_exc())
			return 22

		lLocalSrcIds.append(sLocalId)

	# Handle catalog updates if desired...
	if not opts.bNewCat:
		return 0

	# Write in the _dirinfo_.dsdf entries
	for sPath in lInPaths:

		if bname(sPath) != '_dirinfo_.dsdf': continue

		perr("Input:  %s %s"%(opts.sConfig, sPath))

		# If sLocalId defined, use it.  Otherwise get it from the source
		if not opts.sLocalId:

			# Check to see if we are getting local IDs from filesystem paths
			if opts.sLocalRoot:
				sDir = dname(sPath)
				n = sDir.find(sLocalRoot)
				if n < 0:
					perr("Local Root %s does not appear in source path %s"%(
						opts.sLocalRoot, sPath
					))
				sLocalId = sDir[n+1:].replace(os.sep, '/')
			else:
				sLocalId = U.convdsdf.getLocalId(fLog, dConf, sPath)
				if not sLocalId:
					perr("Local ID not defined in %s nor provided via the command line"%sPath)
					return 22
		else:
			sLocalId = opts.sLocalId

		sDesc = U.convdsdf.getDescription(fLog, dConf, sPath)
		if sDesc:
			U.catalog.addCatTitle(dConf, sCatRoot, sLocalId, sDesc)


	# Walk backwards up the tree updating catalogs as you go
	for sLocalId in lLocalSrcIds:
		lUpdates = U.catalog.updateFromSrc(dConf, sCatRoot, sLocalId)
		if not lUpdates:
			return 7
		perr("Node Update: %s"%("\n             ".join(lUpdates)))

	# Recreate the summary listings
	lWrote = U.catalog.updateLists(dConf, sCatRoot)
	if not lWrote:
		return 8
	perr("List Update: %s"%("\n             ".join(lWrote)))
		
	return 0

# ########################################################################## #
if __name__ == '__main__':
	main()
