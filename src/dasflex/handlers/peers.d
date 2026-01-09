module dasflex.handlers.peers;

import std.stdio;
import std.file : isFile, read;
import std.path : buildPath;

import cgimain : IHandler, FieldStorage, registerHandler;
import dasflex.webutil.webio : UType, DasLog;

/// Python counterpart: handlers/peers.py
final class PeersHandler : IHandler {
    override int handleReq(ref UType U, string sReqType,
                           const string[string] dConf,
                           ref DasLog fLog,
                           const FieldStorage form,
                           string sPathInfo)
    {
        auto root = dConf.get("RESOURCE_PATH", "");
        auto peers = buildPath(root, "peers.xml");
        if (!isFile(peers)) { U.webio.notFoundError(fLog, "peers.xml not found"); return 1; }
        U.webio.writeHeaders("application/xml", true);
        auto data = read(peers);
        stdout.rawWrite(data);
        fLog.write("Peers XML served");
        return 0;
    }
    override @property string __file__() { return __FILE__; }
    override @property string __name__() { return "dasflex.handlers.peers"; }
}
static this() { registerHandler("dasflex.handlers.peers", new PeersHandler()); }
