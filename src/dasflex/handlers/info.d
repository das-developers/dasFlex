module dasflex.handlers.info;

import std.stdio;
import std.file : isFile, readText;
import std.string : format, endsWith;
import std.path : buildPath;

import cgimain : IHandler, FieldStorage, registerHandler;
import dasflex.webutil.webio : UType, DasLog;

/// Python counterpart: handlers/info.py
final class InfoHandler : IHandler {
    override int handleReq(ref UType U, string sReqType,
                           const string[string] dConf,
                           ref DasLog fLog,
                           const FieldStorage form,
                           string sPathInfo)
    {
        // Show basic info for a source node (html)
        U.webio.writeHeaders("text/html; charset=utf-8", true);
        stdout.write("<html><body>\n<h2>Source Info</h2>\n");
        stdout.write(format("<p>PATH_INFO: %s</p>\n", sPathInfo));
        // If there is a matching json file, display its contents link
        if (sPathInfo.endsWith(".html")) {
            auto jsonRel = sPathInfo["/source/".length .. $].replace(".html", ".json");
            auto fs = buildPath(dConf.get("DATASRC_ROOT", ""), "root", jsonRel);
            if (isFile(fs)) {
                stdout.write(format("<p>Catalog: <a href=\"%s\">%s</a></p>\n", sPathInfo.replace(".html", ".json"), jsonRel));
            }
        }
        stdout.write("</body></html>\n");
        fLog.write("Info page served");
        return 0;
    }
    override @property string __file__() { return __FILE__; }
    override @property string __name__() { return "dasflex.handlers.info"; }
}
static this() { registerHandler("dasflex.handlers.info", new InfoHandler()); }
