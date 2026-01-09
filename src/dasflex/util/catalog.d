module dasflex.util.catalog;

import std.file : dirEntries, SpanMode, isDir, isFile, readText;
import std.path : buildPath, baseName;
import std.string : format;
import std.json;

/// Python counterpart: util/catalog.py
namespace CatalogUtil {
    JSONValue buildRoot(string root) {
        JSONValue j; j["type"] = "Root"; JSONValue cats;
        foreach (de; dirEntries(buildPath(root, "root"), SpanMode.depth)) {
            if (!de.isDir) continue; auto name = baseName(de.name);
            JSONValue node; node["type"] = "Catalog"; node["label"] = name;
            JSONValue urls; urls.array ~= JSONValue("/source/" ~ name ~ "/index.html");
            urls.array ~= JSONValue("/source/" ~ name ~ "/catalog.json"); node["urls"] = urls;
            cats.array ~= node;
        }
        j["catalog"] = cats; return j;
    }

    string listNodesCSV(string root) {
        string out = "label,type,url\n";
        foreach (de; dirEntries(buildPath(root, "root"), SpanMode.depth)) {
            if (de.isDir) { auto name = baseName(de.name);
                out ~= format("%s,Catalog,/source/%s/index.html\n", name, name);
            }
        }
        return out;
    }
}
