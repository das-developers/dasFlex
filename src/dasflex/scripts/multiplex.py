#!/usr/bin/env python3

"""Stream Multiplex - runs muliple sub commands and merges thier output
Reads configuration data either from a file or from standard input

This is most useful for packing multiple real-time das3 streams into 
a single real-time stream
"""

import sys
import os
import fcntl
import select
import subprocess
import argparse
import traceback

# ########################################################################### #

g_sInvoke = "/project/tracers/etc/invoke.sh"

g_lAllPktIds = []  # Needed to make sure all packet IDs in stream are unique


def uniqueId(nRdr, nLocalId):
	"""
	Make a new globally unique packet ID number for a local ID from the reader
	"""
	global g_lAllPktIds

	i = 0
	while True:
		nTry = (nRdr * 1000) + nLocalId + i
		if nTry not in g_lAllPktIds:
			g_lAllPktIds.append(nTry)
			return nTry

		i += 100

def writeHdr(sType, nId, sHeader):
	xHdr = sHeader.encode('utf-8')

	if nId > 0:
		sTag = "|%s|%d|%d|"%(sType, nId, len(xHdr))
	else:
		sTag = "|%s||%d|"%(sType, len(xHdr))

	sys.stdout.buffer.write(sTag.encode('utf-8'))
	sys.stdout.buffer.write(xHdr)
	sys.stdout.buffer.flush()

g_dXmlEsc = str.maketrans({  # From stack overflow user: Pugsley ...Thanks!
	"<": "&lt;",
	">": "&gt;",
	"&": "&amp;",
	"'": "&apos;",
	'"': "&quot;",
})

def writeErr(sMsg):
	sys.stderr.buffer.write(("ERROR: %s"%sMsg).encode('utf-8'))
	sys.stderr.buffer.flush()

	writeHdr("Ex", 0, 
		"<exception type=\"ServerError\">\n%s\n</exception>\n"%sMsg.translate(g_dXmlEsc)
	)

def perr(sMsg):
	sys.stderr.buffer.write(sMsg.encode('utf-8') )
	sys.stderr.buffer.flush()

# ########################################################################### #

def makeComands(sConfig, sSv, sBeg, sEnd, bSubscribe):
	"""Hacks in fixed commands for now.  Will make general later"""

	sRdr = "%s dastlm_l1db_reader "%g_sInvoke
	if bSubscribe:
		sRdr += " -w "

	dRep = {"begin":sBeg, "end":sEnd}

	lArgTplts = [
		"ACE %(model)s -I x2a1 -D HSK_Analog -P temp %(begin)s %(end)s",

		"ACI %(model)s -I x28e -D HSK -P tmon_emi_lvps,tmon_fpga_lvps,zone1_tmon_fee0,"+
		  "zone2_tmon_fee0,zone3_tmon_fee0,zone4_tmon_fee0 %(begin)s %(end)s",

		"EFI %(model)s -I x261 -D HSK -P esp_tmon,pa1_tmon,pa2_tmon,pa3_tmon,pa4_tmon,"+
		  "beb_tmon,fltr12_tmon,fltr34_tmon,pn30v_tmon %(begin)s %(end)s",

		"MAG %(model)s -I x221 -D HSK -P sprt,eprt %(begin)s %(end)s",

		"MAGIC %(model)s -I x201 -D HSK_Fast -P adc_sens_temp,adc_board_temp,adc_zener_temp"+
		  " %(begin)s %(end)s"
	]

	tTis1 = ('ts1','sv1','1')

	dRep["model"] = "fm1" if sSv.lower() in tTis1 else "fm2"
	lCmds = [ sRdr + sTplt%dRep for sTplt in lArgTplts[:4] ]

	dRep["model"] = "fm2" if sSv.lower() in tTis1 else "fm3"
	lCmds.append(sRdr + lArgTplts[4]%dRep)

	# Todo: Add list of sub commands here
	sAltHdr = """
<stream version="3.0" type="das-basic-stream">
  <properties><p name="source">mutiplexed stream</p></properties>
</stream>
"""
	return sAltHdr, lCmds

# ########################################################################### #

class Reader:
	def __init__(self, nRdr, sCmd):
		self.nRdr = nRdr
		self.command = sCmd

		sys.stderr.buffer.write(("Reader %d: %s\n"%(nRdr, sCmd)).encode('utf-8'))
		sys.stderr.buffer.flush()

		self.proc = subprocess.Popen(
			sCmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
			bufsize=-1
		)

		#perr("Reader %d: stderr fn: %d\n"%(nRdr, self.fdErr()))
		#perr("Reader %d: stdout fn: %d\n"%(nRdr, self.fdOut()))
		#perr("Reader %d: proc poll: %s\n"%(nRdr, self.proc.poll()))
		#perr("Reader %d: running: %s\n"%(nRdr, self.running()))

		self.nMore = 0  # The amount that needs to be read to finish out a packet
		self.lPkts = [] # Each element is a type, id & bytes tuple
		self.lErrs = [] # Each element is just a line of text

		self.dId = {}   # Map of input packet IDs to output IDs

		# The packet data buffer. Should always start with a packet tag, may not
		# end with one, may have more then one in the middel
		self.xPktBuf = bytearray()  

		# The error string buffer. Should always start at the beginning of a line
		# may not end at the end of the line and may have multiple lines 
		self.xErrBuf = bytearray()

		# Set to non-blocking IO on both descriptors
		fl = fcntl.fcntl(self.fdOut(), fcntl.F_GETFL)
		fcntl.fcntl(self.fdOut(), fcntl.F_SETFL, fl | os.O_NONBLOCK)
	
		fl = fcntl.fcntl(self.fdErr(), fcntl.F_GETFL)
		fcntl.fcntl(self.fdErr(), fcntl.F_SETFL, fl | os.O_NONBLOCK)

	def fdOut(self):
		return self.proc.stdout.fileno()

	def fdErr(self):
		return self.proc.stderr.fileno()

	def rtnCode(self):
		nRet = self.proc.returncode

		return nRet if nRet != None else -1

	def _parseTag(self):
		# Find a packet tag within 38 bytes
		nPipes = 0
		iDatStart = -1
		#perr(str(self.xPktBuf[:32]) + "\n")
		xTag = None
		for i in range(len(self.xPktBuf)):
			if self.xPktBuf[i] == ord('|'): nPipes += 1
			
			if nPipes == 4:
				iDatStart = i + 1
				xTag = self.xPktBuf[0:iDatStart]
				break

			if i > 38:
				raise ValueError("Reader %d: Sanity limit of 38 bytes exceeded for packet tag"%self.nRdr)

		if xTag == None:
			return (None, None, None, None)

		try:
			lTag = [x.decode('utf-8') for x in xTag.split(b'|')[1:4] ]
			#perr(str(lTag) + "\n")
		except UnicodeDecodeError:
			raise ValueError(
				"Reader %d: Packet tag '%s' is not utf-8 text"%(self.nRdr, xTag)
			)
		sType = lTag[0]
		
		nPktId = 0
		if len(lTag[1]) > 0:  # Empty packet IDs are the same as 0
			try:
				nPktId = int(lTag[1], 10)
			except ValueError:
				raise ValueError("Reader %d: Invalid packet ID '%s'"%(self.nRdr, lTag[1]))
		if (nPktId < 0):
			raise ValueError("Reader %d: Invalid packet ID %d"%(self.nRdr, nPktId))
		
		try:
			nPktLen = int(lTag[2], 10)
		except ValueError:
			raise ValueError(
				"Reader %d: Invalid length '%s' in packet tag"%(self.nRdr, lTag[2])
			)
			
		if nPktLen < 2:
			raise ValueError(
				"Reader %d: Invalid packet length %d bytes at offset %d"%(self.nRdr, nPktLen)
			)

		return (sType, nPktId, iDatStart, nPktLen)


	def _makeTag(self, xOldTag, sType, nId, nPktLen):
		"""Check out the packet ID.  If it's unique, kick out the same
		bytes, if it's not make a new tag and kick that out
		"""
		global g_lAllPktIds

		if nId not in self.dId:			
			if nId not in g_lAllPktIds:  # Just re-use it
				g_lAllPktIds.append(nId)
				self.dId[nId] = nId
			else:
				self.dId[nId] = uniqueId(self.nRdr, nId)

		if nId == self.dId[nId]:
			return xOldTag

		# Make a new binary 
		xNewTag = ("|%s|%d|%d|"%(sType, self.dId[nId], nPktLen)).encode('utf-8')
		return xNewTag


	def readPackets(self):
		"""Transmit as many packets as your can, store any fragments for 
		the next call
		"""
		xStdOut = self.proc.stdout.read()
		if len(xStdOut) == 0: return

		self.xPktBuf += xStdOut
		if len(self.xPktBuf) < 8: return

		# Write as many packets as you can based on teh input data
		while True:

			(sType, nId, nTagLen, nPktLen) = self._parseTag()
			# If 8 bytes weren't enough to make a tag, try again later
			if(sType == None):
				break

			# if we don't have a full packet just bail
			if len(self.xPktBuf) < (nTagLen + nPktLen):
				return

			iNextPkt = nTagLen + nPktLen

			xTag = self.xPktBuf[:nTagLen]
			xPkt = self.xPktBuf[nTagLen:iNextPkt]

			self.xPktBuf = self.xPktBuf[iNextPkt:]

			if sType == 'Sx':	  # If stream header, dump it
				continue

			xTag = self._makeTag(xTag, sType, nId, nPktLen)
			sys.stdout.buffer.write( xTag )
			sys.stdout.buffer.write( xPkt )   # If not, write it
			sys.stdout.buffer.flush()

			if len(self.xPktBuf) < 8:  # Get another if possible
				return


	def readErrors(self):
		"""Read and transmit as many error lines as you can, store any
		partial lines for the next call"""
		xStdErr = self.proc.stderr.read()
		if len(xStdErr) == 0: return

		self.xErrBuf += xStdErr

		while True:
			iEnd = self.xErrBuf.find(ord('\n'))
			if iEnd < 0:
				return

			xLine = self.xErrBuf[:iEnd+1]
			self.xErrBuf = self.xErrBuf[iEnd+1:]

			sys.stderr.buffer.write( ("Reader %d: "%self.nRdr).encode('utf-8') )
			sys.stderr.buffer.write( xLine )
			sys.stderr.buffer.flush()

	def readAllErrors(self):
		"""Return to blocking IO and read stderr till end of stream"""
		fl = fcntl.fcntl(self.fdErr(), fcntl.F_GETFL)
		fcntl.fcntl(self.fdErr(), fcntl.F_SETFL, fl & ~os.O_NONBLOCK)		

		self.readErrors()


	def readAllPackets(self):
		"""Return to blocking IO and read stdout until end of stream"""
		fl = fcntl.fcntl(self.fdOut(), fcntl.F_GETFL)
		fcntl.fcntl(self.fdOut(), fcntl.F_SETFL, fl & ~os.O_NONBLOCK)
		
		self.readPackets()

	def running(self):
		return (self.proc.poll() == None)

	def close(self):
		self.proc.terminate()


# ########################################################################### #
def main():

	psr = argparse.ArgumentParser(
		description = """
Merge the output of mulitple dass3 readers into a single stream.  This program
can be thought of as a single über reader.  The only arguments it takes are
a start time and end time.  All further specifics are handled by the sub-reader
configuration provided either in a file or on standard input.  NOTE: this is
a prerelase alpha test, commands are not actually read from a file or std input
"""
	)

	# Add in later
	#psr.add_argument(
	#	'-c', '--config', default=None, metavar="FILE", dest="sConfig",
	#	help="Get sub-reader command lines from this file instead of standard input"
	#)
	psr.add_argument(
		'-w', '--wait', default=False, action="store_true", dest="bSubscribe",
		help="Tell the sub-readers to wait on subsequent data."
	)

	psr.add_argument(
		'SV', help="TEMPORARY ARG: The spacecraft of interest"
	)
	psr.add_argument(
		'BEGIN', help="The start time to read"
	)
	psr.add_argument(
		'END', help="The time to stop reading, an exclusive upper bound."
	)

	opts = psr.parse_args()

	sAltHdr, lCmds = makeComands(None, opts.SV, opts.BEGIN, opts.END, opts.bSubscribe)

	# Write a generic stream header
	writeHdr("Sx", 0, sAltHdr)


	lReaders = []
	for i in range(len(lCmds)):
		lReaders.append( Reader(i, lCmds[i]) )

	#perr("%s\n"%str( [reader.running() for reader in lReaders] ))
	
	try:
		# Create a user-land connection to a kernel based epoll object.  Despite
		# the name, this is not a polling check but an event based notifier.
		poller = select.epoll()
		dFdOut = {}
		dFdErr = {}
		for reader in lReaders:

			# We will need to find our readers by thier file descriptors
			dFdOut[reader.fdOut()] = reader
			dFdErr[reader.fdErr()] = reader

			# tell the kernel we want to know when new data are available on
			# either stdandard output or standard error and when the sub-program 
			# sends the hangup signal.
			poller.register(reader.fdOut(), select.EPOLLIN | select.EPOLLHUP)
			poller.register(reader.fdErr(), select.EPOLLIN | select.EPOLLHUP)

		while any( [reader.running() for reader in lReaders] ):
			lEvents = poller.poll(timeout=0.1)

			for nFd, nEvent in lEvents:

				# Standard read, more to come
				if nEvent & select.EPOLLIN:
					if nFd in dFdErr:
						dFdErr[nFd].readErrors()
					if nFd in dFdOut:
						dFdOut[nFd].readPackets()

				# Last read, drain the input buffer
				if nEvent & select.EPOLLHUP:
					
					if nFd in dFdErr:
						dFdErr[nFd].readAllErrors()
					if nFd in dFdOut:
						dFdOut[nFd].readAllPackets()
					
					poller.unregister(nFd)

	except Exception as e:
		sMsg = "%s\n%s"%(str(e), traceback.format_exc())
		writeErr(sMsg)

	finally:
		poller.close()

	for reader in lReaders:
		reader.close()

	return max( (reader.rtnCode() for reader in lReaders) )

# ########################################################################### #

if __name__ == "__main__":
	sys.exit(main())


