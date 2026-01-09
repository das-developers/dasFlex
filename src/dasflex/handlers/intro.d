module dasflex.handlers.intro;

import std.stdio;
import std.string : format;
import std.process : environment;

import cgimain : IHandler, FieldStorage, registerHandler;
import dasflex.webutil.webio : UType, DasLog;

final class IntroHandler : IHandler {
    override int handleReq(ref UType U, string sReqType,
                           const string[string] dConf,
                           ref DasLog fLog,
                           const FieldStorage form,
                           string sPathInfo)
    {
        auto site = dConf.get("SERVER_NAME", "DASFlex Server");
        auto id   = dConf.get("SERVER_ID",   "unknown");
        U.webio.writeHeaders("text/plain; charset=utf-8", true);
        stdout.write(format(
            "Welcome to %s (%s)\n\nVisit /source/, /catalog.json, /id.txt, or try ?server=list\n",
            site, id));
        fLog.write("Intro page served");
        return 0;
    }
    override @property string __file__() { return __FILE__; }
    override @property string __name__() { return "dasflex.handlers.intro"; }
}
static this() { registerHandler("dasflex.handlers.intro", new IntroHandler()); }
