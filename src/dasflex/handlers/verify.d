
module dasflex.handlers.verify;

import std.stdio;
import std.string : startsWith, strip, replace, toLower;
import std.path : baseName, buildPath;
import std.array : split, array;
import std.conv : to;

import cgimain : IHandler, FieldStorage, registerHandler;

alias pout = writeLine; // Simple text line output

// Browser identification (short list used by errorExit)
auto _g_BrowserAgent = ["firefox","explorer","chrome","safari"];

// Cut down error handling used before util modules are loaded
void errorExit(string sOut) {
    bool bClientIsBrowser = false;
    auto ua = std.process.environment.get("HTTP_USER_AGENT");
    if (ua.length) {
        auto sAgent = ua.toLower();
        foreach (sTest; _g_BrowserAgent) {
            if (sAgent.indexOf(sTest) != -1) {
                bClientIsBrowser = true;
                break;
            }
        }
    }
    pout("Status: 500 Internal Server Error\r\n");
    if (bClientIsBrowser) {
        pout("Content-Type: text/plain; charset=utf-8\r\n\r\n");
        // cgitb.enable(format='text') — Python-only
        pout(sOut);
    } else {
        pout("Content-Type: text/plain; charset=utf-8\r\n\r\n");
        pout(sOut);
    }
    // sys.exit(5) — D return via caller
}

// Service disabled page
int sendDisabled(auto fLog, const string[string] dConf) {
    pout("Content-Type: text/html; charset=utf-8\r\n");
    pout(`

### The das2 stream validation service is not enable for this server.

Set ENABLE_VERIFY = true and possibly update VERIFY_FROM in your dasflex.conf file to enable the stream verification service.
`);
    return 0;
}

// BEGIN/END article helpers
void _preArticle(U, const string[string] dConf, auto fLog, string sTitle) {
    pout("Content-Type: text/html; charset=utf-8\r\n");
    pout("");
    auto dReplace = ["script": U.webio.getScriptUrl()];
    auto sScriptURL = U.webio.getScriptUrl();
    string sCssLink;
    if ("STYLE_SHEET" in dConf) {
        sCssLink = format("%s/static/%s", sScriptURL, dConf["STYLE_SHEET"]);
    } else {
        sCssLink = format("%s/static/dasflex.css", sScriptURL);
    }
    string sSiteId;
    if ("SITE_TITLE" in dConf) sSiteId = dConf["SITE_TITLE"];
    else sSiteId = format("Set SITE_TITLE in %s", dConf["__file__"]);
    pout(format("# %s\n", sSiteId));
    pout("");
    U.page.header(dConf, fLog, sTitle);
    pout("\n");
    U.page.sidenav(dConf, fLog);
    pout("\n");
}

void _postArticle(U, const string[string] dConf, auto fLog) {
    U.page.footer(dConf, fLog);
    pout("");
}

// Print upload form
int printForm(U, const string[string] dConf, auto fLog) {
    _preArticle(U, dConf, fLog, "_das2 / das3_ Validation Service");
    auto sScriptURL = U.webio.getScriptUrl();
    pout(`
\`\`\`
application/vnd.das2.das2stream
\`\`\`
\`\`\`
text/vnd.das2.das2stream; charset=utf-8
\`\`\`
\`\`\`
application/vnd.das2.das2doc+xml
\`\`\`

Check the format of a das/v2.2 or das/v3.0 basic-stream. This validator can parse the following mime types:

_das2_ Binary Stream: (*.d2s)
_das2_ Text Stream: (*.d2t)
_das2_ XML Document: (*.d2x)

### Select a file to Upload

Upload a stream file for validation. Only the first megabyte of the uploaded file will be scanned.

Treat extensions as errors (strict mode)
`);
    _postArticle(U, dConf, fLog);
    return 0;
}

// Print context around an XML/header error
void prnErrorContext(/*curPkt*/ auto curPkt, int nLine) {
    auto sHdr = cast(string) curPkt.content; // expect UTF-8
    auto lLines = sHdr.split("\n");
    foreach (i, lineRaw; lLines) {
        string sLine;
        if (lineRaw.length > 80) sLine = lineRaw[0 .. 76] ~ " ...";
        else sLine = lineRaw;
        sLine = sLine.replace(">", "&gt;").replace("<", "&lt;");
        if ((nLine > 0) && (abs(nLine - (cast(int)i + 1)) > 6)) continue;
        if (cast(int)i + 1 == nLine) pout(format(" %3d---> %s", i+1, sLine));
        else pout(format(" %3d %s", i+1, sLine));
    }
}

// Validate file using das2 schema (wire your D das2 implementation)
auto validateFile(U, const string[string] dConf, auto fLog, const FieldStorage form)
{
    auto formItem = form.params["file"]; // adapt once multipart parsing is added
    auto sFile = formItem;               // name/path; you will parse real upload parts later
    auto bStrict = false;

    // Same parsing state info to help with exception output
    typeof(null) curPkt = null;
    string sCurType;
    int[int] dDataPktCount; // id -> count

    // TODO: Replace with real das2 D API
    try {
        // auto reader = das2.PacketReader(fIn, bStrict);
        // auto (sStreamContent, sStreamVer, bVarTags) = reader.streamType();
        string sStreamContent = "das2"; // placeholder
        string sStreamVer = "3.0";      // placeholder

        if (sStreamContent != "das2") {
            pout(format("This is a %s stream, expected a das2 stream", sStreamContent));
            return tuple(5, null);
        }

        // auto (schema, loc) = das2.loadStreamSchema(sStreamVer, bStrict);
        auto loc = "schema.xsd"; // placeholder
        pout(format("Loaded XSD: %s", baseName(loc)));

        // Iterate packets (placeholder)
        foreach (pkt; /*reader*/ []) {
            curPkt = pkt;
            // if (pkt is das2.DataPkt) { dDataPktCount[pkt.id] += 1; continue; }

            // auto docTree = pkt.docTree();
            // auto elRoot = docTree.getroot();
            // sCurType = elRoot.tag;
            // schema.assertValid(docTree);

            // if (pkt is das2.DataHdrPkt) {
            //     dDataPktCount[pkt.id] = 0;
            //     pout(format("\n%s\n ID %s %s header [OKAY] (data size %d bytes)",
            //         pkt.tag, pkt.id, sCurType, pkt.baseDataLen()));
            // } else {
            //     pout(format("\n%s\n ID %s %s header [OKAY]", pkt.tag, pkt.id, sCurType));
            // }
            curPkt = null;
            sCurType = null;
        }
    } catch (Throwable e) {
        pout("\n- ");
        if (curPkt !is null) {
            if (sCurType.length) {
                pout(format("\n- Packet type **%s**, %s ID %s", /*curPkt.tag*/"", sCurType, /*curPkt.id*/0));
                pout(format("\n%s\n ID %s %s header ERROR (context follows)", /*curPkt.tag*/"", /*curPkt.id*/0, sCurType));
            } else {
                pout(format("\n%s\n ID %s data [ERROR]", /*pkt.tag*/"", /*pkt.id*/0));
            }
        }
        int nLine = -1;
        // TODO: derive line from XML errors
        if (curPkt !is null /* && curPkt.tag !in ("Dx","Qd") */) {
            try { prnErrorContext(curPkt, nLine); }
            catch { pout(format("Header packet %s%d is not valid UTF-8 text", /*curPkt.tag*/"", /*curPkt.id*/0)); }
        }
        auto sErr = e.msg;
        pout(sErr);
        if (curPkt is null)
            pout("No current packet, this usually means the packet tag length value is incorrect.");
        return tuple(5, "3.0"); // placeholder stream version
    }

    foreach (nId, nCount; dDataPktCount) {
        pout(format("\n- \nDx\n ID %d %d data packets [OKAY]\n", nId, nCount));
    }
    pout("");
    if (bStrict)
        pout(format("Stream validates as a strict %s version %s stream without extensions\n", "das2", "3.0"));
    else
        pout(format("Stream validates as a %s version %s stream\n", "das2", "3.0"));

    return tuple(0, "3.0");
}

// Handler entry
final class VerifyHandler : IHandler {
    override int handleReq(U, string sReqType,
                           const string[string] dConf,
                           auto fLog,
                           const FieldStorage form,
                           string sPathInfo)
    {
        // Check authorization to even know about the verify link
        if ("ALLOW_VALIDATE_FROM" !in dConf) {
            // Default: localhost ranges
            // dConf["ALLOW_VALIDATE_FROM"] = "127.0.0.1/8 ::1";
        }
        auto remote = std.process.environment.get("REMOTE_ADDR");
        if (!remote.length || !U.auth.addrInRange(fLog, remote, dConf["ALLOW_VALIDATE_FROM"])) {
            U.webio.notFoundError(fLog, "/verify not found");
            return 0;
        }

        if (!U.misc.isTrue("ENABLE_VALIDATOR", dConf))
            return sendDisabled(fLog, dConf);

        if (!("file" in form.params))
            return printForm(U, dConf, fLog);

        // Main section, processing...
        _preArticle(U, dConf, fLog, "_das2_ Validation Service");

        auto formItemFileName = form.params["file"]; // placeholder
        pout(format("\n### Validation Report for %s\n\n\n", formItemFileName));
        pout(" \n");

        auto result = validateFile(U, dConf, fLog, form);
        auto nRet = result[0];
        auto sStreamVer = result[1];
        pout(" \n");

        auto sSchema = U.das2.getSchemaName(sStreamVer); // integrate with your das2 impl

        if (nRet == 0) {
            pout(format(`
Validation successful!
- All stream headers validate again schema **%s**.
- All stream packets are consistent with the given headers
`, sSchema));
        } else {
            pout(" \nValidation Errors were detected \n");
        }

        pout(" \n");
        if (sStreamVer.length)
            pout(format("\n- Validation failed against schema **%s**.\n", sSchema));
        else
            pout("\n- Could not determine the stream type.\n");

        pout(" \n");
        _postArticle(U, dConf, fLog);
        return nRet;
    }

    override @property string __file__() { return __FILE__; }
    override @property string __name__() { return "dasflex.handlers.verify"; }
}

static this() {
    registerHandler("dasflex.handlers.verify", new VerifyHandler());
}
