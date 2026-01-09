module dasflex.handlers.directory;

import std.stdio;
import std.file : dirEntries, SpanMode, isDir;
import std.path : buildPath, baseName;
import std.string : format, toLower;

import cgimain : IHandler, FieldStorage, registerHandler;
import dasflex.webutil.webio : UType, DasLog;

/// Python counterpart: handlers/directory.py
final class DirectoryHandler : IHandler {
    override int handleReq(ref UType U, string sReqType,
                           const string[string] dConf,
                           ref DasLog fLog,
                           const FieldStorage form,
                           string sPathInfo)
    {
        // Expect PATH_INFO like /source/<collection>/
        auto root = dConf.get("DATASRC_ROOT", "");
        auto rel  = sPathInfo.length ? sPathInfo[1 .. $] : ""; // strip leading '/'
        auto fs   = buildPath(root, rel.replace("/source/", "root/"));
        if (!isDir(fs)) { U.webio.notFoundError(fLog, "Directory not found"); return 1; }
        U.webio.writeHeaders("text/html; charset=utf-8");
        stdout.write("<html><body>\n");
        stdout.write(format("<h2>Index of %s</h2>\n<ul>\n", sPathInfo));
        foreach (de; dirEntries(fs, SpanMode.shallow)) {
            auto name = baseName(de.name);
            // Simple filter: hide dotfiles
            if (name.length && name[0]=='.') continue;
            auto link = U.webio.getUrl().split('?')[0];
            // ensure trailing slash on dirs
            auto suffix = de.isDir ? (name ~ "/") : name;
            stdout.write(format("<li><a href=\"%s\">%s</a></li>\n", link ~ suffix, name));
        }
        stdout.write("</ul></body></html>\n");
        fLog.write("Served directory listing");
        return 0;
    }
    override @property string __file__() { return __FILE__; }
    override @property string __name__() { return "dasflex.handlers.directory"; }
}
static this() { registerHandler("dasflex.handlers.directory", new DirectoryHandler()); }
