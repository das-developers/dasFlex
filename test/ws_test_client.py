#!/usr/bin/env python3
"""
A websocket client for server testing

A Note on Capitalization:
   
   Async functions in python are actually objects in the classic sense. Calling
   one actually instantiates an object and registers it with the main event
   loop.  Thus ALL async functions in this code are capitalized so that the
   reader thinks of them as the objects that they are instead of the direct
   call functions that they emulate.
"""

import os
import sys
import ssl
import argparse
from functools import partial as delegate
from urllib.parse import urlparse
import trio
from trio_websocket import open_websocket_url, ConnectionRejected, ConnectionClosed

def perr(sMsg):
	sys.stderr.write("%s\n"%sMsg)

# ########################################################################## #

async def ReadPkt(ws):
	await ws.send_message("howdy")
	while True:
		try:
			pkt = await ws.get_message()
			sys.stdout.buffer.write(pkt)
		except ConnectionClosed:
			break

async def ConnectAndRead(sUrl, sCAFile=None):#, bSubscribe=False):
	
	if sUrl.startswith('wss'):
		if sCAFile == None:
			perr("ERROR: Certificate authority needed for wss connections, use -p")
			return
		ssl_context = ssl.create_default_context()
		ssl_context.load_verify_locations(sCAFile)
	else:
		ssl_context = None
		
	#if bSubscribe:
	#	tSub = ('subscribe',)
	#else:
	#	tSub = ('request',)

	try:
		async with open_websocket_url(sUrl, ssl_context) as ws:
		#async with open_websocket_url(sUrl, ssl_context, subprotocols=tSub) as ws:
			#await ws.send_message('hello world!')
			await ReadPkt(ws)

	except ConnectionClosed as ex:
		perr("Data source read complete")

# ########################################################################## #

def main(args):

	psr = argparse.ArgumentParser(
		description="""A simple test program for the dasflex websocket interface.
		It issues a single datasource request and send the resulting data to
		standard output.

		To test the output of a server operation pipe the output of this program
		into das_valid.
		"""
	)

	sDef = "%s/client.pem"%os.environ['PWD']
	psr.add_argument(
		"-p", '--pem', metavar="PEM_FILE", dest="sCAFile", default=sDef,
		help="Certificate file used to validate SSL connections to the server. "+\
		"defaults to "+sDef+" ."
	)
	#psr.add_argument(
	#	"-s", "--subscribe", dest="bSubscribe", action="store_true", default=False,
	#	help="Instead of a download and quit, request a data subscription that "+\
	#	"is held open allowing new data to come in"
	#)
	psr.add_argument(
		'SOURCE_URL', help="The base socket data source URL without query options,"+\
		" for example: ws://localhost:52245/dasws/examples/random"
	)
	psr.add_argument(
		"PARAMS", nargs="*", help="Any number of query key=value pairs.  For example: "+\
		"read.time.min=2022-09-15 read.time.max=2022-09-16"
	)

	opts = psr.parse_args()

	sUrl = opts.SOURCE_URL
	if len(opts.PARAMS) > 0:
		sUrl = "%s?%s"%(sUrl, "&".join(opts.PARAMS))

	perr("Data request is: %s"%sUrl)

	try:
		trio.run(ConnectAndRead, sUrl, opts.sCAFile)#, opts.bSubscribe)
		return 0
	except BaseException as grp:
		# Yay! Exception groups, just what I didn't want.
		
		for subex in grp.exceptions:
			if isinstance(subex, ConnectionRejected):
				perr("Connection rejected with status %d, full content follows"%subex.status_code)
				perr("-------")
				for t in subex.headers:
					perr("%s: %s"%(t[0].decode('utf-8'), t[1].decode('utf-8')))
				perr("")
				perr(subex.body.decode('utf-8'))
				return 3
				
		perr('Connection attempt failed: %s'%grp)

	except OSError as ex:
		perr('Connection attempt failed: %s'%ex)

	except KeyboardInterrupt:
		perr('CTRL-C recieved, shutting down')

	return 3

# ########################################################################## #
if __name__ == "__main__":
	sys.exit(main(sys.argv))
