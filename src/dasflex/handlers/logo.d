module dasflex.handlers.logo;

import std.stdio;
import std.file   : read, isFile;
import std.path   : buildPath;

import cgimain : IHandler, FieldStorage, registerHandler;
import dasflex.webutil.webio : UType, DasLog;

final class LogoHandler : IHandler {
    override int handleReq(ref UType U, string sReqType,
                           const string[string] dConf,
                           ref DasLog fLog,
                           const FieldStorage form,
                           string sPathInfo)
    {
        auto root = dConf.get("RESOURCE_PATH", "");
        auto logo = buildPath(root, "logo.png");
        if (!isFile(logo)) { U.webio.notFoundError(fLog, "logo.png not found in RESOURCE_PATH"); return 1; }
        U.webio.writeHeaders("image/png");
        auto data = read(logo);
        stdout.rawWrite(data);
        fLog.write("Served logo.png");
        return 0;
    }
    override @property string __file__() { return __FILE__; }
    override @property string __name__() { return "dasflex.handlers.logo"; }
}
static this() { registerHandler("dasflex.handlers.logo", new LogoHandler()); }
