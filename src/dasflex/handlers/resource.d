
module dasflex.handlers.resource;

import std.stdio;
import std.file : isFile, read;
import std.path : baseName, buildPath;
import std.string : replace, startsWith, toLower;
import std.conv : to;

import cgimain : IHandler, FieldStorage, registerHandler; // IHandler registry from cgimain.d

// --- Small helper: guess basic mime by extension when U.mime is absent ---
private string guessMimeByExt(string sFile) {
    auto extPos = sFile.lastIndexOf('.');
    if (extPos < 0) return "application/octet-stream";
    auto ext = sFile[extPos+1 .. $].toLower();
    // Minimal set; extend as needed
    final switch (ext) {
        case "html": return "text/html; charset=utf-8";
        case "htm":  return "text/html; charset=utf-8";
        case "css":  return "text/css; charset=utf-8";
        case "js":   return "application/javascript";
        case "json": return "application/json; charset=utf-8";
        case "png":  return "image/png";
        case "jpg":
        case "jpeg": return "image/jpeg";
        case "svg":  return "image/svg+xml";
        case "txt":  return "text/plain; charset=utf-8";
        case "d2t":  return "text/vnd.das2.das2stream; charset=utf-8";
        case "d2s":  return "application/vnd.das2.das2stream";
        default:     return "application/octet-stream";
    }
}

final class ResourceHandler : IHandler {
    override int handleReq(U, string sReqType,
                           const string[string] dConf,
                           auto fLog,
                           const FieldStorage form,
                           string sPathInfo)
    {
        // """See dasflex.handlers.intro.py for a decription of this function interface"""
        // Get files from either the static or catalog areas
        string sResource;
        string sFile;

        if (sPathInfo.startsWith("/static/")) {
            sResource = sPathInfo.replace("/static/", "");
            sFile = buildPath(dConf["RESOURCE_PATH"], sResource);
            U.webio.pout("Expires: " ~ U.webio.httpNextYear() ~ "\r\n"); // long time-out for static
        } else if (sPathInfo.startsWith("/source/")) {
            sResource = sPathInfo.replace("/source/", "root/");
            sFile = buildPath(dConf["DATASRC_ROOT"], sResource);
        } else {
            U.webio.serverError(fLog, "Resource path must start with /static/ or /source/");
            return 17;
        }

        if (!isFile(sFile)) {
            U.webio.serverError(fLog, "Resource '" ~ sResource ~ "' doesn't exist");
            return 17;
        }

        // Handle our own mime types...
        // Prefer site’s mime table via U.mime.getMimeByExt, else fall back to local guess.
        string sType;
        string sContentDis = "inline";
        // Compile-time check in case U.mime is not present yet.
        static if (__traits(compiles, U.mime.getMimeByExt(sFile))) {
            auto tRet = U.mime.getMimeByExt(sFile); // Expecting (type, contentDisposition, ext)
            // If your U.mime returns Tuple!(string,string,string), index by [0],[1],[2];
            // otherwise adjust this block accordingly.
            sType = tRet[0];
            sContentDis = tRet[1];
            auto sOutFile = baseName(sFile);
            U.webio.pout(format("Content-Disposition: %s; filename=\"%s\"\r\n", sContentDis, sOutFile));
        } else {
            sType = guessMimeByExt(sFile);
            if (sType.length == 0) {
                U.webio.serverError(fLog, "Unrecognized mime type for " ~ sFile);
                return 17;
            }
        }

        U.webio.pout("Access-Control-Allow-Origin: *\r\n");
        U.webio.pout("Access-Control-Allow-Methods: GET\r\n");
        U.webio.pout("Access-Control-Allow-Headers: Content-Type\r\n");
        U.webio.pout("Content-Type: " ~ sType ~ "\r\n");
        U.webio.pout("\r\n");

        // Stream file bytes
        auto data = read(sFile);
        stdout.rawWrite(data);

        return 0;
    }

    override @property string __file__() { return __FILE__; }
    override @property string __name__() { return "dasflex.handlers.resource"; }
}

// Register this handler at program load time
static this() {
    registerHandler("dasflex.handlers.resource", new ResourceHandler());
}
``
