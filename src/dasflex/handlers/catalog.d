module dasflex.handlers.catalog;

import std.stdio;
import std.file : isDir, dirEntries, SpanMode, isFile, readText;
import std.path : buildPath, baseName;
import std.string : format, endsWith, toLower;
import std.json;

import cgimain : IHandler, FieldStorage, registerHandler;
import dasflex.webutil.webio : UType, DasLog;

/// Python counterpart: handlers/catalog.py
final class CatalogHandler : IHandler {
    override int handleReq(ref UType U, string sReqType,
                           const string[string] dConf,
                           ref DasLog fLog,
                           const FieldStorage form,
                           string sPathInfo)
    {
        auto root = dConf.get("DATASRC_ROOT", "");
        // Top-level resources requested by cgimain routing
        if (sPathInfo == "/catalog.json" || sReqType == "HANDLE_LIST") {
            U.webio.writeHeaders("application/json", true);
            auto j = buildRootJSON(root);
            stdout.write(j.toString());
            return 0;
        }
        if (sPathInfo == "/nodes.csv") {
            U.webio.writeHeaders("text/csv; charset=utf-8", true);
            stdout.write(listNodesCSV(root));
            return 0;
        }
        if (sPathInfo == "/root.json") {
            U.webio.writeHeaders("application/json", true);
            auto j = buildRootJSON(root, /*minimal*/ true);
            stdout.write(j.toString());
            return 0;
        }
        // Otherwise, try path-based JSON under /source/.../*.json
        if (sPathInfo.endsWith(".json")) {
            auto rel = sPathInfo["/source/".length .. $];
            auto fs  = buildPath(root, "root", rel);
            if (!isFile(fs)) { U.webio.notFoundError(fLog, format("Catalog node not found: %s", rel)); return 1; }
            U.webio.writeHeaders("application/json", true);
            stdout.write(readText(fs));
            return 0;
        }
        U.webio.notFoundError(fLog, "Unknown catalog request");
        return 1;
    }

    JSONValue buildRootJSON(string root, bool minimal = false) {
        JSONValue j;
        j["type"] = "Root";
        JSONValue cats;
        foreach (de; dirEntries(buildPath(root, "root"), SpanMode.depth)) {
            if (!de.isDir) continue;
            auto name = baseName(de.name);
            if (name.length && name[0]=='.') continue;
            JSONValue node;
            node["type"] = "Catalog";
            node["label"] = name;
            JSONValue urls;
            urls.array ~= JSONValue("/source/" ~ name ~ "/index.html");
            urls.array ~= JSONValue("/source/" ~ name ~ "/catalog.json");
            node["urls"] = urls;
            cats.array ~= node;
        }
        j["catalog"] = cats;
        return j;
    }

    string listNodesCSV(string root) {
        string out = "label,type,url\n";
        foreach (de; dirEntries(buildPath(root, "root"), SpanMode.depth)) {
            if (de.isDir) {
                auto name = baseName(de.name);
                out ~= format("%s,Catalog,/source/%s/index.html\n", name, name);
            }
        }
        return out;
    }

    override @property string __file__() { return __FILE__; }
    override @property string __name__() { return "dasflex.handlers.catalog"; }
}

static this() { registerHandler("dasflex.handlers.catalog", new CatalogHandler()); }
