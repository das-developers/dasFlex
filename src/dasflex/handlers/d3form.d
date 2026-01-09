
module dasflex.handlers.d3form;

import std.stdio;
import std.string : strip, replace, startsWith, toLower, join, split;
import std.path : baseName, buildPath;
import std.array : array;
import std.json;
import std.conv : to;

import cgimain : IHandler, FieldStorage, registerHandler;

// ---------------------------------------------------------------------------
// Lightweight output helpers to mimic Python pout/sout
// ---------------------------------------------------------------------------
void pout(string sOut) { stdout.write(sOut ~ "\n"); }
void sout(auto fOut, string sOut) { fOut.write(sOut ~ "\n"); }

// ---------------------------------------------------------------------------
// Error helpers
// ---------------------------------------------------------------------------
auto _missingKeyError(auto fOut, string sKey, string sUrl) {
    sout(fOut, format(`
Schema error in node from [%s](%s), key **%s** is missing.
`, sUrl, sUrl, sKey));
    return null;
}

bool _isTrue(JSONValue d, string key) {
    if (!(key in d.object)) return false;
    auto v = d.object[key];
    if (v.type == JSONType.true_) return true;
    if (v.type == JSONType.false_) return false;
    if (v.type == JSONType.string) {
        auto s = v.str.toLower();
        return (s == "true" || s == "1" || s == "yes");
    }
    return false;
}

// Nested element helpers (adapted to JSONValue; wire to your typed model as needed)
bool _hasElement(JSONValue d, string[] path) {
    JSONValue cur = d;
    foreach (p; path) {
        if (cur.type != JSONType.object || !(p in cur.object)) return false;
        cur = cur.object[p];
    }
    return true;
}

JSONValue _getElement(auto fLog, JSONValue d, string[] path) {
    if (!_hasElement(d, path)) {
        fLog.write(format(" ERROR: Could not locate dictionary element: %s", path));
        return JSONValue.init;
    }
    JSONValue cur = d;
    foreach (p; path) {
        if (cur.type != JSONType.object || !(p in cur.object)) return JSONValue.init;
        cur = cur.object[p];
    }
    return cur;
}

string _getPropDataType(JSONValue dProp, JSONValue dParams) {
    // Get the type value direct from the property, or from the underlying protocol if the type is not set directly.
    // The default type is 'string' if nothing else can be determined.
    if (dProp.type == JSONType.object && ("type" in dProp.object))
        return dProp.object["type"].str;

    if (!_hasElement(dProp, ["set","param"])) return "string";
    auto sParam = dProp.object["set"].object["param"].str;

    // Pull up full parameter, or from a flag if not
    if (!_hasElement(dProp, ["set","flag"])) {
        if (dParams.type == JSONType.object && (sParam in dParams.object) && ("type" in dParams.object[sParam].object))
            return dParams.object[sParam].object["type"].str;
    } else {
        auto sFlag = dProp.object["set"].object["flag"].str;
        if (_hasElement(dParams, [sParam, "flags", sFlag])) {
            auto dFlag = dParams.object[sParam].object["flags"].object[sFlag];
            if ("type" in dFlag.object) return dFlag.object["type"].str;
        }
    }
    return "string";
}

// Search nested dict for a key name; yields matching elements
// NOTE: Python yields/generator; here we accumulate
JSONValue[] _searchNestedDict(auto fLog, JSONValue d, string key) {
    JSONValue[] results;
    void search(JSONValue node) {
        final switch (node.type) {
            case JSONType.object:
                foreach (k, v; node.object) {
                    if (k == key) results ~= v;
                    search(v);
                }
                break;
            case JSONType.array:
                foreach (v; node.array) search(v);
                break;
            default: break;
        }
    }
    search(d);
    return results;
}

// ---------------------------------------------------------------------------
// prnCatalog: Given a catalog node, print the sub items.
// ---------------------------------------------------------------------------
void prnCatalog(U, auto fLog, const string[string] dConf,
                string sRelPath, JSONValue dNode, auto fOut)
{
    // Args: dNode (dict) - Catalog node definition with fully qualified URLs for sub items.
    auto sScriptUrl = U.webio.getScriptUrl(dConf);
    auto dSub = dNode.object["catalog"];
    string sSep = "/";
    if ("separator" in dNode.object && dNode.object["separator"].type == JSONType.string)
        sSep = dNode.object["separator"].str;
    if (sSep is null) sSep = "";

    string[] lKeys;
    foreach (k, _; dSub.object) lKeys ~= k;
    lKeys.sort;
    sout(fOut, " ");
    foreach (sKey; lKeys) {
        string sName = sKey;
        if ("label" in dSub.object[sKey].object)
            sName = dSub.object[sKey].object["label"].str;
        if (sName.length < 2) sName = format(" %s ", sName);

        string sTitle = format("An untitled %s", dSub.object[sKey].object["type"].str);
        if ("title" in dSub.object[sKey].object)
            sTitle = dSub.object[sKey].object["title"].str;

        auto sClass = "cat_cat";
        if (dSub.object[sKey].object["type"].str == "Collection")
            sClass = "type_stream";

        if ("urls" in dSub.object[sKey].object) {
            auto sSubUrl = dSub.object[sKey].object["urls"].array[0].str.replace(".json",".html");
            sout(fOut, format("\n- [%s](%s) - %s \n", sClass, sSubUrl, sName, sTitle));
        }
        sout(fOut, " ");
    }
    sout(fOut, " ");
}

// ---------------------------------------------------------------------------
// UrlBldr: Given 1-N interface parameters to set, build URLs for GET
// ---------------------------------------------------------------------------
final class UrlBldr {
    JSONValue dNode; // source node
    string[string] dQuery;
    typeof(stdout) fLog;

    this(typeof(stdout) fLog, JSONValue dNode) {
        this.fLog = fLog;
        if (!("interface" in dNode.object))
            fLog.write(" ERROR: Source node is missing the 'interface' element");
        if (!("protocol" in dNode.object))
            fLog.write(" ERROR: Source node is missing the 'protocol' element");
        else if (!("httpParams" in dNode.object["protocol"].object))
            fLog.write(" ERROR: Node protocol definition is missing the 'httpParams' element.");
        else if (!("baseUrls" in dNode.object["protocol"].object))
            fLog.write(" ERROR: Node protocol definition is missing the 'baseUrls' element.");
        else
            this.dNode = dNode;
    }

    bool setProperty(string sProperty, JSONValue value) {
        // Set a single interface property
        if (this.dNode.type == JSONType.null) return false;
        if (!sProperty.length) { fLog.write(format(" ERROR: Invalid property path %s", sProperty)); return false; }

        auto lPath = sProperty.strip("/").split("/").array;
        auto dProp = _getElement(fLog, this.dNode.object["interface"], lPath);
        if (dProp.type == JSONType.null) return false;
        if (!("set" in dProp.object)) { fLog.write(format("%s is not a settable interface property", sProperty)); return false; }

        auto dSet = dProp.object["set"];
        auto dParams = this.dNode.object["protocol"].object["httpParams"];
        if (!("param" in dSet.object)) { fLog.write(" ERROR: key 'param' missing in settable property."); return false; }
        auto sParam = dSet.object["param"].str;
        if (!(sParam in dParams.object)) { fLog.write(format(" ERROR: Invalid httpParam reference from interface '%s' ", sParam)); return false; }

        // If the settable thing is an enumeration, make sure the value is in the enum (simplified)
        if ("enum" in dSet.object) {
            string[] lAccept;
            foreach (dEnum; dSet.object["enum"].array) {
                if (!("value" in dEnum.object)) { fLog.write(" ERROR: enum missing value in settable property"); return false; }
                lAccept ~= dEnum.object["value"].str;
                if (dEnum.object["value"].str == value.str) break;
            }
            // (strict check omitted – you’ll wire your real enum/flag mapping)
        }

        // Flags vs normal params
        if ("flag" !in dSet.object) {
            dQuery[sParam] = value.toString();
            return true;
        }
        // Combine flags into single param value (simplified)
        auto sFlag = dSet.object["flag"].str;
        if (!("flags" in dParams.object[sParam].object)) { fLog.write(format(" ERROR: HTTP parameter '%s' has no flags to set.", sParam)); return false; }
        if (!(sFlag in dParams.object[sParam].object["flags"].object)) { fLog.write(format(" ERROR: Invalid flag '%s' for HTTP parameter '%s'", sFlag, sParam)); return false; }
        auto dFlag = dParams.object[sParam].object["flags"].object[sFlag];
        string sTmp = (("prefix" in dFlag.object) ? dFlag.object["prefix"].str : "");
        string sFlagVal = sTmp ~ (( "value" in dFlag.object) ? dFlag.object["value"].str : value.toString());
        if (sParam !in dQuery) dQuery[sParam] = sFlagVal;
        else dQuery[sParam] ~= " " ~ sFlagVal; // default flagSep " "
        return true;
    }

    string[] getUrls() {
        if (this.dNode.type == JSONType.null) return null;
        string[] out;
        foreach (sBase; this.dNode.object["protocol"].object["baseUrls"].array) {
            auto base = sBase.str;
            if (dQuery.length > 0) {
                auto sPre = (base.indexOf('?') != -1) ? "&" : "?";
                string[] lQuery;
                foreach (k, v; dQuery) lQuery ~= format("%s=%s", k, v);
                out ~= base ~ sPre ~ lQuery.join("&");
            } else {
                out ~= base;
            }
        }
        return out;
    }
}

string[] _translateSettings(auto fLog, JSONValue dNode, JSONValue dSettings) {
    auto bldr = new UrlBldr(fLog, dNode);
    foreach (k, v; dSettings.object) bldr.setProperty(k, v);
    return bldr.getUrls();
}

// Host simple name
string _hostSimpleName(string sBase) {
    auto sLow = sBase.toLower();
    if (sLow.startsWith("https")) sLow = sLow[8 .. $];
    else if (sLow.startsWith("http")) sLow = sLow[7 .. $];
    else if (sLow.startsWith("wss"))  sLow = sLow[6 .. $];
    else if (sLow.startsWith("ws"))   sLow = sLow[5 .. $];
    sLow = sLow[0 .. 1].toUpper ~ sLow[1 .. $];
    int n = sLow.indexOf('.');
    if (n != -1) return sLow[0 .. n];
    n = sLow.indexOf('/');
    if (n != -1) return sLow[0 .. n];
    n = sLow.indexOf('?');
    if (n != -1) return sLow[0 .. n];
    return sLow;
}

// Hidden param extractor
void _setHidden(auto fOut, JSONValue dBaseUrls) {
    string[string] dHidden;
    foreach (urlVal; dBaseUrls.array) {
        auto sUrl = urlVal.str;
        auto n = sUrl.indexOf('?');
        if (n == -1) continue;
        foreach (pair; sUrl[n+1 .. $].split("&")) {
            auto parts = pair.split("=");
            if (parts.length > 1 && !(parts[0] in dHidden))
                dHidden[parts[0]] = parts[1];
        }
    }
    foreach (k, v; dHidden) sout(fOut, format(" ", k, v)); // placeholder HTML
}

// Default mime from formats section
auto _getDefaultMime(U, const string[string] dConf, JSONValue dFormats) {
    string sType;
    JSONValue dFmt;
    foreach (sFmt, dTmp; dFormats.object) {
        if (!("props" in dTmp.object)) { dFmt = dTmp; sType = sFmt; break; }
        auto dProps = dTmp.object["props"];
        if (("enabled" in dProps.object) && ("value" in dProps.object["enabled"].object)) {
            if (dProps.object["enabled"].object["value"].type == JSONType.true_) {
                dFmt = dTmp; sType = sFmt; break;
            }
        }
    }
    if (dFmt.type == JSONType.null) return tuple("", "", "");
    string sVer, sSerial;
    if (_hasElement(dFmt, ["props","version","value"]))
        sVer = dFmt.object["props"].object["version"].object["value"].str;
    if (_hasElement(dFmt, ["props","serial","value"]))
        sSerial = dFmt.object["props"].object["serial"].object["value"].str;

    auto dMimes = U.mime.load(dConf);
    return U.mime.get(dMimes, sType, sVer, sSerial); // expect (mime, ext, title)
}

string _getAction(string sBase) {
    auto n = sBase.indexOf('?');
    if (n != -1) return sBase[0 .. n];
    return sBase;
}

// ---------------------------------------------------------------------------
// prnHttpSource — main form generation (simplified framework preserved)
// ---------------------------------------------------------------------------
void prnHttpSource(U, auto fLog, const string[string] dConf, JSONValue dSrc, auto fOut)
{
    auto sSrcUrl = dSrc.object["_url"].str;

    // Contacts (technical/scientific)
    if ("contacts" in dSrc.object) {
        string[] lTech, lSci;
        foreach (dContact; dSrc.object["contacts"].array) {
            auto typ = dContact.object["type"].str;
            if (typ == "technical")  lTech ~= dContact.object["name"].str;
            else if (typ == "scientific") lSci ~= dContact.object["name"].str;
        }
        if (lTech.length > 0) sout(fOut, format(" Technical problems using this data source should be directed to: _%s_ ", lTech.join(", ")));
        if (lSci.length > 0)  sout(fOut, format(" Questions concerning the content or usefulness of these data should be directed to: _%s_ ", lSci.join(", ")));
    }

    foreach (sKey; ["protocol","interface"]) {
        if (!(sKey in dSrc.object)) { _missingKeyError(fOut, sKey, sSrcUrl); return; }
    }

    auto dProto = dSrc.object["protocol"];
    auto dIface = dSrc.object["interface"];

    // Authentication banner
    if ("authentication" in dProto.object) {
        if (_isTrue(dProto.object["authentication"], "required")) {
            sout(fOut, " _Restricted data source._");
            if ("REALM" in dProto.object["authentication"].object)
                sout(fOut, format("You will be asked to authentication to the realm \"**%s**\" on submit.", dProto.object["authentication"].object["realm"].str));
            else
                sout(fOut, "You will be asked to authentication on submit.");
        }
    }

    // Examples
    if ("examples" in dIface.object) {
        sout(fOut, " **Examples:** ");
        int iTmp = 0;
        foreach (dExample; dIface.object["examples"].array) {
            ++iTmp;
            auto sTmpTxt = format("Example %d", iTmp);
            if ("label" in dExample.object) sTmpTxt = dExample.object["label"].str;
            else if ("title" in dExample.object) sTmpTxt = dExample.object["title"].str;
            auto lTmpUrl = _translateSettings(fLog, dSrc, dExample.object["settings"]);
            if (lTmpUrl && lTmpUrl.length) {
                if (iTmp > 1) sout(fOut, " ");
                sTmpTxt = sTmpTxt.replace(" ", "&nbsp;");
                sout(fOut, format("[%s](%s)", lTmpUrl[0], sTmpTxt));
            }
        }
        sout(fOut, " ");
    }

    // Form ID/action
    auto sBaseUri = baseName(dSrc.object["_url"].str).replace(".json","");
    auto sFormId  = sBaseUri ~ "_download";
    sout(fOut, format("", sFormId));

    // Base URLs → hidden params (pre-filled)
    if (!("baseUrls" in dProto.object)) { _missingKeyError(fOut, "protocol:baseUrls", dSrc.object["_url"].str); return; }
    _setHidden(fOut, dProto.object["baseUrls"]);

    // (Coordinates/Data/Options/Formats generation omitted for brevity; porting stubs can be added here)

    // Submit buttons (one per non-websocket base URL)
    foreach (urlVal; dProto.object["baseUrls"].array) {
        auto sBase = urlVal.str;
        if (sBase.startsWith("ws")) continue;
        auto sLabel = "Download";
        if (dProto.object["baseUrls"].array.length > 1)
            sLabel = format("Download from %s", _hostSimpleName(sBase));
        sout(fOut, format(" ", sLabel, /*onSubmit function*/ sFormId, _getAction(sBase)));
        sout(fOut, " ");
    }

    // Source definition link
    sout(fOut, format("Source definition: [%s](%s)",
        dSrc.object["_url"].str, dSrc.object["_url"].str));

    // Permanent IDs
    if ("uris" in dSrc.object && dSrc.object["uris"].array.length > 0) {
        sout(fOut, "Permanent IDs:");
        // NOTE: sorting omitted (std.json arrays not keyed)
        foreach (sUri; dSrc.object["uris"].array)
            sout(fOut, format(" _%s_", sUri.str));
        sout(fOut, " ");
    }
}

// Load JSON (1-liner)
JSONValue _loadJson(auto fLog, string sInPath) {
    fLog.write(" Loading: " ~ sInPath);
    auto txt = std.file.readText(sInPath);
    return parseJSON(txt);
}

// Convert URL to local catalog path
string _urlToCatPath(U, const string[string] dConf, auto fLog, string sUrl) {
    auto sScriptUrl = U.webio.getScriptUrl(dConf);
    if (!sUrl.startsWith(sScriptUrl)) return null;
    auto sUrlRoot = format("%s/source", sScriptUrl);
    auto sFileSysRoot = buildPath(dConf["DATASRC_ROOT"], "root");
    auto sPath = sUrl.replace(sUrlRoot, sFileSysRoot).replace("/", std.path.sep);
    return sPath;
}

// ---------------------------------------------------------------------------
// Handler entry
// ---------------------------------------------------------------------------
final class D3FormHandler : IHandler {
    override int handleReq(U, string sReqType,
                           const string[string] dConf,
                           auto fLog,
                           const FieldStorage form,
                           string sPathInfo)
    {
        fLog.write("\nLocal catalog node GUI handler");

        // Find the corresponding json object and load it
        sPathInfo = std.process.environment.get("PATH_INFO");
        if (!sPathInfo.startsWith("/source/"))
            return U.webio.serverError(fLog, "PATH_INFO did not start with /source/");
        if (!sPathInfo.endsWith(".html"))
            return U.webio.serverError(fLog, "PATH_INFO did not end with .html");

        auto sFormUrl = U.webio.getScriptUrl(dConf) ~ sPathInfo;
        auto sCatUrl  = sFormUrl.replace(".html",".json");
        auto sLocalId = sPathInfo["/source/".length .. $].strip("/");
        auto sRelPath = sLocalId.replace("/", std.path.sep).replace(".html",".json");
        auto sPath    = buildPath(dConf["DATASRC_ROOT"], "root", sRelPath);

        if (!std.file.isFile(sPath))
            return U.webio.notFoundError(fLog, "PATH_INFO did not end with /form.html");

        JSONValue dNode;
        try {
            dNode = _loadJson(fLog, sPath);
        } catch (Throwable e) {
            return U.webio.serverError(fLog, e.msg);
        }

        // Slide in the json data location in case they want to look at it
        dNode.object["_url"] = sCatUrl;

        if (!("type" in dNode.object) || !("catalog" in dNode.object))
            return U.webio.serverError(fLog, format("Unknown file at %s", dNode.object["_url"].str));

        auto sType = dNode.object["type"].str;
        if (!(sType == "Catalog" || sType == "SourceSet"))
            return U.webio.serverError(fLog, format("Unknown object type %s in %s", sType, dNode.object["_url"].str));

        // If this is a source set, then pull up the HttpStreamSrc
        if (sType == "SourceSet") {
            string sSrcPath, sSrcUrl;
            foreach (sSource, v; dNode.object["catalog"].object) {
                if (("type" in v.object) && (v.object["type"].str == "HttpStreamSrc")) {
                    sSrcUrl = v.object["urls"].array[0].str;
                    sSrcPath = _urlToCatPath(U, dConf, fLog, sSrcUrl);
                    break;
                }
            }
            if (!sSrcPath.length)
                return U.webio.notFoundError(fLog, format("%s %s does not have an HttpStreamSrc node", dNode.object["type"].str, sPath));

            JSONValue dSrcNode;
            try {
                dSrcNode = _loadJson(fLog, sSrcPath);
            } catch (Throwable e) {
                return U.webio.serverError(fLog, e.msg);
            }
            dSrcNode.object["_url"] = sSrcUrl;
            dNode = dSrcNode;
        }

        // ...okay should output something
        auto sScriptUrl = U.webio.getScriptUrl(dConf);
        stdout.write("Content-Type: text/html; charset=utf-8\r\n\r\n");
        string sCssLink;
        if ("STYLE_SHEET" in dConf) sCssLink = format("%s/static/%s", sScriptUrl, dConf["STYLE_SHEET"]);
        else sCssLink = format("%s/static/dasflex.css", sScriptUrl);

        string sSiteId;
        if ("SITE_TITLE" in dConf) sSiteId = dConf["SITE_TITLE"];
        else sSiteId = format("Set SITE_TITLE in %s", dConf["__file__"]);
        pout(format("# %s\n", sSiteId));
        pout("");

        // U.page.header(dConf, fLog);
        pout("\n");
        U.page.sidenav(dConf, fLog, true);
        pout("\n");

        // The main show
        // U.page.navheader(dConf, fLog, sPathInfo);
        if ("label" in dNode.object)
            pout(format("\n\n## %s\n \n", dNode.object["label"].str));
        else
            pout("\n\n## Unlabeled Data Source\n \n");

        if ("title" in dNode.object) pout(format("\n\n### %s\n \n", dNode.object["title"].str));
        if ("description" in dNode.object) pout(format("\n\\n%s\\n\n", dNode.object["description"].str));

        // Buffered output collector
        auto fOut = new OutputRangeApp; // simple sink below
        try {
            if (dNode.object["type"].str == "Catalog")
                prnCatalog(U, fLog, dConf, sRelPath, dNode, fOut);
            else
                prnHttpSource(U, fLog, dConf, dNode, fOut);
            pout(fOut.buffer);
        } catch (Throwable e) {
            pout("\n\n### Catalog Node Display Error\n \n");
            pout(format("\n%s\n", e.toString()));
        }

        // Footer
        pout("");
        return 0;
    }

    override @property string __file__() { return __FILE__; }
    override @property string __name__() { return "dasflex.handlers.d3form"; }
}

// Simple buffered sink to mimic StringIO for sout()
final class OutputRangeApp {
    string buffer;
    void write(string s) { buffer ~= s; }
}

static this() {
    registerHandler("dasflex.handlers.d3form", new D3FormHandler());
}
