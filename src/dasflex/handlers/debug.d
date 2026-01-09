module dasflex.handlers.debug;

import std.stdio;
import std.string : format;
import std.process : environment;

import cgimain : IHandler, FieldStorage, registerHandler;
import dasflex.webutil.webio : UType, DasLog;

/// Python counterpart: handlers/debug.py
final class DebugHandler : IHandler {
    override int handleReq(ref UType U, string sReqType,
                           const string[string] dConf,
                           ref DasLog fLog,
                           const FieldStorage form,
                           string sPathInfo)
    {
        U.webio.writeHeaders("text/plain; charset=utf-8", true);
        stdout.write("# Debug Environment\n\n");
        foreach (k, v; environment.toAA) {
            stdout.write(format("%s=%s\n", k, v));
        }
        stdout.write("\n# Query Params\n");
        foreach (k, v; form.params) {
            stdout.write(format("%s=%s\n", k, v));
        }
        fLog.write("Debug page served");
        return 0;
    }
    override @property string __file__() { return __FILE__; }
    override @property string __name__() { return "dasflex.handlers.debug"; }
}
static this() { registerHandler("dasflex.handlers.debug", new DebugHandler()); }
