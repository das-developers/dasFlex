#!/usr/bin/env python3
"""Quick and dirty dasFlex node generator for das{2,3}_from_cdf readers.

THROW-AWAY.  Written to get TRACERS L2 CDFs onto a das server quickly.  It
will be replaced by the cadd CDF input path and the command info registry
(see co_notes/dev_plan.md).  Until then it does its best by scraping the
human readable -n and -V output of the readers.

Usage::

   from_cdf_wrap.py -l LOCAL_ID [options] PATTERN

PATTERN is the das3_from_cdf file pattern, e.g.
'/data/L2/TS2/$Y/$m/$d/ts2_l2_msc_bac_$Y$m$d_v$v.cdf'.  Quote it.

Writes flex.json, internal.json, das2.d2t and the SourceSet for LOCAL_ID
under -o DIR (default ./), or under the server's DATASRC_ROOT with -I.  With
-I the parent Catalog nodes and global lists are updated too.

TRACERS assumptions:
  * ISTP CDFs, time is the only range coordinate
  * vector frames are in the COORD_FRAME attribute (-p COORD_FRAME:frame)
  * the newest file is representative of the whole pile
"""

import os
import re
import sys
import glob
import json
import argparse
import subprocess
from datetime import timedelta
from os.path import join as pjoin
from xml.sax.saxutils import escape

from dasflex.scripts.cadd import getConf
from dasflex.util import catalog

# ########################################################################## #

def perr(s):
	sys.stderr.write(s)
	sys.stderr.write('\n')

class SimpleLog(object):
	def write(self, s): perr(s)

def run(lCmd):
	"""Run a reader in info mode.  Info goes to stdout, but some notes (das2
	flattening) go to stderr as INFO lines, so keep both."""
	p = subprocess.run(lCmd, capture_output=True, text=True)
	return (p.returncode, p.stdout, p.stderr)

def patternFiles(sPattern):
	"""Every file the pattern could match, sorted.  The readers pick the
	greatest $v themselves; for range extremes duplicates don't matter."""
	sGlob = re.sub(r'\$(\([^)]*\)|[A-Za-z])', '*', sPattern)
	return sorted(glob.glob(sGlob))

# ########################################################################## #
# Scrape reader info output

def parseVars(sOut):
	"""das3_from_cdf -V lines look like:
	   * NAME (.c1 .c2 .c3)  "CATDESC"
	   * NAME  "CATDESC"
	"""
	lVars = []
	for sLine in sOut.splitlines():
		m = re.match(r'^\*\s+(\S+)(?:\s+\(([^)]*)\))?\s+"(.*)"\s*$', sLine)
		if not m: continue
		lComp = [s.lstrip('.') for s in m.group(2).split()] if m.group(2) else []
		lVars.append({'name':m.group(1), 'comps':lComp, 'desc':m.group(3)})
	return lVars

def parseNoOp(sOut):
	"""Pull what we need out of das3_from_cdf -n: the time base and offset
	variables, which variables are streamed by default, and any Ignored or
	Notes text to show the person running this."""
	d = {'timeVar':None, 'offsetVar':None, 'default':[], 'ignored':[], 'notes':[]}
	sSect = None
	for sLine in sOut.splitlines():
		s = sLine.strip()
		if re.match(r'^-+$', s): continue
		if s in ('Datasets','Ignored','Notes') or s.startswith('Time bases'):
			sSect = s.split()[0]
			continue
		if not s: continue

		if sSect == 'Time' and d['timeVar'] is None:
			d['timeVar'] = s.split()[0]
		elif sSect == 'Datasets':
			m = re.match(r'^OFFSET\s+(\S+)', s)
			if m and not d['offsetVar']: d['offsetVar'] = m.group(1)
			# A DATA item's CDF variable is on the CENTER line that follows it
			if s.startswith('DATA '): sSect = 'DatasetsData'
		elif sSect == 'DatasetsData':
			m = re.match(r'^CENTER\s+(\S+)', s)
			if m:
				d['default'].append(m.group(1))
				sSect = 'Datasets'
		elif sSect == 'Ignored':
			d['ignored'].append(s)
		elif sSect == 'Notes':
			if s.startswith('*'): d['notes'].append(s[1:].strip())
			elif d['notes']:      d['notes'][-1] += ' ' + s
	return d

# ########################################################################## #
# Ranges from the records, not the file names.  A file named for a day
# usually ends well before midnight, and an example range built from the name
# can land on no data at all.

def timeExtremes(sFirst, sLast, sTimeVar, sOffVar):
	from das2 import pycdf   # bundled with das2py 3

	def _ends(sPath):
		with pycdf.CDF(sPath) as cdf:
			e = cdf[sTimeVar]
			dtBeg, dtEnd = e[0], e[-1]
			if sOffVar and sOffVar in cdf:
				a = cdf[sOffVar][...]   # ns, non-record varying
				dtBeg += timedelta(microseconds=int(a.min())//1000)
				dtEnd += timedelta(microseconds=int(a.max())//1000)
			return (dtBeg, dtEnd)

	return (_ends(sFirst)[0], _ends(sLast)[1])

def globalAttrs(sPath):
	from das2 import pycdf
	with pycdf.CDF(sPath) as cdf:
		return {k:str(cdf.attrs[k][0]) for k in cdf.attrs.keys() if len(cdf.attrs[k]) > 0}

def varAttrs(sPath, lNames):
	from das2 import pycdf
	d = {}
	with pycdf.CDF(sPath) as cdf:
		for s in lNames:
			if s in cdf:
				d[s] = {k:str(v) for k,v in cdf[s].attrs.items() if not isinstance(v, pycdf.Var)}
	return d

def minute(dt, bUp=False):
	"""Minute precision ISO strings, as in the hand made nodes."""
	if bUp and (dt.second or dt.microsecond):
		dt += timedelta(minutes=1)
	return dt.strftime('%Y-%m-%dT%H:%M')

# ########################################################################## #
# Formatter boilerplate, copied from the live tracers nodes with the bugs found
# on 2026-10-19 fixed (co_notes/command_info_design.md):
#  - headers / dataset IDs use value tests, so UI defaults match the output
#  - only delimiters that survive misc.checkParams and das3_csv -d are offered

def formatsIface():
	dEnabled = lambda sType, bOn: {
		"type":"boolean", "xorGroup":"format", "value":bOn,
		"set":{"value":True, "param":"format.type", "pval":sType}
	}
	dFrac = {
		"label":"Fractional Seconds", "title":"Number of fractional seconds digits in text streams",
		"value":3, "set":{"param":"format.secfrac"}
	}
	dSig = {
		"label":"Significant Digits", "title":"General significant digits for values in text streams",
		"value":5, "set":{"param":"format.sigdigit"}
	}
	return {
		"das": {
			"label":"das stream", "title":"Streaming format for plots",
			"mimeTypes":[
				"application/vnd.das2.das2stream", "application/vnd.das.stream",
				"text/vnd.das2.das2stream", "text/vnd.das.stream"
			],
			"props":{
				"enabled": dEnabled("das", True),
				"version": {
					"label":"Stream Version", "value":"das3", "type":"enum",
					"set":{"param":"format.version", "enum":[
						{"value":"das3", "pval":"3"}, {"value":"das2", "pval":"2"}
					]}
				},
				"serial": {
					"label":"Serialization", "value":"binary",
					"set":{"param":"format.serial", "enum":[{"value":"text"}, {"value":"binary"}]}
				},
				"fracSecs": dFrac, "sigDigits": dSig
			},
			"order":["enabled", "version", "serial", "sigDigits", "fracSecs"]
		},
		"csv": {
			"label":"CSV stream", "title":"(Comma) Separated Values for export",
			"mimeTypes":["text/csv"],
			"props":{
				"enabled": dEnabled("csv", False),
				"attributes": {
					"value":False, "type":"boolean", "label":"Attributes",
					"title":"Output data object property rows",
					"set":{"value":True, "param":"format.csv.props", "pval":"1"}
				},
				"headers": {
					"value":True, "type":"boolean", "label":"Headers",
					"title":"Output column headers",
					"set":{"value":False, "param":"format.headers", "pval":"false"}
				},
				"datasetIds": {
					"value":True, "type":"boolean", "label":"Dataset IDs",
					"title":"Output the dataset ID column",
					"set":{"value":False, "param":"format.csv.dsid", "pval":"false"}
				},
				"delimiter": {
					"value":"Comma", "type":"enum", "label":"Value Separator",
					"set":{"param":"format.delim", "enum":[
						{"value":"Comma", "pval":","}, {"value":"Tab", "pval":"\t"}
					]}
				},
				"fracSecs": dFrac, "sigDigits": dSig
			},
			"order":["enabled", "attributes", "headers", "datasetIds", "delimiter",
			         "fracSecs", "sigDigits"]
		},
		"cdf": {
			"label":"CDF file", "title":"NASA Common Data Format",
			"mimeTypes":["application/x-cdf"],
			"props":{
				"enabled": dEnabled("cdf", False),
				"nocompress": {
					"value":False, "type":"boolean", "label":"No-Compression",
					"title":"Do not compress variables, needed for PDS compliant output.",
					"set":{"value":True, "param":"format.cdf.nocomp", "pval":"1"}
				}
			}
		}
	}

def formatParams():
	return {
		"format.type":     {"required":False, "type":"enum", "enum":["das","csv","cdf"]},
		"format.secfrac":  {"required":False, "type":"integer", "range":[0,9]},
		"format.sigdigit": {"required":False, "type":"integer", "range":[2,17]},
		"format.delim":    {"required":False, "type":"string"},
		"format.headers":  {"required":False, "type":"boolean"},
		"format.csv.props":{"required":False, "type":"boolean"},
		"format.csv.dsid": {"required":False, "type":"boolean"},
		"format.cdf.nocomp":{"required":False, "type":"boolean"},
		"format.serial":   {"label":"Serialization", "required":False, "type":"enum",
		                    "enum":["text","binary"]},
		"format.version":  {"required":False, "type":"string"}
	}

def formatCmds():
	_act = lambda **kw: [{"key":k.replace('_','.'), "value":v} for k,v in kw.items()]
	return {
		"das2_average": {
			"label":"das2_bin_avgsec", "title":"Legacy time resolution reducer", "order":3,
			"input":{"type":"das","version":"2"}, "output":{"type":"das","version":"2"},
			"template":"das2_bin_avgsec #[bin.time.max]",
			"activation":[{"key":"bin.time.max", "value":0, "compare":"gt"}]
			            + _act(format_type="das", format_version="2")
		},
		"das2_ascii": {
			"label":"das 2 binary to text", "order":5,
			"template":"das2_ascii -c #[format.secfrac#-s @#] #[format.sigdigit#-r @#]",
			"activation":_act(format_type="das", format_version="2", format_serial="text"),
			"input":{"type":"das","version":"2"},
			"output":{"type":"das","version":"2","variant":"text"}
		},
		# Not in the live tracers nodes, which serve das3 binary when asked for
		# das3 text.
		"das3_text": {
			"label":"das 3 binary to text", "order":5,
			"template":"das3_text #[format.secfrac#-s @#] #[format.sigdigit#-r @#]",
			"activation":_act(format_type="das", format_version="3", format_serial="text"),
			"input":{"type":"das","version":"3"},
			"output":{"type":"das","version":"3","variant":"text"}
		},
		"das_csv": {
			"label":"das3_csv", "title":"das 2/3 to delimited UTF-8 stream", "order":5,
			"template":[
				"das3_csv #[format.headers(|false|)#-n#] #[format.csv.props#-p#] ",
				"#[format.csv.dsid(|false|)#-i#] #[format.secfrac#-s @#] ",
				"#[format.sigdigit#-r @#] #[format.delim#-d \"@\"#-d ,]"
			],
			"activation":_act(format_type="csv"),
			"set":_act(format_type="das", format_version="3"),
			"input":{"type":"das","version":"3"}, "output":{"type":"csv"}
		},
		"das_cdf": {
			"label":"das3_cdf", "title":"das 2/3 to CDF file", "order":5,
			"template":["das3_cdf #[format.cdf.nocomp#-u#] "],
			"activation":_act(format_type="cdf"),
			"set":_act(format_type="das", format_version="3"),
			"input":{"type":"das","version":"3"}, "output":{"type":"cdf"}
		}
	}

# ########################################################################## #
# Node builders

def makeFlex(o, dConf, sTitle, lVars, dVarAtt, tValid, lExamples):
	sBaseUrl = '%s/source/%s/flex'%(dConf['SERVER_URL'].rstrip('/'), o.sLocalId.lower())

	dParams = {
		"read.time.min": {"required":True, "type":"isotime"},
		"read.time.max": {"required":True, "type":"isotime"},
		"bin.time.max":  {"required":False, "type":"real", "units":"s"},
		"read.data": {
			"type":"FlagSet", "required":False, "flagSep":",",
			"flags":{v['name']:{"value":v['name']} for v in lVars}
		}
	}
	dParams.update(formatParams())

	dData = {}
	for v in lVars:
		dAtt = dVarAtt.get(v['name'], {})
		dData[v['name']] = {
			"label": dAtt.get('LABLAXIS', v['name']),
			"title": v['desc'],
			"props":{"enabled":{
				"type":"boolean", "value":False,
				"set":{"value":True, "param":"read.data", "flag":v['name']}
			}}
		}

	dAuth = {"required":False}
	if o.sRealm: dAuth = {"required":True, "methods":["http-basic"]}

	return {
		"label": o.sLabel, "name": o.sName, "title": sTitle,
		"type":"HttpStreamSrc", "version":"0.7",
		"contacts": contacts(o),
		"protocol":{
			"method":"GET", "convention":"HTTP/1.1", "baseUrls":[sBaseUrl],
			"authorization":dAuth, "httpParams":dParams
		},
		"interface":{
			"coords":{"time":{
				"label":"Time",
				"props":{
					"min":{"label":"Minimum", "value":None, "title":"Minimum time value to stream",
					       "set":{"param":"read.time.min", "required":True}},
					"max":{"label":"Maximum", "value":None, "title":"Maximum time value to stream",
					       "set":{"param":"read.time.max", "required":True}},
					"units":{"value":"UTC"},
					"res":{"label":"Resolution", "value":None, "units":"s",
					       "title":"The maximum time bin width for bin-reduced data in seconds",
					       "set":{"param":"bin.time.max", "required":False}}
				},
				"validRange":list(tValid)
			}},
			"examples":[
				{"settings":{"coords/time/props/min":a, "coords/time/props/max":b, **dExtra},
				 "label":sLbl}
				for (sLbl, a, b, dExtra) in lExamples
			],
			"formats": formatsIface(),
			"data": dData
		}
	}

def contacts(o):
	l = []
	if o.sTech: l.append({"type":"maintainer", "name":o.sTech})
	if o.sSci:  l.append({"type":"scientific", "name":o.sSci})
	return l

def makeInternal(o, sShortName):
	# The pattern has $ fields and commands run under a shell, so it must be
	# single quoted.  VARs come from a FlagSet whose values were checked
	# against the variable list, so they go in bare.
	sPat = "'%s'"%o.sPattern
	sMap = '-p %s '%o.sPropMap if o.sPropMap else ''
	sPre = (o.sInvoke + ' ') if o.sInvoke else ''

	dCmds = {
		"das2_reader": {
			"label":"das2_from_cdf", "title":"Legacy full resolution upstream data reader",
			"order":1, "output":{"type":"das","version":"2"},
			"template":[
				"%sdas2_from_cdf %s%s "%(sPre, sMap, sPat),
				"#[read.time.min] #[read.time.max] #[read.data#@#]"
			],
			"activation":[{"key":"read.time.min"}, {"key":"format.type","value":"das"},
			              {"key":"format.version","value":"2"}]
		},
		"das3_reader": {
			"label":"das3_from_cdf", "title":"Full resolution upstream data reader",
			"order":1, "output":{"type":"das","version":"3"},
			"template":[
				"%sdas3_from_cdf %s"%(sPre, sMap),
				"-r time,#[read.time.min],#[read.time.max] %s #[read.data#@#]"%sPat
			],
			"activation":[{"key":"read.time.min"}, {"key":"format.type","value":"das"},
			              {"key":"format.version","value":"3"}]
		}
	}
	dCmds.update(formatCmds())

	d = {
		"parameters":{
			"translate":{"das2":{
				"start_time":"read.time.min", "end_time":"read.time.max",
				"resolution":"bin.time.max", "params":"read.data",
				"start":"read.time.min", "stop":"read.time.max",
				"server":None, "dataset":None
			}},
			"defaults":{
				"das2":{"format.type":"das", "format.version":"2"},
				"flex":{"format.type":"das", "format.version":"3"}
			}
		},
		"files":{"baseName":[
			{"function":"echo", "args":[sShortName]},
			{"function":"isorange", "args":["#[read.time.min]", "#[read.time.max]"]},
			{"function":"timeres", "args":["_", "#[bin.time.max#@#]", "s"]}
		]},
		"commands": dCmds
	}
	if o.sRealm:
		d["authorization"] = {"allow":{"passfile":{"realm":o.sRealm, "groups":[o.sGroup]}}}
	return d

def makeD2t(o, sTitle, sSummary, lVars, tValid, lExamples):
	q = lambda s: escape(s, {'"':'&quot;'})
	l = [
		'<stream version="2.2">', '  <properties',
		'    localId="%s"'%q(o.sLocalId),
		'    description="%s"'%q(sTitle),
		'    summary="%s"'%q(sSummary),
		'    das2Stream="true"', '',
		'    validRange="%s to %s UTC"'%tValid,
	]
	for i,(sLbl,a,b,dExtra) in enumerate([e for e in lExamples if not e[3]]):
		l.append('    exampleRange_%02d="%s to %s UTC"'%(i, a, b))
	l.append('')
	if o.sRealm: l.append('    securityRealm="%s"'%q(o.sRealm))
	if o.sSci:   l.append('    sciContact="%s"'%q(o.sSci))
	if o.sTech:  l.append('    techContact="%s"'%q(o.sTech))
	l.append('')
	for i,v in enumerate(lVars):
		l.append('    item_%02d="%s|%s"'%(i, v['name'], q(v['desc'])))
	for i,v in enumerate(lVars):
		l.append('    param_%02d="%s|Output %s"'%(i, v['name'], v['name']))
	l += ['  />', '</stream>', '']
	sXml = '\n'.join(l)
	return '[00]%06d%s'%(len(sXml.encode('utf-8')), sXml)

# ########################################################################## #

def main():
	psr = argparse.ArgumentParser(
		prog='from_cdf_wrap.py', description=__doc__.split('\n\n')[0],
		formatter_class=argparse.RawDescriptionHelpFormatter
	)
	psr.add_argument('sPattern', metavar='PATTERN')
	psr.add_argument('-l', '--local-id', dest='sLocalId', required=True)
	psr.add_argument('-c', '--config', dest='sConfig', default=os.getenv('DASFLEX_CONFIG'))
	psr.add_argument('-o', '--out-dir', dest='sOutRoot', default='.')
	psr.add_argument('-I', '--install', action='store_true', dest='bInstall')
	psr.add_argument('-t', '--title', dest='sTitle', help='Default: Logical_source_description')
	psr.add_argument('-L', '--label', dest='sLabel', help='Default: last localId part, upper case')
	psr.add_argument('-n', '--name', dest='sName', help='Default: Logical_source, upper case')
	psr.add_argument('-p', '--prop-map', dest='sPropMap', default='COORD_FRAME:frame')
	psr.add_argument('--sci-contact', dest='sSci', default=None)
	psr.add_argument('--tech-contact', dest='sTech', default=None)
	psr.add_argument('--realm', dest='sRealm', default=None,
		help='Require a login from this security realm, e.g. "TRACERS Mission Team"')
	psr.add_argument('--group', dest='sGroup', default='tracers')
	psr.add_argument('--invoke', dest='sInvoke', default=None,
		help='Wrapper to run the readers under, e.g. /project/tracers/etc/invoke.sh')
	psr.add_argument('--bin', dest='sBin', default='',
		help='Directory holding das3_from_cdf, for running the info commands here')
	o = psr.parse_args()

	if not o.sConfig: perr("No server config, use -c or set DASFLEX_CONFIG"); return 3
	dConf = getConf(o.sConfig)
	if not dConf: return 3
	if o.bInstall and o.sOutRoot != '.':
		perr("-I and -o conflict"); return 3
	sCatRoot = dConf['DATASRC_ROOT'] if o.bInstall else o.sOutRoot

	lFiles = patternFiles(o.sPattern)
	if not lFiles: perr("No files match %s"%o.sPattern); return 4
	sLast = lFiles[-1]
	perr("INFO: %d files, describing from %s"%(len(lFiles), sLast))

	# A single file bounds itself, so the info modes need no range
	sD3 = pjoin(o.sBin, 'das3_from_cdf') if o.sBin else 'das3_from_cdf'
	sD2 = pjoin(o.sBin, 'das2_from_cdf') if o.sBin else 'das2_from_cdf'
	lMap = ['-p', o.sPropMap] if o.sPropMap else []

	(n, sOut, sErr) = run([sD3, '-V'] + lMap + [sLast])
	if n: perr(sOut + sErr); return 5
	lVars = parseVars(sOut)
	(n, sOut, sErr) = run([sD3, '-n'] + lMap + [sLast])
	if n: perr(sOut + sErr); return 5
	dInfo = parseNoOp(sOut)

	if not lVars or not dInfo['timeVar']:
		perr("Couldn't scrape variables or the time base from das3_from_cdf output")
		return 5
	for s in dInfo['ignored']: perr("IGNORED: %s"%s)
	for s in dInfo['notes']:   perr("NOTE: %s"%s)

	(dtBeg, dtEnd) = timeExtremes(lFiles[0], sLast, dInfo['timeVar'], dInfo['offsetVar'])
	tValid = (minute(dtBeg), minute(dtEnd, True))
	perr("INFO: data from %s to %s"%(dtBeg.isoformat(), dtEnd.isoformat()))

	# das2 path check.  It's only advisory: das2_from_cdf flattens waveforms
	# but still works, which is fine for Autoplot.
	(n, sOut, sErr) = run([sD2, '-n'] + lMap + [sLast,
		dtEnd.strftime('%Y-%m-%dT%H:%M:%S'),
		(dtEnd + timedelta(seconds=1)).strftime('%Y-%m-%dT%H:%M:%S')])
	for s in sErr.splitlines():
		if s.startswith('INFO:'): perr("DAS2 %s"%s)
	if n: perr("WARNING: das2_from_cdf -n failed, das2 output may not work:\n%s"%sErr)

	dGlob = globalAttrs(sLast)
	dVarAtt = varAttrs(sLast, [v['name'] for v in lVars])
	sShort = dGlob.get('Logical_source', os.path.basename(sLast).split('_20')[0])
	sTitle = o.sTitle or dGlob.get('Logical_source_description', sShort)
	sSummary = ' '.join(dGlob.get('TEXT', sTitle).split())
	if not o.sLabel: o.sLabel = o.sLocalId.rstrip('/').split('/')[-1].upper()
	if not o.sName:  o.sName = sShort.upper()
	if not o.sSci:   o.sSci = dGlob.get('PI_name')

	sEx0 = minute(dtEnd - timedelta(minutes=10))
	sEx1 = minute(dtEnd - timedelta(days=1)) if dtEnd - dtBeg > timedelta(days=1) else tValid[0]
	lExamples = [
		("Most Recent 10 minutes", sEx0, tValid[1], {}),
		("Most Recent Day (CDF)", sEx1, tValid[1], {"formats/cdf/props/enabled":True})
	]

	dPaths = catalog.sourceFiles(sCatRoot, o.sLocalId)
	fLog = SimpleLog()
	catalog._writeJsonFile(fLog, dPaths['flex'],
		makeFlex(o, dConf, sTitle, lVars, dVarAtt, tValid, lExamples))
	catalog._writeJsonFile(fLog, dPaths['intern'], makeInternal(o, sShort))
	catalog._writeFile(fLog, dPaths['das2'],
		makeD2t(o, sTitle, sSummary, lVars, tValid, lExamples))
	catalog.makeSrcSet(fLog, dConf, o.sLocalId,
		[dPaths['flex'], dPaths['intern'], dPaths['das2']], dPaths['set'])

	if o.bInstall:
		if not catalog.updateFromSrc(fLog, dConf, sCatRoot, o.sLocalId): return 7
		if not catalog.updateLists(fLog, dConf, sCatRoot): return 8
	else:
		perr("INFO: Not installed, parent catalogs and lists untouched (use -I)")
	return 0

if __name__ == '__main__':
	sys.exit(main())
