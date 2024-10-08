"""Default Handler for no argument hit on the top level of the server"""

import sys

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')
	
##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""The interface for a handler function is as follows:
	
	Parameter Inputs:
	
	   U - The dasflex utility module, contains handy functions
	
	   sReqType - A string indicating the internal name for this type of 
		    request

		dConf - A dictionary containing all the parameters loaded from 
		    the configuration file
			 
		fLog - A DasLogFile object, contains a write member, just use that
		
		form - A cgi.FieldStorage instance, provides the query parameters
		
		sPathInfo - The URL path after the script name itself

   File Inputs:

      stdin - Has already been consumed by the FieldStorage instance, there's
		   nothing to read there
			
   Environment Inputs:
	
	   The standard CGI environment variables are present and set up, some of
		the utilitly module functions use these is the background
			
	Outputs:
		stdout - Write any data ment for the client program to standard output
		
		stderr - Not used, don't even bother unless you are doing some wierd
		         non-embedded testing
					
	   fLog - Log your errors or other information in fLog, or better yet use
		       the error output functions in U.webio.
		
	Return Value:
	
	   Return 0 if everything went okay, non-zero to indicate an error return
	
	Exceptions:
		There is a traceback handler at the top level, so thrown exceptions will
		be caught, logged and sent to the client.  In addition the log message
		will be sent as plain  text or as a das2exception packet depending on the
		client type.
	"""
	
	pout('Content-Type: text/html; charset=utf-8\r\n')
	
	dReplace = {"script":U.webio.getScriptUrl()}
				
	sScriptURL = U.webio.getScriptUrl()

	if 'STYLE_SHEET' in dConf:
		sCssLink = "%s/static/%s"%(sScriptURL, dConf['STYLE_SHEET'])
	else:
		sCssLink = "%s/static/dasflex.css"%sScriptURL

	if 'SITE_TITLE' in dConf:
		sSiteId = dConf['SITE_TITLE']
	else:
		sSiteId = "Set SITE_TITLE in %s"%dConf['__file__']

	pout('''<!DOCTYPE html>
<html>
<head>
   <title>%s</title>
   <link rel="stylesheet" type="text/css" media="screen" href="%s" />
</head>
'''%(sSiteId, sCssLink))
	
	pout('<body>')

	#U.page.header(dConf, fLog)
	
	# Add side navigation bar to top level categories, need to put this in a
	# libray call
	pout('<div class="main">')
	
	U.page.sidenav(dConf, fLog, True)
	
	pout('<div class="article">')
			
	pout("""
<!-- <h1><i>das</i> Flexible Server</i></h1> -->
<h1>Multistream Server</i></h1>
<p>
This server provides data streams in a variety of formats using a variety of 
Application Programming Interfaces (APIs).  In addition to fixed APIs such
as <i>das2</i>, interface definition files are provided to allow for arbitrary
query parameters linked to physical coordinates.  Internally the server runs
full-resolution data stream generators, processes the flow, and optionally
caches the results.  Almost all processing steps are optional.
</p>

<!--
<div class="flowdiagram_parent">
<img src="%(script)s/static/flowdiagram.svg"
  alt="das2-pyserver data flow diagram" class="flowdiagram"
/>
<center><i><span style="font-size: 80%%">Stream Processing</span></i></center>
</div>
-->
<p>
The core server itself generates no primary data.  That tasks falls to readers
which may output:
<ul>
<li> CSV Text streams </li>
<li> CCSDS packet streams</li>
<li> <i>das3</i> display streams</li>
</ul>
or any other format so long as some set of HTTP query parameters can be mapped
to some data supplied by a reader program.
</p>
<!-- 
<h4><span style="color: #993300"><i>This is an <b>beta version</b> of the server and not all
functionality is complete.</i></span></h4>
-->

<h2>Clients</h2>

<p>Forms are provided to download data from this server as das streams,
text delimited value streams (CSV), PNG images, hapi streams, and eventually
as VOTables (in work) via the navigation bar to the right.  Full use of this
server requires a client program capable of reading data in one of the provided
formats and producing plots.  Programs which can parse <i>das2</i> streams include:</p>
<ul>
<li> <a href="https://das2.org/autoplot">Autoplot</a> via the
<a href="https://github.com/das-developers/das2java">das2java</a> library.  
This is the most common client.</li>
<li> <a href="https://spedas.org/blog/">SPEDAS (Space Physics Environment Data Analysis Software)</a>
via the <a href="https://github.com/das-developers/das2dlm">das2dlm</a> module.</li>
<li><a href="http://www.sddas.org/">SDDAS (Southwest Data Display and Analysis System)</a>
    via the <a href="https://github.com/das-developers/das2C">das2C</a> library</li>
</ul>
<p>Programs which can parse <i>das3</i> real-time streams include:</p>
<ul>
<li> <a href="https://space-physics.git-pages.research.uiowa.edu/tracers/soc/dasoc/">DASOC</a>
</li>
</ul>

<p>In addition, custom scripts written in 
<a href="https://github.com/das-developers/das2py">Python</a>, 
or <a href="https://github.com/das-developers/das2pro">IDL</a>
my utilize these data.</p>

"""%dReplace)
			
	# Site Navagation ######################################################## #

	pout("""
<h2>Interface</h2>

<p>The most common data output format is mime-type: <tt>application/vnd.das2.das2stream</tt>
However, streams may be reformatted if requested.</p>

<p>This server provides the following "filesytem" style interface which is accessed
via HTTP GET messages.</p>
<p>Note that clients do <i>not</i> need to understand this layout. 
Merely reading one of the catalog files: <a href="%(script)s/catalog.json">catalog.json</a>
or <a href="%(script)s/nodes.csv">nodes.csv</a> is sufficent.</p>

<pre>
  / This introductory page, at <a href="%(script)s">%(script)s</a>
  |
  |- <a href="%(script)s/source/">source/</a> - root directory for all data sources 
  |    |
  |    |- <i>category</i>.html - A top level category user interface
  |    |- <i>category</i>.json - A top level category catalog
  |    |- <i>category</i>/     - A top level category contents directory
  |         |         <i>(typically named after missions)</i>
  |         |
  |         |- <i>sub-category</i>.html - A sub-category user interface
  |         |- <i>sub-category</i>.json - A sub-category catalog
  |         |- <i>sub-category</i>/     - A sub-category contents directory
  |             |              <i>(typically named after instruments)</i>
  |             |
  |             |- <i>source-set</i>.html - A data source set user interface
  |             |- <i>source-set</i>.json - A data source set catalog
  |             |- <i>source-set</i>/     - A data source set directory
  |                  |
  |                  |- das2.d2t    - A das2 data source definition (if das2 query compatable)
  |                  |- flex.json   - An general HttpStreamSrc definiton
  |                  |- flexRT.json - A real-time source definition (if real-time capable)
  |                  |- vo.xml      - An IVOA <a href="https://www.ivoa.net/documents/DataLink/20150617/index.html">DataLink</a> definition (optional)
  |
  |- <a href="%(script)s/catalog.json">catalog.json</a> - A combined catalog of all data sources
  |     local to this server.  May be provided to <b>new_RootNode_url()</b> in das2C or
  |     <b>das2.get_node()</b> in das2py.  When preforming multiple requests from the same
  |     server, this format is more efficent than <a herf="%(script)s/root.json">root.json</a>
  |     below but is not suitable for building distributed server catalogs.
  |
  |- <a href="%(script)s/nodes.csv">nodes.csv</a> - A flat listing of individual data
  |     source catalog nodes for this server.  Any one of the URLs in this file can be 
  |     used as a data query point.
  |
  |- <a href="%(script)s/static/">static/</a> - static files such as logos, etc
  |
  |- <a href="%(script)s/root.json">root.json</a> - The root of all individual catalog
  |     nodes on this server.  Also happens to be the first node listed in <a href="%(script)s/nodes.csv">nodes.csv</a> above.
  |
  |- <a href="%(script)s/verify">verify/</a> - Included das stream verification tool (if enabled)
  |
  |- <a href="%(script)s/id.json">id.json</a> - Server identification information
  |- <a href="%(script)s/id.txt">id.txt</a> - das2 v2.2 style info text
  |- <a href="%(script)s/logo.png">logo.png</a> - A server identifier logo
  |- <a href="%(script)s/peers.xml">peers.xml</a> - Other recognized das2 servers
</pre>
"""%dReplace)

#	'''	
#	<p>
#	Almost all content provided by this server is generated dynamically.  The filesystem
#	interface is just a facade.  You can ease the load on your server and provide faster
#	metadata response times by replicating non-data content onto a static site.
#	The following commands illustrate this process.
#	</p>
#	<pre>
#	   $ wget -nH --cut-dirs=2 -r --no-parent %(script)s/sources/  # note trailing slash
#	   $ wget -nH %(script)s/sources.json
#	   $ wget -nH %(script)s/sources.csv
#	</pre>
#	<p>Of course you'll have to repeat the process whenever data source definitions
#	are altered.</p>
#	'''

	# Das 2.1/2.2 support ################################################### #

	if 'SAMPLE_DSDF' in dConf:
		dReplace['dataset'] = dConf['SAMPLE_DSDF']
			
	if 'SAMPLE_START' in dConf and 'SAMPLE_END' in dConf:
		dReplace['min'] = dConf['SAMPLE_START']
		dReplace['max'] = dConf['SAMPLE_END']

	pout("""
<h2>Traditional Queries</h2>

<p>The das2/v2.2 server query API is also supported by this server.  A summary
of the scheme follows.</p>
<ul>
<li><b>Data Source List:</b>  <a href="%(script)s?server=list">%(script)s?server=list</a><br /><br /></li>
<li><b>Peer List:</b>  <a href="%(script)s?server=peers">%(script)s?server=peers</a><br /><br /></li>
<li><b>Dataset Definition:</b>  %(script)s?server=dsdf&dataset=<i>DATA_SET_ID</i>
"""%dReplace)
	
	if 'dataset' in dReplace:
		pout("""<br />Example: <a href="%(script)s?server=dsdf&dataset=%(dataset)s">
%(script)s?server=dsdf&dataset=%(dataset)s</a>"""%dReplace)
	pout("<br /><br /></li>")
	
	pout("""<li><b>Data Download:</b> Use the pattern<br />
%(script)s?server=dataset&dataset=<i>DATA_SET_ID</i>&start_time=<i>BEGIN</i>&end_time=<i>END</i>&resolution=<i>SECONDS</i>
<br />
Where the <i>START</i> and <i>END</i> are time strings, and <i>SECONDS</i> is a floating
point number.  To reterive data at the native resolution omitt the <b>resolution</b> 
parameter.
"""%dReplace)

	if 'dataset' in dReplace and 'min' in dReplace and 'max' in dReplace:
		pout("""<br />
Example:
<a href="%(script)s?server=dataset&dataset=%(dataset)s&start_time=%(min)s&end_time=%(max)s">
%(script)s?server=dataset&dataset=%(dataset)s&start_time=%(min)s&end_time=%(max)s</a>
		"""%dReplace)
	
	pout("<br /><br /></li>")
	
	pout("</ul>")

	# Plot maker ############################################################ #

	if 'PNG_MAKER' in dConf:
		pout("""
<li><b>Plot Download</b> -- This server has been extended with a server side
plotter which delivers data as PNG images.  To use this functionality enter a
URL with the pattern:
<br /><br />
%(script)s?server=image&dataset=<i>DATA_SET_NAME</i>&start_time=<i>BEGIN</i>&end_time=<i>END</i>		
<br /><br />
"""%dReplace)

		if 'min' in dReplace and 'max' in dReplace and \
		   'dataset' in dReplace:
			pout("""
For example:
<br /><br />
<a href="%(script)s?server=image&dataset=%(dataset)s&start_time=%(min)s&end_time=%(max)s">
%(script)s?server=image&dataset=%(dataset)s&start_time=%(min)s&end_time=%(max)s</a>
		"""%dReplace)
			
		pout("<br /><br /></li>")
	
	# Helophysics API support ############################################### #

	bHSubSys	= False
	sKey = "ENABLE_HAPI_SUBSYS"
	if sKey in dConf:
		bHSubSys = dConf[sKey].lower() in ('true','yes','1')

	if bHSubSys:
		pout("""
<h2>Helophysics API Support</h2>
<p>All queries rooted at <a href="%s/hapi">%s/hapi</a> will respond to
helophysics API requests as documented at 
https://github.com/hapi-server/data-specification</p>
"""%(dReplace["script"], dReplace["script"]))
		
	
	# END Article Div, and Main DIV ######################################### #
	pout('  </div>\n</div>\n') 
	
	#U.page.footer(dConf, fLog)

	pout('''</body>
</html>''')
	
	return 0
