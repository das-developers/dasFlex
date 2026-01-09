module dasflex.handlers.id;

import std.stdio;
import std.string : format, toLower, replace;
import std.json;

import cgimain : IHandler, FieldStorage, registerHandler;
import dasflex.webutil.webio : UType, DasLog;

/// Python counterpart: handlers/id.py
final class IdHandler : IHandler {
    override int handleReq(ref UType U, string sReqType,
                           const string[string] dConf,
                           ref DasLog fLog,
                           const FieldStorage form,
                           string sPathInfo)
    {
        auto accept = form.getfirst("accept", "text").toLower();
        if (sPathInfo == "/id.json" || accept == "json") {
            U.webio.writeHeaders("application/json", true);
            JSONValue j;
            j["server_id"]   = dConf.get("SERVER_ID", "unknown");
            j["server_name"] = dConf.get("SERVER_NAME", "Unknown");
            j["site_tag"]    = dConf.get("SITE_CATALOG_TAG", "tag:unknown.site.org,2021");
            j["script"]      = U.webio.getUrl();
            auto s = j.toString();
            stdout.write(s);
        } else {
            U.webio.writeHeaders("text/plain; charset=utf-8", true);
            stdout.write(format("server_id:   %s\n", dConf.get("SERVER_ID", "unknown")));
            stdout.write(format("server_name: %s\n", dConf.get("SERVER_NAME", "Unknown")));
            stdout.write(format("site_tag:    %s\n", dConf.get("SITE_CATALOG_TAG", "tag:unknown.site.org,2021")));
        }
        fLog.write("Served id info");
        return 0;
    }
    override @property string __file__() { return __FILE__; }
    override @property string __name__() { return "dasflex.handlers.id"; }
}
static this() { registerHandler("dasflex.handlers.id", new IdHandler()); }
