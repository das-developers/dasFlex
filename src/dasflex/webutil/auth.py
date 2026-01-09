"""Handle Das2 Authentication and Authorization"""

import os
import base64
import crypt
import os.path

import unittest

import das2

from . import command

AUTH_SUCCESS = 0
AUTH_FAIL    = 1
AUTH_SRV_ERR = 2

# ########################################################################### #
# Helpers #

def _getElement(fLog, d, l):
	if not _hasElement(d, l):
		fLog.write("   ERROR: Could not locate dictionary element: %s"%str(l))
		return None

	for i in range(len(l)):
		if l[i] not in d:
			return None

		d = d[l[i]]

	return d

def _isElTrue(d, l):
	"""Return true if a nested set of dictionaries has the given key
	and the key evaluates to true
	"""
	for i in range(len(l)):
		if l[i] not in d:
			return False
		d = d[l[i]]
	if d: return True
	else: return False

# ########################################################################### #
# Authorization by remote address                                             #
# ########################################################################### #

def _mkMask(fLog, nBytes, nOnesBits):
	"""Generate a bytearray that starts with all binary 1's and then switches to 0's 

	Args:
		fLog - An object with a .write method that takes as string
		nBytes - The number of bytes (not bits) in the output bytearray
		nOnesBits - In binary, this many bits will be set to 1 after that
			all remaining bits in the the returned bytearray will be 0.

	Returns:
		bytearray
	"""

	xRet = bytearray([0]*nBytes)

	if (nOnesBits / 8) > nBytes:
		fLog.write("Not enough output bytes for %d 1's bits"%nOnesBits)
		return None

	if nOnesBits < 0:
		fLog.write("Negative number of 1's bits: %d "%nOnesBits)
		return None

	# Start with full byte setting, depends on truncation
	for i in range(nOnesBits // 8):
		xRet[i] = 0xFF

	# Handle the last partial byte's worth of bits
	if ((nOnesBits / 8) - (nOnesBits // 8)) > 0:
		
		i = nOnesBits // 8  # Index depends on truncation

		nLeft = nOnesBits - ((nOnesBits // 8) * 8)

		# "Big-endian" bits mapping
		dRep = { 1: 0x80, 2: 0xC0, 3: 0xE0, 4: 0xF0, 5: 0xF8, 6: 0xFC, 7: 0xFE }

		xRet[i] = dRep[nLeft]

	return xRet


def _parseIP4Address(fLog, sAddr):
	"""Returns: A bytearray containing the address"""

	if not sAddr:
		fLog.write("Empty IPv4 address '%s'"%sAddr)
		return None

	lParts = [s.strip() for s in sAddr.split('.')]
	if len(lParts) == 0 or len(lParts) > 4:
		fLog.write("Empty IPv4 address '%s'"%sAddr)
		return None		

	xAddr = bytearray([0]*4)

	for i in range(len(lParts)):
		if not lParts[i]:
			fLog.write("Invalid IPv4 address '%s'"%sAddr)
		try:
			n = int(lParts[i], 10)
		except ValueError:
			fLog.write("Invalid IPv4 address '%s"%sAddr)
			return None

		xAddr[i] = n

	return xAddr
	

def _parseIP6Address(fLog, sAddr):
	"""Parse an IPv6 address with standard shortcuts (aka :: ). Assumes hexdecimal
	"""

	if not sAddr:
		fLog.write("Empty IPv6 address '%s'"%sAddr)
		return None


	lSides = sAddr.split('::')
	sFront = lSides[0].strip()
	if len(lSides) == 1:
		sBack = ''
	elif len(lSides) == 2:
		sBack = lSides[1].strip()
	else:
		fLog.write("Invalid IPv6 address '%s'"%sAddr)
		return None

	lDest = [0]*8; # There are 8 16-bit sections to an IPv4 address

	lFront = []
	lBack = []
	if len(sFront) > 0: lFront = [s.strip() for s in sFront.split(':') ]
	if len(sBack) > 0:  lBack =  [s.strip() for s in sBack.split(':')  ]

	if (len(lFront) + len(lBack)) > 8:
		fLog.write("Invalid IPv6 address '%s'"%sAddr)
		return None		
	
	i = 0
	for sPart in lFront:
		try:
			n = int(sPart, 16)
		except ValueError:
			fLog.write("Invalid IPv6 address '%s'"%sAddr)
			return None

		lDest[i] = n
		i += 1

	i = 7
	for sPart in reversed(lBack):
		try:
			n = int(sPart, 16)
		except ValueError:
			fLog.write("Invalid IPv6 address '%s'"%sAddr)
			return None

		lDest[i] = n
		i -= 1

	for n in lDest:
		if (n > 0xFFFF) or (n < 0):
			fLog.write("Invalid IPv6 address '%s'"%sAddr)
			return None


	lBytes = [0]*16;
	for i in range(8):
		lBytes[2*i]     = (lDest[i] >> 8) & 0xFF
		lBytes[2*i + 1] = lDest[i] & 0xFF

	return bytearray(lBytes)

def _parseIP4Range(fLog, sNet):
	"""Parse an IPv4 network string of *decimal* digits into two bytearray objects"""

	if not sNet:
		fLog.write("Empty network address provided")
		return (None, None)

	lRng = [s.strip() for s in sNet.split('/')]
	sNet = lRng[0]

	if len(sNet) == 0:
		fLog.write("Empty network address portion in '%s'"%sNet)
		return (None, None)

	xNet = _parseIP4Address(fLog, sNet)

	sSig = ""
	if len(lRng) > 1:
		sSig = lRng[1]

	if len(sSig) == 0:
		xMask = bytearray([1]*4)
	else:
		try:
			nSig = int(sSig,10)
		except ValueError:
			fLog.write("Couldn't convert network significant bits in network range %s, ")
			return (None, None)
		xMask = _mkMask(fLog, 4, nSig)
		if not xMask:
			return (None, None)

	xMaskNet = bytearray(
		[a & m for a, m in zip(xNet, xMask)] # 'cause "xNet & xMast" would be too easy :(
	)

	return (xMaskNet, xMask)


def _parseIP6Range(fLog, sNet):
	"""Parse an IPv6 network string of *hexidecimal* digits into two bytearray
	objects.

	Args:
		fLog - A logger object

		sNet - A string in standard IPv6 forms, optionally followed by the number
			of network bits in the address.  Some examples:
			::1  ::1/128  2620:0:e50::/48 2620:0000:0e50:0000:0000:0000:0000:000/48

	Returns: ( Network - bytearray, Netmask - bytearray)
		The first array contains the network portion of the range, the second
		contains the network mask.  If the address could net be parsed,
		(None,None) is returned
	"""

	if not sNet:
		fLog.write("Empty network address provided")
		return (None, None)

	lRng = [s.strip() for s in sNet.split('/')]
	sNet = lRng[0]

	if len(sNet) == 0:
		fLog.write("Empty network address portion in '%s'"%sNet)
		return (None, None)

	xNet = _parseIP6Address(fLog, sNet)

	sSig = ""
	if len(lRng) > 1:
		sSig = lRng[1]

	if len(sSig) == 0:
		xMask = bytearray([1]*16)
	else:
		try:
			nSig = int(sSig,10)
		except ValueError:
			fLog.write("Couldn't convert network significant bits in network range %s, ")
			return (None, None)
		xMask = _mkMask(fLog, 16, nSig)

	xMaskNet = bytearray(
		[a & m for a, m in zip(xNet, xMask)] # 'cause "xNet & xMast" would be too easy :(
	)

	return (xMaskNet, xMask)

def authByAddress(fLog, sAddr, ranges):
	"""Check to see if an address is in a set of address ranges.

	Works with intermixed IPv6 and IPv4 addresses.

	TODO: Add host name checks if the end user wants to trust DNS.

	Args:
		sAddr - The address to check.  Assumed to be an IPv4 or IPv6 range

		ranges - Either a whitespace separated list of address ranges, or an
			actual python list containing the forms:
					 
		    DDD.DDD.DDD.DDD/bits
		    HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH/bits

		    Common IPv4 and IPv6 short forms are acceptable, for example:

		    192.168/16
		    ::1
		    2620:0:e50::/48

		fLog - Anything with 
	"""

	if not sAddr:
		fLog.write("Empty address")
		return False

	if not isinstance(ranges, list): 
		ranges = [s.strip() for s in ranges.split() ]
		ranges = [s for s in ranges if len(s) > 0]

	if len(ranges) == 0:
		return False

	if ':' in sAddr:
		xAddr = _parseIP6Address(fLog, sAddr)
		if not xAddr: return False

		for sRng in ranges:
			if ':' in sRng:
				(xRng, xMask) = _parseIP6Range(fLog, sRng)
				if not xRng: return False

				# Bytearray doesn't overload '&', so this is  "xAddr & aMask" in 
				# much less readable form :-( 
				xMaskAddr = bytearray( [a & m for a, m in zip(xAddr, xMask)] )

				if xMaskAddr == xRng:
					return True

	else:
		xAddr = _parseIP4Address(fLog, sAddr)
		if not xAddr: return False

		for sRng in ranges:
			if ':' not in sRng:
				(xRng, xMask) = _parseIP4Range(fLog, sRng)
				if not xRng: return False

				xMaskAddr = bytearray( [a & m for a, m in zip(xAddr, xMask)] )

				if xMaskAddr == xRng:
					return True

	return False


# ########################################################################### #
# Authorization by Query coordinate range                                     #
# ########################################################################### #

def _ageToTime(fLog, sResource, sAge):
	sAge = sAge.strip()
	
	dtLockPt = das2.DasTime.now()
	bAdjusted = False
	
	try:
		sAccmVal = ""
		for c in sAge:
			c = c.lower()
			if c.isdigit():
				sAccmVal += c
			elif c == 'y':
				if sAccmVal != "":
					nDec = int(sAccmVal, 10)
					dtLockPt.adjust(-nDec)
					sAccmVal = ''
					bAdjusted = True
			elif c == 'm':
				if sAccmVal != "":
					nDec = int(sAccmVal, 10)
					dtLockPt.adjust(0, -nDec)
					sAccmVal = ''
					bAdjusted = True
			elif c == 'd':
				if sAccmVal != "":
					nDec = int(sAccmVal, 10)
					dtLockPt.adjust(0, 0, -nDec)
					sAccmVal = ''
					bAdjusted = True
			elif c == 'h':
				if sAccmVal != "":
					nDec = int(sAccmVal, 10)
					dtLockPt.adjust(0, 0, 0, -nDec)
					sAccmVal = ''
					bAdjusted = True
			else:
				raise ValueError("Unexpected Units value '%s', in '%s'"%(c, sAge))
				
	except ValueError as e:
		bAdjusted = False
		
	if not bAdjusted:
		fLog.write("   Authorization: ERROR! In AGE value '%s' for %s"%(
		           sAge, sResource))
		return None
	else:
		return dtLockPt


def _getTime(fLog, sTime, sUnits):
	"""Handle things like 'age 1y6m3d' as well struct time and epoch time parsing

	Returns: (dasTime, bParseErr)
		If the returned dasTime is None, but bError is false this is simply
		not a time, but there was no error parsing what looked to be a time
	"""
	if sTime.lower() == 'age':
		dt = _ageToTime(fLog, sUnits)
		if dt == None:
			return (None, True)  # Was a time, but couldn't parse
	
	if sUnits == '': # No units, just see if it's parseable as a time string 
		try:
			dt = das2.DasTime(sTime)
			return (dt, False)
		except:
			return (None, False)  # Not a time string, but not an error

	elif sUnits.lower() == 'utc':  # Should be a time string
		try:
			dt = das2.DasTime(sTime)
			return (dt, False)
		except ValueError:
			return (None, True)

	elif das2.convertible(sUnits, 'us2000'):  # An epoch time
		try:
			dt = das2.DasTime(float(sTime), sUnits)
			return (dt, False)
		except ValueError:
			return (None, True)

	else:                    # Not a time at all
		return (None, False)


def _parseValue(fLog, sValue):
	"""
	Parse a value allowing for special strings such as "age 6m"

	Returns: A das2.Quantity (.value, .units), the value may be a DasTime.
	  or None if the value was not parsable
	"""

	if not sValue:
		return None

	# If it doesn't start with a number, assume it's a special string
	sValue = sValue.strip()
	if len(sValue) == 0:
		return None

	sNumber, sUnits = "",""
	lValue = sValue.split()
	sNumber = lValue[0]
	if len(lValue) > 1:
		sUnits = " ".join(lValue[1:])

	(dt, bParseErr) = _getTime(fLog, sNumber, sUnits)
	if dt != None:
		return das2.Quantity(dt, "utc")
	elif bParseErr:
		return None
	else:
		return das2.Quantity(float(sNumber), sUnits)


def _compare(fLog, userval, sCmp, testval):

	if userval.units != testval.units:
		testval.value = das2.convert(testval.value, testval.units, userval.units)

	sCmp = sCmp.lower()
	if sCmp == "le":
		if userval.value <= testval.value: return AUTH_SUCCESS
	elif sCmp == "ge":
		if userval.value >= testval.value: return AUTH_SUCCESS
	elif sCmp == "lt":
		if userval.value < testval.value: return AUTH_SUCCESS
	elif sCmp == "gt":
		if userval.value > testval.value: return AUTH_SUCCESS
	elif sCmp == 'eq':
		if userval.value == testval.value: return AUTH_SUCCESS
	else:
		fLog.write("   Authorization: Unknown comparison operator %s", sCmp)
		return AUTH_SRV_ERR

	return AUTH_FAIL

def authByCoords(dConf, fLog, lExpect, dParams):
	"""
	Handle authorization by query parameters.  This is commonly used to
	allow a certian time range of data to be public, but to close off newer
	data.  However, *any* parameter value can be checked.

	Operation:

	  1. Entries are checked *in order*.  
	  2. At least one check must succeeded.
	  3. All checks marked as required must succeed.

	How to generate an OR list of query requirements (this is the deafult):

	  A required = false (the default)
	  B required = false 
	  C required = false

	How to generate an AND list of query requirements

	  A required = true
	  B required = true
	  C required = true

	Success is defined as:

	  1. At least one check passed
	  2. and all required checks passed

	Args:
	  dConf - The server configuration

	  fLog - A logger

	  lExpect - The list of query expectations, each one is a dictionary of
	    one of the forms 
	       {"value":TEMPLATE, "compare":OP, "to":TEST_VALUE}
	       {"range":TEMPLATE, "compare":OP, "to":TEST_RANGE} (not yet implemented)

	  dParams - The query parameters *after* and translations are applied and
	    and defaults are added

	Returns one of: AUTH_SUCCESS, AUTH_FAIL, AUTH_SRV_ERR
	"""
	
	nSuccess = 0

	for dExpect in lExpect:
		
		if 'range' in dExpect:
			fLog.write("   Authorization: Range checks not yet impelmented")
			return AUTH_SRV_ERR

		for sElm in ('value', 'compare', 'to'):
			if sElm not in dExpect:
				fLog.write("   Authorization: '%s' element missing query check"%sElm)
				return AUTH_SRV_ERR

		sValue = command.substitute(fLog, dExpect['value'], dParams)
		val = _parseValue(fLog, sValue)           # Should return a Quantity
		test  = _parseValue(fLog, dExpect['to'])  # should return a Quantity
		if (not test) or (not val):
			return AUTH_SRV_ERR

		sCmp = dExpect['compare']
		nRet = _compare(val, sCmp, test)

		if nRet == AUTH_SRV_ERR:
			return AUTH_SRV_ERR

		if nRet == AUTH_SUCCESS:
			nSuccess += 1
		else:
			if _isElTrue(dExpect, ('required',)):
				fLog.write("   Authorization: Failed required check %s %s %s"%(
					sValue, sCmp, dExpect['to']
				))
				return AUTH_FAIL

	# Did I have at least one success and failures of required items?
	if nSuccess > 0:
		return AUTH_SUCCESS
	else:
		return AUTH_FAIL


# ########################################################################### #
# Authorization by local passwd/group files                                   #
# ########################################################################### #

def _getUserPasswd(fLog):
	"""
	Returns:  (username, password, bSrvErr)
	"""	
	if 'HTTP_AUTHORIZATION' in os.environ:
		sAuth = os.environ['HTTP_AUTHORIZATION']
		
		if sAuth.startswith('Basic') and len(sAuth) > 12:
			sAuthPlain = base64.b64decode(sAuth[6:]).decode('utf-8')
			lAuth = sAuthPlain.split(':')
			return( lAuth[0], ':'.join(lAuth[1:]), False)
			
	else:
		fLog.write("Required variable HTTP_AUTHORIZATION no available to script!\n")
		fLog.write("Check your sever config (Hint: Apache need a mod_rewrite rule to set this\n")
		return (None, None, True)
			
	return (None, None, False)

def _authCrypt(dConf, fLog, sUser, sPasswd):
	"""Nitty gritty of user authentication"""
	
	if 'PASSWD_FILE' not in dConf: 
		fLog.write("   Authorization: ERROR! Configuration entry 'PASSWD_FILE' "+\
		           "missing. Can't support 'passfile' authorization method")
		return AUTH_SRV_ERR
		
	if not os.path.isfile(dConf['PASSWD_FILE']):
		fLog.write("   Authorization: ERROR! Password file '%s' is missing."%dConf['PASSWD_FILE'])
		return AUTH_SRV_ERR
	
	try:
		fIn = open(dConf['PASSWD_FILE'], 'r')
	except IOError:
		fLog.write("   Authorization: ERROR! Can't open password file, '%s'"%dConf['PASSWD_FILE'])
		return AUTH_SRV_ERR
	
	for sLine in fIn:
		sLine = sLine.strip()
		if len(sLine) == 0:
			continue
		lLine = sLine.split(':')
		if len(lLine) < 2:
			fLog.write("   Authorization: ERROR! Improperly formatted password file, %s"%dConf['PASSWD_FILE'])

		if len(lLine) > 1 and lLine[0] == sUser:
			sCrypt = ':'.join(lLine[1:])         # Passwd string may have hand a ':'
			                                     # character in it
			sTest = crypt.crypt(sPasswd, sCrypt)
			
			#fLog.write("Test Crypt: %s"%sTest)
			
			if sTest == sCrypt:
				fLog.write("   Authorization: User %s authenticated"%sUser)
				return AUTH_SUCCESS
				
	fLog.write("   Authorization: Cipher match failure for user %s"%sUser)
	return AUTH_FAIL

def _getUserGroups(dConf, fLog, sUser):
	"""Returns:
	
	   (nStatus, lGroups)
	
	Where nStatus is one of: 
	
	  AUTH_SRV_ERR - Can't read group file
	  AUTH_SUCCESS - Read group file, lGroups has valid data
	  
	Note: It is possible that the user isn't in any groups, so lGroups may
	      be a zero length list
	"""
	if 'USER_GROUP' not in dConf: 
		fLog.write("   Authorization: ERROR! Configuration entry 'USER_GROUP'"+\
		           " missing, can't authenticate Das2 users")
		return (AUTH_SRV_ERR, None)
	
	if not os.path.isfile(dConf['USER_GROUP']):
		fLog.write("   Authorization: ERROR! Group file '%s' is missing."%dConf['USER_GROUP'])
		return (AUTH_SRV_ERR, None)

	lGroups = []

	try:
		fIn = open(dConf['USER_GROUP'], 'r')
	except IOError:
		fLog.write("   Authorization: ERROR! Can't open group file, '%s'"%dConf['USER_GROUP'])
		return (AUTH_SRV_ERR, None)
		
	for sLine in fIn:
		sLine = sLine.strip()
		if len(sLine) == 0:
			continue
		lLine = sLine.split(':')
		if len(lLine) != 4:
			fLog.write("   Authorization: ERROR! Expected 4 sections in each line of %s"%dConf['USER_GROUP'])
			return (AUTH_SRV_ERR, None)
					
		if len(lLine[0]) == 0:
			fLog.write("   Authorization: ERROR! Bad group name in %s"%dConf['USER_GROUP'])
			return (AUTH_SRV_ERR, None)
		
		lUsers = lLine[3].split(',')
		
		if sUser in lUsers:
			lGroups.append( lLine[0])
		
	return (AUTH_SUCCESS, lGroups)
	

def authByPassFile(dConf, fLog, dExpect):
	"""Handle authorization by local password and group files.

	Params:
		dConf - The server configuration
		dExpect - A dictionary containing a realm, and one of the
		  the lists: 'groups' or 'users'
	"""

	# Check for server errors first
	if ("groups" not in dExpect) and ('users' not in dExpect):
		fLow.write('  Authorization: ERROR! No "users" or "groups" listed for data source')
		return AUTH_SRV_ERR

	(sUser, sPasswd, bSrvErr) = _getUserPasswd(fLog)
	if bSrvErr:
		return AUTH_SRV_ERR
	if (sUser == None) or (sPasswd == None):
		return AUTH_FAIL

	# It's an older code, but does it check out?
	# TODO: I know this is the rudimentary lowest-common denominator method, 
	#       but see if browsers will support auth stronger then crypt
	nRet = _authCrypt(dConf, fLog, sUser, sPasswd)
	if nRet != AUTH_SUCCESS:
		return nRet

	if 'groups' in dExpect:
		(nRet, lUserGroups) = _getUserGroups(dConf, fLog, sUser)
		if nRet == AUTH_SRV_ERR:
			return nRet

		for sGroup in dExpect['groups']:
			if sGroup in lUserGroups:
				fLog.write("   Authorization: %s is a member of %s"%(sUser, sGroup))
				return AUTH_SUCCESS

	if 'users' in dExpect:
		if sUser in dExpect['users']:
			return AUTH_SUCCESS

	fLog.write("  Authorization:  Password file authentication failed for '%s'"%sUser)
	return AUTH_FAIL


# ########################################################################### #
# The main function of this module #

def authorize(dConf, fLog, dInternal, dParams):
	"""
	Handle authorization for a das resource
	
	dConf - The configuration dictionary, The keywords PASSWD_FILE and
	        possibly GROUP_FILE are consulted from this.  If those strings
	        aren't present in the configuration file authorization will
	        likely fail.
			  	
	fLog - The logger object
	
	dInternal - The internal.json for this data source
	
	dParams - The query parameters for this request
	
	In addition the os.environ dictionary is consulted to get the value
	of the 'HTTP_AUTHORIZATION' variable.  Note, the name of this variable
	can be changed in the config if desired.

	An example of an authorization area within a flex.json file follows:
   {
      "protocol": {
         "authorization": {
	         "required":true, "methods":["query","http-basic"]
         }
         ...
      }
      ...
   }

   And the detailed backend information in internal.json, which allows
   access if the max read time is older than 6 months, or if the user
   is in the tracers group, or is the user tracers-sot.
   {
	   "authorization": {
	      "allow":{
            "params":[
               {
                 "value":"#[read.time.max]",
                 "compare":"le",
                 "to":"age 6m"
               }
            ],
		      "passfile":{
		         "realm":"TRACERS Science Team",
		         "groups":["tracers"],
		         "users":["tracers-sot"]
		      }
		   }
	   }
      ...
   }

   Note that all items are under the "allow" property, just incase a "deny" 
   list is provided in the future.
	
	Returns:
	  AUTH_SUCCESS - If at least one check passes
	  AUTH_FAIL - If all access checks are processed normally but none succeed.
	  AUTH_SRV_ERR - If there is a sever error when processing the request.
	"""

	# See if the request comes from a system that has been configured with
	# auto-allow access in dasflex.conf:
	if 'ALLOW_TEST_FROM' in dConf and 'REMOTE_ADDR' in os.environ:
		if authByAddress(fLog, os.environ['REMOTE_ADDR'], dConf['ALLOW_TEST_FROM']):
			fLog.write("   Authorization: Host %s allowed access"%os.environ['REMOTE_ADDR'])
			return AUTH_SUCCESS
	
	dAllow = _getElement(dInternal, ('authorization','allow'))
	if not dAllow or (len(dAllow) == 0):
		return AUTH_SRV_ERR

	if 'params' in dAllow:
		nRet = authByCoords(dConf, fLog, dAllow['params'], dParams)
		if nRet in (AUTH_SUCCESS, AUTH_SRV_ERR): 
			return nRet

	if 'passfile' in dAllow:
		nRet = authByPassFile(dConf, fLog, dAllow['passfile'])
		if nRet in (AUTH_SUCCESS, AUTH_SRV_ERR):
			return nRet

	fLog.write("   Authorizaiton: Access denied")
	return AUTH_FAIL  # Nothing worked

# ########################################################################## #
# to run these tests from the build area issue:
#
#    python3 -m unittest dasflex/util/auth.py 
#
# from the root das2-pyserver directory

class TestAddrParsing(unittest.TestCase):

	# Define myself as a logger, which writes nothing
	def write(self, sMessage):
		#import sys
		#sys.stderr.write("%s\n"%sMessage)
		pass  # Sometimes I test thing that should fail!

	def test_addr4(self):
		sAddr = '10.14.237.62'
		xAddr = bytearray([10, 14, 237, 62])
		self.assertEqual( _parseIP4Address(self, sAddr), xAddr)

		sAddr = ''
		self.assertEqual( _parseIP4Address(self, sAddr), None)

		sAddr = 'a.d.ed.3e'
		self.assertEqual( _parseIP4Address(self, sAddr), None)

		sAddr = '255.255'
		xAddr = bytearray([0xFF, 0xFF, 0, 0])
		self.assertEqual( _parseIP4Address(self, sAddr), xAddr)

	def test_addr6(self):
		sAddr = '::1'
		xAddr = bytearray([0]*15 + [1])
		self.assertEqual( _parseIP6Address(self, sAddr), xAddr)

		sAddr = 'AAAA:BBBB::'
		xAddr = bytearray([0xAA]*2 + [0xBB]*2 + [0]*12)
		self.assertEqual( _parseIP6Address(self, sAddr), xAddr)

		sAddr = '0001:0203:0405:0607:0809:0a0b:0c0d:0e0f'
		xAddr = bytearray(list(range(16)))
		self.assertEqual( _parseIP6Address(self, sAddr), xAddr)

	def test_net4(self):
		sNet = '127.0.0.1/8'
		xNet  = bytearray([127,0,0,0])
		xMask = bytearray([255, 0, 0, 0])
		self.assertEqual( _parseIP4Range(self, sNet), (xNet, xMask))

		sNet = '128.0.0.1/33'
		self.assertEqual( _parseIP4Range(self, sNet), (None, None))

		sNet = '255.255.33.127/25'
		xNet = bytearray([255, 255, 33, 0x00])
		xMask  = bytearray([0xFF,0xFF,0xFF,0x80])
		self.assertEqual( _parseIP4Range(self, sNet), (xNet, xMask))

	def test_net6(self):
		sNet = '::1/128'
		xNet = bytearray([0]*15 + [1])
		xMask = bytearray([0xFF]*16)
		self.assertEqual( _parseIP6Range(self, sNet), (xNet, xMask))

		sNet = "2620:0:e51::/47"
		xNet = bytearray([0x26, 0x20, 0, 0, 0x0e, 0x50] + [0]*10)
		xMask = bytearray( [0xFF]*5 + [0xFE] + [0]*10)
		self.assertEqual( _parseIP6Range(self, sNet), (xNet, xMask))

	def test_inrange(self):

		ranges = ["::1", "127.0.0.1/8", "10.14.0.0/16", "fe80::/10"]
		sAddr = "fe80::0807:0605:0403:0201"

		self.assertTrue(  authByAddress(self, sAddr, ranges))
		self.assertFalse( authByAddress(self, "192.168.1.1", ranges))
		self.assertFalse( authByAddress(self, "2620:0:e50:1::", ranges) )

if __name__ == '__main__':
	unittest.main()
