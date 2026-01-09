
// #!/usr/bin/env python
module cgimain;

import std.stdio;
import std.string : strip, splitLines, replace, startsWith;
import std.algorithm : canFind;
import std.array : array, appender;
import std.conv : to;
import std.file : readText, exists, isFile, isDir;
import std.format : format;
import std.datetime.stopwatch : StopWatch, AutoStart;
import std.exception : enforce;
import std.path : dirName;
import std.uri : decodeComponent;
import std.process : environment, thisProcessID;
import core.stdc.stdlib : getenv; // for direct env access
import core.stdc.string : strlen;
import core.stdc.stdint;

// ---------------------------------------------------------------------------
// Helper: write bytes or UTF-8 text to stdout (CGI safe), matching 'pout'
// ---------------------------------------------------------------------------
void pout(const(ubyte)[] item) {
    // Raw binary write
    stdout.rawWrite(item);
}

void pout(string item) {
    // Encode to UTF-8 and write
    // D strings are UTF-8 by default; rawWrite expects bytes.
    import std.utf : byUTF;
    // Efficiently write as bytes; no BOM
    foreach (ubyte b; item.byUTF) {
        stdout.rawWrite([b]);
    }
}

// ---------------------------------------------------------------------------
// Browser identification used before util modules are loaded.
// If you update this list, also update the list in util.io
// ---------------------------------------------------------------------------
auto _g_BrowserAgent = ["firefox","explorer","chrome","safari","edge"];

// _g_siteTree = "tag:das2.org,2012:site:/"
// _g_testTree = "tag:das2.org,2012:test:/"

// ---------------------------------------------------------------------------
// Default request handler map.
// (comments preserved from Python source)
// Here's the user-facing virtual filesystem presented by the server
//
// server/  An introductory html page
//  - hapi/  - Heliophysics API subsystem (if enabled)
//  - static/ - A blind directory (no output)
//    - static files such as logos, etc
//  - source/ - An html directory listing, useful for wget
//    - juno.html  - A display page for humans
//    - juno.json  - Top-level catalog node for Juno stuff
//    - juno/      - An html directory listing for wget
//    - wav.html   - A sub page for fumans
//    - wav.json   - A sub level catalog node for Waves stuff
//    - wav/       - An html directory listing for wget
//    - survey.html - A query from for survey stuff
//    - survey.json - A sub catalog node for Survey data sources
//    - survey/     - An html directory listing, useful for wget
//    - das2.d2t    - the old dsdf as das2 stream trick
//    - flex.json   - a fed cat HttpStreamSource object
//    - voservice.xml
//    - data        - form action handler (hidden from indexes)
//    - catalog.json - A das2 catalog listing of all items down to the
//                     HttpStreamSource level, can feed URL to node.c as detached root
//    - nodes.csv    - A listing of all stand along catalog end points
//    - root.json    - The root node of the stand alone catalog points
//    - verify       - Included das2 stream verification tool
//    - id.json      - Server identification information
//    - id.txt       - Old das2.2 info text
//    - logo.png     - Old das2.2 logo
//    - peers.xml    - A listing of peer servers
//
// To merge sources list here into a central catalog:
//  1) Pull root.json
//  2) Iterate through the levels merging information, creating collections
// ---------------------------------------------------------------------------
string[string] g_dDefHandlers = [
    // No path given
    "HANDLE_NONE":     "dasflex.handlers.intro",
    // ?server=debug /debug
    "HANDLE_DEBUG":    "dasflex.handlers.debug",
    // ?server=peers /peers.xml
    "HANDLE_PEERS":    "dasflex.handlers.peers",
    // /static/*
    "HANDLE_RESOURCE": "dasflex.handlers.resource",
    // ?server=logo /logo.png
    "HANDLE_LOGO":     "dasflex.handlers.logo",
    // ?server=id /id.txt /id.json
    "HANDLE_ID":       "dasflex.handlers.id",
    // ?server=discovery ?server=list /catalog.json /nodes.csv /root.json
    "HANDLE_LIST":     "dasflex.handlers.catalog",
    // Effectively index.html files for wget... /source /static
    "HANDLE_DIR":      "dasflex.handlers.directory",
    // Directory info pages leading to a data source page
    "HANDLE_INFO":     "dasflex.handlers.info",
    // New flex requests: /source/juno/wav/survey.html
    "HANDLE_FORM":     "dasflex.handlers.d3form",
    // New das flex: /source/juno/wav/survey/flex (can handle others as well)
    "HANDLE_DATA":     "dasflex.handlers.d3data",
    // List of services offered by this server (failed experiment)
    // "HANDLE_SERVICES": "dasflex.handlers.services",
    // /verify the validation service from & action
    "HANDLE_VERIFY":   "dasflex.handlers.verify",
];

// ---------------------------------------------------------------------------
// Cut down version of error handling for use before the module path is loaded
// ---------------------------------------------------------------------------
void preLoadError(string sOut) {
    // """Cut down error handling for use before the util modules are loaded,
    // script must exit after calling this or multiple HTTP headers will be
    // emitted.
    // """
    string sType = "ServerError";
    bool bClientIsBrowser = false;

    auto ua = environment.get("HTTP_USER_AGENT");
    if (ua.length) {
        auto sAgent = ua.toLower();
        foreach (sTest; _g_BrowserAgent) {
            if (sAgent.canFind(sTest)) {
                bClientIsBrowser = true;
                break;
            }
        }
    }

    pout("Status: 500 Internal Server Error\r\n");
    if (bClientIsBrowser) {
        // Match Python behavior: plain text
        pout("Content-Type: text/plain; charset=utf-8\r\n\r\n");
        pout(sOut);
    } else {
        // Das2 stream error format
        pout("Content-Type: text/vnd.das2.das2stream\r\n\r\n");
        auto sTmp = sOut.replace("\n", "\n\r").replace("\"", "'");
        auto sErr = format("<exception type=\"%s\" message=\"%s\" />\n", sType, sTmp);
        // Length header + payload
        import std.utf : toUTF8;
        auto xOut = cast(const(ubyte)[]) sErr.toUTF8();
        pout(format("[00]%06d", xOut.length));
        pout(xOut);
    }
}

// ---------------------------------------------------------------------------
// Config file reader: readConf(sConfPath)
// ---------------------------------------------------------------------------
string[string] readConf(string sConfPath) {
    if (!isFile(sConfPath)) {
        if (isFile(sConfPath ~ ".example")) {
            preLoadError(format(
                "Move\n %s.example\nto\n %s\nto enable your site", sConfPath, sConfPath));
        } else {
            auto sGuessRoot = dirName(dirName(sConfPath));
            preLoadError(format(
                "The config file:\n %s \n"
                ~ "is missing. Either update your Apache config to point to some other location\n"
                ~ "or run:\n dasflex_mkroot %s \n"
                ~ ", or similar, to initialize the server root area.\n",
                sConfPath, sGuessRoot));
        }
        return null;
    }

    string contents = readText(sConfPath); // UTF-8
    string[string] dConf;
    size_t nLine = 0;

    foreach (sLineRaw; contents.splitLines()) {
        ++nLine;
        auto sLine = sLineRaw;
        auto iComment = sLine.indexOf('#');
        if (iComment > -1) sLine = sLine[0 .. iComment];
        sLine = sLine.strip;
        if (sLine.length == 0) continue;

        auto iEquals = sLine.indexOf('=');
        if (iEquals < 1 || iEquals > (sLine.length - 2)) {
            preLoadError(format("Error in %s line %d", sConfPath, nLine));
            return null;
        }
        auto sKey = sLine[0 .. iEquals].strip;
        auto sVal = sLine[(iEquals + 1) .. $].strip(" \t\v\r\n'\"");

        dConf[sKey] = sVal;
    }

    // include a reference to the config file itself
    dConf["__file__"] = sConfPath;

    // Some replacement text
    if ("SERVER_ID" !in dConf)        dConf["SERVER_ID"] = "unknown";
    if ("SERVER_NAME" !in dConf)      dConf["SERVER_NAME"] = "Unknown";
    if ("SITE_CATALOG_TAG" !in dConf) dConf["SITE_CATALOG_TAG"] = "tag:unknown.site.org,2021";

    return dConf;
}

// ---------------------------------------------------------------------------
// Update module path (Python sys.path) — not directly applicable in D.
// We keep the function to preserve structure; it returns true if MODULE_PATH
// present, and you may use it later to load shared libs or configure your
// registry.
// ---------------------------------------------------------------------------
bool setModulePath(const string[string] dConf) {
    if ("MODULE_PATH" !in dConf) {
        preLoadError("Set MODULE_PATH = /dir/containing/dasflex_python_module");
        return false;
    }
    // In D we cannot alter compile-time import paths at runtime.
    // You may still use this value for runtime-loaded resources or a handler registry.
    return true;
}

// ---------------------------------------------------------------------------
// Minimal CGI FieldStorage replacement supporting getfirst()
// (GET via QUERY_STRING; POST for application/x-www-form-urlencoded)
// ---------------------------------------------------------------------------
struct FieldStorage {
    string[string] params;

    this() {
        auto qs = environment.get("QUERY_STRING");
        if (qs.length) parseUrlEncoded(qs);

        auto method = environment.get("REQUEST_METHOD");
        if (method == "POST") {
            auto ctype = environment.get("CONTENT_TYPE");
            auto clen  = environment.get("CONTENT_LENGTH");
            if (ctype.startsWith("application/x-www-form-urlencoded") && clen.length) {
                size_t n = to!size_t(clen);
                ubyte[] buf;
                buf.length = n;
                // Read exactly CONTENT_LENGTH bytes from stdin
                size_t read = stdin.rawRead(buf);
                string body = cast(string) buf; // UTF-8 assumed
                parseUrlEncoded(body);
            }
            // NOTE: multipart/form-data is not handled here; add if needed.
        }
    }

    void parseUrlEncoded(string s) {
        foreach (pair; s.split("&")) {
            if (!pair.length) continue;
            auto kv = pair.split("=", 2);
            auto k  = decodeComponent(kv[0]);
            auto v  = (kv.length > 1) ? decodeComponent(kv[1]) : "";
            params[k] = v;
        }
    }

    string getfirst(string key, string defaultVal) const {
        return (key in params) ? params[key] : defaultVal;
    }
}

// ---------------------------------------------------------------------------
// Handler lookup
// In Python this dynamically imports modules by dotted name.
// In D, you will typically map string names to concrete handler objects
// (e.g., via a registry that your handler modules populate at static init).
// This function keeps the same signature and logs via U.webio.
// ---------------------------------------------------------------------------

/* Placeholder handler interface — your modules should provide concrete types */
interface IHandler {
    // Return-style preserved: int nRet (0=ok, nonzero=error)
    int handleReq(/*U*/ auto ref U, string sReqType,
                  const string[string] dConf, /*fLog*/ auto fLog,
                  const FieldStorage form, string sPathInfo);
    @property string __file__();  // for logging Handler: %s
    @property string __name__();  // for exception reporting
}

// Registry map: fully qualified handler module name -> handler instance
__gshared IHandler[string] g_handlersRegistry;

/* You may call this from your handler modules to register themselves */
void registerHandler(string qualifiedName, IHandler h) {
    g_handlersRegistry[qualifiedName] = h;
}

// getHandler(U, fLog, dConf, sReqType)
IHandler getHandler(/*U*/ auto ref U, /*fLog*/ auto fLog,
                    const string[string] dConf, string sReqType)
{
    // """Return a handler module object. This doesn't just return the handler
    // function in the module because future handler interfaces may involve more
    // than one function in the API"""

    if (sReqType is null) {
        U.webio.queryError(fLog, "No handler for request type " ~ to!string(sReqType));
        return null;
    }

    if (sReqType != "HANDLE_RESOURCE") {
        fLog.write(" Request Type: " ~ sReqType);
    }

    // Take the handler from the conf, if not present, use the default
    string sModule;
    if (sReqType in dConf) {
        sModule = dConf[sReqType];
    } else if (sReqType in g_dDefHandlers) {
        sModule = g_dDefHandlers[sReqType];
    } else {
        U.webio.notFoundError(fLog, "No handler for request type " ~ sReqType);
        return null;
    }

    // D: no runtime import; resolve from registry
    if (auto ph = sModule in g_handlersRegistry) {
        auto module = *ph;
        if (sReqType != "HANDLE_RESOURCE")
            fLog.write(" Handler: " ~ module.__file__);
        return module;
    } else {
        U.webio.serverError(fLog,
            format("Error loading module %s: not registered", sModule));
        return null;
    }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
int main() {
    auto sConfPath = environment.get("DASFLEX_CONFIG");
    if (!sConfPath.length) {
        preLoadError(
            "Can not load configuration data because the DASFLEX_CONFIG environment variable is not set.\n"
            ~ "Add:\n"
            ~ " SetEnv DASFLEX_CONFIG /path/to/dasflex.conf\n"
            ~ "to your Apache configuration in the appropriate <Directory> section and restart/reload Apache.\n"
            ~ "The default location on Linux is:\n"
            ~ " /var/www/dasflex/etc/dasflex.conf\n"
            ~ "but any location readable by the web-server user account is sufficent.\n"
        );
        return 16;
    }

    StopWatch sw(AutoStart.yes);
    pout(""); // match Python stdout.buffer warm-up

    auto dConf = readConf(sConfPath);
    if (dConf is null) return 17;

    // Set the system path
    if (!setModulePath(dConf)) return 18;

    // Load the webutil module
    // In Python: mTmp = __import__('dasflex', globals(), locals(), ['webutil'], 0)
    //            U = mTmp.webutil
    // In D: you will provide an object U with fields 'webio' and 'misc' later.
    // Here we assume a function or global that yields U.
    // Replace the following line with your actual acquisition:
    auto U = dasflexGetU(); // <-- YOU WILL IMPLEMENT THIS (factory or global)

    // env path munging
    U.misc.envPathMunge("PATH",          dConf.get("BIN_PATH", ""));
    U.misc.envPathMunge("LD_LIBRARY_PATH", dConf.get("LIB_PATH", ""));

    // Logging
    typeof(U.webio.DasLogFile(null, null)) fLog; // type inference with dummy args may not work if unknown; you can replace with 'auto'
    if ("LOG_PATH" in dConf) {
        fLog = U.webio.DasLogFile(dConf["LOG_PATH"], environment.get("REMOTE_ADDR"));
        // fLog.write(format("INFO: Logging to %s", dConf["LOG_PATH"]));
    } else {
        fLog = U.webio.DasLogFile();
    }

    // for sKey in list(dConf.keys()):
    //     fLog.write("%s = %s"%(sKey, dConf[sKey]))

    foreach (sEnv; ["SCRIPT_NAME", "SERVER_NAME", "QUERY_STRING"]) {
        if (!environment.get(sEnv).length) {
            preLoadError(format("Wierd Error, %s is not set in the script environment\r\n", sEnv));
            return 21;
        }
    }

    auto form = FieldStorage();

    // Way up high, before anything Check the query parameters for obvious problems
    if (!U.misc.checkParams(fLog, form)) { // check for obvious problems,
        U.webio.queryError(
            fLog,
            "One or more of the query parameters looks like a shell injection "
            ~ "attack, data output halted."
        );
        return 13;
    }

    string sPathInfo = "";
    auto pi = environment.get("PATH_INFO");
    if (pi.length) sPathInfo = pi;

    if (sPathInfo.canFind("..")) {
        U.webio.queryError(fLog, "Bad Path");
        return 25;
    }

    // Don't log static resource requests, this just clutters up the logs
    if (!sPathInfo.startsWith("/static")) {
        fLog.write("Input");
        fLog.write(" Request URL: " ~ U.webio.getUrl());
        fLog.write(" On Host: " ~ environment.get("SERVER_NAME"));
        fLog.write(" For Program: " ~ environment.get("SCRIPT_NAME"));
        fLog.write(" For Path: " ~ sPathInfo);
        fLog.write(" Parameters: " ~ environment.get("QUERY_STRING"));

        auto ua = environment.get("HTTP_USER_AGENT");
        if (ua.length) {
            fLog.write(" User Agent: " ~ ua);
        } else {
            fLog.write(" User Agent: Unknown (HTTP_USER_AGENT not given)");
        }
    }

    // Check to see that our resource path is sent and exists, or just exit with an error
    if ("RESOURCE_PATH" !in dConf) {
        U.webio.serverError(fLog, "Set the RESOURCE_PATH keyword in " ~ sConfPath);
        return 22;
    }
    if (!isDir(dConf["RESOURCE_PATH"])) {
        U.webio.serverError(
            fLog,
            "Can't locate resources, server path " ~ dConf["RESOURCE_PATH"] ~ " doesn't exsit"
        );
        return 23;
    }

    // Handle Das2.2 style queries, except for the intro, these all have the server = keyword pattern
    auto sServer = form.getfirst("server", null);
    string sReqType = null;

    if (sServer !is null) {
        sServer = to!string(sServer).toLower();

        if (sServer == "list") {
            sReqType = "HANDLE_LIST";
        } else if (sServer == "discovery") {
            sReqType = "HANDLE_LIST";
        } else if (sServer == "dsdf") {
            // For this one just re-write as a file request
            auto sLocalId = form.getfirst("dataset", "nosuchset");
            sPathInfo = format("/source/%s/das2.d2t", to!string(sLocalId).toLower());
            sReqType = "HANDLE_RESOURCE";
        } else if (sServer == "logo") {
            sReqType = "HANDLE_LOGO";
        } else if (sServer == "id") {
            sReqType = "HANDLE_ID";
        // Note as a das2 request and send to general das3 handler
        } else if (sServer == "dataset" || sServer == "compactdataset") {
            sPathInfo = format("/source/%s/das2",
                to!string(form.getfirst("dataset", "nosuchset")).toLower());
            sReqType = "HANDLE_DATA";
        // elif sServer == 'image':
        //     sReqType = 'HANDLE_DSDF_IMAGE'
        } else if (sServer == "peers") {
            sReqType = "HANDLE_PEERS";
        } else if (sServer == "debug") {
            sReqType = "HANDLE_DEBUG";
        } else {
            U.webio.queryError(
                fLog,
                "Bad server keyword. Server must be "
                ~ "[dataset\ndsdf\nlogo\nlist\ndiscovery\nlogo\nid\npeers]\n"
            );
        }

    // If the path starts with '/hapi' send requests to subsystem handlers
    } else if (sPathInfo.startsWith("/hapi")) {
        auto sKey = "ENABLE_HAPI_SUBSYS";
        auto en = dConf.get(sKey, "").toLower();
        if (en != "true" && en != "yes" && en != "1") {
            U.webio.queryError(
                fLog,
                "Heliophysics API Subsystem not enabled, "
                ~ "contact the server administrator if this feature is needed"
            );
        } else {
            string[string] dTmp = [
                "/hapi/capabilities": "HANDLE_H_API_CAPS",
                "/hapi/catalog":     "HANDLE_H_API_CATALOG",
                "/hapi/info":        "HANDLE_H_API_INFO",
                "/hapi/data":        "HANDLE_H_API_DATA"
            ];
            foreach (k, v; dTmp) {
                if (sPathInfo.startsWith(k)) { sReqType = v; break; }
            }
            // Fall back, just send info page
            if (sReqType is null) sReqType = "HANDLE_H_API_NONE";
        }

    // Handle DasFlex path oriented queries
    } else {
        if (sPathInfo == "" || sPathInfo == "/" ) {
            sReqType = "HANDLE_NONE";
        } else if (sPathInfo == "/catalog.json" || sPathInfo == "/nodes.csv" || sPathInfo == "/root.json") {
            sReqType = "HANDLE_LIST";
        } else if (sPathInfo == "/id.txt" || sPathInfo == "/id.json") {
            sReqType = "HANDLE_ID";
        } else if (sPathInfo == "/logo.png") {
            sReqType = "HANDLE_LOGO";
        } else if (sPathInfo.startsWith("/peers.xml")) {
            sReqType = "HANDLE_PEERS";
        } else if (sPathInfo.startsWith("/debug")) {
            sReqType = "HANDLE_DEBUG";
        } else if (sPathInfo.startsWith("/static")) {
            sReqType = "HANDLE_RESOURCE";
        } else if (sPathInfo.startsWith("/verify")) {
            sReqType = "HANDLE_VERIFY";
        } else if (sPathInfo.startsWith("/source/")) {
            if (sPathInfo.endsWith("das2") || sPathInfo.endsWith("flex")) {
                sReqType = "HANDLE_DATA";
            } else if (sPathInfo.endsWith("/") || sPathInfo.endsWith("index.html")) {
                sReqType = "HANDLE_DIR";
            } else if (sPathInfo.endsWith(".html")) {
                sReqType = "HANDLE_FORM";
            } else if (sPathInfo.endsWith("vodata")) {
                sReqType = "HANDLE_VOSERVICE";
            } else {
                sReqType = "HANDLE_RESOURCE";
            }
        // elif sPathInfo.startswith('/coverage'):
        //     sReqType = 'HANDLE_COVERAGE'
        }
    }

    auto H = getHandler(U, fLog, dConf, sReqType);
    if (H is null) return 25;

    int nRet = 0;
    try {
        nRet = H.handleReq(U, sReqType, dConf, fLog, form, sPathInfo);
    } catch (Throwable t) {
        import std.array : appender;
        auto sMsg = format("\nException in handler: %s\n%s", H.__name__, t.msg);
        U.webio.serverError(fLog, sMsg);
        nRet = 26;
    }

    stdout.flush();
    if (nRet != 0) {
        fLog.write(format("\nError handling query, return value = %s", nRet));
        return nRet;
    }

    auto rDuration = sw.peek.total!"seconds";
    string sDuration;
    if (rDuration < 0.001) {
        sDuration = format("%.1f nanoseconds", rDuration * 1_000_000.0);
    } else if (rDuration < 1.0) {
        sDuration = format("%.1f milliseconds", rDuration * 1_000.0);
    } else if (rDuration < 120.0) {
        sDuration = format("%.1f seconds", rDuration);
    } else {
        sDuration = format("%.2f minutes", rDuration / 60.0);
    }

    if (!sPathInfo.startsWith("/static")) {
        fLog.write(format("\nQuery handled without error in %s.", sDuration));
    }

    return 0;
}

// ---------------------------------------------------------------------------
// Stub to obtain U (dasflex.webutil) — you will replace this.
// Keeping the function name separate avoids changing your variable names.
// ---------------------------------------------------------------------------
auto dasflexGetU() {
    // Provide U via your own module/package once available.
    // For now, this is just a placeholder so the file remains self-consistent.
    // You can change the return type to your concrete U type.
    static struct StubWebIO {
        void queryError(auto, string) {}
        void notFoundError(auto, string) {}
        void serverError(auto, string) {}
        string getUrl() { return environment.get("REQUEST_URI"); }
        auto DasLogFile(string path = null, string ip = null) { return this; }
        void write(string) {}
    }
    static struct StubMisc {
        void envPathMunge(string, string) {}
        bool checkParams(auto, FieldStorage) { return true; }
    }
    static struct UStub {
        StubWebIO webio;
        StubMisc  misc;
    }
    return UStub.init;
}
